import { Anchor, Badge, Box, Button, Group, Paper, Select, SimpleGrid, Stack, Switch, Tabs, Text, TextInput } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { useDebouncedValue } from "@mantine/hooks";
import { IconDownload, IconFileInvoice, IconPlus, IconSearch, IconTable, IconUsers } from "@tabler/icons-react";
import dayjs from "dayjs";
import { DataTable } from "mantine-datatable";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { download } from "../../api/client";
import { useBills, useFacets, type BillSummary } from "../../api/sales";
import { Explorer } from "../../components/Explorer";
import { PageHeader } from "../../components/ui";
import { formatDayWord, formatINR, formatNumber } from "../../lib/format";
import { CustomersTable } from "./ContactsTables";

function BillsTab() {
  const navigate = useNavigate();
  const { data: facets } = useFacets();
  const [q, setQ] = useState("");
  const [dq] = useDebouncedValue(q, 250);
  const [range, setRange] = useState<[string | null, string | null]>([dayjs().startOf("month").format("YYYY-MM-DD"), null]);
  const [country, setCountry] = useState<string | null>(null);
  const [city, setCity] = useState<string | null>(null);
  const [showVoid, setShowVoid] = useState(false);
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [dq, range, country, city, showVoid]);
  const { data, isFetching } = useBills({
    q: dq || undefined, date_from: range[0] ?? undefined, date_to: range[1] ?? undefined, country: country ?? undefined,
    city: city ?? undefined, include_void: showVoid, page, page_size: 50,
  });
  const t = data?.totals;
  return (
    <Stack gap="sm">
      <Group gap="xs" wrap="wrap">
        <TextInput size="xs" leftSection={<IconSearch size={14} />} placeholder="Bill no., name or phone" value={q} onChange={(e) => setQ(e.currentTarget.value)} w={220} />
        <DatePickerInput size="xs" type="range" w={230} placeholder="All time" clearable valueFormat="D MMM YYYY" value={range}
          onChange={(v) => setRange([v[0] ? dayjs(v[0]).format("YYYY-MM-DD") : null, v[1] ? dayjs(v[1]).format("YYYY-MM-DD") : null])} />
        <Select size="xs" w={150} placeholder="Country" data={facets?.countries ?? []} value={country} onChange={setCountry} clearable searchable />
        <Select size="xs" w={140} placeholder="City" data={facets?.cities ?? []} value={city} onChange={setCity} clearable searchable />
        <Switch size="xs" label="Show cancelled" checked={showVoid} onChange={(e) => setShowVoid(e.currentTarget.checked)} />
      </Group>
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
        {[{ l: "Bills", v: formatNumber(t?.bills ?? 0) }, { l: "Sales (before GST)", v: formatINR(t?.taxable ?? 0, { compact: true }) },
          { l: "GST collected", v: formatINR(t?.gst ?? 0, { compact: true }) }, { l: "Billed total", v: formatINR(t?.total ?? 0, { compact: true }) }]
          .map((s, i) => (
            <Paper key={s.l} p="sm" radius="md" className={i === 3 ? "gold-border" : "soft-card"}>
              <Text size="xs" c="dimmed">{s.l}</Text>
              <Text fw={800} fz="xl" className="num">{s.v}</Text>
            </Paper>
          ))}
      </SimpleGrid>
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<BillSummary>
          minHeight={180} fetching={isFetching} records={data?.items ?? []} totalRecords={data?.total ?? 0}
          recordsPerPage={50} page={page} onPageChange={setPage} striped highlightOnHover
          onRowClick={({ record }) => navigate(`/app/sales/bills/${record.id}`)}
          rowStyle={(b) => ({ cursor: "pointer", opacity: b.is_void ? 0.5 : 1 })}
          columns={[
            { accessor: "number", title: "Bill", render: (b) => <Group gap={6}><Anchor component={Link} to={`/app/sales/bills/${b.id}`} size="sm" fw={600}>{b.number}</Anchor>{b.is_void && <Badge size="xs" color="red" variant="light">Cancelled</Badge>}</Group> },
            { accessor: "bill_date", title: "Date", render: (b) => formatDayWord(b.bill_date) },
            { accessor: "customer_name", title: "Customer", render: (b) => <Box><Text size="sm">{b.customer_name}</Text><Text size="xs" c="dimmed">{b.customer_phone ?? ""}</Text></Box> },
            { accessor: "city", title: "Place", render: (b) => <Text size="sm">{[b.city, b.country].filter(Boolean).join(", ") || "—"}</Text> },
            { accessor: "pieces", title: "Pcs", textAlign: "right" },
            { accessor: "payment_mode", title: "Paid by", render: (b) => b.payment_mode ?? "—" },
            { accessor: "total", title: "Total", textAlign: "right", render: (b) => <Text size="sm" fw={700} className="num">{formatINR(b.total)}</Text> },
            {
              accessor: "pdf", title: "", width: 60,
              render: (b) => (
                <Button size="compact-xs" variant="subtle" leftSection={<IconDownload size={12} />}
                  onClick={(e) => { e.stopPropagation(); download(`/bills/${b.id}/pdf`, undefined, `${b.number}.pdf`); }}>PDF</Button>
              ),
            },
          ]}
          noRecordsText="No bills in this period"
        />
      </Box>
    </Stack>
  );
}

export default function SalesPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "bills";
  return (
    <>
      <PageHeader
        title="Sales"
        subtitle="Bills, customers and every sale, filtered any way you like."
        actions={<Button leftSection={<IconPlus size={16} />} onClick={() => navigate("/app/sales/new")}>New bill</Button>}
      />
      <Tabs value={tab} onChange={(v) => setParams({ tab: v ?? "bills" })} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="bills" leftSection={<IconFileInvoice size={16} />}>Bills</Tabs.Tab>
          <Tabs.Tab value="explore" leftSection={<IconTable size={16} />}>Explore sales</Tabs.Tab>
          <Tabs.Tab value="customers" leftSection={<IconUsers size={16} />}>Customers</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="bills"><BillsTab /></Tabs.Panel>
        <Tabs.Panel value="explore"><Explorer kind="sales" /></Tabs.Panel>
        <Tabs.Panel value="customers"><CustomersTable /></Tabs.Panel>
      </Tabs>
    </>
  );
}
