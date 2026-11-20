import { Anchor, Badge, Box, Button, Chip, Group, Paper, Progress, ScrollArea, Select, SimpleGrid, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { BarChart } from "@mantine/charts";
import { DatePickerInput } from "@mantine/dates";
import { useDebouncedValue } from "@mantine/hooks";
import { IconDownload, IconFilterOff, IconSearch } from "@tabler/icons-react";
import dayjs from "dayjs";
import { DataTable, type DataTableColumn, type DataTableSortStatus } from "mantine-datatable";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { download } from "../api/client";
import {
  cleanQuery, useExplore, useFacets,
  type ExploreFilters, type ExploreKind, type GroupRow, type PurchaseRow, type SaleRow,
} from "../api/sales";
import { METAL_LABEL, METAL_OPTIONS } from "../lib/constants";
import { formatDayWord, formatINR, formatNumber } from "../lib/format";
import { ErrorState, LabelCode } from "./ui";

type Row = GroupRow | SaleRow | PurchaseRow;
const fmt = (d: dayjs.Dayjs) => d.format("YYYY-MM-DD");
const today = dayjs();
const PRESETS = [
  { label: "Today", value: [fmt(today), fmt(today)] as [string, string] },
  { label: "This month", value: [fmt(today.startOf("month")), fmt(today)] as [string, string] },
  { label: "Last month", value: [fmt(today.subtract(1, "month").startOf("month")), fmt(today.subtract(1, "month").endOf("month"))] as [string, string] },
  { label: "Last 3 months", value: [fmt(today.subtract(2, "month").startOf("month")), fmt(today)] as [string, string] },
  { label: "This year", value: [fmt(today.startOf("year")), fmt(today)] as [string, string] },
];

const SALES_GROUPS = [
  { value: "", label: "Every sale" }, { value: "customer", label: "Customer" }, { value: "city", label: "City" },
  { value: "state", label: "State" }, { value: "country", label: "Country" }, { value: "design", label: "Design" },
  { value: "category", label: "Category" }, { value: "metal", label: "Material" }, { value: "month", label: "Month" },
  { value: "payment_mode", label: "Payment" },
];
const PURCHASE_GROUPS = [
  { value: "", label: "Every purchase" }, { value: "dealer", label: "Dealer" }, { value: "dealer_city", label: "Dealer city" },
  { value: "design", label: "Design" }, { value: "category", label: "Category" }, { value: "metal", label: "Material" },
  { value: "month", label: "Month" },
];
// clicking a grouped row filters to it and shows the next useful breakdown
const DRILL: Record<string, string> = {
  customer: "design", city: "customer", state: "city", country: "state", design: "customer", category: "design",
  metal: "category", month: "design", payment_mode: "customer", dealer: "design", dealer_city: "dealer",
};

export function Explorer({ kind, initialGroup = "", initialRange = "This month" }: {
  kind: ExploreKind; initialGroup?: string; initialRange?: string | null;
}) {
  const sales = kind === "sales";
  const { data: facets } = useFacets();
  const preset = PRESETS.find((p) => p.label === initialRange);
  const [range, setRange] = useState<[string | null, string | null]>(preset ? preset.value : [null, null]);
  const [f, setF] = useState<ExploreFilters>({});
  const [label, setLabel] = useState("");
  const [debounced] = useDebouncedValue(label, 300);
  const [group, setGroup] = useState(initialGroup);
  const [sort, setSort] = useState<DataTableSortStatus<Row>>({ columnAccessor: initialGroup ? "value" : "date", direction: "desc" });
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const params = useMemo(() => cleanQuery({
    ...f, label: debounced || undefined, date_from: range[0] ?? undefined, date_to: range[1] ?? undefined,
    group_by: group || undefined, sort_by: String(sort.columnAccessor), sort_dir: sort.direction, page, page_size: pageSize,
  }), [f, debounced, range, group, sort, page]);
  useEffect(() => setPage(1), [f, debounced, range, group]);
  const { data, isFetching, isError, refetch } = useExplore(kind, params);

  const setFilter = (k: keyof ExploreFilters) => (v: string | null) => setF((x) => ({ ...x, [k]: v ?? undefined }));
  const changeGroup = (g: string) => {
    setGroup(g);
    setSort({ columnAccessor: g && g !== "month" ? "value" : g === "month" ? "label" : "date", direction: g === "month" ? "asc" : "desc" });
  };
  const activeFilters = Object.values(f).filter(Boolean).length + (debounced ? 1 : 0);

  const drill = (r: GroupRow) => {
    const next = { ...f };
    const map: Record<string, keyof ExploreFilters> = {
      customer: "customer_id", city: "city", state: "state", country: "country", metal: "metal", payment_mode: "payment_mode",
      dealer: "dealer_id", dealer_city: "dealer_city",
    };
    if (group === "customer" && r.key === "0") next.walk_in = true;
    else if (group === "dealer" && r.key === "0") next.no_dealer = true;
    else if (map[group]) (next as Record<string, unknown>)[map[group]] = group === "customer" || group === "dealer" ? r.key : r.key === "Not set" ? undefined : r.key;
    else if (group === "category") next.category_id = facets?.categories.find((c) => c.label === r.label)?.value;
    else if (group === "design") setLabel(r.label);
    else if (group === "month") {
      const m = dayjs(`${r.key}-01`);
      setRange([fmt(m.startOf("month")), fmt(m.endOf("month"))]);
    }
    setF(next);
    changeGroup(DRILL[group] ?? "");
  };

  const t = data?.totals;
  const maxShare = Math.max(1, ...((data?.items ?? []) as GroupRow[]).map((x) => x.share_pct ?? 0));
  const vName = sales ? "Revenue" : "Amount";
  const stats = sales
    ? [{ l: "Revenue", v: formatINR(t?.value ?? 0, { compact: true }) }, { l: "Pieces sold", v: formatNumber(t?.qty ?? 0) },
       { l: "Bills", v: formatNumber(t?.bills ?? 0) }, { l: "Customers", v: formatNumber(t?.customers ?? 0) }]
    : [{ l: "Bought for", v: formatINR(t?.value ?? 0, { compact: true }) }, { l: "Pieces", v: formatNumber(t?.qty ?? 0) },
       { l: "Dealers", v: formatNumber(t?.dealers ?? 0) }, { l: "Designs", v: formatNumber(t?.designs ?? 0) }];

  const groupCols: DataTableColumn<Row>[] = [
    {
      accessor: "label", title: data?.group_label ?? "", sortable: true,
      render: (r) => {
        const g = r as GroupRow;
        return (
          <Box>
            {group === "design" ? <LabelCode>{g.label}</LabelCode> : <Text size="sm" fw={600}>{group === "metal" ? METAL_LABEL[g.label] ?? g.label : g.label}</Text>}
            {g.sub && <Text size="xs" c="dimmed">{g.sub}</Text>}
          </Box>
        );
      },
    },
    { accessor: "qty", title: "Pieces", textAlign: "right", sortable: true, render: (r) => <Text size="sm" className="num">{formatNumber((r as GroupRow).qty)}</Text> },
    { accessor: "value", title: vName, textAlign: "right", sortable: true, render: (r) => <Text size="sm" fw={700} className="num">{formatINR((r as GroupRow).value, { compact: true })}</Text> },
    {
      accessor: "share_pct", title: "Share", sortable: true, width: 150,
      render: (r) => (
        <Group gap={6} wrap="nowrap">
          <Progress value={((r as GroupRow).share_pct / maxShare) * 100} w={70} color="gold" size="sm" />
          <Text size="xs" c="dimmed" className="num">{(r as GroupRow).share_pct}%</Text>
        </Group>
      ),
    },
    { accessor: "avg_price", title: sales ? "Avg price" : "Avg cost", textAlign: "right", sortable: true, render: (r) => <Text size="sm" className="num">{formatINR((r as GroupRow).avg_price, { compact: true })}</Text> },
    ...(sales
      ? [{ accessor: "bills", title: "Bills", textAlign: "right", sortable: true } as DataTableColumn<Row>,
         ...(group !== "customer" ? [{ accessor: "customers", title: "Customers", textAlign: "right", sortable: true } as DataTableColumn<Row>] : [])]
      : [{ accessor: "entries", title: "Deliveries", textAlign: "right", sortable: true } as DataTableColumn<Row>,
         ...(group !== "design" ? [{ accessor: "designs", title: "Designs", textAlign: "right", sortable: true } as DataTableColumn<Row>] : [])]),
  ];

  const designCell = (r: SaleRow | PurchaseRow) => (
    <Box>
      <Anchor component={Link} to={`/app/designs/${r.design_id}`}><LabelCode>{r.design}</LabelCode></Anchor>
      <Text size="xs" c="dimmed" truncate maw={150}>{r.design_name ?? r.category}</Text>
    </Box>
  );
  const saleCols: DataTableColumn<Row>[] = [
    { accessor: "date", title: "Date", sortable: true, render: (r) => <Text size="sm">{formatDayWord((r as SaleRow).date)}</Text> },
    {
      accessor: "bill_number", title: "Bill", sortable: true,
      render: (r) => ((r as SaleRow).bill_id ? <Anchor component={Link} size="sm" to={`/app/sales/bills/${(r as SaleRow).bill_id}`}>{(r as SaleRow).bill_number}</Anchor> : <Text size="sm" c="dimmed">—</Text>),
    },
    { accessor: "customer", title: "Customer", sortable: true },
    { accessor: "city", title: "City", sortable: true },
    { accessor: "state", title: "State", sortable: true },
    { accessor: "country", title: "Country", sortable: true },
    { accessor: "design", title: "Design", sortable: true, render: (r) => designCell(r as SaleRow) },
    { accessor: "category", title: "Category", sortable: true },
    { accessor: "metal", title: "Material", sortable: true, render: (r) => METAL_LABEL[(r as SaleRow).metal] ?? (r as SaleRow).metal },
    { accessor: "qty", title: "Pcs", textAlign: "right", sortable: true },
    { accessor: "unit_price", title: "Price", textAlign: "right", sortable: true, render: (r) => <Text size="sm" className="num">{formatINR((r as SaleRow).unit_price)}</Text> },
    { accessor: "revenue", title: "Revenue", textAlign: "right", sortable: true, render: (r) => <Text size="sm" fw={700} className="num">{formatINR((r as SaleRow).revenue)}</Text> },
  ];
  const purchaseCols: DataTableColumn<Row>[] = [
    { accessor: "date", title: "Date", sortable: true, render: (r) => <Text size="sm">{formatDayWord((r as PurchaseRow).date)}</Text> },
    { accessor: "type", title: "Type", sortable: true, render: (r) => <Badge variant="light" color={(r as PurchaseRow).type === "Purchase" ? "teal" : "gray"} size="sm">{(r as PurchaseRow).type}</Badge> },
    { accessor: "dealer", title: "Dealer", sortable: true },
    { accessor: "dealer_city", title: "Dealer city", sortable: true },
    { accessor: "design", title: "Design", sortable: true, render: (r) => designCell(r as PurchaseRow) },
    { accessor: "category", title: "Category", sortable: true },
    { accessor: "metal", title: "Material", sortable: true, render: (r) => METAL_LABEL[(r as PurchaseRow).metal] ?? (r as PurchaseRow).metal },
    { accessor: "qty", title: "Pcs", textAlign: "right", sortable: true },
    { accessor: "unit_cost", title: "Cost / pc", textAlign: "right", sortable: true, render: (r) => <Text size="sm" className="num">{formatINR((r as PurchaseRow).unit_cost)}</Text> },
    { accessor: "amount", title: "Amount", textAlign: "right", sortable: true, render: (r) => <Text size="sm" fw={700} className="num">{formatINR((r as PurchaseRow).amount)}</Text> },
  ];

  const groups = sales ? SALES_GROUPS : PURCHASE_GROUPS;
  const sel = (k: keyof ExploreFilters, placeholder: string, opts: (string | { value: string; label: string })[] | undefined, w = 150) => (
    <Select key={k} size="xs" w={w} placeholder={placeholder} data={opts ?? []} value={(f[k] as string) ?? null} onChange={setFilter(k)} clearable searchable />
  );

  return (
    <Stack gap="sm">
      <Paper className="soft-card" p="sm" radius="md">
        <Group gap="xs" wrap="wrap">
          <DatePickerInput
            size="xs" type="range" w={230} placeholder="All time" clearable valueFormat="D MMM YYYY" presets={PRESETS}
            value={range} onChange={(v) => setRange([v[0] ? fmt(dayjs(v[0])) : null, v[1] ? fmt(dayjs(v[1])) : null])}
          />
          {sales ? (
            <>
              {sel("country", "Country", facets?.countries, 140)}
              {sel("state", "State", facets?.states, 140)}
              {sel("city", "City", facets?.cities, 130)}
              {sel("customer_id", "Customer", facets?.customers, 190)}
              {sel("payment_mode", "Payment", facets?.payment_modes, 120)}
            </>
          ) : (
            <>
              {sel("dealer_id", "Dealer", facets?.dealers, 190)}
              {sel("dealer_city", "Dealer city", facets?.dealer_cities, 140)}
            </>
          )}
          {sel("category_id", "Category", facets?.categories, 150)}
          {sel("metal", "Material", METAL_OPTIONS, 140)}
          <TextInput size="xs" w={120} leftSection={<IconSearch size={14} />} placeholder="Design" value={label} onChange={(e) => setLabel(e.currentTarget.value)} />
          {(activeFilters > 0 || f.walk_in || f.no_dealer) && (
            <Button size="xs" variant="subtle" color="gray" leftSection={<IconFilterOff size={14} />} onClick={() => { setF({}); setLabel(""); }}>
              Clear
            </Button>
          )}
          <Box style={{ flex: 1 }} />
          <Tooltip label="Download exactly what you see as Excel">
            <Button size="xs" variant="default" leftSection={<IconDownload size={14} />} onClick={() => download(`/explore/${kind}/export`, { ...params, page: undefined, page_size: undefined })}>
              Excel
            </Button>
          </Tooltip>
        </Group>
        <ScrollArea type="never" mt="xs">
          <Group gap={6} wrap="nowrap">
            <Text size="xs" c="dimmed" fw={600}>Group by</Text>
            <Chip.Group value={group} onChange={(v) => changeGroup(v as string)}>
              {groups.map((g) => <Chip key={g.value} value={g.value} size="xs" variant="light">{g.label}</Chip>)}
            </Chip.Group>
          </Group>
        </ScrollArea>
      </Paper>

      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        {stats.map((s, i) => (
          <Paper key={s.l} p="sm" radius="md" className={i === 0 ? "gold-border" : "soft-card"}>
            <Text size="xs" c="dimmed">{s.l}</Text>
            <Text fw={800} fz="xl" className="num">{s.v}</Text>
          </Paper>
        ))}
      </SimpleGrid>

      {group && data && data.chart.length > 1 && (
        <Paper className="soft-card" p="md" radius="md">
          <Text size="sm" fw={600} mb="xs">{vName} by {data.group_label?.toLowerCase()}</Text>
          <BarChart
            h={group === "month" ? 200 : Math.min(40 + data.chart.length * 28, 380)}
            data={data.chart.map((c) => ({ name: group === "metal" ? METAL_LABEL[c.label] ?? c.label : c.label, value: c.value }))}
            dataKey="name"
            orientation={group === "month" ? "horizontal" : "vertical"}
            yAxisProps={group === "month" ? undefined : { width: 130 }}
            series={[{ name: "value", color: "gold.6", label: vName }]}
            valueFormatter={(v) => formatINR(v, { compact: true })}
            gridAxis="none"
            withTooltip
          />
        </Paper>
      )}

      {isError && <ErrorState onRetry={() => refetch()} />}
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<Row>
          minHeight={180}
          fetching={isFetching}
          records={data?.items ?? []}
          idAccessor={(r) => ("key" in r ? `${r.key}` : String(r.id))}
          columns={group ? groupCols : sales ? saleCols : purchaseCols}
          sortStatus={sort}
          onSortStatusChange={setSort}
          totalRecords={data?.total ?? 0}
          recordsPerPage={pageSize}
          page={page}
          onPageChange={setPage}
          striped
          highlightOnHover
          defaultColumnProps={{ noWrap: true }}
          onRowClick={group ? ({ record }) => drill(record as GroupRow) : undefined}
          rowStyle={() => (group ? { cursor: "pointer" } : undefined)}
          noRecordsText={sales ? "No sales match these filters" : "No purchases match these filters"}
        />
      </Box>
      {group && <Text size="xs" c="dimmed">Tip: click a row to see what's inside it.</Text>}
    </Stack>
  );
}
