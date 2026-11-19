import { ActionIcon, Avatar, Box, Button, CopyButton, Group, Menu, Paper, ScrollArea, Stack, Table, Text, Textarea, ThemeIcon, Tooltip, UnstyledButton } from "@mantine/core";
import { BarChart, DonutChart, LineChart } from "@mantine/charts";
import { notifications } from "@mantine/notifications";
import { IconArrowUp, IconCheck, IconCopy, IconHistory, IconMessagePlus, IconSparkles } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { errorMessage } from "../../api/client";
import { createChatSession, postChatMessage, useChatSession, useChatSessions, useChatSuggestions } from "../../api/hooks";
import { useJobEvents } from "../../api/sse";
import type { ChatMessage } from "../../api/types";
import { CATEGORY_COLORS } from "../../lib/constants";
import { formatINR, formatNumber, formatRelative } from "../../lib/format";
import { useAuth } from "../../stores";

function Pill({ children, onClick }: { children: string; onClick: () => void }) {
  return (
    <UnstyledButton
      onClick={onClick}
      className="lift"
      px={12}
      py={6}
      style={{ border: "1px solid var(--mantine-color-gold-4)", borderRadius: 16, fontSize: 13, lineHeight: 1.35, textAlign: "left", background: "var(--jaa-surface)" }}
    >
      {children}
    </UnstyledButton>
  );
}

function modelLabel(m?: string) {
  if (!m) return "";
  if (m === "rule-based") return "Automatic";
  if (m === "instant") return "⚡ Instant · from your data";
  return m.replace("gemini/", "").replace(/-/g, " ").replace("gemini", "Gemini");
}

function AnswerChart({ chart }: { chart: NonNullable<ChatMessage["payload"]["chart"]> }) {
  const fmt = (v: number) => (chart.value_format === "inr" ? formatINR(v, { compact: true }) : formatNumber(v));
  const data = chart.data.map((d) => ({ label: d.label, value: d.value }));
  return (
    <Box mt="xs">
      {chart.title && <Text size="xs" fw={600} mb={4}>{chart.title}</Text>}
      {chart.type === "pie" ? (
        <DonutChart h={180} size={150} thickness={22} withTooltip valueFormatter={fmt}
          data={data.map((d, i) => ({ name: d.label, value: d.value, color: `${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}.6` }))} />
      ) : chart.type === "line" ? (
        <LineChart h={180} data={data} dataKey="label" series={[{ name: "value", color: "gold.6", label: chart.title || "Value" }]} valueFormatter={fmt} curveType="natural" yAxisProps={{ width: 60 }} />
      ) : (
        <BarChart h={180} data={data} dataKey="label" series={[{ name: "value", color: "gold.6", label: chart.title || "Value" }]} valueFormatter={fmt} yAxisProps={{ width: 60 }} barProps={{ radius: 4 }} />
      )}
    </Box>
  );
}

function AnswerTable({ table }: { table: NonNullable<ChatMessage["payload"]["table"]> }) {
  const money = (col: string) => /₹|value|cost|amount|price|budget|total/i.test(col);
  return (
    <ScrollArea mt="xs" type="auto">
      <Table fz="xs" striped withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>{table.columns.map((c) => <Table.Th key={c}>{c}</Table.Th>)}</Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {table.rows.slice(0, 30).map((r, i) => (
            <Table.Tr key={i}>
              {r.map((cell, j) => (
                <Table.Td key={j} className="num">
                  {typeof cell === "number" && money(table.columns[j] ?? "") ? formatINR(cell) : typeof cell === "number" ? formatNumber(cell) : cell}
                </Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}

function PendingBubble({ jobId }: { jobId: string }) {
  const qc = useQueryClient();
  // the moment the answer is ready, reload the conversation (no waiting for polling)
  const p = useJobEvents(jobId, () => qc.invalidateQueries({ queryKey: ["chatSession"] }));
  const waiting = p.steps.find((s) => s.key === "think")?.note;
  return (
    <Group gap="sm" align="flex-start" wrap="nowrap">
      <Avatar radius="xl" size="sm" variant="gradient" gradient={{ from: "gold.3", to: "gold.7" }}>
        <IconSparkles size={14} />
      </Avatar>
      <Paper p="sm" radius="lg" withBorder style={{ borderTopLeftRadius: 4 }}>
        <Group gap={4} h={14}>
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </Group>
        <Text size="xs" c="dimmed" mt={6}>
          {p.currentTool ?? waiting ?? "Thinking…"}
        </Text>
      </Paper>
    </Group>
  );
}

function Bubble({ m, onAsk }: { m: ChatMessage; onAsk: (q: string) => void }) {
  if (m.role === "USER") {
    return (
      <Group justify="flex-end">
        <Paper p="sm" radius="lg" maw="85%" style={{ background: "var(--mantine-color-gold-light)", borderBottomRightRadius: 4 }}>
          <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{m.content}</Text>
        </Paper>
      </Group>
    );
  }
  if (m.status === "PENDING" && m.job_id) return <PendingBubble jobId={m.job_id} />;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <Avatar radius="xl" size="sm" variant="gradient" gradient={{ from: "gold.3", to: "gold.7" }}>
          <IconSparkles size={14} />
        </Avatar>
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Paper p="sm" radius="lg" withBorder style={{ borderTopLeftRadius: 4 }} bg={m.status === "FAILED" ? "var(--mantine-color-red-light)" : undefined}>
            <Box className="chat-md" fz="sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || "…"}</ReactMarkdown>
            </Box>
            {m.payload.table && <AnswerTable table={m.payload.table} />}
            {m.payload.chart && m.payload.chart.data?.length > 0 && <AnswerChart chart={m.payload.chart} />}
          </Paper>
          <Group gap={6} mt={4}>
            <Text size="10px" c="dimmed">
              {formatRelative(m.created_at)}
              {m.payload.model_used ? ` · ${modelLabel(m.payload.model_used)}` : ""}
              {m.payload.seconds !== undefined ? ` · ${m.payload.seconds}s` : ""}
            </Text>
            <CopyButton value={m.content}>
              {({ copied, copy }) => (
                <Tooltip label={copied ? "Copied" : "Copy answer"}>
                  <ActionIcon size="xs" variant="subtle" color="gray" onClick={copy} aria-label="Copy answer">
                    {copied ? <IconCheck size={12} /> : <IconCopy size={12} />}
                  </ActionIcon>
                </Tooltip>
              )}
            </CopyButton>
          </Group>
          {!!m.payload.follow_up_questions?.length && (
            <Stack gap={6} mt={6} align="flex-start">
              {m.payload.follow_up_questions.map((q) => (
                <Pill key={q} onClick={() => onAsk(q)}>{q}</Pill>
              ))}
            </Stack>
          )}
        </Box>
      </Group>
    </motion.div>
  );
}

export function ChatPanel({ height = "100%" }: { height?: string | number }) {
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const [sessionId, setSessionId] = useState<number | null>(() => {
    try {
      const v = sessionStorage.getItem("jaa.chatSession");
      return v ? Number(v) : null;
    } catch {
      return null;
    }
  });
  const { data: session } = useChatSession(sessionId);
  const { data: sessions } = useChatSessions();
  const { data: sugg } = useChatSuggestions();
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const viewport = useRef<HTMLDivElement>(null);

  const messages = session?.messages ?? [];
  const pending = messages.some((m) => m.status === "PENDING");

  useEffect(() => {
    try {
      if (sessionId) sessionStorage.setItem("jaa.chatSession", String(sessionId));
      else sessionStorage.removeItem("jaa.chatSession");
    } catch {
      /* ignore */
    }
  }, [sessionId]);

  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.status]);

  // when a pending answer finishes, the global SSE invalidates chatSession; also poll lightly as a fallback
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => qc.invalidateQueries({ queryKey: ["chatSession", sessionId] }), 4000);
    return () => clearInterval(t);
  }, [pending, sessionId, qc]);

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || sending || pending) return;
    setSending(true);
    try {
      let sid = sessionId;
      if (!sid) {
        const s = await createChatSession();
        sid = s.id;
        setSessionId(sid);
      }
      const res = await postChatMessage(sid, question);
      qc.setQueryData(["chatSession", sid], (old: { session: unknown; messages: ChatMessage[] } | undefined) => ({
        session: old?.session ?? { id: sid, title: question, updated_at: "", message_count: 0 },
        messages: [...(old?.messages ?? []), res.user_message, res.assistant_message],
      }));
      qc.invalidateQueries({ queryKey: ["chatSessions"] });
      setText("");
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    } finally {
      setSending(false);
    }
  };

  return (
    <Paper className="soft-card" radius="lg" h={height} style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Group justify="space-between" p="md" style={{ borderBottom: "1px solid var(--jaa-border)" }} wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <ThemeIcon radius="xl" size={36} variant="gradient" gradient={{ from: "gold.3", to: "gold.7", deg: 135 }}>
            <IconSparkles size={18} />
          </ThemeIcon>
          <Box>
            <Text fw={700} lh={1.2}>Ask your AI Accountant</Text>
            <Text size="xs" c="dimmed">Answers from your real shop data</Text>
          </Box>
        </Group>
        <Group gap={4}>
          <Menu position="bottom-end" width={260} withinPortal>
            <Menu.Target>
              <ActionIcon variant="subtle" aria-label="Chat history"><IconHistory size={18} /></ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>Recent chats</Menu.Label>
              {(sessions ?? []).slice(0, 10).map((s) => (
                <Menu.Item key={s.id} onClick={() => setSessionId(s.id)}>
                  <Text size="sm" truncate>{s.title}</Text>
                </Menu.Item>
              ))}
              {!sessions?.length && <Menu.Item disabled>No chats yet</Menu.Item>}
            </Menu.Dropdown>
          </Menu>
          <Tooltip label="New chat">
            <ActionIcon variant="subtle" aria-label="New chat" onClick={() => setSessionId(null)}>
              <IconMessagePlus size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <ScrollArea viewportRef={viewport} style={{ flex: 1 }} p="md" type="auto" scrollbars="y">
        <Stack gap="md" pb="sm">
          <Group gap="sm" align="flex-start" wrap="nowrap">
            <Avatar radius="xl" size="sm" variant="gradient" gradient={{ from: "gold.3", to: "gold.7" }}>
              <IconSparkles size={14} />
            </Avatar>
            <Paper p="sm" radius="lg" withBorder style={{ borderTopLeftRadius: 4 }}>
              <Text size="sm">
                Hi {user?.display_name}! Ask me anything about your stock, sales or purchases. I'll look up the exact numbers.
              </Text>
            </Paper>
          </Group>
          {messages.length === 0 && (
            <Stack gap={6} align="flex-start">
              <Text size="xs" c="dimmed" fw={600}>Try asking:</Text>
              {(sugg?.questions ?? []).map((q) => (
                <Pill key={q} onClick={() => ask(q)}>{q}</Pill>
              ))}
            </Stack>
          )}
          {messages.map((m) => <Bubble key={m.id} m={m} onAsk={ask} />)}
        </Stack>
      </ScrollArea>

      <Box p="sm" style={{ borderTop: "1px solid var(--jaa-border)" }}>
        <Group gap="xs" align="flex-end" wrap="nowrap">
          <Textarea
            style={{ flex: 1 }}
            autosize
            minRows={1}
            maxRows={5}
            maxLength={1000}
            placeholder="Ask about sales, stock, reorders… (English or Hindi)"
            value={text}
            onChange={(e) => setText(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(text);
              }
            }}
            disabled={pending}
            aria-label="Your question"
          />
          <ActionIcon size={38} radius="xl" variant="gradient" gradient={{ from: "gold.4", to: "gold.8" }} onClick={() => ask(text)} loading={sending} disabled={!text.trim() || pending} aria-label="Send">
            <IconArrowUp size={20} />
          </ActionIcon>
        </Group>
        {pending && <Button variant="subtle" size="compact-xs" mt={4} disabled>Waiting for the answer…</Button>}
      </Box>
    </Paper>
  );
}
