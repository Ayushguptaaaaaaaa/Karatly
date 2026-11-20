import { Anchor, Badge, Box, Breadcrumbs, Button, Grid, Group, Paper, Skeleton, Stack, Table, Text } from "@mantine/core";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconDownload, IconPlus, IconX } from "@tabler/icons-react";
import { Link, useNavigate, useParams } from "react-router";
import { download, errorMessage } from "../../api/client";
import { useBill, useVoidBill } from "../../api/sales";
import { EmptyBox, LabelCode, PhotoThumb } from "../../components/ui";
import { METAL_LABEL } from "../../lib/constants";
import { formatDayWord, formatINR } from "../../lib/format";

export default function BillDetailPage() {
  const id = Number(useParams().billId);
  const navigate = useNavigate();
  const { data: b, isLoading, isError } = useBill(id);
  const voidBill = useVoidBill();
  if (isError) return <EmptyBox title="Bill not found" action={<Button onClick={() => navigate("/app/sales")}>Back to sales</Button>} />;
  if (isLoading || !b) return <Skeleton h={300} radius="md" />;

  const cancel = () => modals.openConfirmModal({
    title: `Cancel bill ${b.number}?`,
    children: <Text size="sm">The {b.pieces} piece{b.pieces > 1 ? "s go" : " goes"} back into stock and the sale is removed from reports.</Text>,
    labels: { confirm: "Cancel bill", cancel: "Keep" }, confirmProps: { color: "red" },
    onConfirm: () => voidBill.mutateAsync({ id: b.id, reason: "Cancelled" })
      .then(() => notifications.show({ color: "gray", message: `Bill ${b.number} cancelled` }))
      .catch((e) => notifications.show({ color: "red", message: errorMessage(e) })),
  });
  const place = [b.customer.city, b.customer.state, b.customer.country].filter(Boolean).join(", ");

  return (
    <>
      <Breadcrumbs mb="sm">
        <Anchor component={Link} to="/app/sales" size="sm">Sales</Anchor>
        <Text size="sm">{b.number}</Text>
      </Breadcrumbs>
      <Group justify="space-between" mb="lg" wrap="wrap">
        <Box>
          <Group gap="xs">
            <Text className="serif" fw={700} fz={28}>{b.number}</Text>
            {b.is_void ? <Badge color="red" variant="light">Cancelled</Badge> : <Badge color="teal" variant="light">Paid · {b.payment_mode ?? "—"}</Badge>}
          </Group>
          <Text c="dimmed" size="sm">{formatDayWord(b.bill_date)}</Text>
        </Box>
        <Group gap="xs">
          {!b.is_void && <Button variant="subtle" color="red" leftSection={<IconX size={16} />} onClick={cancel} loading={voidBill.isPending}>Cancel bill</Button>}
          <Button variant="default" leftSection={<IconPlus size={16} />} onClick={() => navigate("/app/sales/new")}>New bill</Button>
          <Button leftSection={<IconDownload size={16} />} onClick={() => download(`/bills/${b.id}/pdf`, undefined, `${b.number}.pdf`)}>Download PDF</Button>
        </Group>
      </Group>
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Paper className="soft-card" radius="lg" style={{ overflow: "hidden", opacity: b.is_void ? 0.6 : 1 }}>
            <Table verticalSpacing="sm" striped>
              <Table.Thead><Table.Tr><Table.Th>Design</Table.Th><Table.Th ta="right">Qty</Table.Th><Table.Th ta="right">Rate</Table.Th><Table.Th ta="right">Amount</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {b.lines.map((l) => (
                  <Table.Tr key={l.movement_id}>
                    <Table.Td>
                      <Group gap="sm" wrap="nowrap">
                        <PhotoThumb url={l.design.photo_url} size={36} />
                        <Box>
                          <Anchor component={Link} to={`/app/designs/${l.design.id}`}><LabelCode>{l.design.label}</LabelCode></Anchor>
                          <Text size="xs" c="dimmed">{l.design.name ?? l.design.category_name} · {[l.design.purity, METAL_LABEL[l.design.metal]].filter(Boolean).join(" ")}</Text>
                        </Box>
                      </Group>
                    </Table.Td>
                    <Table.Td ta="right" className="num">{l.quantity}</Table.Td>
                    <Table.Td ta="right" className="num">{formatINR(l.list_price)}</Table.Td>
                    <Table.Td ta="right" fw={700} className="num">{formatINR(l.amount)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack>
            <Paper className="soft-card" p="lg" radius="lg">
              <Text size="xs" c="dimmed">Customer</Text>
              <Text fw={700} fz="lg">{b.customer.name}</Text>
              {b.customer.phone && <Text size="sm">{b.customer.phone}</Text>}
              {place && <Text size="sm" c="dimmed">{place}</Text>}
            </Paper>
            <Paper className="gold-border" p="lg" radius="lg">
              <Stack gap={6}>
                {[["Subtotal", b.subtotal], ["Discount", -b.discount], ["Taxable value", b.taxable],
                  [`CGST ${b.gst_pct / 2}%`, b.gst_amount / 2], [`SGST ${b.gst_pct / 2}%`, b.gst_amount / 2]]
                  .filter(([l, v]) => !(l === "Discount" && v === 0))
                  .map(([l, v]) => (
                    <Group key={l as string} justify="space-between"><Text size="sm" c="dimmed">{l}</Text><Text size="sm" className="num">{formatINR(v as number)}</Text></Group>
                  ))}
                <Group justify="space-between" mt={4}>
                  <Text fw={700}>Total</Text>
                  <Text className="serif" fw={800} fz={28}>{formatINR(b.total)}</Text>
                </Group>
                {b.notes && <Text size="xs" c="dimmed">Note: {b.notes}</Text>}
              </Stack>
            </Paper>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  );
}
