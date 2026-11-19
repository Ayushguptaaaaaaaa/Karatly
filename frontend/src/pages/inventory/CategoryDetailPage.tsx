import { ActionIcon, Anchor, Box, Breadcrumbs, Button, Chip, Group, Menu, Popover, ScrollArea, SimpleGrid, Skeleton, Text, TextInput, ThemeIcon, Title, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconDots, IconEdit, IconFileSpreadsheet, IconPlus } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { errorMessage } from "../../api/client";
import { useCategory, useCreateSubcategory, useDeleteSubcategory, useUpdateSubcategory } from "../../api/hooks";
import { CategoryIcon, ErrorState, Money } from "../../components/ui";
import { formatINR, formatNumber } from "../../lib/format";
import { AddCategoryModal, AddDesignsWizard, ImportExcelModal } from "./components";
import { DesignsView } from "./DesignsView";

function Stat({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <Box>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} fz="lg" c={color} className="num">
        {value}
      </Text>
    </Box>
  );
}

export default function CategoryDetailPage() {
  const id = Number(useParams().categoryId);
  const [params, setParams] = useSearchParams();
  const { data: cat, isLoading, isError, refetch } = useCategory(id);
  const sub = params.get("sub") ? Number(params.get("sub")) : null;
  const [wizard, { open: openWizard, close: closeWizard }] = useDisclosure(false);
  const [editOpen, { open: openEdit, close: closeEdit }] = useDisclosure(false);
  const [importOpen, { open: openImport, close: closeImport }] = useDisclosure(false);
  const [adding, setAdding] = useState(false);
  const [newSub, setNewSub] = useState("");
  const [hint, setHint] = useState(params.get("new") === "1");
  const createSub = useCreateSubcategory();
  const renameSub = useUpdateSubcategory();
  const delSub = useDeleteSubcategory();

  useEffect(() => {
    if (hint) {
      const t = setTimeout(() => setHint(false), 7000);
      return () => clearTimeout(t);
    }
  }, [hint]);

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading || !cat) return <Skeleton h={200} radius="md" />;

  const saveSub = async () => {
    if (!newSub.trim()) return setAdding(false);
    try {
      await createSub.mutateAsync({ categoryId: id, name: newSub.trim() });
      setNewSub("");
      setAdding(false);
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    }
  };

  const addBtn = (
    <Button leftSection={<IconPlus size={16} />} onClick={() => { setHint(false); openWizard(); }}>
      Add designs
    </Button>
  );

  return (
    <>
      <Breadcrumbs mb="sm">
        <Anchor component={Link} to="/app/inventory" size="sm">
          Inventory
        </Anchor>
        <Text size="sm">{cat.name}</Text>
      </Breadcrumbs>

      <Box className="soft-card" p="lg" mb="lg" style={{ borderRadius: 16 }}>
        <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
          <Group gap="md" wrap="nowrap">
            <ThemeIcon size={60} radius="xl" variant="light">
              <CategoryIcon icon={cat.icon} size={32} />
            </ThemeIcon>
            <Box>
              <Group gap="xs">
                <Title order={1} fz={30}>
                  {cat.name}
                </Title>
                <Text className="label-code" c="dimmed">
                  {cat.label_prefix}-
                </Text>
              </Group>
              {cat.description && (
                <Text size="sm" c="dimmed">
                  {cat.description}
                </Text>
              )}
            </Box>
          </Group>
          <Group gap="sm">
            <Button variant="default" leftSection={<IconEdit size={16} />} onClick={openEdit}>
              Edit
            </Button>
            <Button variant="default" leftSection={<IconFileSpreadsheet size={16} />} onClick={openImport}>
              Import
            </Button>
            <Popover opened={hint && cat.design_count === 0} position="bottom-end" withArrow shadow="md">
              <Popover.Target>{addBtn}</Popover.Target>
              <Popover.Dropdown>
                <Text size="sm" fw={600}>
                  Next: add your designs ✨
                </Text>
                <Text size="xs" c="dimmed">
                  Enter how many designs you have and their labels.
                </Text>
              </Popover.Dropdown>
            </Popover>
          </Group>
        </Group>
        <SimpleGrid cols={{ base: 2, sm: 4, lg: 8 }} mt="lg">
          <Stat label="Designs" value={formatNumber(cat.design_count)} />
          <Stat label="Pieces" value={formatNumber(cat.total_pieces)} />
          <Stat label="Stock value" value={<Money value={cat.stock_value_cost} compact />} />
          <Stat label="Sold (30 days)" value={formatNumber(cat.sold_last_30d)} />
          <Stat label="Sold out" value={cat.out_of_stock_count} color={cat.out_of_stock_count ? "red" : undefined} />
          <Stat label="Low" value={cat.low_stock_count} color={cat.low_stock_count ? "orange" : undefined} />
          <Stat label="Net revenue (30 days)" value={<Money value={cat.net_revenue_30d} compact />} />
          <Stat label="Net profit (30 days)" color={cat.net_profit_30d < 0 ? "red.7" : "teal.8"}
            value={<>{<Money value={cat.net_profit_30d} compact />}{cat.margin_pct_30d !== null ? <Text span size="xs" c="dimmed"> {cat.margin_pct_30d}%</Text> : null}</>} />
        </SimpleGrid>
      </Box>

      <ScrollArea type="never" mb="md">
        <Group gap="xs" wrap="nowrap">
          <Chip checked={!sub} onChange={() => setParams({})} variant="filled">
            All ({cat.design_count})
          </Chip>
          {cat.subcategories.filter((s) => s.is_active).map((s) => (
            <Group key={s.id} gap={0} wrap="nowrap">
              <Tooltip label={`Last 30 days · net revenue ${formatINR(s.net_revenue_30d ?? 0, { compact: true })} · net profit ${formatINR(s.net_profit_30d ?? 0, { compact: true })}${s.margin_pct_30d != null ? ` (${s.margin_pct_30d}%)` : ""}`}>
                <Chip checked={sub === s.id} onChange={() => setParams({ sub: String(s.id) })} variant="filled">
                  {s.name} ({s.design_count ?? 0})
                </Chip>
              </Tooltip>
              <Menu withinPortal position="bottom-end">
                <Menu.Target>
                  <ActionIcon size="sm" variant="subtle" aria-label={`Actions for ${s.name}`}>
                    <IconDots size={14} />
                  </ActionIcon>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item
                    onClick={() => {
                      const name = window.prompt("Rename subcategory", s.name);
                      if (name && name.trim() && name !== s.name)
                        renameSub.mutateAsync({ id: s.id, name: name.trim() }).catch((e) => notifications.show({ color: "red", message: errorMessage(e) }));
                    }}
                  >
                    Rename
                  </Menu.Item>
                  <Menu.Item
                    color="red"
                    disabled={!!s.design_count}
                    onClick={() =>
                      modals.openConfirmModal({
                        title: `Delete ${s.name}?`,
                        labels: { confirm: "Delete", cancel: "Cancel" },
                        confirmProps: { color: "red" },
                        onConfirm: () => delSub.mutateAsync(s.id).then(() => sub === s.id && setParams({})).catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
                      })
                    }
                  >
                    Delete
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          ))}
          {adding ? (
            <TextInput
              size="xs"
              autoFocus
              placeholder="Subcategory name"
              value={newSub}
              onChange={(e) => setNewSub(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveSub();
                if (e.key === "Escape") setAdding(false);
              }}
              onBlur={saveSub}
              w={180}
            />
          ) : (
            <Chip checked={false} onChange={() => setAdding(true)} variant="outline" icon={<IconPlus size={12} />} styles={{ label: { borderStyle: "dashed" } }}>
              + Add subcategory
            </Chip>
          )}
        </Group>
      </ScrollArea>

      <DesignsView base={{ category_id: id, subcategory_id: sub ?? undefined }} emptyAction={addBtn} />

      <AddDesignsWizard opened={wizard} onClose={closeWizard} categoryId={id} defaultSubId={sub} />
      <AddCategoryModal opened={editOpen} onClose={closeEdit} editing={cat} />
      <ImportExcelModal opened={importOpen} onClose={closeImport} />
    </>
  );
}
