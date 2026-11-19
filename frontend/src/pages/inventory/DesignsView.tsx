import { Box, Card, Group, Menu, MultiSelect, Pagination, SegmentedControl, Select, SimpleGrid, Stack, Text, TextInput, ActionIcon } from "@mantine/core";
import { useDebouncedValue, useMediaQuery } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconArchive, IconDots, IconExternalLink, IconLayoutGrid, IconSearch, IconTable } from "@tabler/icons-react";
import { DataTable } from "mantine-datatable";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { errorMessage } from "../../api/client";
import { useArchiveDesign, useDesigns, type DesignFilters } from "../../api/hooks";
import type { DesignListItem } from "../../api/types";
import { StockStepper, type StockTarget } from "../../components/stock";
import { DemandBadge, EmptyBox, ErrorState, LabelCode, Money, PhotoThumb, StatusBadge } from "../../components/ui";
import { STATUS_META } from "../../lib/constants";
import { useUi } from "../../stores";

export function toTarget(d: DesignListItem): StockTarget {
  return { id: d.id, label: d.label, name: d.name, current_stock: d.current_stock, selling_price: d.selling_price,
    cost_price: d.last_unit_cost, photo_url: d.photo_url, status: d.status };
}

const STATUS_OPTS = [
  { value: "OUT", label: "Sold out" }, { value: "LOW", label: "Low" }, { value: "IN", label: "In stock" }, { value: "DEAD", label: "Not selling" },
];
const DEMAND_OPTS = [
  { value: "HIGH", label: "High demand" }, { value: "STEADY", label: "Steady" }, { value: "LOW", label: "Low demand" },
  { value: "DEAD", label: "Not selling" }, { value: "NEW", label: "New" },
];
const SORT_OPTS = [
  { value: "label", label: "Label" }, { value: "current_stock", label: "Stock: low → high" },
  { value: "-sold_last_30d", label: "Best selling" }, { value: "-stock_value", label: "Stock value" },
  { value: "-created_at", label: "Newest" },
];

function RowMenu({ d }: { d: DesignListItem }) {
  const navigate = useNavigate();
  const arch = useArchiveDesign();
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <ActionIcon data-stop-row variant="subtle" aria-label={`More actions for ${d.label}`} onClick={(e) => e.stopPropagation()}>
          <IconDots size={16} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
        <Menu.Item leftSection={<IconExternalLink size={14} />} onClick={() => navigate(`/app/designs/${d.id}`)}>
          Open details
        </Menu.Item>
        <Menu.Item
          leftSection={<IconArchive size={14} />}
          color="red"
          onClick={() =>
            modals.openConfirmModal({
              title: `Archive ${d.label}?`,
              children: <Text size="sm">It will be hidden from lists and alerts. History is kept and you can unarchive it later.</Text>,
              labels: { confirm: "Archive", cancel: "Cancel" },
              confirmProps: { color: "red" },
              onConfirm: () =>
                arch.mutateAsync({ id: d.id, archive: true })
                  .then(() => notifications.show({ message: `${d.label} archived` }))
                  .catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
            })
          }
        >
          Archive
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function DesignCard({ d }: { d: DesignListItem }) {
  const navigate = useNavigate();
  return (
    <Card className="soft-card lift" withBorder={false} padding="sm" onClick={() => navigate(`/app/designs/${d.id}`)} style={{ cursor: "pointer" }}>
      <Card.Section style={{ position: "relative" }}>
        {d.photo_url ? (
          <img src={d.photo_url} alt="" style={{ width: "100%", aspectRatio: "4/3", objectFit: "cover", display: "block" }} />
        ) : (
          <Box style={{ aspectRatio: "4/3", display: "grid", placeItems: "center", background: "linear-gradient(135deg, var(--mantine-color-gold-light), transparent)" }}>
            <PhotoThumb url={null} icon={d.category.icon} size={64} radius={32} />
          </Box>
        )}
        <Box style={{ position: "absolute", top: 8, left: 8 }}>
          <StatusBadge status={d.status} size="xs" />
        </Box>
      </Card.Section>
      <Group justify="space-between" mt="sm" wrap="nowrap">
        <Box style={{ minWidth: 0 }}>
          <LabelCode>{d.label}</LabelCode>
          <Text size="xs" c="dimmed" truncate>
            {d.name ?? d.subcategory?.name ?? d.category.name}
          </Text>
        </Box>
        <Text size="sm" fw={600}>
          <Money value={d.selling_price} compact />
        </Text>
      </Group>
      <Group justify="space-between" mt="sm">
        <DemandBadge demand={d.demand_class} size="xs" />
        <StockStepper target={toTarget(d)} />
      </Group>
    </Card>
  );
}

export function DesignsView({ base, initialStatus, emptyAction, showCategory = false }: {
  base: DesignFilters; initialStatus?: string[]; emptyAction?: React.ReactNode; showCategory?: boolean;
}) {
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 48em)");
  const view = useUi((s) => s.designView);
  const setView = useUi((s) => s.setDesignView);
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 250);
  const [status, setStatus] = useState<string[]>(initialStatus ?? []);
  const [demand, setDemand] = useState<string | null>(null);
  const [sort, setSort] = useState("label");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  useEffect(() => setPage(1), [debounced, status, demand, sort, base.category_id, base.subcategory_id]);
  useEffect(() => setStatus(initialStatus ?? []), [initialStatus?.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const filters: DesignFilters = { ...base, search: debounced || undefined, status: status.join(",") || undefined, demand: demand ?? undefined, sort, page, page_size: pageSize };
  const { data, isLoading, isError, refetch } = useDesigns(filters);
  const asCards = isMobile || view === "cards";
  const filtered = !!(debounced || status.length || demand);

  return (
    <Stack gap="md">
      <Group justify="space-between" gap="sm">
        <Group gap="sm" style={{ flex: 1 }} wrap="wrap">
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Search label or name" value={search} onChange={(e) => setSearch(e.currentTarget.value)} w={{ base: "100%", sm: 240 }} />
          <MultiSelect data={STATUS_OPTS} value={status} onChange={setStatus} placeholder={status.length ? undefined : "Status"} clearable w={{ base: "100%", sm: 220 }} />
          <Select data={DEMAND_OPTS} value={demand} onChange={setDemand} placeholder="Demand" clearable w={{ base: "48%", sm: 160 }} />
          <Select data={SORT_OPTS} value={sort} onChange={(v) => setSort(v ?? "label")} allowDeselect={false} w={{ base: "48%", sm: 180 }} aria-label="Sort" />
        </Group>
        {!isMobile && (
          <SegmentedControl
            value={view}
            onChange={(v) => setView(v as "table" | "cards")}
            data={[
              { value: "table", label: <IconTable size={16} aria-label="Table view" /> },
              { value: "cards", label: <IconLayoutGrid size={16} aria-label="Card view" /> },
            ]}
          />
        )}
      </Group>

      {isError && <ErrorState onRetry={() => refetch()} />}

      {data && data.total === 0 && !isLoading ? (
        filtered ? (
          <EmptyBox title="No designs match these filters" text="Try clearing the search or filters." />
        ) : (
          <EmptyBox title="No designs here yet" text="Add all your designs at once: just tell us how many." action={emptyAction} />
        )
      ) : asCards ? (
        <SimpleGrid cols={{ base: 1, xs: 2, md: 3, xl: 4 }} spacing="md">
          {(data?.items ?? []).map((d, i) => (
            <motion.div key={d.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 10) * 0.03 }}>
              <DesignCard d={d} />
            </motion.div>
          ))}
        </SimpleGrid>
      ) : (
        <Box className="soft-card" style={{ borderRadius: 12, overflow: "hidden" }}>
          <DataTable<DesignListItem>
            minHeight={data?.items.length ? undefined : 180}
            fetching={isLoading}
            records={data?.items ?? []}
            highlightOnHover
            verticalSpacing="sm"
            onRowClick={({ record, event }) => {
              const t = event.target as HTMLElement | null;
              if (t?.closest("[data-stop-row], button, [role=menu], .mantine-Popover-dropdown")) return;
              navigate(`/app/designs/${record.id}`);
            }}
            rowStyle={(r) => (r.status === "OUT" ? { boxShadow: `inset 3px 0 0 ${STATUS_META.OUT.hex}` } : undefined)}
            columns={[
              {
                accessor: "label",
                title: "Design",
                render: (d) => (
                  <Group gap="sm" wrap="nowrap">
                    <PhotoThumb url={d.photo_url} icon={d.category.icon} />
                    <Box style={{ minWidth: 0 }}>
                      <LabelCode>{d.label}</LabelCode>
                      <Text size="xs" c="dimmed" truncate maw={200}>
                        {d.name ?? "—"}
                      </Text>
                    </Box>
                  </Group>
                ),
              },
              {
                accessor: "subcategory",
                title: showCategory ? "Category" : "Subcategory",
                render: (d) => <Text size="sm">{showCategory ? d.category.name : d.subcategory?.name ?? "—"}</Text>,
              },
              { accessor: "current_stock", title: "Stock", render: (d) => <StockStepper target={toTarget(d)} /> },
              { accessor: "status", title: "Status", render: (d) => <StatusBadge status={d.status} /> },
              { accessor: "demand_class", title: "Demand", render: (d) => <DemandBadge demand={d.demand_class} /> },
              { accessor: "sold_last_30d", title: "Sold 30d", textAlign: "right", render: (d) => <Text className="num" size="sm">{d.sold_last_30d}</Text> },
              {
                accessor: "selling_price",
                title: "Cost / Selling",
                textAlign: "right",
                render: (d) => (
                  <Box>
                    <Text size="xs" c="dimmed" className="num">
                      <Money value={d.last_unit_cost} compact />
                    </Text>
                    <Text size="sm" fw={600} className="num">
                      <Money value={d.selling_price} compact />
                    </Text>
                  </Box>
                ),
              },
              { accessor: "actions", title: "", width: 50, render: (d) => <RowMenu d={d} /> },
            ]}
            noRecordsText="No designs"
          />
        </Box>
      )}
      {data && data.total > pageSize && (
        <Group justify="space-between">
          <Text size="sm" c="dimmed">
            {data.total} designs
          </Text>
          <Pagination total={Math.ceil(data.total / pageSize)} value={page} onChange={setPage} size="sm" />
        </Group>
      )}
    </Stack>
  );
}
