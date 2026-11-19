import {
  Anchor,
  Badge,
  Box,
  Button,
  Collapse,
  Grid,
  Group,
  Paper,
  Progress,
  RingProgress,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  Timeline,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { AreaChart, DonutChart } from "@mantine/charts";
import { useDisclosure } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconArrowRight,
  IconCategoryPlus,
  IconChartPie,
  IconCheck,
  IconCoin,
  IconDiamond,
  IconFlame,
  IconLock,
  IconPackage,
  IconShoppingBag,
  IconSparkles,
  IconTrendingDown,
  IconTrendingUp,
  IconZzz,
  type Icon,
} from "@tabler/icons-react";
import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { errorMessage } from "../../api/client";
import { useCategories, useDashboard, useLoadDemo, useRunningInsights, useSettings, useStartInsights } from "../../api/hooks";
import { useJobEvents } from "../../api/sse";
import type { Dashboard, InstantInsight } from "../../api/types";
import { PeriodPicker } from "../../components/PeriodPicker";
import { StockStepper } from "../../components/stock";
import { DemandBadge, ErrorState, KpiCard, LabelCode, LiveIndicator, Money, PhotoThumb, SectionCard, StatusBadge } from "../../components/ui";
import { celebrate } from "../../lib/confetti";
import { MOVEMENT_META, STATUS_META } from "../../lib/constants";
import { formatINR, formatNumber, formatRelative, greeting } from "../../lib/format";
import { useAuth, useUi } from "../../stores";
import { AddCategoryModal, AddDesignsWizard } from "../inventory/components";

const SEV: Record<InstantInsight["severity"], { color: string }> = {
  critical: { color: "red" }, warning: { color: "orange" }, info: { color: "blue" }, success: { color: "teal" },
};
const INSIGHT_ICONS: Record<string, Icon> = {
  "alert-triangle": IconAlertTriangle, flame: IconFlame, "alert-circle": IconAlertCircle, "trending-up": IconTrendingUp,
  "trending-down": IconTrendingDown, zzz: IconZzz, "chart-pie": IconChartPie, "category-plus": IconCategoryPlus,
  diamond: IconDiamond, "shopping-bag": IconShoppingBag,
};

// ---------------------------------------------------------------------------------------------
// Onboarding (blank shop)
// ---------------------------------------------------------------------------------------------
function SetupChecklist({ d, compact = false }: { d: Dashboard; compact?: boolean }) {
  const navigate = useNavigate();
  const { data: cats } = useCategories();
  const openQuick = useUi((s) => s.openQuickStock);
  const [catOpen, setCatOpen] = useState(false);
  const [wizardFor, setWizardFor] = useState<number | null>(null);
  const firstCat = cats?.[0];
  const steps: { done: boolean; title: string; help: string; cta: string; icon: Icon; action: () => void }[] = [
    { done: d.setup.has_category, title: "Add your first category", help: "Like Earrings, Necklaces or Bangles.", cta: "Add category", icon: IconCategoryPlus, action: () => setCatOpen(true) },
    { done: d.setup.has_designs, title: "Add designs with their labels", help: "Enter how many designs you have and type their labels (e.g. ER-1012).", cta: "Add designs", icon: IconDiamond, action: () => (firstCat ? setWizardFor(firstCat.id) : setCatOpen(true)) },
    { done: d.setup.has_opening_stock, title: "Enter opening stock", help: "Done automatically when designs are created with stock.", cta: "Go to inventory", icon: IconPackage, action: () => navigate("/app/inventory") },
    { done: d.setup.has_sale, title: "Record your first sale", help: "Tap − on any design to record a sale.", cta: "Record a sale", icon: IconShoppingBag, action: () => openQuick("OUT") },
    { done: d.setup.has_insights, title: "Generate your first AI insights", help: "Your AI accountant will analyse everything.", cta: "Generate insights", icon: IconSparkles, action: () => navigate("/app/insights") },
  ];
  const nextIdx = steps.findIndex((s) => !s.done);
  return (
    <>
      <Stack gap={compact ? "xs" : "sm"}>
        {steps.map((s, i) => {
          const isNext = i === nextIdx;
          return (
            <motion.div key={s.title} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
              <Paper
                p={compact ? "sm" : "md"}
                radius="md"
                withBorder
                style={{ borderColor: isNext ? "var(--mantine-color-gold-5)" : undefined, background: isNext ? "var(--mantine-color-gold-light)" : undefined }}
              >
                <Group justify="space-between" wrap="nowrap" gap="sm">
                  <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
                    <ThemeIcon radius="xl" size={38} color={s.done ? "teal" : isNext ? "gold" : "gray"} variant={s.done ? "filled" : "light"}>
                      {s.done ? <IconCheck size={20} /> : <s.icon size={18} />}
                    </ThemeIcon>
                    <Box style={{ minWidth: 0 }}>
                      <Text fw={600} td={s.done ? "line-through" : undefined} c={s.done ? "dimmed" : undefined}>
                        {i + 1}. {s.title}
                      </Text>
                      {!compact && (
                        <Text size="sm" c="dimmed">
                          {s.done ? "Done" : s.help}
                        </Text>
                      )}
                    </Box>
                  </Group>
                  {!s.done && (
                    <Button size="xs" variant={isNext ? "filled" : "default"} onClick={s.action} rightSection={<IconArrowRight size={14} />}>
                      {s.cta}
                    </Button>
                  )}
                </Group>
              </Paper>
            </motion.div>
          );
        })}
      </Stack>
      <AddCategoryModal opened={catOpen} onClose={() => setCatOpen(false)} onSaved={(c) => setWizardFor(c.id)} />
      {wizardFor && <AddDesignsWizard opened={!!wizardFor} onClose={() => setWizardFor(null)} categoryId={wizardFor} />}
    </>
  );
}

function LockedPreview() {
  const fake = [{ label: "Jun", value: 4 }, { label: "Jul", value: 6 }, { label: "Aug", value: 5 }, { label: "Sep", value: 8 }, { label: "Oct", value: 12 }, { label: "Nov", value: 9 }];
  const items = [
    { title: "Live KPIs", body: <SimpleGrid cols={2}>{["₹48.6 L", "1,248", "9", "₹9.1 L"].map((v) => <Text key={v} className="serif" fw={700} fz={22}>{v}</Text>)}</SimpleGrid> },
    { title: "Stock health", body: <DonutChart h={120} size={110} thickness={18} data={[{ name: "In", value: 70, color: "teal.6" }, { name: "Low", value: 15, color: "orange.6" }, { name: "Out", value: 10, color: "red.6" }]} withTooltip={false} /> },
    { title: "Sales trend", body: <AreaChart h={120} data={fake} dataKey="label" series={[{ name: "value", color: "gold.6" }]} withXAxis={false} withYAxis={false} gridAxis="none" withTooltip={false} curveType="natural" /> },
  ];
  return (
    <Box>
      <Text fw={600} mb="sm">
        What you'll see once your shop is set up
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        {items.map((it) => (
          <Paper key={it.title} className="soft-card" p="md" radius="md" style={{ position: "relative", overflow: "hidden" }}>
            <Text size="sm" c="dimmed" mb="xs">
              {it.title}
            </Text>
            <Box style={{ filter: "blur(3px)", opacity: 0.6, pointerEvents: "none" }}>{it.body}</Box>
            <Stack align="center" justify="center" gap={4} style={{ position: "absolute", inset: 0 }}>
              <ThemeIcon radius="xl" variant="light" size={36}>
                <IconLock size={18} />
              </ThemeIcon>
              <Text size="xs" c="dimmed">
                Unlocks when you add designs
              </Text>
            </Stack>
          </Paper>
        ))}
      </SimpleGrid>
    </Box>
  );
}

function Onboarding({ d }: { d: Dashboard }) {
  const { data: settings } = useSettings();
  const loadDemo = useLoadDemo();
  const user = useAuth((s) => s.user);
  return (
    <Stack gap="xl">
      <Paper className="gold-border" p={{ base: "lg", sm: "xl" }} radius="xl">
        <Group justify="space-between" wrap="wrap" gap="lg">
          <Box maw={560}>
            <Title order={1} fz={{ base: 26, sm: 32 }}>
              Welcome to {settings?.shop_name ?? "your shop"}, {user?.display_name} 👋
            </Title>
            <Text c="dimmed" mt="xs">
              Let's set up your shop. It takes about 5 minutes. Add your categories and designs, record stock, and your AI
              accountant takes it from there.
            </Text>
          </Box>
          <RingProgress
            size={110}
            thickness={10}
            roundCaps
            sections={[{ value: (d.setup.completed_steps / d.setup.total_steps) * 100, color: "gold.6" }]}
            label={<Text ta="center" fw={700} className="serif" fz={22}>{d.setup.completed_steps}/{d.setup.total_steps}</Text>}
          />
        </Group>
      </Paper>
      <SetupChecklist d={d} />
      <LockedPreview />
      <Text size="sm" c="dimmed" ta="center">
        Just exploring?{" "}
        <Anchor
          component="button"
          type="button"
          onClick={() =>
            modals.openConfirmModal({
              title: "Load demo data?",
              children: (
                <Text size="sm">
                  This fills your empty shop with a sample jewellery store: 8 categories, about 120 designs and 12 months of sales,
                  purchases and returns, so you can try every feature. You can reset it later in Settings.
                </Text>
              ),
              labels: { confirm: "Load demo data", cancel: "Cancel" },
              onConfirm: () =>
                loadDemo.mutateAsync()
                  .then((r) => {
                    celebrate();
                    notifications.show({ color: "teal", title: "Demo shop loaded ✨", message: `${r.designs} designs with 12 months of history.` });
                  })
                  .catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
            })
          }
        >
          Load demo data
        </Anchor>
      </Text>
    </Stack>
  );
}

// ---------------------------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------------------------
function AiHeadlineCard({ d }: { d: Dashboard }) {
  const navigate = useNavigate();
  const start = useStartInsights();
  const { data: running } = useRunningInsights();
  const progress = useJobEvents(running?.id);
  const ai = d.latest_ai;
  const doneSteps = progress.steps.filter((s) => s.status === "DONE").length;
  const total = progress.steps.length || 7;

  const generate = () =>
    start.mutateAsync({ period_type: d.period.period_type, anchor: d.period.start })
      .then(() => navigate("/app/insights"))
      .catch((e) => notifications.show({ color: "red", message: errorMessage(e) }));

  return (
    <Paper className="gold-border lift" p="lg" radius="lg">
      <Group justify="space-between" wrap="wrap" gap="md" align="flex-start">
        <Group gap="md" wrap="nowrap" align="flex-start" style={{ flex: 1, minWidth: 260 }}>
          <ThemeIcon size={44} radius="xl" variant="gradient" gradient={{ from: "gold.3", to: "gold.7", deg: 135 }}>
            <IconSparkles size={24} />
          </ThemeIcon>
          <Box style={{ minWidth: 0, flex: 1 }}>
            <Group gap="xs">
              <Text size="xs" fw={700} tt="uppercase" c="gold.8">
                AI Accountant
              </Text>
              {ai?.is_stale && <Badge color="orange" variant="light" size="sm">{ai.changes_since} changes since</Badge>}
              {ai?.status === "PARTIAL" && <Badge color="gray" variant="light" size="sm">Automatic</Badge>}
            </Group>
            {running ? (
              <>
                <Text className="serif" fw={700} fz={20} mt={4}>
                  Analysing your shop…
                </Text>
                <Progress value={(doneSteps / total) * 100} mt="sm" animated striped color="gold" />
                <Text size="xs" c="dimmed" mt={4}>
                  Step {Math.min(doneSteps + 1, total)} of {total}
                  {progress.currentTool ? ` · ${progress.currentTool}` : ""}
                </Text>
              </>
            ) : ai ? (
              <>
                <Text className="serif" fw={700} fz={20} mt={4} lh={1.3}>
                  {ai.headline}
                </Text>
                <Text size="sm" c="dimmed" mt={4} lineClamp={2}>
                  {ai.conclusion_short}
                </Text>
                <Text size="xs" c="dimmed" mt={6}>
                  Generated {formatRelative(ai.created_at)} · {ai.period_label}
                </Text>
              </>
            ) : (
              <Text mt={4}>Your AI accountant hasn't analysed the shop yet.</Text>
            )}
          </Box>
        </Group>
        <Group gap="xs">
          {ai?.is_stale && !running && (
            <Button variant="light" size="sm" onClick={generate} loading={start.isPending}>
              Refresh
            </Button>
          )}
          {ai ? (
            <Button rightSection={<IconArrowRight size={16} />} onClick={() => navigate("/app/insights")}>
              Open full insights
            </Button>
          ) : (
            !running && (
              <Button leftSection={<IconSparkles size={16} />} onClick={generate} loading={start.isPending} disabled={!d.kpis.total_designs}>
                Generate insights
              </Button>
            )
          )}
        </Group>
      </Group>
    </Paper>
  );
}

function InsightsList({ items }: { items: InstantInsight[] }) {
  const navigate = useNavigate();
  if (!items.length) return <Text size="sm" c="dimmed">All good, nothing needs attention right now ✨</Text>;
  return (
    <Stack gap="xs">
      {items.map((it, i) => {
        const I = INSIGHT_ICONS[it.icon] ?? IconSparkles;
        return (
          <motion.div key={it.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
            <UnstyledButton onClick={() => navigate(it.action.route)} w="100%" p="sm" style={{ borderRadius: 12 }} className="lift">
              <Group wrap="nowrap" gap="md">
                <ThemeIcon radius="xl" size={36} variant="light" color={SEV[it.severity].color}>
                  <I size={18} />
                </ThemeIcon>
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <Text fw={600} size="sm">
                    {it.title}
                  </Text>
                  <Text size="xs" c="dimmed" truncate>
                    {it.detail}
                  </Text>
                </Box>
                <Text size="xs" c="gold.8" fw={600} style={{ whiteSpace: "nowrap" }}>
                  {it.action.label} →
                </Text>
              </Group>
            </UnstyledButton>
          </motion.div>
        );
      })}
    </Stack>
  );
}

function Overview({ d }: { d: Dashboard }) {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: settings } = useSettings();
  const [trendMode, setTrendMode] = useState<"value" | "units">("value");
  const [setupOpen, { toggle: toggleSetup }] = useDisclosure(false);
  const k = d.kpis;
  const healthData = (Object.keys(d.stock_health) as (keyof typeof d.stock_health)[]).map((s) => ({
    name: STATUS_META[s].label, value: d.stock_health[s], color: STATUS_META[s].hex, key: s,
  }));
  const totalDesigns = healthData.reduce((a, b) => a + b.value, 0);
  const periodWord = d.period.period_type === "quarter" ? "this quarter" : "this month";

  const block = (node: ReactNode, i: number) => (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} style={{ height: "100%" }}>
      {node}
    </motion.div>
  );

  return (
    <Stack gap="lg">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Box>
          <Title order={1} fz={{ base: 24, sm: 30 }}>
            {greeting()}, {settings?.owner_name && user?.role === "OWNER" ? settings.owner_name : user?.display_name} ✨
          </Title>
          <Text c="dimmed" size="sm">
            {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short", year: "numeric" })} · Viewing {d.period.label}
          </Text>
        </Box>
        <Group gap="md">
          <PeriodPicker compact />
          <LiveIndicator />
        </Group>
      </Group>

      {d.setup.completed_steps < d.setup.total_steps && (
        <Paper p="sm" radius="md" withBorder>
          <Group justify="space-between">
            <Group gap="sm">
              <Progress value={(d.setup.completed_steps / d.setup.total_steps) * 100} w={120} color="gold" />
              <Text size="sm" fw={600}>
                Finish setup ({d.setup.completed_steps}/{d.setup.total_steps})
              </Text>
            </Group>
            <Anchor size="sm" component="button" type="button" onClick={toggleSetup}>
              {setupOpen ? "Hide" : "Show steps"}
            </Anchor>
          </Group>
          <Collapse expanded={setupOpen}>
            <Box mt="sm">
              <SetupChecklist d={d} compact />
            </Box>
          </Collapse>
        </Paper>
      )}

      {block(<AiHeadlineCard d={d} />, 0)}

      <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }} spacing="md">
        {block(
          <KpiCard icon={<IconCoin size={20} />} label="Stock value (at cost)" value={k.stock_value_cost} format="inr-compact"
            sub={`${formatNumber(k.total_pieces)} pieces · ${formatNumber(k.total_designs)} designs`} spark={d.kpi_sparklines.stock_value_cost} />, 1)}
        {block(
          <KpiCard icon={<IconShoppingBag size={20} />} label={`Sales ${periodWord}`} value={k.sales_value} format="inr-compact" delta={k.sales_change_pct}
            sub={`${formatNumber(k.sales_units)} pieces sold`} spark={d.kpi_sparklines.sales_value} color="teal" onClick={() => navigate("/app/reports?tab=sales")} />, 2)}
        {block(
          <KpiCard icon={<IconAlertTriangle size={20} />} label="Needs attention" value={k.needs_attention} color="orange"
            valueColor={k.needs_attention ? "orange.8" : undefined} sub={`${k.out_of_stock} sold out · ${k.low_stock} low`}
            onClick={() => navigate("/app/inventory?status=OUT,LOW")} />, 3)}
        {block(
          <KpiCard icon={<IconZzz size={20} />} label="Money stuck in slow stock" value={k.dead_stock_value} format="inr-compact" color="gray"
            sub={`${k.dead_stock} designs not selling for ${settings?.dead_stock_days ?? 90}+ days`} onClick={() => navigate("/app/reports?tab=dead")} />, 4)}
      </SimpleGrid>

      <Grid gap="md">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          {block(
            <SectionCard
              title="Sales trend · last 6 months"
              icon={<IconTrendingUp size={18} />}
              actions={
                <SegmentedControl size="xs" value={trendMode} onChange={(v) => setTrendMode(v as "value" | "units")}
                  data={[{ value: "value", label: "₹ value" }, { value: "units", label: "Pieces" }]} />
              }
            >
              <AreaChart
                h={260}
                data={d.sales_trend}
                dataKey="label"
                series={[{ name: trendMode, label: trendMode === "value" ? "Sales" : "Pieces", color: "gold.6" }]}
                curveType="natural"
                gridAxis="y"
                withGradient
                valueFormatter={(v) => (trendMode === "value" ? formatINR(v, { compact: true }) : formatNumber(v))}
                yAxisProps={{ width: 70 }}
              />
            </SectionCard>, 5)}
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          {block(
            <SectionCard title="Stock health" icon={<IconChartPie size={18} />}>
              <Group justify="center">
                <DonutChart
                  size={170}
                  thickness={24}
                  data={healthData.filter((x) => x.value > 0)}
                  chartLabel={`${totalDesigns} designs`}
                  withTooltip
                  tooltipDataSource="segment"
                  paddingAngle={2}
                />
              </Group>
              <Stack gap={4} mt="md">
                {healthData.map((h) => (
                  <UnstyledButton key={h.key} onClick={() => navigate(`/app/inventory?status=${h.key}`)} p={4} style={{ borderRadius: 8 }}>
                    <Group justify="space-between">
                      <Group gap={8}>
                        <Box w={10} h={10} style={{ borderRadius: 3, background: h.color }} />
                        <Text size="sm">{h.name}</Text>
                      </Group>
                      <Text size="sm" fw={600} className="num">
                        {h.value}
                      </Text>
                    </Group>
                  </UnstyledButton>
                ))}
              </Stack>
            </SectionCard>, 6)}
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          {block(
            <SectionCard title="Today at a glance" icon={<IconSparkles size={18} />}>
              <InsightsList items={d.instant_insights} />
            </SectionCard>, 7)}
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          {block(
            <SectionCard title={`Top sellers · ${d.period.short_label}`} icon={<IconFlame size={18} />}>
              {d.top_sellers.length === 0 ? (
                <Text size="sm" c="dimmed">No sales recorded {periodWord} yet.</Text>
              ) : (
                <Stack gap="sm">
                  {d.top_sellers.map((t) => {
                    const max = d.top_sellers[0].sold_units || 1;
                    return (
                      <UnstyledButton key={t.design_id} onClick={() => navigate(`/app/designs/${t.design_id}`)}>
                        <Group gap="sm" wrap="nowrap">
                          <PhotoThumb url={t.photo_url} size={36} />
                          <Box style={{ flex: 1, minWidth: 0 }}>
                            <Group justify="space-between" wrap="nowrap">
                              <Text size="sm" truncate>
                                <LabelCode>{t.label}</LabelCode> <Text span c="dimmed" size="xs">{t.name}</Text>
                              </Text>
                              <Text size="sm" fw={600} className="num" style={{ whiteSpace: "nowrap" }}>
                                {t.sold_units} · <Money value={t.sales_value} compact />
                              </Text>
                            </Group>
                            <Progress value={(t.sold_units / max) * 100} size="sm" color="gold" mt={4} />
                          </Box>
                        </Group>
                      </UnstyledButton>
                    );
                  })}
                </Stack>
              )}
            </SectionCard>, 8)}
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          {block(
            <SectionCard
              title="Sold out & running low"
              icon={<IconAlertTriangle size={18} />}
              actions={<Anchor size="xs" onClick={() => navigate("/app/inventory?status=OUT,LOW")}>See all</Anchor>}
            >
              {d.alerts.length === 0 ? (
                <Text size="sm" c="dimmed">Nothing sold out or low. 🎉</Text>
              ) : (
                <Stack gap="xs">
                  {d.alerts.map((a) => (
                    <Group key={a.design_id} justify="space-between" wrap="nowrap" gap="sm">
                      <UnstyledButton onClick={() => navigate(`/app/designs/${a.design_id}`)} style={{ minWidth: 0, flex: 1 }}>
                        <Group gap="sm" wrap="nowrap">
                          <PhotoThumb url={a.photo_url} size={32} />
                          <Box style={{ minWidth: 0 }}>
                            <LabelCode>{a.label}</LabelCode>
                            <Group gap={4} mt={2} wrap="nowrap">
                              <StatusBadge status={a.status} size="xs" />
                              {a.demand_class === "HIGH" && <DemandBadge demand="HIGH" size="xs" />}
                            </Group>
                          </Box>
                        </Group>
                      </UnstyledButton>
                      <StockStepper target={{ id: a.design_id, label: a.label, name: a.name, current_stock: a.current_stock, selling_price: a.selling_price, cost_price: a.last_unit_cost, photo_url: a.photo_url, status: a.status }} />
                    </Group>
                  ))}
                </Stack>
              )}
            </SectionCard>, 9)}
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          {block(
            <SectionCard title="Recent activity" icon={<IconPackage size={18} />} actions={<Anchor size="xs" onClick={() => navigate("/app/stock?tab=history")}>Stock history</Anchor>}>
              {d.recent_activity.length === 0 ? (
                <Text size="sm" c="dimmed">No entries yet.</Text>
              ) : (
                <Timeline bulletSize={24} lineWidth={2}>
                  {d.recent_activity.slice(0, 8).map((m) => {
                    const meta = MOVEMENT_META[m.type];
                    const I = meta.icon;
                    return (
                      <Timeline.Item key={m.id} bullet={<I size={13} />} color={m.is_void ? "gray" : meta.color}>
                        <Text size="sm" td={m.is_void ? "line-through" : undefined}>
                          {meta.short} {m.quantity} × <LabelCode>{m.design.label}</LabelCode>
                          {m.value ? <Text span c="dimmed" size="xs"> · {formatINR(m.value, { compact: true })}</Text> : null}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {m.created_by?.display_name ?? "System"} · {m.occurred_on === d.today ? formatRelative(m.created_at) : m.occurred_on}
                        </Text>
                      </Timeline.Item>
                    );
                  })}
                </Timeline>
              )}
            </SectionCard>, 10)}
        </Grid.Col>
      </Grid>

      {user?.role === "OWNER" && d.pending_approvals > 0 && (
        <Paper p="md" radius="md" bg="var(--mantine-color-gold-light)">
          <Group justify="space-between">
            <Text fw={600}>
              {d.pending_approvals} purchase plan{d.pending_approvals > 1 ? "s are" : " is"} waiting for your approval
            </Text>
            <Button size="sm" onClick={() => navigate("/app/purchase-plans")}>
              Review
            </Button>
          </Group>
        </Paper>
      )}
    </Stack>
  );
}

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useDashboard();
  if (isError) return <ErrorState message="Couldn't load the dashboard." onRetry={() => refetch()} />;
  if (isLoading || !data) {
    return (
      <Stack>
        <Skeleton h={50} w={320} />
        <Skeleton h={110} radius="lg" />
        <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} h={170} radius="md" />)}
        </SimpleGrid>
        <Skeleton h={300} radius="md" />
      </Stack>
    );
  }
  const onboarding = !data.setup.has_designs;
  return onboarding ? <Onboarding d={data} /> : <Overview d={data} />;
}
