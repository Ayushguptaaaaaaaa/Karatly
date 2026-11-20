import { ActionIcon, Box, Button, Group, Menu, Stack, Text, TextInput } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconDots, IconPencil, IconPlus, IconSearch, IconTrash } from "@tabler/icons-react";
import { DataTable, type DataTableSortStatus } from "mantine-datatable";
import { useMemo, useState } from "react";
import { errorMessage } from "../../api/client";
import { useCustomers, useDealers, useDeleteCustomer, useDeleteDealer, type Customer, type Dealer } from "../../api/sales";
import { ContactModal } from "../../components/contacts";
import { formatDayWord, formatINR, formatNumber } from "../../lib/format";

function sortRows<T>(rows: T[], s: DataTableSortStatus<T>): T[] {
  const k = s.columnAccessor as keyof T;
  return [...rows].sort((a, b) => {
    const x = a[k] ?? "", y = b[k] ?? "";
    const r = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return s.direction === "asc" ? r : -r;
  });
}

function RowMenu({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon variant="subtle" color="gray" aria-label="Actions" onClick={(e) => e.stopPropagation()}><IconDots size={16} /></ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item leftSection={<IconPencil size={14} />} onClick={onEdit}>Edit</Menu.Item>
        <Menu.Item leftSection={<IconTrash size={14} />} color="red" onClick={onDelete}>Delete</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

export function CustomersTable() {
  const [q, setQ] = useState("");
  const [dq] = useDebouncedValue(q, 250);
  const { data, isFetching } = useCustomers(dq || undefined);
  const del = useDeleteCustomer();
  const [edit, setEdit] = useState<Customer | null | undefined>(undefined);
  const [sort, setSort] = useState<DataTableSortStatus<Customer>>({ columnAccessor: "revenue", direction: "desc" });
  const rows = useMemo(() => sortRows(data ?? [], sort), [data, sort]);
  const remove = (c: Customer) => modals.openConfirmModal({
    title: `Delete ${c.name}?`, children: <Text size="sm">Their old bills stay as they are.</Text>,
    labels: { confirm: "Delete", cancel: "Cancel" }, confirmProps: { color: "red" },
    onConfirm: () => del.mutateAsync(c.id).catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
  });
  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <TextInput leftSection={<IconSearch size={16} />} placeholder="Name, phone or city" value={q} onChange={(e) => setQ(e.currentTarget.value)} w={260} />
        <Button leftSection={<IconPlus size={16} />} onClick={() => setEdit(null)}>New customer</Button>
      </Group>
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<Customer>
          minHeight={180} fetching={isFetching} records={rows} striped highlightOnHover
          sortStatus={sort} onSortStatusChange={setSort}
          onRowClick={({ record }) => setEdit(record)}
          columns={[
            { accessor: "name", title: "Customer", sortable: true, render: (c) => <Box><Text size="sm" fw={600}>{c.name}</Text><Text size="xs" c="dimmed">{c.phone ?? ""}</Text></Box> },
            { accessor: "city", title: "City", sortable: true },
            { accessor: "state", title: "State", sortable: true },
            { accessor: "country", title: "Country", sortable: true },
            { accessor: "bills", title: "Bills", textAlign: "right", sortable: true },
            { accessor: "pieces", title: "Pieces", textAlign: "right", sortable: true, render: (c) => formatNumber(c.pieces) },
            { accessor: "revenue", title: "Revenue", textAlign: "right", sortable: true, render: (c) => <Text size="sm" fw={700} className="num">{formatINR(c.revenue, { compact: true })}</Text> },
            { accessor: "last_bill_on", title: "Last bill", sortable: true, render: (c) => (c.last_bill_on ? formatDayWord(c.last_bill_on) : "—") },
            { accessor: "actions", title: "", width: 50, render: (c) => <RowMenu onEdit={() => setEdit(c)} onDelete={() => remove(c)} /> },
          ]}
          noRecordsText="No customers yet. They are added when you make a bill."
        />
      </Box>
      <ContactModal kind="customer" opened={edit !== undefined} onClose={() => setEdit(undefined)} initial={edit} />
    </Stack>
  );
}

export function DealersTable() {
  const { data, isFetching } = useDealers();
  const del = useDeleteDealer();
  const [edit, setEdit] = useState<Dealer | null | undefined>(undefined);
  const [sort, setSort] = useState<DataTableSortStatus<Dealer>>({ columnAccessor: "amount", direction: "desc" });
  const rows = useMemo(() => sortRows(data ?? [], sort), [data, sort]);
  const remove = (d: Dealer) => modals.openConfirmModal({
    title: `Delete ${d.name}?`, children: <Text size="sm">Past purchases keep the dealer's name.</Text>,
    labels: { confirm: "Delete", cancel: "Cancel" }, confirmProps: { color: "red" },
    onConfirm: () => del.mutateAsync(d.id).catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
  });
  return (
    <Stack gap="sm">
      <Group justify="flex-end">
        <Button leftSection={<IconPlus size={16} />} onClick={() => setEdit(null)}>New dealer</Button>
      </Group>
      <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
        <DataTable<Dealer>
          minHeight={180} fetching={isFetching} records={rows} striped highlightOnHover
          sortStatus={sort} onSortStatusChange={setSort}
          onRowClick={({ record }) => setEdit(record)}
          columns={[
            { accessor: "name", title: "Dealer", sortable: true, render: (d) => <Box><Text size="sm" fw={600}>{d.name}</Text><Text size="xs" c="dimmed">{d.gstin ?? d.phone ?? ""}</Text></Box> },
            { accessor: "city", title: "City", sortable: true },
            { accessor: "state", title: "State", sortable: true },
            { accessor: "purchases", title: "Deliveries", textAlign: "right", sortable: true },
            { accessor: "designs", title: "Designs", textAlign: "right", sortable: true },
            { accessor: "pieces", title: "Pieces", textAlign: "right", sortable: true, render: (d) => formatNumber(d.pieces) },
            { accessor: "amount", title: "Bought for", textAlign: "right", sortable: true, render: (d) => <Text size="sm" fw={700} className="num">{formatINR(d.amount, { compact: true })}</Text> },
            { accessor: "last_purchase_on", title: "Last delivery", sortable: true, render: (d) => (d.last_purchase_on ? formatDayWord(d.last_purchase_on) : "—") },
            { accessor: "actions", title: "", width: 50, render: (d) => <RowMenu onEdit={() => setEdit(d)} onDelete={() => remove(d)} /> },
          ]}
          noRecordsText="No dealers yet. Add the dealers you buy from."
        />
      </Box>
      <ContactModal kind="dealer" opened={edit !== undefined} onClose={() => setEdit(undefined)} initial={edit} />
    </Stack>
  );
}
