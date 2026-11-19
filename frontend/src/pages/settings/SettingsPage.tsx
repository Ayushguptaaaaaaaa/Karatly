import { Alert, Badge, Box, Button, Grid, Group, NumberInput, Paper, SegmentedControl, Slider, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle, IconBuildingStore, IconDatabase, IconRobot, IconSettings } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { errorMessage } from "../../api/client";
import { useAiStatus, useDashboard, useLoadDemo, useResetData, useSettings, useUpdateSettings } from "../../api/hooks";
import type { Settings } from "../../api/types";
import { PageHeader, SectionCard } from "../../components/ui";
import { celebrate } from "../../lib/confetti";
import { useAuth } from "../../stores";

function Dot({ ok, warn }: { ok: boolean; warn?: boolean }) {
  return <Box w={10} h={10} style={{ borderRadius: "50%", background: ok ? "#2f9e44" : warn ? "#f08c00" : "#e03131" }} />;
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const owner = useAuth((s) => s.user?.role === "OWNER");
  const { data } = useSettings();
  const { data: ai } = useAiStatus();
  const { data: dash } = useDashboard();
  const update = useUpdateSettings();
  const loadDemo = useLoadDemo();
  const reset = useResetData();
  const [form, setForm] = useState<Settings | null>(null);
  useEffect(() => { if (data) setForm(data); }, [data]);

  const dirty = form && data && JSON.stringify(form) !== JSON.stringify(data);
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));
  const save = () => form && update.mutateAsync(form).then(() => notifications.show({ color: "teal", message: "Settings saved" })).catch((e) => notifications.show({ color: "red", message: errorMessage(e) }));
  const hasDesigns = (dash?.kpis.total_designs ?? 0) > 0;
  const time = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }) : "");

  return (
    <>
      <PageHeader title="Settings" subtitle="Shop profile, business rules, AI status and data tools." actions={<Button onClick={save} disabled={!dirty} loading={update.isPending}>Save changes</Button>} />
      {form && (
        <Grid gap="lg">
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Stack>
              <SectionCard title="Shop profile" icon={<IconBuildingStore size={18} />}>
                <Stack>
                  <TextInput label="Shop name" value={form.shop_name} onChange={(e) => set("shop_name", e.currentTarget.value)} maxLength={80} />
                  <TextInput label="Owner name" value={form.owner_name} onChange={(e) => set("owner_name", e.currentTarget.value)} maxLength={80} />
                </Stack>
              </SectionCard>
              <SectionCard title="Business rules" icon={<IconSettings size={18} />}>
                <Stack gap="lg">
                  <Box>
                    <Group justify="space-between"><Text size="sm" fw={500}>Inflation for purchase estimates</Text><Badge>{form.inflation_pct_global}%</Badge></Group>
                    <Text size="xs" c="dimmed" mb="xs">Expected cost = last purchase cost + this %</Text>
                    <Slider min={0} max={25} step={0.5} value={form.inflation_pct_global} onChange={(v) => set("inflation_pct_global", v)} marks={[{ value: 0, label: "0%" }, { value: 5, label: "5%" }, { value: 10, label: "10%" }, { value: 25, label: "25%" }]} mb="md" />
                  </Box>
                  <Group grow>
                    <NumberInput label="Default minimum stock" description="Low-stock alert level" min={0} max={1000} value={form.default_min_stock} onChange={(v) => set("default_min_stock", Number(v) || 0)} />
                    <NumberInput label="'Not selling' after" description="Days without a sale" suffix=" days" min={15} max={730} value={form.dead_stock_days} onChange={(v) => set("dead_stock_days", Number(v) || 90)} />
                  </Group>
                  <NumberInput label="Reorder should cover" description="Months of sales the purchase plan should cover" suffix=" months" min={0.5} max={6} step={0.5} decimalScale={1} value={form.reorder_cover_months} onChange={(v) => set("reorder_cover_months", Number(v) || 1.5)} w={260} />
                  <Box>
                    <Text size="sm" fw={500} mb={4}>Quarters</Text>
                    <SegmentedControl value={form.quarter_system} onChange={(v) => set("quarter_system", v as Settings["quarter_system"])} data={[{ value: "FINANCIAL", label: "Financial year (Apr–Mar)" }, { value: "CALENDAR", label: "Calendar (Jan–Dec)" }]} />
                  </Box>
                </Stack>
              </SectionCard>
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Stack>
              <SectionCard title="AI status" icon={<IconRobot size={18} />}>
                {ai ? (
                  <Stack gap="sm">
                    {ai.mock_mode && <Alert color="gray">AI is switched off (mock mode). Insights use automatic analysis.</Alert>}
                    <Group justify="space-between"><Group gap="xs"><Dot ok={ai.primary_available} warn={!!ai.primary_cooldown_until} /><Text size="sm">Main model</Text></Group><Text size="sm" fw={600}>{ai.primary_model.replace("gemini/", "")}</Text></Group>
                    {ai.primary_cooldown_until && <Text size="xs" c="orange">Resting until {time(ai.primary_cooldown_until)} (free quota or busy). The backup model is used meanwhile.</Text>}
                    <Group justify="space-between"><Group gap="xs"><Dot ok={ai.fallback_available} warn={!!ai.fallback_cooldown_until} /><Text size="sm">Backup model</Text></Group><Text size="sm" fw={600}>{ai.fallback_model.replace("gemini/", "")}</Text></Group>
                    <Group gap="lg"><Text size="xs" c="dimmed">Insights today: {ai.runs_today}</Text><Text size="xs" c="dimmed">Chat answers today: {ai.chat_answers_today}</Text></Group>
                    <Text size="xs" c="dimmed">Free AI tier: limited requests per day. When the main model is busy, a lighter model or the automatic analysis is used, so the app never stops working.</Text>
                  </Stack>
                ) : <Text size="sm" c="dimmed">Loading…</Text>}
              </SectionCard>
              <SectionCard title="Data tools" icon={<IconDatabase size={18} />}>
                <Stack>
                  <Paper p="md" withBorder radius="md">
                    <Group justify="space-between" wrap="wrap">
                      <Box maw={360}>
                        <Text fw={600}>Load demo data</Text>
                        <Text size="xs" c="dimmed">8 categories, about 120 designs and 12 months of history, to try every feature.</Text>
                      </Box>
                      <Tooltip label="Only for an empty shop" disabled={!hasDesigns}>
                        <Button variant="light" disabled={hasDesigns} loading={loadDemo.isPending}
                          onClick={() => modals.openConfirmModal({
                            title: "Load demo data?", labels: { confirm: "Load", cancel: "Cancel" },
                            children: <Text size="sm">Creates a sample jewellery shop with 12 months of sales, purchases and returns.</Text>,
                            onConfirm: () => loadDemo.mutateAsync().then(() => { celebrate(); notifications.show({ color: "teal", message: "Demo shop loaded ✨" }); navigate("/app"); }).catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
                          })}>
                          Load demo data
                        </Button>
                      </Tooltip>
                    </Group>
                  </Paper>
                  {owner && (
                    <Paper p="md" radius="md" style={{ border: "1px solid var(--mantine-color-red-4)" }}>
                      <Group justify="space-between" wrap="wrap">
                        <Box maw={360}>
                          <Group gap={6}><IconAlertTriangle size={16} color="var(--mantine-color-red-6)" /><Text fw={600} c="red.7">Danger zone: reset all inventory data</Text></Group>
                          <Text size="xs" c="dimmed">Deletes categories, designs, stock history, plans, insights and chats. Logins and settings are kept. This cannot be undone.</Text>
                        </Box>
                        <Button color="red" variant="light" loading={reset.isPending}
                          onClick={() => {
                            let typed = "";
                            modals.openConfirmModal({
                              title: "Reset all inventory data?",
                              children: (
                                <Stack gap="xs">
                                  <Text size="sm">Type <b>RESET</b> to confirm.</Text>
                                  <TextInput onChange={(e) => (typed = e.currentTarget.value)} placeholder="RESET" />
                                </Stack>
                              ),
                              labels: { confirm: "Reset everything", cancel: "Cancel" },
                              confirmProps: { color: "red" },
                              onConfirm: () => {
                                if (typed !== "RESET") return notifications.show({ color: "orange", message: "Type RESET to confirm." });
                                reset.mutateAsync().then(() => { notifications.show({ message: "All inventory data was reset." }); navigate("/app"); }).catch((e) => notifications.show({ color: "red", message: errorMessage(e) }));
                              },
                            });
                          }}>
                          Reset all data
                        </Button>
                      </Group>
                    </Paper>
                  )}
                </Stack>
              </SectionCard>
              <Text size="xs" c="dimmed">Jeweler AI Accountant · Demo / POC version 0.1</Text>
            </Stack>
          </Grid.Col>
        </Grid>
      )}
    </>
  );
}
