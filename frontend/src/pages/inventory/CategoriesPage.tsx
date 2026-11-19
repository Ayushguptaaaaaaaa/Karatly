import { Badge, Box, Button, Card, Chip, Group, Menu, SegmentedControl, SimpleGrid, Skeleton, Stack, Text, ThemeIcon, Tooltip, ActionIcon, UnstyledButton } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconCategoryPlus, IconDots, IconEdit, IconFileSpreadsheet, IconPlus, IconTrash } from "@tabler/icons-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { errorMessage } from "../../api/client";
import { useCategories, useDeleteCategory } from "../../api/hooks";
import type { CategoryCard as Cat } from "../../api/types";
import { CategoryIcon, EmptyBox, ErrorState, Money, PageHeader } from "../../components/ui";
import { QUICK_CATEGORIES, STATUS_META } from "../../lib/constants";
import { formatNumber } from "../../lib/format";
import { AddCategoryModal, ImportExcelModal } from "./components";
import { DesignsView } from "./DesignsView";

function StatusBar({ c }: { c: Cat }) {
  const total = c.design_count || 1;
  const parts = [
    { k: "IN", v: c.in_stock_count }, { k: "LOW", v: c.low_stock_count }, { k: "OUT", v: c.out_of_stock_count }, { k: "DEAD", v: c.dead_stock_count },
  ] as const;
  return (
    <Tooltip label={parts.map((p) => `${STATUS_META[p.k].label}: ${p.v}`).join(" · ")}>
      <Group gap={2} h={6} wrap="nowrap" style={{ borderRadius: 4, overflow: "hidden", background: "var(--mantine-color-default-border)" }}>
        {parts.map((p) => p.v > 0 && <Box key={p.k} h={6} style={{ width: `${(p.v / total) * 100}%`, background: STATUS_META[p.k].hex }} />)}
      </Group>
    </Tooltip>
  );
}

function CategoryTile({ c, onEdit }: { c: Cat; onEdit: () => void }) {
  const navigate = useNavigate();
  const del = useDeleteCategory();
  return (
    <Card className="soft-card lift" withBorder={false} onClick={() => navigate(`/app/inventory/${c.id}`)} style={{ cursor: "pointer" }} h="100%">
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <ThemeIcon size={48} radius="xl" variant="light" color="gold">
          <CategoryIcon icon={c.icon} size={26} />
        </ThemeIcon>
        <Menu position="bottom-end" withinPortal>
          <Menu.Target>
            <ActionIcon variant="subtle" aria-label={`Actions for ${c.name}`} onClick={(e) => e.stopPropagation()}>
              <IconDots size={16} />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
            <Menu.Item leftSection={<IconEdit size={14} />} onClick={onEdit}>
              Edit
            </Menu.Item>
            <Menu.Item
              color="red"
              leftSection={<IconTrash size={14} />}
              disabled={c.design_count > 0}
              onClick={() =>
                modals.openConfirmModal({
                  title: `Delete ${c.name}?`,
                  children: <Text size="sm">This empty category and its subcategories will be removed.</Text>,
                  labels: { confirm: "Delete", cancel: "Cancel" },
                  confirmProps: { color: "red" },
                  onConfirm: () => del.mutateAsync(c.id).catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
                })
              }
            >
              Delete {c.design_count > 0 ? "(has designs)" : ""}
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
      <Group gap="xs" mt="md" wrap="nowrap">
        <Text className="serif" fz={22} fw={700} truncate>
          {c.name}
        </Text>
        <Badge variant="outline" color="gray" className="label-code">
          {c.label_prefix}
        </Badge>
      </Group>
      <Text size="sm" c="dimmed">
        {c.design_count} designs · {formatNumber(c.total_pieces)} pcs · <Money value={c.stock_value_cost} compact />
      </Text>
      <Box mt="sm">
        <StatusBar c={c} />
      </Box>
      <Group gap={6} mt="sm">
        {c.out_of_stock_count > 0 && <Badge color="red">{c.out_of_stock_count} sold out</Badge>}
        {c.low_stock_count > 0 && <Badge color="orange">{c.low_stock_count} low</Badge>}
        {c.subcategories.slice(0, 3).map((s) => (
          <Badge key={s.id} color="gray" variant="light">
            {s.name}
          </Badge>
        ))}
        {c.subcategories.length > 3 && <Badge color="gray" variant="light">+{c.subcategories.length - 3}</Badge>}
      </Group>
    </Card>
  );
}

export default function CategoriesPage() {
  const { data, isLoading, isError, refetch } = useCategories();
  const [params, setParams] = useSearchParams();
  const statusParam = params.get("status");
  const [mode, setMode] = useState<"categories" | "all">(statusParam ? "all" : "categories");
  const [addOpen, { open: openAdd, close: closeAdd }] = useDisclosure(false);
  const [importOpen, { open: openImport, close: closeImport }] = useDisclosure(false);
  const [initial, setInitial] = useState<{ name?: string; icon?: string } | undefined>();
  const [editing, setEditing] = useState<Cat | null>(null);
  const navigate = useNavigate();

  const cats = data ?? [];
  const totals = cats.reduce((a, c) => ({ d: a.d + c.design_count, p: a.p + c.total_pieces }), { d: 0, p: 0 });
  const add = (init?: { name?: string; icon?: string }) => {
    setEditing(null);
    setInitial(init);
    openAdd();
  };

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle={cats.length ? `${cats.length} categories · ${formatNumber(totals.d)} designs · ${formatNumber(totals.p)} pieces` : "Categories → designs → stock"}
        actions={
          <>
            <Button variant="default" leftSection={<IconFileSpreadsheet size={16} />} onClick={openImport}>
              Import Excel
            </Button>
            <Button leftSection={<IconPlus size={16} />} onClick={() => add()}>
              Add category
            </Button>
          </>
        }
      />

      {cats.length > 0 && totals.d > 0 && (
        <SegmentedControl
          mb="lg"
          value={mode}
          onChange={(v) => {
            setMode(v as "categories" | "all");
            if (v === "categories" && statusParam) setParams({});
          }}
          data={[
            { value: "categories", label: "Categories" },
            { value: "all", label: "All designs" },
          ]}
        />
      )}

      {isError && <ErrorState onRetry={() => refetch()} />}
      {isLoading && (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3, xl: 4 }}>
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} h={190} radius="md" />)}
        </SimpleGrid>
      )}

      {!isLoading && cats.length === 0 && (
        <EmptyBox
          icon={<IconCategoryPlus size={30} />}
          title="Start by adding your first category"
          text="Categories group your designs: Earrings, Necklaces, Bangles… Pick one below or create your own."
          action={<Button leftSection={<IconPlus size={16} />} onClick={() => add()}>Add category</Button>}
          secondary={<Button variant="default" onClick={openImport}>Import from Excel</Button>}
        >
          <Group gap="xs" justify="center" mt="sm">
            {QUICK_CATEGORIES.map((q) => (
              <Chip key={q.name} checked={false} onChange={() => add(q)} variant="outline">
                {q.name}
              </Chip>
            ))}
          </Group>
        </EmptyBox>
      )}

      {cats.length > 0 && mode === "categories" && (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3, xl: 4 }} spacing="lg">
          {cats.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 10) * 0.04 }}>
              <CategoryTile c={c} onEdit={() => { setEditing(c); openAdd(); }} />
            </motion.div>
          ))}
          <UnstyledButton
            onClick={() => add()}
            style={{ border: "2px dashed var(--jaa-border)", borderRadius: 12, minHeight: 190, display: "grid", placeItems: "center" }}
            aria-label="Add category"
          >
            <Stack align="center" gap={6}>
              <ThemeIcon size={44} radius="xl" variant="light">
                <IconPlus size={22} />
              </ThemeIcon>
              <Text fw={600} c="dimmed">
                Add category
              </Text>
            </Stack>
          </UnstyledButton>
        </SimpleGrid>
      )}

      {cats.length > 0 && mode === "all" && (
        <DesignsView base={{}} showCategory initialStatus={statusParam ? statusParam.split(",") : undefined} />
      )}

      <AddCategoryModal
        opened={addOpen}
        onClose={closeAdd}
        initial={initial}
        editing={editing}
        onSaved={(c) => {
          if (!editing) navigate(`/app/inventory/${c.id}?new=1`);
        }}
      />
      <ImportExcelModal opened={importOpen} onClose={closeImport} />
    </>
  );
}
