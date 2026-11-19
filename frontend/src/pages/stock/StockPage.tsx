import { Badge, Box, Button, Grid, Group, MultiSelect, Paper, Select, SimpleGrid, Stack, Switch, Tabs, Text, TextInput, Tooltip } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconArrowBackUp, IconDownload, IconHistory, IconListDetails, IconPlusMinus, IconSearch } from "@tabler/icons-react";
import dayjs from "dayjs";
import { DataTable } from "mantine-datatable";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { download, errorMessage } from "../../api/client";
import { useCategories, useMovements, usePeriodParams, usePeriodStock, useStockToday, useVoidMovement } from "../../api/hooks";
import type { Movement, PeriodRow } from "../../api/types";
import { PeriodPicker } from "../../components/PeriodPicker";
import { QuickEntryPanel } from "../../components/stock";
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
  return (
    <Grid gap="lg">
      <Grid.Col span={{ base: 12, md: 7 }}>
        <SectionCard title="Record stock" icon={<IconPlusMinus size={18} />}>
          <QuickEntryPanel />
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
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [debounced, types, cat, range, showVoid]);
  const { data, isLoading, isError, refetch } = useMovements({
    label: debounced || undefined, type: types.join(",") || undefined, category_id: cat ?? undefined,
    date_from: range[0] ?? undefined, date_to: range[1] ?? undefined, include_void: showVoid, page, page_size: 25,
  });
  return (
    <Stack>
      <Group gap="sm" wrap="wrap">
        <TextInput leftSection={<IconSearch size={16} />} placeholder="Label" value={label} onChange={(e) => setLabel(e.currentTarget.value)} w={160} />
        <MultiSelect data={TYPE_OPTS} value={types} onChange={setTypes} placeholder={types.length ? undefined : "Type"} clearable w={260} />
        <Select data={(cats ?? []).map((c) => ({ value: String(c.id), label: c.name }))} value={cat} onChange={setCat} placeholder="Category" clearable w={170} />
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
          columns={[
            { accessor: "occurred_on", title: "Date", render: (m) => <Text size="sm">{formatDayWord(m.occurred_on)}</Text> },
            {
              accessor: "type", title: "Type",
              render: (m) => {
                const meta = MOVEMENT_META[m.type];
                return <Badge color={meta.color} variant="light" leftSection={<meta.icon size={12} />}>{meta.label}</Badge>;
              },
            },
            {
              accessor: "design", title: "Design",
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
              accessor: "quantity", title: "Qty", textAlign: "right",
              render: (m) => <Text fw={700} c={m.direction === "IN" ? "teal.7" : "red.7"} className="num" td={m.is_void ? "line-through" : undefined}>{m.direction === "IN" ? "+" : "−"}{m.quantity}</Text>,
            },
            { accessor: "value", title: "Value", textAlign: "right", render: (m) => (m.value ? <Money value={m.value} /> : "—") },
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
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [debounced, cat, status, p.period_type, p.anchor]);
  const params = { ...p, category_id: cat ?? undefined, status: status ?? undefined, search: debounced || undefined, page, page_size: 50 };
  const { data, isLoading, isError, refetch } = usePeriodStock(params);
  const t = data?.totals;
  const sum = [
    { l: "Opening", v: t ? t.opening + t.opening_added : 0 }, { l: "Received", v: t?.received ?? 0, c: "teal.7" },
    { l: "Sold", v: t?.sold ?? 0, c: "red.7" }, { l: "Returns", v: (t?.customer_returns ?? 0) - (t?.supplier_returns ?? 0) },
    { l: "Corrections", v: t?.adjustments_net ?? 0 }, { l: "Closing", v: t?.closing ?? 0, bold: true },
  ];
  return (
    <Stack>
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="sm" wrap="wrap">
          <PeriodPicker />
          <Select data={(cats ?? []).map((c) => ({ value: String(c.id), label: c.name }))} value={cat} onChange={setCat} placeholder="All categories" clearable w={170} />
          <Select data={[{ value: "OUT", label: "Sold out" }, { value: "LOW", label: "Low" }, { value: "IN", label: "In stock" }, { value: "DEAD", label: "Not selling" }]} value={status} onChange={setStatus} placeholder="Any status" clearable w={150} />
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Label" value={search} onChange={(e) => setSearch(e.currentTarget.value)} w={150} />
        </Group>
        <Button variant="default" leftSection={<IconDownload size={16} />} onClick={() => download("/reports/export", { report: "period_stock", ...p, category_id: cat ?? undefined, status: status ?? undefined })}>
          Export Excel
        </Button>
      </Group>
      {data && (
        <Text size="sm" c="dimmed">
          {data.period.label}
          {data.period.is_current ? " (so far)" : ""} · Sales <b>{formatINR(t?.sales_value ?? 0)}</b>
        </Text>
      )}
      <SimpleGrid cols={{ base: 3, sm: 6 }}>
        {sum.map((s) => (
          <Paper key={s.l} p="sm" radius="md" className="soft-card">
            <Text size="xs" c="dimmed">{s.l}</Text>
            <Text fw={s.bold ? 800 : 700} fz={s.bold ? "xl" : "lg"} c={s.c} className="num">{formatNumber(s.v)}</Text>
          </Paper>
        ))}
      </SimpleGrid>
      {isError && <ErrorState onRetry={() => refetch()} />}
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<PeriodRow>
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
              accessor: "design.label", title: "Label",
              render: (r) => (
                <Box>
                  <LabelCode>{r.design.label}</LabelCode>
                  <Text size="xs" c="dimmed" truncate maw={160}>{r.design.name}</Text>
                </Box>
              ),
            },
            { accessor: "design.category_name", title: "Category" },
            { accessor: "opening", title: "Opening", textAlign: "right", render: (r) => <N v={r.opening + r.opening_added} /> },
            { accessor: "received", title: "Received", textAlign: "right", render: (r) => <N v={r.received} /> },
            { accessor: "sold", title: "Sold", textAlign: "right", render: (r) => <N v={r.sold} /> },
            { accessor: "customer_returns", title: "Cust. returns", textAlign: "right", render: (r) => <N v={r.customer_returns} /> },
            { accessor: "supplier_returns", title: "To supplier", textAlign: "right", render: (r) => <N v={r.supplier_returns} /> },
            { accessor: "adjustments_net", title: "Corrections", textAlign: "right", render: (r) => <N v={r.adjustments_net} /> },
            { accessor: "closing", title: "Closing", textAlign: "right", render: (r) => <Text fw={800} className="num">{r.closing}</Text> },
            { accessor: "status_now", title: "Status now", render: (r) => <StatusBadge status={r.status_now} size="xs" /> },
          ]}
          noRecordsText="No designs"
        />
      </Box>
    </Stack>
  );
}

function N({ v }: { v: number }) {
  return <Text size="sm" className="num" c={v === 0 ? "dimmed" : undefined}>{v}</Text>;
}

export default function StockPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "quick";
  return (
    <>
      <PageHeader title="Stock" subtitle="Record sales and new stock, see history, and check any month or quarter." />
      <Tabs value={tab} onChange={(v) => setParams({ tab: v ?? "quick" })} keepMounted={false}>
        <Tabs.List mb="lg">
          <Tabs.Tab value="quick" leftSection={<IconPlusMinus size={16} />}>Quick entry</Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>History</Tabs.Tab>
          <Tabs.Tab value="period" leftSection={<IconListDetails size={16} />}>Month / Quarter view</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="quick"><QuickTab /></Tabs.Panel>
        <Tabs.Panel value="history"><HistoryTab /></Tabs.Panel>
        <Tabs.Panel value="period"><PeriodTab /></Tabs.Panel>
      </Tabs>
    </>
  );
}
