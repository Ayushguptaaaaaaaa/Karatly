import { Anchor, Badge, Box, Breadcrumbs, Button, Grid, Group, Image, Paper, SimpleGrid, Skeleton, Stack, Text, ThemeIcon, Timeline, Title, Tooltip } from "@mantine/core";
import { BarChart } from "@mantine/charts";
import { Dropzone } from "@mantine/dropzone";
import { useDisclosure } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconArchive, IconArrowBackUp, IconEdit, IconMinus, IconPhoto, IconPlus, IconTrash } from "@tabler/icons-react";
import { Link, useNavigate, useParams } from "react-router";
import { errorMessage } from "../../api/client";
import { useArchiveDesign, useDeleteDesign, useDeletePhoto, useDesign, useDesignHistory, useUploadPhoto, useVoidMovement } from "../../api/hooks";
import type { Movement } from "../../api/types";
import { StockStepper } from "../../components/stock";
import { CategoryIcon, DemandBadge, EmptyBox, LabelCode, Money, SectionCard, StatusBadge } from "../../components/ui";
import { MOVEMENT_META, STATUS_META } from "../../lib/constants";
import { formatDate, formatDayWord, formatINR, formatRelative } from "../../lib/format";
import { useUi } from "../../stores";
import { EditDesignModal } from "./components";

export function MovementTimeline({ items }: { items: Movement[] }) {
  const voidMv = useVoidMovement();
  const groups: Record<string, Movement[]> = {};
  items.forEach((m) => (groups[m.occurred_on] ??= []).push(m));
  if (!items.length) return <Text size="sm" c="dimmed">No entries yet.</Text>;
  return (
    <Stack gap="md">
      {Object.entries(groups).map(([day, ms]) => (
        <Box key={day}>
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={6}>
            {formatDayWord(day)}
          </Text>
          <Timeline bulletSize={26} lineWidth={2}>
            {ms.map((m) => {
              const meta = MOVEMENT_META[m.type];
              const I = meta.icon;
              return (
                <Timeline.Item
                  key={m.id}
                  bullet={<I size={14} />}
                  color={m.is_void ? "gray" : meta.color}
                  title={
                    <Group justify="space-between" wrap="nowrap">
                      <Text size="sm" fw={600} td={m.is_void ? "line-through" : undefined}>
                        {meta.label} · {m.direction === "IN" ? "+" : "−"}
                        {m.quantity} pcs{m.value ? ` · ${formatINR(m.value)}` : ""}
                      </Text>
                      {!m.is_void && (
                        <Tooltip label="Undo this entry">
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="gray"
                            leftSection={<IconArrowBackUp size={12} />}
                            onClick={() =>
                              modals.openConfirmModal({
                                title: "Undo this entry?",
                                children: <Text size="sm">{meta.label} of {m.quantity} piece(s) will be undone and stock adjusted back.</Text>,
                                labels: { confirm: "Undo", cancel: "Keep" },
                                onConfirm: () =>
                                  voidMv.mutateAsync({ id: m.id, reason: "Undone from history" })
                                    .then(() => notifications.show({ message: "Entry undone" }))
                                    .catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
                              })
                            }
                          >
                            Undo
                          </Button>
                        </Tooltip>
                      )}
                    </Group>
                  }
                >
                  <Text size="xs" c="dimmed">
                    {m.created_by?.display_name ?? "System"} · {formatRelative(m.created_at)}
                    {m.note ? ` · ${m.note}` : ""}
                    {m.is_void ? ` · Undone${m.void_reason ? ` (${m.void_reason})` : ""}` : ""}
                  </Text>
                </Timeline.Item>
              );
            })}
          </Timeline>
        </Box>
      ))}
    </Stack>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Paper p="sm" radius="md" withBorder>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} className="num">
        {value}
      </Text>
    </Paper>
  );
}

export default function DesignDetailPage() {
  const id = Number(useParams().designId);
  const navigate = useNavigate();
  const { data: d, isLoading, isError } = useDesign(id);
  const { data: hist } = useDesignHistory(id);
  const upload = useUploadPhoto();
  const delPhoto = useDeletePhoto();
  const arch = useArchiveDesign();
  const del = useDeleteDesign();
  const openQuick = useUi((s) => s.openQuickStock);
  const [editOpen, { open: openEdit, close: closeEdit }] = useDisclosure(false);

  if (isError) return <EmptyBox title="Design not found" text="It may have been deleted." action={<Button onClick={() => navigate("/app/inventory")}>Back to inventory</Button>} />;
  if (isLoading || !d) return <Skeleton h={300} radius="md" />;

  const margin = d.selling_price && d.last_unit_cost ? ((d.selling_price - d.last_unit_cost) / d.selling_price) * 100 : null;

  return (
    <>
      <Breadcrumbs mb="sm">
        <Anchor component={Link} to="/app/inventory" size="sm">
          Inventory
        </Anchor>
        <Anchor component={Link} to={`/app/inventory/${d.category.id}`} size="sm">
          {d.category.name}
        </Anchor>
        <Text size="sm" className="label-code">
          {d.label}
        </Text>
      </Breadcrumbs>
      {!d.is_active && (
        <Paper p="sm" mb="md" radius="md" bg="var(--mantine-color-gray-light)">
          <Group justify="space-between">
            <Text size="sm">This design is archived.</Text>
            <Button size="xs" variant="light" onClick={() => arch.mutate({ id: d.id, archive: false })}>
              Unarchive
            </Button>
          </Group>
        </Paper>
      )}
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack>
            <Dropzone
              onDrop={(f) => f[0] && upload.mutateAsync({ id: d.id, file: f[0] }).then(() => notifications.show({ color: "teal", message: "Photo saved" })).catch((e) => notifications.show({ color: "red", message: errorMessage(e) }))}
              accept={["image/jpeg", "image/png", "image/webp"]}
              maxSize={3 * 1024 * 1024}
              maxFiles={1}
              loading={upload.isPending}
              p={0}
              radius="lg"
              style={{ overflow: "hidden" }}
            >
              {d.photo_url ? (
                <Image src={d.photo_url} alt={d.label} style={{ aspectRatio: "1/1", objectFit: "cover" }} />
              ) : (
                <Stack align="center" justify="center" style={{ aspectRatio: "1/1", pointerEvents: "none" }} gap="xs">
                  <ThemeIcon size={64} radius="xl" variant="light">
                    <CategoryIcon icon={d.category.icon} size={34} />
                  </ThemeIcon>
                  <Group gap={6}>
                    <IconPhoto size={16} color="var(--jaa-muted)" />
                    <Text size="sm" c="dimmed">
                      Drop a photo or click to upload
                    </Text>
                  </Group>
                </Stack>
              )}
            </Dropzone>
            {d.photo_url && (
              <Button size="xs" variant="subtle" color="gray" onClick={() => delPhoto.mutate(d.id)}>
                Remove photo
              </Button>
            )}
            <Box>
              <LabelCode size="xl">{d.label}</LabelCode>
              <Title order={3} mt={4}>
                {d.name ?? "Untitled design"}
              </Title>
              <Group gap={6} mt="xs">
                <Badge variant="light">{d.category.name}</Badge>
                {d.subcategory && <Badge variant="light" color="gray">{d.subcategory.name}</Badge>}
                <Badge variant="outline" color="gray">
                  {d.metal}
                  {d.purity ? ` · ${d.purity}` : ""}
                  {d.weight_g ? ` · ${d.weight_g} g` : ""}
                </Badge>
              </Group>
              {d.supplier && (
                <Text size="sm" c="dimmed" mt="xs">
                  Supplier: {d.supplier}
                </Text>
              )}
            </Box>
            <Group>
              <Button variant="default" leftSection={<IconEdit size={16} />} onClick={openEdit}>
                Edit
              </Button>
              {d.is_active && (
                <Button variant="subtle" color="gray" leftSection={<IconArchive size={16} />} onClick={() => arch.mutate({ id: d.id, archive: true })}>
                  Archive
                </Button>
              )}
              <Button
                variant="subtle"
                color="red"
                leftSection={<IconTrash size={16} />}
                onClick={() =>
                  modals.openConfirmModal({
                    title: `Delete ${d.label}?`,
                    children: <Text size="sm">Only possible if it has no sales or stock history beyond its opening stock.</Text>,
                    labels: { confirm: "Delete", cancel: "Cancel" },
                    confirmProps: { color: "red" },
                    onConfirm: () => del.mutateAsync(d.id).then(() => navigate(`/app/inventory/${d.category.id}`)).catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
                  })
                }
              >
                Delete
              </Button>
            </Group>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack>
            <Paper className="gold-border" p="lg" radius="lg">
              <Group justify="space-between" wrap="wrap" gap="lg">
                <Box>
                  <Text size="sm" c="dimmed">
                    In stock now
                  </Text>
                  <Group gap="md" align="center">
                    <Text className="serif num" fz={56} fw={700} lh={1} c={STATUS_META[d.status].hex}>
                      {d.current_stock}
                    </Text>
                    <Stack gap={6}>
                      <StatusBadge status={d.status} />
                      <DemandBadge demand={d.demand_class} />
                    </Stack>
                  </Group>
                  <Text size="xs" c="dimmed" mt={4}>
                    Alert when at or below {d.min_stock}
                  </Text>
                </Box>
                <Stack gap="xs">
                  <StockStepper target={{ id: d.id, label: d.label, name: d.name, current_stock: d.current_stock, selling_price: d.selling_price, cost_price: d.last_unit_cost, photo_url: d.photo_url, status: d.status }} size="lg" />
                  <Group gap="xs">
                    <Button size="sm" variant="light" color="red" leftSection={<IconMinus size={14} />} disabled={!d.current_stock || !d.is_active} onClick={() => openQuick("OUT", d.id)}>
                      Record sale
                    </Button>
                    <Button size="sm" variant="light" color="teal" leftSection={<IconPlus size={14} />} disabled={!d.is_active} onClick={() => openQuick("IN", d.id)}>
                      Add stock
                    </Button>
                  </Group>
                </Stack>
              </Group>
            </Paper>
            <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }}>
              <Fact label="Last cost" value={<Money value={d.last_unit_cost} />} />
              <Fact label="Selling" value={<Money value={d.selling_price} />} />
              <Fact label="Margin" value={margin === null ? "—" : `${margin.toFixed(1)}%`} />
              <Fact label="Sold (30 days)" value={d.sold_last_30d} />
              <Fact label="Pace" value={`${d.velocity_30d}/month`} />
              <Fact label="Last sale" value={d.last_sale_on ? `${d.days_since_last_sale} days ago` : "Never"} />
            </SimpleGrid>
            <SectionCard title="Last 12 months">
              {hist ? (
                <BarChart
                  h={220}
                  data={hist.monthly}
                  dataKey="label"
                  series={[
                    { name: "sold", label: "Sold", color: "gold.6" },
                    { name: "received", label: "Received", color: "teal.4" },
                  ]}
                  tickLine="none"
                  gridAxis="y"
                  withLegend
                  barProps={{ radius: 4 }}
                />
              ) : (
                <Skeleton h={220} />
              )}
            </SectionCard>
            <SectionCard title="Stock history" actions={<Text size="xs" c="dimmed">First entry {formatDate(d.first_movement_on)}</Text>}>
              {hist ? <MovementTimeline items={hist.movements} /> : <Skeleton h={120} />}
            </SectionCard>
          </Stack>
        </Grid.Col>
      </Grid>
      <EditDesignModal design={d} opened={editOpen} onClose={closeEdit} />
    </>
  );
}
