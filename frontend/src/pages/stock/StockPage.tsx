import { Anchor, Badge, Box, Button, Grid, Group, MultiSelect, Paper, SegmentedControl, Select, SimpleGrid, Stack, Switch, Tabs, Text, TextInput, Tooltip } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconArrowBackUp, IconDownload, IconHistory, IconListDetails, IconPlusMinus, IconSearch } from "@tabler/icons-react";
import dayjs from "dayjs";
import { DataTable, type DataTableSortStatus } from "mantine-datatable";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { download, errorMessage } from "../../api/client";
import { useCategories, useMovements, usePeriodParams, usePeriodStock, useStockToday, useVoidMovement } from "../../api/hooks";
import type { Movement, PeriodRow } from "../../api/types";
import { PeriodPicker } from "../../components/PeriodPicker";
import { Explorer } from "../../components/Explorer";
import { QuickEntryPanel } from "../../components/stock";
import { useFacets } from "../../api/sales";
import { ErrorState, LabelCode, Money, PageHeader, PhotoThumb, SectionCard, StatusBadge } from "../../components/ui";
import { MOVEMENT_META } from "../../lib/constants";
import { formatDayWord, formatINR, formatNumber, formatRelative } from "../../lib/format";

function UndoButton({ m }: { m: Movement }) {
  const voidMv = useVoidMovement();
  if (m.is_void) return <Badge color="gray" variant="light" size="xs">Undone</Badge>;
  return (
    <Tooltip label="Undo this entry">
      <Button
        size="compact-xs"
        variant="subtle"
        color="gray"
        leftSection={<IconArrowBackUp size={12} />}
        loading={voidMv.isPending}
        onClick={(e) => {
          e.stopPropagation();
          voidMv.mutateAsync({ id: m.id, reason: "Undo" })
            .then(() => notifications.show({ message: `Undone: ${m.design.label}` }))
            .catch((err) => notifications.show({ color: "red", message: errorMessage(err) }));
        }}
      >
        Undo
      </Button>
    </Tooltip>
  );
}

function MovementLine({ m }: { m: Movement }) {
  const meta = MOVEMENT_META[m.type];
  const I = meta.icon;
  return (
    <Group justify="space-between" wrap="nowrap" py={6} style={{ borderBottom: "1px solid var(--jaa-border)", opacity: m.is_void ? 0.55 : 1 }}>
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Box c={`${meta.color}.7`}>
          <I size={18} />
        </Box>
        <Box style={{ minWidth: 0 }}>
          <Text size="sm" td={m.is_void ? "line-through" : undefined} truncate>
            {meta.short} <b>{m.direction === "IN" ? "+" : "−"}{m.quantity}</b> · <LabelCode>{m.design.label}</LabelCode>
          </Text>
          <Text size="xs" c="dimmed">
            {formatRelative(m.created_at)}
            {m.value ? ` · ${formatINR(m.value)}` : ""}
          </Text>
        </Box>
      </Group>
      <UndoButton m={m} />
    </Group>
  );
}

function QuickTab() {
  const { data: today } = useStockToday();
  const [params] = useSearchParams();
  const mode = params.get("mode") === "IN" ? "IN" : "OUT";
  const designId = Number(params.get("design")) || null;
  return (
    <Grid gap="lg">
      <Grid.Col span={{ base: 12, md: 7 }}>
        <SectionCard title="Record stock" icon={<IconPlusMinus size={18} />}>
          <QuickEntryPanel initialMode={mode} initialDesignId={designId} />
        </SectionCard>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 5 }}>
        <SectionCard title="Today's entries" icon={<IconHistory size={18} />}>
          <SimpleGrid cols={3} mb="md">
            <Paper p="sm" radius="md" withBorder>
              <Text size="xs" c="dimmed">Sold</Text>
              <Text fw={700} className="num">{today?.totals.sold_units ?? 0} pcs</Text>
            </Paper>
            <Paper p="sm" radius="md" withBorder>
              <Text size="xs" c="dimmed">Sales</Text>
              <Text fw={700}><Money value={today?.totals.sold_value ?? 0} compact /></Text>
            </Paper>
            <Paper p="sm" radius="md" withBorder>
              <Text size="xs" c="dimmed">Received</Text>
              <Text fw={700} className="num">{today?.totals.received_units ?? 0} pcs</Text>
            </Paper>
          </SimpleGrid>
          {today?.entries.length ? (
            <Stack gap={0}>
              {today.entries.map((m) => <MovementLine key={m.id} m={m} />)}
            </Stack>
          ) : (
            <Text size="sm" c="dimmed">Nothing recorded by you today yet.</Text>
          )}
        </SectionCard>
      </Grid.Col>
    </Grid>
  );
}

const TYPE_OPTS = Object.entries(MOVEMENT_META).map(([v, m]) => ({ value: v, label: m.label }));

function HistoryTab() {
  const { data: cats } = useCategories();
  const [label, setLabel] = useState("");
  const [debounced] = useDebouncedValue(label, 250);
  const [types, setTypes] = useState<string[]>([]);
  const [cat, setCat] = useState<string | null>(null);
  const [range, setRange] = useState<[string | null, string | null]>([null, null]);
  const [showVoid, setShowVoid] = useState(true);
  const [customer, setCustomer] = useState<string | null>(null);
  const [dealer, setDealer] = useState<string | null>(null);
  const { data: facets } = useFacets();
  const [page, setPage] = useState(1);
  const [hSort, setHSort] = useState<DataTableSortStatus<Movement>>({ columnAccessor: "occurred_on", direction: "desc" });
  useEffect(() => setPage(1), [debounced, types, cat, range, showVoid, customer, dealer, hSort]);
  const { data, isLoading, isError, refetch } = useMovements({
    sort_by: String(hSort.columnAccessor), sort_dir: hSort.direction,
    label: debounced || undefined, type: types.join(",") || undefined, category_id: cat ?? undefined,
    date_from: range[0] ?? undefined, date_to: range[1] ?? undefined, include_void: showVoid, page, page_size: 25,
    customer_id: customer ?? undefined, dealer_id: dealer ?? undefined,
  });
  return (
    <Stack>
      <Group gap="sm" wrap="wrap">
        <TextInput leftSection={<IconSearch size={16} />} placeholder="Label" value={label} onChange={(e) => setLabel(e.currentTarget.value)} w={160} />
        <MultiSelect data={TYPE_OPTS} value={types} onChange={setTypes} placeholder={types.length ? undefined : "Type"} clearable w={260} />
        <Select data={(cats ?? []).map((c) => ({ value: String(c.id), label: c.name }))} value={cat} onChange={setCat} placeholder="Category" clearable w={170} />
        <Select data={facets?.customers ?? []} value={customer} onChange={setCustomer} placeholder="Customer" clearable searchable w={190} />
        <Select data={facets?.dealers ?? []} value={dealer} onChange={setDealer} placeholder="Dealer" clearable searchable w={180} />
        <DatePickerInput type="range" value={range} onChange={(v) => setRange([v[0] ? dayjs(v[0]).format("YYYY-MM-DD") : null, v[1] ? dayjs(v[1]).format("YYYY-MM-DD") : null])} placeholder="Date range" clearable w={240} valueFormat="D MMM YYYY" />
        <Switch label="Show undone" checked={showVoid} onChange={(e) => setShowVoid(e.currentTarget.checked)} />
      </Group>
      {isError && <ErrorState onRetry={() => refetch()} />}
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<Movement>
          minHeight={200}
          fetching={isLoading}
          records={data?.items ?? []}
          totalRecords={data?.total ?? 0}
          recordsPerPage={25}
          page={page}
          onPageChange={setPage}
          rowStyle={(m) => (m.is_void ? { opacity: 0.5 } : undefined)}
          sortStatus={hSort}
          onSortStatusChange={setHSort}
          columns={[
            { accessor: "occurred_on", title: "Date", sortable: true, render: (m) => <Text size="sm">{formatDayWord(m.occurred_on)}</Text> },
            {
              accessor: "type", title: "Type", sortable: true,
              render: (m) => {
                const meta = MOVEMENT_META[m.type];
                return <Badge color={meta.color} variant="light" leftSection={<meta.icon size={12} />}>{meta.label}</Badge>;
              },
            },
            {
              accessor: "design", title: "Design", sortable: true,
              render: (m) => (
                <Group gap="xs" wrap="nowrap">
                  <PhotoThumb url={m.design.photo_url} size={28} />
                  <Box>
                    <LabelCode>{m.design.label}</LabelCode>
                    <Text size="xs" c="dimmed" truncate maw={160}>{m.design.name}</Text>
                  </Box>
                </Group>
              ),
            },
            {
              accessor: "quantity", title: "Qty", textAlign: "right", sortable: true,
              render: (m) => <Text fw={700} c={m.direction === "IN" ? "teal.7" : "red.7"} className="num" td={m.is_void ? "line-through" : undefined}>{m.direction === "IN" ? "+" : "−"}{m.quantity}</Text>,
            },
            { accessor: "value", title: "Value", textAlign: "right", sortable: true, render: (m) => (m.value ? <Money value={m.value} /> : "—") },
            {
              accessor: "party", title: "From / to", sortable: true,
              render: (m) => (m.bill ? (
                <Box>
                  <Text size="sm">{m.bill.customer_name}</Text>
                  <Anchor component={Link} to={`/app/sales/bills/${m.bill.id}`} size="xs" onClick={(e) => e.stopPropagation()}>{m.bill.number}</Anchor>
                </Box>
              ) : m.dealer ? <Text size="sm">{m.dealer.name}</Text> : <Text size="sm" c="dimmed">—</Text>),
            },
            { accessor: "created_by", title: "By", render: (m) => <Text size="sm">{m.created_by?.display_name ?? "System"}</Text> },
            { accessor: "note", title: "Note", render: (m) => <Text size="xs" c="dimmed" truncate maw={160}>{m.note ?? ""}</Text> },
            { accessor: "actions", title: "", render: (m) => <UndoButton m={m} /> },
          ]}
          noRecordsText="No entries"
        />
      </Box>
    </Stack>
  );
}

function PeriodTab() {
  const p = usePeriodParams();
  const { data: cats } = useCategories();
  const [cat, setCat] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 250);
  const [customer, setCustomer] = useState<string | null>(null);
  const [dealer, setDealer] = useState<string | null>(null);
  const { data: facets } = useFacets();
  const [page, setPage] = useState(1);
  const [view, setView] = useState("designs");
  const [sort, setSort] = useState<DataTableSortStatus<PeriodRow>>({ columnAccessor: "design.label", direction: "asc" });
  const sortField = ({ "design.label": "label", "design.category_name": "category" } as Record<string, string>)[String(sort.columnAccessor)] ?? String(sort.columnAccessor);
  const sortParam = `${sort.direction === "desc" ? "-" : ""}${sortField}`;
  useEffect(() => setPage(1), [debounced, cat, status, p.period_type, p.anchor, customer, dealer, sortParam]);
  const params = { ...p, category_id: cat ?? undefined, status: status ?? undefined, search: debounced || undefined, page, page_size: 50,
    customer_id: customer ?? undefined, dealer_id: dealer ?? undefined, sort: sortParam };
  const applyPreset = (v: string | null) => {
    if (!v) return;
    const desc = v.startsWith("-");
    const field = v.replace(/^-/, "");
    setSort({ columnAccessor: ({ label: "design.label", category: "design.category_name" } as Record<string, string>)[field] ?? field, direction: desc ? "desc" : "asc" });
  };
  const { data, isLoading, isError, refetch } = usePeriodStock(params);
  const t = data?.totals;
  const sum: { l: string; v: number | string; c?: string; money?: boolean; bold?: boolean; sub?: string }[] = [
    { l: "Sold", v: t?.sold ?? 0, c: "red.7" }, { l: "Stock at end", v: t?.closing ?? 0, bold: true },
    { l: "Net revenue", v: t?.net_revenue ?? 0, money: true },
    { l: "Net profit", v: t?.net_profit ?? 0, money: true, bold: true, c: (t?.net_profit ?? 0) < 0 ? "red.7" : "teal.8" },
    { l: "Top customer", v: data?.top_customer?.name ?? "—", sub: data?.top_customer ? formatINR(data.top_customer.revenue, { compact: true }) : undefined },
    { l: "Top dealer", v: data?.top_dealer?.name ?? "—", sub: data?.top_dealer ? formatINR(data.top_dealer.amount, { compact: true }) : undefined },
  ];
  return (
    <Stack>
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="sm" wrap="wrap">
          <PeriodPicker />
          <Select data={(cats ?? []).map((c) => ({ value: String(c.id), label: c.name }))} value={cat} onChange={setCat} placeholder="All categories" clearable w={170} />
          <Select data={[{ value: "OUT", label: "Sold out" }, { value: "LOW", label: "Low" }, { value: "IN", label: "In stock" }, { value: "DEAD", label: "Not selling" }]} value={status} onChange={setStatus} placeholder="Any status" clearable w={150} />
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Label" value={search} onChange={(e) => setSearch(e.currentTarget.value)} w={150} />
          <Select data={facets?.dealers ?? []} value={dealer} onChange={setDealer} placeholder="Dealer" clearable searchable w={180} />
          <Select data={facets?.customers ?? []} value={customer} onChange={setCustomer} placeholder="Customer" clearable searchable w={190} />
        </Group>
        <Button variant="default" leftSection={<IconDownload size={16} />} onClick={() => download("/reports/export", { report: "period_stock", ...p, category_id: cat ?? undefined, status: status ?? undefined })}>
          Export Excel
        </Button>
      </Group>
      {data && (
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Text size="sm" c="dimmed">
            {data.period.label}
            {data.period.is_current ? " (so far)" : ""} · Sales <b>{formatINR(t?.sales_value ?? 0)}</b>
          </Text>
          <SegmentedControl size="xs" value={view} onChange={setView}
            data={[{ value: "designs", label: "Designs" }, { value: "dealers", label: "Dealers" }, { value: "customers", label: "Customers" }]} />
        </Group>
      )}
      <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }}>
        {sum.map((s) => (
          <Paper key={s.l} p="sm" radius="md" className={s.money ? "gold-border" : "soft-card"}>
            <Text size="xs" c="dimmed">{s.l}</Text>
            {typeof s.v === "string" ? (
              <>
                <Text fw={700} fz="md" truncate>{s.v}</Text>
                {s.sub && <Text size="xs" c="dimmed" className="num">{s.sub}</Text>}
              </>
            ) : (
              <Text fw={s.bold ? 800 : 700} fz={s.bold ? "xl" : "lg"} c={s.c} className="num">{s.money ? formatINR(s.v, { compact: true }) : formatNumber(s.v)}</Text>
            )}
          </Paper>
        ))}
      </SimpleGrid>
      {isError && <ErrorState onRetry={() => refetch()} />}
      {view === "dealers" && data && (
        <Explorer kind="purchases" initialGroup="dealer" lockGroup fixedRange={[data.period.start, data.period.effective_end]} />
      )}
      {view === "customers" && data && (
        <Explorer kind="sales" initialGroup="customer" lockGroup fixedRange={[data.period.start, data.period.effective_end]} />
      )}
      {view === "designs" && (
      <Group gap="xs">
        <Text size="sm" c="dimmed">Sort</Text>
        <Select size="xs" w={200} value={SORT_PRESETS.find((s) => s.value === sortParam)?.value ?? null} onChange={applyPreset}
          placeholder="Click a column, or pick…" data={SORT_PRESETS} />
      </Group>
      )}
      {view === "designs" && (
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<PeriodRow>
          sortStatus={sort}
          onSortStatusChange={setSort}
          minHeight={200}
          fetching={isLoading}
          records={data?.rows.items ?? []}
          idAccessor={(r) => r.design.id}
          totalRecords={data?.rows.total ?? 0}
          recordsPerPage={50}
          page={page}
          onPageChange={setPage}
          striped
          columns={[
            {
              accessor: "design.label", title: "Label", sortable: true,
              render: (r) => (
                <Box>
                  <LabelCode>{r.design.label}</LabelCode>
                  <Text size="xs" c="dimmed" truncate maw={160}>{r.design.name}</Text>
                </Box>
              ),
            },
            { accessor: "design.category_name", title: "Category", sortable: true },
            { accessor: "opening", title: "Opening", textAlign: "right", sortable: true, render: (r) => <N v={r.opening + r.opening_added} /> },
            { accessor: "received", title: "Received", textAlign: "right", sortable: true, render: (r) => <N v={r.received} /> },
            { accessor: "sold", title: "Sold", textAlign: "right", sortable: true, render: (r) => <N v={r.sold} /> },
            { accessor: "closing", title: "Closing", textAlign: "right", sortable: true, render: (r) => <Text fw={800} className="num">{r.closing}</Text> },
            { accessor: "net_revenue", title: "Net revenue", textAlign: "right", sortable: true, render: (r) => <Text size="sm" className="num" c={r.net_revenue ? undefined : "dimmed"}>{r.net_revenue ? formatINR(r.net_revenue, { compact: true }) : "—"}</Text> },
            {
              accessor: "net_profit", title: "Net profit", textAlign: "right", sortable: true,
              render: (r) => (r.net_revenue || r.net_profit ? (
                <Tooltip label={r.margin_pct === null ? "" : `Margin ${r.margin_pct}%`} disabled={r.margin_pct === null}>
                  <Text size="sm" fw={700} className="num" c={r.net_profit < 0 ? "red.7" : "teal.8"}>{formatINR(r.net_profit, { compact: true })}</Text>
                </Tooltip>
              ) : <Text size="sm" c="dimmed">—</Text>),
            },
            { accessor: "dealer", title: "Dealer", sortable: true, render: (r) => <Text size="sm" truncate maw={150}>{r.dealer ?? "—"}</Text> },
            {
              accessor: "top_customer", title: "Sold to", sortable: true,
              render: (r) => (r.customers ? (
                <Tooltip label={`${r.customers} customer${r.customers > 1 ? "s" : ""} this period`}>
                  <Text size="sm" truncate maw={150}>{r.top_customer}{r.customers > 1 ? ` +${r.customers - 1}` : ""}</Text>
                </Tooltip>
              ) : <Text size="sm" c="dimmed">—</Text>),
            },
            { accessor: "status_now", title: "Status now", sortable: true, render: (r) => <StatusBadge status={r.status_now} size="xs" /> },
          ]}
          noRecordsText="No designs"
        />
      </Box>
      )}
    </Stack>
  );
}

const SORT_PRESETS = [
  { value: "-net_profit", label: "Most profit first" }, { value: "net_profit", label: "Least profit first" },
  { value: "-net_revenue", label: "Most revenue first" }, { value: "-sold", label: "Most sold first" },
  { value: "sold", label: "Least sold first" }, { value: "-closing", label: "Most stock left" },
  { value: "closing", label: "Least stock left" }, { value: "-received", label: "Most received" },
  { value: "-customers", label: "Most customers" }, { value: "dealer", label: "Dealer A–Z" }, { value: "label", label: "Label A–Z" },
];

function N({ v }: { v: number }) {
  return <Text size="sm" className="num" c={v === 0 ? "dimmed" : undefined}>{v}</Text>;
}

export default function StockPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "quick";
  return (
    <>
      <PageHeader title="Stock" subtitle="Add new stock, record sales, see history." />
      <Tabs value={tab} onChange={(v) => setParams({ tab: v ?? "quick" })} keepMounted={false}>
        <Tabs.List mb="lg">
          <Tabs.Tab value="quick" leftSection={<IconPlusMinus size={16} />}>Record</Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>History</Tabs.Tab>
          <Tabs.Tab value="period" leftSection={<IconListDetails size={16} />}>By period</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="quick"><QuickTab /></Tabs.Panel>
        <Tabs.Panel value="history"><HistoryTab /></Tabs.Panel>
        <Tabs.Panel value="period"><PeriodTab /></Tabs.Panel>
      </Tabs>
    </>
  );
}
