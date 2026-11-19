import { ActionIcon, Box, Button, Grid, Group, Paper, SegmentedControl, Skeleton, Table, Tabs, Text, Tooltip } from "@mantine/core";
import { AreaChart, BarChart, DonutChart } from "@mantine/charts";
import { useDisclosure } from "@mantine/hooks";
import { IconChartBar, IconDownload, IconPrinter, IconTable, IconZzz } from "@tabler/icons-react";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { download } from "../../api/client";
import { useDashboard, usePeriodOptions, usePeriodParams, useReport } from "../../api/hooks";
import type { PeriodType, StockStatus } from "../../api/types";
import { PeriodPicker } from "../../components/PeriodPicker";
import { EmptyBox, LabelCode, Money, PageHeader, SectionCard } from "../../components/ui";
import { CATEGORY_COLORS, STATUS_META } from "../../lib/constants";
import { formatINR, formatNumber, formatPct } from "../../lib/format";

type Trend = { series: { key: string; name: string; points: { month: string; label: string; units: number; value: number }[] }[] };
type Breakdown = { category_id: number; name: string; sold_units: number; sales_value: number; stock_value_cost: number; pieces: number; share_pct: number }[];
type Top = { design: { id: number; label: string; name: string | null; category_name: string }; sold_units: number; sales_value: number; current_stock: number }[];
type Dead = { total_value: number; dead_stock_days: number; items: { design: { id: number; label: string; name: string | null; category_name: string }; current_stock: number; days_since_last_sale: number; last_sale_on: string | null; value_tied_up: number }[] };
type Turnover = { category: string; opening: number; closing: number; sold: number; turnover: number }[];
type Compare = { a: { label: string }; b: { label: string }; rows: { key: string; name: string; a_units: number; b_units: number; a_value: number; b_value: number; change_pct: number | null }[] };

const inrC = (v: number) => formatINR(v, { compact: true });

function ChartCard({ title, children, table, exportArgs }: { title: string; children: ReactNode; table?: ReactNode; exportArgs?: Record<string, string | number | undefined> }) {
  const [showTable, { toggle }] = useDisclosure(false);
  return (
    <SectionCard
      title={title}
      actions={
        <Group gap={4} className="no-print">
          {table && <Tooltip label={showTable ? "Show chart" : "View table"}><ActionIcon variant="subtle" onClick={toggle} aria-label="Toggle table">{showTable ? <IconChartBar size={16} /> : <IconTable size={16} />}</ActionIcon></Tooltip>}
          {exportArgs && <Tooltip label="Export to Excel"><ActionIcon variant="subtle" aria-label="Export" onClick={() => download("/reports/export", exportArgs)}><IconDownload size={16} /></ActionIcon></Tooltip>}
        </Group>
      }
    >
      {showTable && table ? table : children}
    </SectionCard>
  );
}

function SimpleTable({ head, rows }: { head: string[]; rows: (string | number | ReactNode)[][] }) {
  return (
    <Box style={{ overflowX: "auto" }}>
      <Table fz="sm" striped>
        <Table.Thead><Table.Tr>{head.map((h) => <Table.Th key={h}>{h}</Table.Th>)}</Table.Tr></Table.Thead>
        <Table.Tbody>{rows.map((r, i) => <Table.Tr key={i}>{r.map((c, j) => <Table.Td key={j} className="num">{c}</Table.Td>)}</Table.Tr>)}</Table.Tbody>
      </Table>
    </Box>
  );
}

function SalesTab() {
  const p = usePeriodParams();
  const [group, setGroup] = useState<"total" | "category">("category");
  const [metric, setMetric] = useState<"value" | "units">("value");
  const trend = useReport<Trend>("sales-trend", { months: 12, group_by: group });
  const bd = useReport<Breakdown>("category-breakdown", p);
  const top = useReport<Top>("top-sellers", { ...p, limit: 10, order: "desc" });
  const bottom = useReport<Top>("top-sellers", { ...p, limit: 10, order: "asc" });
  const series = trend.data?.series ?? [];
  const data = series[0]?.points.map((pt, i) => {
    const row: Record<string, string | number> = { label: `${pt.label} ${pt.month.slice(2, 4)}` };
    series.forEach((s) => (row[s.name] = s.points[i][metric]));
    return row;
  }) ?? [];
  const fmt = metric === "value" ? inrC : formatNumber;
  return (
    <Grid gap="md">
      <Grid.Col span={12}>
        <ChartCard
          title="Sales trend · 12 months"
          exportArgs={{ report: "sales_trend" }}
          table={<SimpleTable head={["Month", ...series.map((s) => s.name)]} rows={data.map((r) => [r.label, ...series.map((s) => fmt(Number(r[s.name])))])} />}
        >
          <Group mb="sm" gap="sm">
            <SegmentedControl size="xs" value={group} onChange={(v) => setGroup(v as "total" | "category")} data={[{ value: "category", label: "By category" }, { value: "total", label: "Total" }]} />
            <SegmentedControl size="xs" value={metric} onChange={(v) => setMetric(v as "value" | "units")} data={[{ value: "value", label: "₹" }, { value: "units", label: "Pieces" }]} />
          </Group>
          {trend.isLoading ? <Skeleton h={280} /> : (
            <AreaChart h={300} data={data} dataKey="label" type={group === "category" ? "stacked" : "default"} curveType="natural" withLegend={group === "category"}
              series={series.map((s, i) => ({ name: s.name, color: group === "total" ? "gold.6" : `${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}.6` }))}
              valueFormatter={fmt} yAxisProps={{ width: 70 }} />
          )}
        </ChartCard>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 6 }}>
        <ChartCard title="Sales by category" table={<SimpleTable head={["Category", "Pieces", "Sales", "Share"]} rows={(bd.data ?? []).map((b) => [b.name, b.sold_units, formatINR(b.sales_value), `${b.share_pct}%`])} />}>
          {bd.isLoading ? <Skeleton h={260} /> : <BarChart h={260} data={bd.data ?? []} dataKey="name" series={[{ name: "sales_value", label: "Sales", color: "gold.6" }]} valueFormatter={inrC} yAxisProps={{ width: 70 }} barProps={{ radius: 6 }} />}
        </ChartCard>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 6 }}>
        <ChartCard title="Top 10 sellers" exportArgs={{ report: "top_sellers", ...p }} table={<SimpleTable head={["Label", "Category", "Sold", "Sales"]} rows={(top.data ?? []).map((t) => [t.design.label, t.design.category_name, t.sold_units, formatINR(t.sales_value)])} />}>
          {top.data?.length ? (
            <BarChart h={260} orientation="vertical" data={(top.data ?? []).map((t) => ({ label: t.design.label, sold: t.sold_units }))} dataKey="label" series={[{ name: "sold", label: "Pieces sold", color: "orange.6" }]} yAxisProps={{ width: 80 }} barProps={{ radius: 4 }} />
          ) : <Text size="sm" c="dimmed">No sales in this period.</Text>}
        </ChartCard>
      </Grid.Col>
      <Grid.Col span={12}>
        <ChartCard title="Slowest designs in stock (bottom 10)">
          <SimpleTable head={["Label", "Name", "Category", "Sold", "In stock"]} rows={(bottom.data ?? []).map((t) => [<LabelCode key="l">{t.design.label}</LabelCode>, t.design.name ?? "—", t.design.category_name, t.sold_units, t.current_stock])} />
        </ChartCard>
      </Grid.Col>
    </Grid>
  );
}

function StockTab() {
  const p = usePeriodParams();
  const { data: dash } = useDashboard();
  const bd = useReport<Breakdown>("category-breakdown", p);
  const turn = useReport<Turnover>("stock-turnover", p);
  const health = dash ? (Object.keys(dash.stock_health) as StockStatus[]).map((s) => ({ name: STATUS_META[s].label, value: dash.stock_health[s], color: STATUS_META[s].hex })) : [];
  return (
    <Grid gap="md">
      <Grid.Col span={{ base: 12, md: 8 }}>
        <ChartCard title="Stock value by category (at cost)" table={<SimpleTable head={["Category", "Pieces", "Value"]} rows={(bd.data ?? []).map((b) => [b.name, b.pieces, formatINR(b.stock_value_cost)])} />}>
          <BarChart h={280} data={bd.data ?? []} dataKey="name" series={[{ name: "stock_value_cost", label: "Stock value", color: "teal.6" }]} valueFormatter={inrC} yAxisProps={{ width: 70 }} barProps={{ radius: 6 }} />
        </ChartCard>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 4 }}>
        <ChartCard title="Stock health">
          <Group justify="center"><DonutChart size={200} thickness={28} withTooltip data={health.filter((h) => h.value > 0)} chartLabel={`${health.reduce((a, b) => a + b.value, 0)} designs`} /></Group>
        </ChartCard>
      </Grid.Col>
      <Grid.Col span={12}>
        <ChartCard title="Stock turnover by category" table={<SimpleTable head={["Category", "Opening", "Closing", "Sold", "Turnover"]} rows={(turn.data ?? []).map((t) => [t.category, t.opening, t.closing, t.sold, `${t.turnover}×`])} />}>
          <Text size="xs" c="dimmed" mb="xs">Turnover = pieces sold ÷ average stock in the period. Higher means stock moves faster.</Text>
          <BarChart h={240} data={turn.data ?? []} dataKey="category" series={[{ name: "turnover", label: "Turnover ×", color: "grape.6" }]} barProps={{ radius: 6 }} />
        </ChartCard>
      </Grid.Col>
    </Grid>
  );
}

function DeadTab() {
  const dead = useReport<Dead>("dead-stock");
  if (dead.isLoading) return <Skeleton h={300} />;
  if (!dead.data?.items.length) return <EmptyBox icon={<IconZzz size={30} />} title="No dead stock" text="Every design with stock has sold recently. 🎉" />;
  return (
    <Box>
      <Paper className="gold-border" p="lg" radius="lg" mb="md">
        <Text size="sm" c="dimmed">Money tied up in designs with no sale for {dead.data.dead_stock_days}+ days</Text>
        <Text className="serif" fw={700} fz={40}>{formatINR(dead.data.total_value, { compact: true })}</Text>
        <Text size="sm" c="dimmed">{dead.data.items.length} designs. Options: festive offers, exchange or remake, better display.</Text>
      </Paper>
      <ChartCard title="Dead stock list" exportArgs={{ report: "dead_stock" }}>
        <SimpleTable head={["Label", "Name", "Category", "Stock", "Days since sale", "Value tied up"]}
          rows={dead.data.items.map((r) => [<LabelCode key="l">{r.design.label}</LabelCode>, r.design.name ?? "—", r.design.category_name, r.current_stock, r.days_since_last_sale, <Money key="m" value={r.value_tied_up} />])} />
      </ChartCard>
    </Box>
  );
}

function CompareTab() {
  const { data: opts } = usePeriodOptions();
  const [type, setType] = useState<PeriodType>("month");
  const list = (type === "quarter" ? opts?.quarters : opts?.months) ?? [];
  const [a, setA] = useState<string | null>(null);
  const [b, setB] = useState<string | null>(null);
  const [metric, setMetric] = useState<"value" | "units">("value");
  const anchorA = a ?? list[0]?.anchor;
  const anchorB = b ?? list[1]?.anchor;
  const cmp = useReport<Compare>("period-comparison", { period_type: type, anchor_a: anchorA, anchor_b: anchorB, group_by: "category" });
  const rows = cmp.data?.rows ?? [];
  const la = cmp.data?.a.label ?? "A";
  const lb = cmp.data?.b.label ?? "B";
  const chart = rows.map((r) => ({ name: r.name, [la]: metric === "value" ? r.a_value : r.a_units, [lb]: metric === "value" ? r.b_value : r.b_units }));
  return (
    <Box>
      <Group mb="md" gap="sm" wrap="wrap">
        <PeriodPicker value={{ period_type: type, anchor: anchorA ?? null }} onChange={(v) => { setType(v.period_type); setA(v.anchor); if (v.period_type !== type) setB(null); }} />
        <Text c="dimmed">vs</Text>
        <PeriodPicker value={{ period_type: type, anchor: anchorB ?? null }} onChange={(v) => { setType(v.period_type); setB(v.anchor ?? list[0]?.anchor ?? null); }} />
        <SegmentedControl size="xs" value={metric} onChange={(v) => setMetric(v as "value" | "units")} data={[{ value: "value", label: "₹" }, { value: "units", label: "Pieces" }]} />
      </Group>
      <ChartCard title={`${la} vs ${lb}`} table={<SimpleTable head={["Category", la, lb, "Change"]} rows={rows.map((r) => [r.name, formatINR(r.a_value), formatINR(r.b_value), formatPct(r.change_pct)])} />}>
        <BarChart h={300} data={chart} dataKey="name" withLegend series={[{ name: la, color: "gold.6" }, { name: lb, color: "gray.5" }]} valueFormatter={metric === "value" ? inrC : formatNumber} yAxisProps={{ width: 70 }} barProps={{ radius: 4 }} />
      </ChartCard>
    </Box>
  );
}

export default function ReportsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "sales";
  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Charts for sales, stock and slow-moving designs. Export any of them to Excel."
        actions={<>{tab !== "compare" && tab !== "dead" && <PeriodPicker compact />}<Button variant="default" leftSection={<IconPrinter size={16} />} onClick={() => window.print()}>Print</Button></>}
      />
      <Tabs value={tab} onChange={(v) => setParams({ tab: v ?? "sales" })} keepMounted={false}>
        <Tabs.List mb="lg">
          <Tabs.Tab value="sales">Sales</Tabs.Tab>
          <Tabs.Tab value="stock">Stock</Tabs.Tab>
          <Tabs.Tab value="dead">Dead stock</Tabs.Tab>
          <Tabs.Tab value="compare">Compare periods</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="sales"><SalesTab /></Tabs.Panel>
        <Tabs.Panel value="stock"><StockTab /></Tabs.Panel>
        <Tabs.Panel value="dead"><DeadTab /></Tabs.Panel>
        <Tabs.Panel value="compare"><CompareTab /></Tabs.Panel>
      </Tabs>
    </>
  );
}
