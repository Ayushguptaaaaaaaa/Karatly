import {
  ActionIcon,
  Affix,
  Alert,
  Badge,
  Box,
  Button,
  Collapse,
  Drawer,
  Grid,
  Group,
  List,
  Menu,
  Paper,
  Progress,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Tabs,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { AreaChart, DonutChart } from "@mantine/charts";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconAlertTriangle,
  IconBulb,
  IconCheck,
  IconChevronDown,
  IconChevronUp,
  IconClock,
  IconFlame,
  IconInfoCircle,
  IconLoader2,
  IconMessageChatbot,
  IconPrinter,
  IconShoppingCart,
  IconSparkles,
  IconTrendingUp,
  IconUsers,
  IconZzz,
} from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { errorMessage } from "../../api/client";
import { useDashboard, useInsightRun, useInsightRuns, useInsightsLatest, usePeriodParams, useRunningInsights, useStartInsights } from "../../api/hooks";
import { useJobEvents } from "../../api/sse";
import type { InsightRun, JobStep, WhoRow, WhoSummary } from "../../api/types";
import { PeriodPicker } from "../../components/PeriodPicker";
import { EmptyBox, ErrorState, LabelCode, PageHeader, SectionCard } from "../../components/ui";
import { CATEGORY_COLORS, METAL_LABEL } from "../../lib/constants";
import { celebrate } from "../../lib/confetti";
import { formatINR, formatRelative } from "../../lib/format";
import { useUi } from "../../stores";
import { ChatPanel } from "./ChatPanel";

const PRIO_COLOR: Record<string, string> = { HIGH: "red", MEDIUM: "orange", LOW: "gray" };
const TIPS = [
  "Dead stock is money sitting in your showcase. Spotting it early frees cash.",
  "Sold-out best sellers cost sales every day they stay at zero.",
  "Every number in the report comes from your records. The AI only explains them.",
  "Wedding season (Nov–Feb) usually lifts necklaces, bangles and sets.",
  "You can keep working. We'll let you know when the report is ready.",
];

function modelBadge(models: string[]) {
  const m = models.find((x) => x !== "rule-based") ?? models[0];
  if (!m || m === "rule-based") return <Badge color="gray" variant="light">Automatic (AI unavailable)</Badge>;
  const lite = m.includes("lite");
  return <Badge color={lite ? "blue" : "gold"} variant="light">{m.replace("gemini/", "").replace("gemini", "Gemini")}</Badge>;
}

function WhyCollapse({ children }: { children: ReactNode }) {
  const [open, { toggle }] = useDisclosure(false);
  return (
    <Box mt="sm">
      <UnstyledButton onClick={toggle} aria-expanded={open}>
        <Group gap={4}>
          <IconInfoCircle size={14} color="var(--mantine-color-gold-8)" />
          <Text size="xs" c="gold.8" fw={600}>Why?</Text>
          {open ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
        </Group>
      </UnstyledButton>
      <Collapse expanded={open}>
        <Paper p="sm" mt="xs" radius="md" withBorder>
          {children}
          <Text size="10px" c="dimmed" mt="xs">Numbers calculated by the system; the AI explains them.</Text>
        </Paper>
      </Collapse>
    </Box>
  );
}

function EvidenceTable({ rows, cols }: { rows: Record<string, unknown>[]; cols: [string, string][] }) {
  if (!rows.length) return <Text size="xs" c="dimmed">No data.</Text>;
  return (
    <Box style={{ overflowX: "auto" }}>
      <Table fz="xs" striped>
        <Table.Thead>
          <Table.Tr>{cols.map(([, l]) => <Table.Th key={l}>{l}</Table.Th>)}</Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.slice(0, 12).map((r, i) => (
            <Table.Tr key={i}>
              {cols.map(([k]) => {
                const v = r[k];
                return <Table.Td key={k} className="num">{typeof v === "number" && /value|cost|total|price/.test(k) ? formatINR(v) : String(v ?? "—")}</Table.Td>;
              })}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Box>
  );
}

// ---- generation progress ---------------------------------------------------------------------
function GenerationProgress({ jobId, onDone }: { jobId: string; onDone: (runId: number | null, ok: boolean) => void }) {
  const p = useJobEvents(jobId, (res) => onDone(res.resultId, res.status === "SUCCEEDED"));
  const [tip, setTip] = useState(0);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const a = setInterval(() => setTip((t) => (t + 1) % TIPS.length), 6000);
    const b = setInterval(() => setTick((t) => t + 1), 1000);
    return () => { clearInterval(a); clearInterval(b); };
  }, []);
  const steps: JobStep[] = p.steps.length ? p.steps : [];
  const done = steps.filter((s) => s.status === "DONE").length;
  const elapsed = (s: JobStep) => (s.started_at ? Math.max(0, Math.round((Date.now() - new Date(s.started_at).getTime()) / 1000)) : 0);
  void tick;
  return (
    <Paper className="gold-border" p={{ base: "lg", sm: "xl" }} radius="lg">
      <Group gap="md" mb="lg">
        <ThemeIcon size={48} radius="xl" variant="gradient" gradient={{ from: "gold.3", to: "gold.7" }}>
          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 3, ease: "linear" }} style={{ display: "flex" }}>
            <IconSparkles size={24} />
          </motion.div>
        </ThemeIcon>
        <Box style={{ flex: 1 }}>
          <Title order={3}>Your AI accountant is analysing the shop…</Title>
          <Text size="sm" c="dimmed">This usually takes 1–3 minutes on the free AI tier.</Text>
        </Box>
      </Group>
      <Progress value={steps.length ? (done / steps.length) * 100 : 5} color="gold" animated striped mb="lg" />
      <Stack gap="sm">
        {steps.map((s, i) => (
          <motion.div key={s.key} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
            <Group gap="md" wrap="nowrap">
              <ThemeIcon radius="xl" size={30} color={s.status === "DONE" ? "teal" : s.status === "RUNNING" ? "gold" : "gray"} variant={s.status === "PENDING" ? "light" : "filled"}>
                {s.status === "DONE" ? (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}><IconCheck size={16} /></motion.div>
                ) : s.status === "RUNNING" ? (
                  <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} style={{ display: "flex" }}><IconLoader2 size={16} /></motion.div>
                ) : (
                  <Text size="xs" fw={700}>{i + 1}</Text>
                )}
              </ThemeIcon>
              <Box style={{ flex: 1 }}>
                <Text size="sm" fw={s.status === "RUNNING" ? 700 : 500} c={s.status === "PENDING" ? "dimmed" : undefined}>{s.label}</Text>
                {s.status === "RUNNING" && (
                  <Text size="xs" c="dimmed">{p.currentTool ?? s.note ?? "Working…"} · {elapsed(s)}s</Text>
                )}
                {s.status === "DONE" && s.note && <Text size="xs" c="dimmed">{s.note}</Text>}
              </Box>
              {s.status === "DONE" && s.model_used && s.model_used !== "system" && (
                <Badge size="xs" variant="light" color={s.model_used === "rule-based" ? "gray" : "gold"}>
                  {s.model_used === "rule-based" ? "automatic" : s.model_used.replace("gemini/", "")}
                </Badge>
              )}
            </Group>
          </motion.div>
        ))}
        {!steps.length && <Skeleton h={160} />}
      </Stack>
      <AnimatePresence mode="wait">
        <motion.div key={tip} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <Group gap="xs" mt="lg">
            <IconBulb size={16} color="var(--mantine-color-gold-7)" />
            <Text size="sm" c="dimmed">{TIPS[tip]}</Text>
          </Group>
        </motion.div>
      </AnimatePresence>
    </Paper>
  );
}

// ---- report ------------------------------------------------------------------------------------
const MATERIAL_COLOR: Record<string, string> = { GOLD: "yellow.6", SILVER: "gray.5", PLATINUM: "blue.4", IMITATION: "pink.5", OTHER: "teal.5" };

function BarList({ rows, color = "gold" }: { rows: WhoRow[]; color?: string }) {
  if (!rows.length) return <Text size="sm" c="dimmed">No data yet</Text>;
  const max = Math.max(...rows.map((r) => r.revenue), 1);
  return (
    <Stack gap={8}>
      {rows.map((r) => (
        <Box key={r.name}>
          <Group justify="space-between" wrap="nowrap" gap="xs">
            <Text size="sm" fw={500} truncate>{r.name}</Text>
            <Text size="sm" fw={700} className="num">{formatINR(r.revenue, { compact: true })}</Text>
          </Group>
          <Progress value={(r.revenue / max) * 100} size="sm" color={color} mt={3} />
        </Box>
      ))}
    </Stack>
  );
}

function WhoSection({ who, note }: { who: WhoSummary; note?: string }) {
  const navigate = useNavigate();
  const [place, setPlace] = useState<"top_cities" | "top_states" | "top_countries">("top_cities");
  const mix = who.material_mix.filter((m) => m.revenue > 0);
  return (
    <SectionCard
      title="Who buys, from where"
      icon={<IconUsers size={18} />}
      actions={<Button size="xs" variant="light" onClick={() => navigate("/app/sales?tab=explore")}>Explore sales →</Button>}
    >
      {note && <Text size="sm" mb="md">{note}</Text>}
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl" verticalSpacing="lg">
        <Box>
          <Text size="xs" fw={700} tt="uppercase" c="dimmed" mb="xs">Top customers</Text>
          <BarList rows={who.top_customers} />
          <Text size="xs" c="dimmed" mt="xs">Walk-in: {who.customers.walk_in_share_pct}% of sales</Text>
        </Box>
        <Box>
          <SegmentedControl size="xs" mb="xs" value={place} onChange={(v) => setPlace(v as typeof place)}
            data={[{ value: "top_cities", label: "City" }, { value: "top_states", label: "State" }, { value: "top_countries", label: "Country" }]} />
          <BarList rows={who[place]} color="teal" />
        </Box>
        <Box>
          <Text size="xs" fw={700} tt="uppercase" c="dimmed" mb="xs">Gold vs silver vs imitation</Text>
          {mix.length ? (
            <Group gap="md" wrap="nowrap">
              <DonutChart size={110} thickness={16} withTooltip valueFormatter={(v) => formatINR(v, { compact: true })}
                data={mix.map((m) => ({ name: METAL_LABEL[m.name] ?? m.name, value: m.revenue, color: MATERIAL_COLOR[m.name] ?? "gray.5" }))} />
              <Stack gap={2}>
                {mix.map((m) => <Text key={m.name} size="xs"><b>{METAL_LABEL[m.name] ?? m.name}</b> {m.share_pct}%</Text>)}
              </Stack>
            </Group>
          ) : <Text size="sm" c="dimmed">No data yet</Text>}
        </Box>
        <Box>
          <Text size="xs" fw={700} tt="uppercase" c="dimmed" mb="xs">Bought from (dealers)</Text>
          {who.top_dealers.length ? (
            <Table fz="sm" verticalSpacing={4}>
              <Table.Tbody>
                {who.top_dealers.map((d) => (
                  <Table.Tr key={d.name}>
                    <Table.Td><Text size="sm" truncate maw={200}>{d.name}</Text></Table.Td>
                    <Table.Td ta="right"><Text size="xs" c="dimmed" className="num">{d.pieces} pcs</Text></Table.Td>
                    <Table.Td ta="right"><Text size="sm" fw={700} className="num">{formatINR(d.amount, { compact: true })}</Text></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : <Text size="sm" c="dimmed">No purchases in this period</Text>}
        </Box>
      </SimpleGrid>
    </SectionCard>
  );
}

function ReportView({ run }: { run: InsightRun }) {
  const navigate = useNavigate();
  const r = run.report;
  const ev = run.evidence ?? { designs_of_interest: [], categories: [], anomaly_candidates: [], reorder_baseline: [] };
  const targetAction = (t: string): { label: string; go: () => void } => {
    switch (t) {
      case "PURCHASE_PLAN": return { label: "Review purchase plan", go: () => navigate(run.purchase_plan ? `/app/purchase-plans/${run.purchase_plan.id}` : "/app/purchase-plans") };
      case "OUT_OF_STOCK": return { label: "See sold-out designs", go: () => navigate("/app/inventory?status=OUT") };
      case "LOW_STOCK": return { label: "See low-stock designs", go: () => navigate("/app/inventory?status=LOW") };
      case "DEAD_STOCK": return { label: "See slow stock", go: () => navigate("/app/reports?tab=dead") };
      case "ANOMALIES": return { label: "Show entries", go: () => document.getElementById("anomalies")?.scrollIntoView({ behavior: "smooth" }) };
      case "REPORTS": return { label: "Open reports", go: () => navigate("/app/reports") };
      case "SALES": return { label: "Explore sales", go: () => navigate("/app/sales?tab=explore") };
      default: return { label: "Open inventory", go: () => navigate("/app/inventory") };
    }
  };
  const trend = run.facts?.sales_trend_by_category ?? [];
  const trendData = useMemo(() => {
    if (!trend.length) return [];
    return trend[0].points.map((pt, i) => {
      const row: Record<string, string | number> = { month: pt.month.slice(5) + "/" + pt.month.slice(2, 4) };
      trend.forEach((s) => (row[s.name] = s.points[i]?.value ?? 0));
      return row;
    });
  }, [trend]);
  const doi = ev.designs_of_interest as Record<string, unknown>[];

  const sec = (i: number, node: ReactNode) => (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>{node}</motion.div>
  );

  return (
    <Stack gap="lg">
      {run.status === "PARTIAL" && (
        <Alert color="orange" icon={<IconAlertTriangle size={18} />} variant="light">
          Some parts were generated automatically because the free AI quota was reached or the AI was busy. Numbers are exact;
          explanations are simpler. Try "Refresh insights" later for a full AI report.
        </Alert>
      )}
      {sec(0,
        <Paper className="gold-border" p={{ base: "lg", sm: "xl" }} radius="lg">
          <Group gap="xs" mb="xs">
            <IconSparkles size={16} color="var(--mantine-color-gold-7)" />
            <Text size="xs" fw={700} tt="uppercase" c="gold.8">The accountant's conclusion · {run.period_label}</Text>
            <Tooltip label={r.confidence_reason || "Confidence"} multiline w={260}>
              <Badge color={r.confidence === "HIGH" ? "teal" : r.confidence === "MEDIUM" ? "orange" : "gray"} variant="light">
                {r.confidence.toLowerCase()} confidence
              </Badge>
            </Tooltip>
          </Group>
          <Title order={2} fz={{ base: 22, sm: 28 }} lh={1.25}>{r.headline}</Title>
          <Text mt="md" fz={{ base: "sm", sm: "md" }} lh={1.7}>{r.conclusion}</Text>
          <SimpleGrid cols={{ base: 2, sm: 3, md: Math.min(6, Math.max(2, r.key_numbers.length)) }} mt="lg">
            {r.key_numbers.map((k) => (
              <Paper key={k.label} p="sm" radius="md" withBorder>
                <Text size="xs" c="dimmed">{k.label}</Text>
                <Text className="serif" fw={700} fz="xl">{k.value}</Text>
              </Paper>
            ))}
          </SimpleGrid>
          {r.data_quality_notes.length > 0 && (
            <List size="xs" c="dimmed" mt="md" icon={<IconInfoCircle size={12} />}>
              {r.data_quality_notes.map((n) => <List.Item key={n}>{n}</List.Item>)}
            </List>
          )}
        </Paper>)}

      {sec(1,
        <SectionCard title="Recommended actions" icon={<IconCheck size={18} />}>
          <Stack gap="sm">
            {r.recommended_actions.map((a, i) => {
              const t = targetAction(a.target);
              return (
                <Paper key={i} p="md" radius="md" withBorder style={{ borderLeft: `4px solid var(--mantine-color-${PRIO_COLOR[a.priority]}-6)` }}>
                  <Group justify="space-between" wrap="wrap" gap="sm">
                    <Box style={{ flex: 1, minWidth: 220 }}>
                      <Group gap="xs">
                        <Text fw={700}>{i + 1}. {a.title}</Text>
                        <Badge size="xs" color={PRIO_COLOR[a.priority]} variant="light">{a.priority.toLowerCase()}</Badge>
                      </Group>
                      <Text size="sm" c="dimmed" lineClamp={1}>{a.why}</Text>
                    </Box>
                    <Button size="xs" variant="light" onClick={t.go}>{t.label} →</Button>
                  </Group>
                </Paper>
              );
            })}
          </Stack>
        </SectionCard>)}

      {run.facts?.who && sec(2, <WhoSection who={run.facts.who} note={r.customers_view} />)}

      {sec(2,
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <SectionCard title="What's selling" icon={<IconFlame size={18} />}>
            <Text size="sm" mb="sm">{r.whats_selling}</Text>
            <Stack gap={6}>
              {run.demand.high_demand.slice(0, 8).map((d) => {
                const max = Math.max(...run.demand.high_demand.map((x) => x.velocity_30d), 1);
                return (
                  <Box key={d.label}>
                    <Group justify="space-between" wrap="nowrap">
                      <Tooltip label={d.reason} multiline w={300} disabled={!d.reason}>
                        <Text size="sm" style={{ cursor: "help" }}><LabelCode>{d.label}</LabelCode> <Text span size="xs" c="dimmed">{d.category}</Text></Text>
                      </Tooltip>
                      <Text size="xs" fw={600} className="num">{d.velocity_30d}/mo</Text>
                    </Group>
                    <Progress value={(d.velocity_30d / max) * 100} size="sm" color="orange" mt={2} />
                  </Box>
                );
              })}
            </Stack>
            <WhyCollapse>
              <EvidenceTable rows={doi.filter((x) => x.demand === "HIGH")} cols={[["label", "Label"], ["sold_period", "Sold (period)"], ["sold_prev_period", "Previous"], ["velocity_30d", "Pace/month"], ["stock", "Stock"]]} />
            </WhyCollapse>
          </SectionCard>
          <SectionCard title="What's not selling" icon={<IconZzz size={18} />}>
            <Text size="sm" mb="sm">{r.whats_not_selling}</Text>
            <Stack gap={6}>
              {run.demand.low_demand.slice(0, 8).map((d) => (
                <Tooltip key={d.label} label={d.reason} multiline w={300} disabled={!d.reason}>
                  <Text size="sm" style={{ cursor: "help" }}><LabelCode>{d.label}</LabelCode> <Text span size="xs" c="dimmed">{d.category}</Text></Text>
                </Tooltip>
              ))}
            </Stack>
            <WhyCollapse>
              <EvidenceTable rows={doi.filter((x) => x.status === "DEAD" || x.demand === "LOW")} cols={[["label", "Label"], ["days_since_last_sale", "Days since sale"], ["stock", "Stock"], ["value_tied_up", "Value tied up"]]} />
            </WhyCollapse>
          </SectionCard>
        </SimpleGrid>)}

      {(run.demand.seasonal_notes.length > 0 || run.demand.trend_notes.length > 0) && sec(3,
        <Paper p="md" radius="md" withBorder>
          <Group gap="xs" mb={6}><IconTrendingUp size={16} /><Text fw={600} size="sm">Seasons & trends</Text></Group>
          <List size="sm" spacing={4}>
            {[...run.demand.seasonal_notes, ...run.demand.trend_notes].map((n) => <List.Item key={n}>{n}</List.Item>)}
          </List>
        </Paper>)}

      {sec(4,
        <SectionCard title="Stock risks" icon={<IconAlertTriangle size={18} />}>
          <Text size="sm" mb="sm">{r.risks}</Text>
          <Tabs defaultValue="out">
            <Tabs.List>
              <Tabs.Tab value="out">Sold out ({run.stock_position.out_of_stock.length})</Tabs.Tab>
              <Tabs.Tab value="low">Low ({run.stock_position.low_stock.length})</Tabs.Tab>
              <Tabs.Tab value="dead">Not selling ({run.stock_position.dead_stock.length})</Tabs.Tab>
            </Tabs.List>
            {(["out", "low", "dead"] as const).map((k) => {
              const list = k === "out" ? run.stock_position.out_of_stock : k === "low" ? run.stock_position.low_stock : run.stock_position.dead_stock;
              return (
                <Tabs.Panel key={k} value={k} pt="sm">
                  {list.length ? (
                    <Table fz="sm" verticalSpacing={6}>
                      <Table.Tbody>
                        {list.map((n) => (
                          <Table.Tr key={n.label}>
                            <Table.Td w={110}><LabelCode>{n.label}</LabelCode></Table.Td>
                            <Table.Td w={110}><Text size="xs" c="dimmed">{n.category}</Text></Table.Td>
                            <Table.Td w={70} className="num">{n.stock} pcs</Table.Td>
                            <Table.Td><Tooltip label={n.note} multiline w={300} disabled={!n.note}><Text size="xs" c="dimmed" lineClamp={1}>{n.note}</Text></Tooltip></Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  ) : <Text size="sm" c="dimmed">None 🎉</Text>}
                </Tabs.Panel>
              );
            })}
          </Tabs>
          <Text size="xs" c="dimmed" mt="sm">{run.stock_position.summary}</Text>
        </SectionCard>)}

      {sec(5,
        <SectionCard
          title="Purchase plan & budget"
          icon={<IconShoppingCart size={18} />}
          actions={run.purchase_plan && <Button size="xs" onClick={() => navigate(`/app/purchase-plans/${run.purchase_plan!.id}`)}>Open purchase plan →</Button>}
        >
          <Grid gap="md" align="center">
            <Grid.Col span={{ base: 12, sm: 5 }}>
              <Text size="sm" c="dimmed">Suggested restock budget</Text>
              <Text className="serif" fw={700} fz={34}>{formatINR(run.budget.total_budget, { compact: true })}</Text>
              <Text size="xs" c="dimmed">{run.budget.items.length} designs · {run.budget.notes}</Text>
              {run.budget.by_category.length > 0 && (
                <DonutChart mt="sm" size={150} thickness={20} withTooltip valueFormatter={(v) => formatINR(v, { compact: true })}
                  data={run.budget.by_category.map((b, i) => ({ name: b.category, value: b.amount, color: `${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}.6` }))} />
              )}
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 7 }}>
              <Text size="sm" mb="sm">{r.money_view}</Text>
              <Table fz="sm">
                <Table.Thead><Table.Tr><Table.Th>Design</Table.Th><Table.Th ta="right">Qty</Table.Th><Table.Th ta="right">Total</Table.Th></Table.Tr></Table.Thead>
                <Table.Tbody>
                  {run.budget.items.slice(0, 6).map((b) => (
                    <Table.Tr key={b.label}>
                      <Table.Td><LabelCode>{b.label}</LabelCode></Table.Td>
                      <Table.Td ta="right" className="num">{b.quantity}</Table.Td>
                      <Table.Td ta="right" className="num">{formatINR(b.line_total, { compact: true })}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Grid.Col>
          </Grid>
          <WhyCollapse>
            <Text size="xs" mb="xs">Cost per piece = last purchase price × (1 + inflation %). Quantities start from: pieces sold per month × cover months + minimum stock − stock on hand.</Text>
            <EvidenceTable rows={ev.reorder_baseline as Record<string, unknown>[]} cols={[["label", "Label"], ["stock", "Stock"], ["suggested_qty", "Baseline qty"], ["expected_unit_cost", "Unit cost"], ["line_total", "Total"]]} />
          </WhyCollapse>
        </SectionCard>)}

      {sec(6,
        <SectionCard title="Things to double-check" icon={<IconAlertTriangle size={18} />} id="anomalies">
          <Text size="sm" mb="sm">{run.anomalies.summary}</Text>
          {run.anomalies.items.length ? (
            <Stack gap="xs">
              {run.anomalies.items.map((a, i) => (
                <Paper key={i} p="sm" radius="md" withBorder>
                  <Group gap="xs" wrap="nowrap" align="flex-start">
                    <ThemeIcon size={26} radius="xl" color={PRIO_COLOR[a.severity]} variant="light"><IconAlertTriangle size={14} /></ThemeIcon>
                    <Box>
                      <Text size="sm" fw={600}>{a.label && <LabelCode>{a.label}</LabelCode>} {a.issue}</Text>
                      {a.evidence && <Text size="xs" c="dimmed">{a.evidence}</Text>}
                      {a.suggested_check && <Text size="xs" mt={2}>✓ {a.suggested_check}</Text>}
                    </Box>
                  </Group>
                </Paper>
              ))}
            </Stack>
          ) : <Text size="sm" c="dimmed">No unusual entries found ✓</Text>}
        </SectionCard>)}

      {trendData.length > 0 && sec(7,
        <SectionCard title="Sales by category · 12 months" icon={<IconTrendingUp size={18} />}>
          <AreaChart
            h={280}
            data={trendData}
            dataKey="month"
            type="stacked"
            curveType="natural"
            withLegend
            legendProps={{ verticalAlign: "bottom" }}
            series={trend.map((s, i) => ({ name: s.name, color: `${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}.6` }))}
            valueFormatter={(v) => formatINR(v, { compact: true })}
            yAxisProps={{ width: 70 }}
          />
        </SectionCard>)}

      <Group justify="space-between" className="no-print">
        <Text size="xs" c="dimmed">This report gives insights only. All decisions are yours.</Text>
        <Button variant="subtle" size="xs" leftSection={<IconPrinter size={14} />} onClick={() => window.print()}>Print / Save as PDF</Button>
      </Group>
    </Stack>
  );
}

export default function InsightsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const runParam = params.get("run") ? Number(params.get("run")) : undefined;
  const isWide = useMediaQuery("(min-width: 75em)");
  const [chatOpen, { open: openChat, close: closeChat }] = useDisclosure(false);
  const period = usePeriodParams();
  const { data: dash } = useDashboard();
  const latestQ = useInsightsLatest();
  const runQ = useInsightRun(runParam);
  const { data: runs } = useInsightRuns();
  const { data: running, refetch: refetchRunning } = useRunningInsights();
  const start = useStartInsights();
  const setSeen = useUi((s) => s.setInsightsSeen);
  const chatMinimized = useUi((s) => s.chatMinimized);
  const setChatMinimized = useUi((s) => s.setChatMinimized);
  const run = runParam ? runQ.data : latestQ.data;
  const [jobId, setJobId] = useState<string | null>(null);
  const activeJob = jobId ?? running?.id ?? null;

  useEffect(() => {
    if (run) setSeen(run.id);
  }, [run, setSeen]);

  const generate = async () => {
    try {
      const anchor = period.anchor;
      const res = await start.mutateAsync({ period_type: period.period_type, anchor });
      setJobId(res.job_id);
      if (runParam) setParams({});
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
      refetchRunning();
    }
  };

  const onDone = (runId: number | null, ok: boolean) => {
    setJobId(null);
    ["insightsLatest", "insightRuns", "insightsRunning", "dashboard", "plans"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    if (ok) {
      celebrate();
      notifications.show({ color: "gold", title: "✨ Insights ready", message: "Your AI accountant has finished the report." });
      if (runId) setSeen(runId);
    } else notifications.show({ color: "red", title: "Insights failed", message: "Please try again in a minute." });
  };

  const hasDesigns = (dash?.kpis.total_designs ?? 0) > 0;
  const lowData = dash ? dash.kpis.sales_units < 20 : false;

  const header = (
    <PageHeader
      title={<Group gap="xs"><IconSparkles size={28} color="var(--mantine-color-gold-6)" />Insights</Group>}
      subtitle={
        run ? (
          <Group gap={6} component="span">
            <span>Generated {formatRelative(run.finished_at ?? run.created_at)} · {run.period_label} ·</span>
            {modelBadge(run.models_used)}
            {run.is_stale && <Badge color="orange" variant="light">{run.changes_since} changes since this report</Badge>}
          </Group>
        ) : "Your AI accountant's analysis of the shop"
      }
      actions={
        <>
          <PeriodPicker compact />
          {runs && runs.length > 0 && (
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon variant="default" size="lg" aria-label="Past reports"><IconClock size={18} /></ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>Past reports</Menu.Label>
                {runs.map((r) => (
                  <Menu.Item key={r.id} onClick={() => setParams({ run: String(r.id) })} disabled={r.status === "RUNNING" || r.status === "FAILED"}>
                    <Text size="sm" fw={600}>{r.period_label} · {formatRelative(r.created_at)}</Text>
                    <Text size="xs" c="dimmed" lineClamp={1}>{r.headline ?? r.status.toLowerCase()}</Text>
                  </Menu.Item>
                ))}
              </Menu.Dropdown>
            </Menu>
          )}
          {hasDesigns && (
            <Tooltip label="Uses your free AI quota. Takes about 1–3 minutes.">
              <Button leftSection={<IconSparkles size={16} />} onClick={generate} loading={start.isPending} disabled={!!activeJob} variant="gradient" gradient={{ from: "gold.5", to: "gold.8", deg: 135 }}>
                {run ? "Refresh insights" : "Generate insights"}
              </Button>
            </Tooltip>
          )}
        </>
      }
    />
  );

  let body: ReactNode;
  if (!dash || latestQ.isLoading) body = <Stack><Skeleton h={220} radius="lg" /><Skeleton h={160} radius="lg" /></Stack>;
  else if (!hasDesigns) {
    body = <EmptyBox title="Add your inventory first" text="The AI needs some designs and stock to analyse." action={<Button onClick={() => navigate("/app/inventory")}>Go to inventory</Button>} />;
  } else if (activeJob) body = <GenerationProgress jobId={activeJob} onDone={onDone} />;
  else if (latestQ.isError || runQ.isError) body = <ErrorState onRetry={() => { latestQ.refetch(); runQ.refetch(); }} />;
  else if (!run) {
    body = (
      <Paper className="gold-border" p={{ base: "lg", sm: 48 }} radius="xl" ta="center">
        <motion.div animate={{ y: [0, -6, 0] }} transition={{ repeat: Infinity, duration: 3 }}>
          <ThemeIcon size={80} radius="xl" variant="gradient" gradient={{ from: "gold.3", to: "gold.7" }} mx="auto"><IconSparkles size={42} /></ThemeIcon>
        </motion.div>
        <Title order={2} mt="lg">Meet your AI accountant</Title>
        <Text c="dimmed" maw={560} mx="auto" mt="xs">It reads your stock and sales and writes you a report, just like a senior accountant would.</Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }} mt="xl" maw={760} mx="auto">
          {[["A clear conclusion", "What's happening and what to do first"], ["What sells, what doesn't", "Best sellers, slow stock, seasons"], ["A purchase plan", "What to restock, how many, and the budget"]].map(([t, s]) => (
            <Paper key={t} p="md" radius="md" withBorder><Text fw={700}>{t}</Text><Text size="sm" c="dimmed">{s}</Text></Paper>
          ))}
        </SimpleGrid>
        <Button mt="xl" size="lg" leftSection={<IconSparkles size={20} />} onClick={generate} loading={start.isPending} variant="gradient" gradient={{ from: "gold.5", to: "gold.8", deg: 135 }}>
          Generate my first insights
        </Button>
        {lowData && <Text size="xs" c="dimmed" mt="sm">Tip: insights get sharper as you record more sales. You can still generate now.</Text>}
      </Paper>
    );
  } else body = <ReportView run={run} />;

  if (isWide && chatMinimized) {
    return (
      <>
        {header}
        {body}
        <Affix position={{ bottom: 24, right: 24 }} className="no-print">
          <Button radius="xl" size="md" leftSection={<IconMessageChatbot size={20} />} onClick={() => setChatMinimized(false)} variant="gradient" gradient={{ from: "gold.5", to: "gold.8" }} style={{ boxShadow: "0 8px 24px rgba(157,122,24,.35)" }}>
            Ask AI
          </Button>
        </Affix>
      </>
    );
  }
  if (isWide) {
    return (
      <>
        {header}
        <Grid gap="lg">
          <Grid.Col span={8}>{body}</Grid.Col>
          <Grid.Col span={4}>
            <Box style={{ position: "sticky", top: 80 }}>
              <ChatPanel height="calc(100vh - 96px)" onMinimize={() => setChatMinimized(true)} />
            </Box>
          </Grid.Col>
        </Grid>
      </>
    );
  }
  return (
    <>
      {header}
      {body}
      <Affix position={{ bottom: 90, right: 20 }} className="no-print">
        <Button radius="xl" size="md" leftSection={<IconMessageChatbot size={20} />} onClick={openChat} variant="gradient" gradient={{ from: "gold.5", to: "gold.8" }} style={{ boxShadow: "0 8px 24px rgba(157,122,24,.35)" }}>
          Ask AI
        </Button>
      </Affix>
      <Drawer opened={chatOpen} onClose={closeChat} position="right" size="100%" withCloseButton padding={0} title={<Text fw={700} px="md">AI Accountant</Text>}>
        <Box h="calc(100dvh - 70px)" p="xs"><ChatPanel height="100%" /></Box>
      </Drawer>
    </>
  );
}
