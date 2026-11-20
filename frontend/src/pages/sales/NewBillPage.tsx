import { ActionIcon, Anchor, Box, Breadcrumbs, Button, Divider, Grid, Group, NumberInput, Paper, SegmentedControl, Stack, Table, Text, Textarea } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { IconDeviceFloppy, IconTrash } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api, download, errorMessage } from "../../api/client";
import { useSettings } from "../../api/hooks";
import { PAYMENT_MODES, useCreateBill } from "../../api/sales";
import type { DesignDetail, DesignSearchHit } from "../../api/types";
import { CustomerPicker } from "../../components/contacts";
import { DesignPicker } from "../../components/stock";
import { LabelCode, PhotoThumb } from "../../components/ui";
import { milestone } from "../../lib/confetti";
import { formatINR, todayISO } from "../../lib/format";

interface Line { d: DesignSearchHit; qty: number; price: number }

export default function NewBillPage() {
  const navigate = useNavigate();
  const { data: settings } = useSettings();
  const create = useCreateBill();
  const [customer, setCustomer] = useState<number | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [picker, setPicker] = useState<DesignSearchHit | null>(null);
  const [pickerKey, setPickerKey] = useState(0);  // remount = empty search box, ready for the next label
  const [date, setDate] = useState(todayISO());
  const [mode, setMode] = useState("Cash");
  const [discount, setDiscount] = useState<number>(0);
  const [gst, setGst] = useState<number>(3);
  const [notes, setNotes] = useState("");
  useEffect(() => {
    if (settings) setGst(settings.gst_pct ?? 3);
  }, [settings?.gst_pct]); // eslint-disable-line react-hooks/exhaustive-deps
  const [params] = useSearchParams();
  useEffect(() => {  // "Record sale" on a design page opens the bill with that design
    const id = Number(params.get("design"));
    if (!id) return;
    api<DesignDetail>(`/designs/${id}`).then((d) => add({
      id: d.id, label: d.label, name: d.name, category_name: d.category.name, current_stock: d.current_stock, status: d.status,
      photo_url: d.photo_url, selling_price: d.selling_price, cost_price: d.last_unit_cost, min_stock: d.min_stock,
    })).catch(() => undefined);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const add = (d: DesignSearchHit | null) => {
    setPicker(null);
    if (!d) return;
    setPickerKey((k) => k + 1);
    if (d.current_stock <= 0) return notifications.show({ color: "orange", message: `${d.label} is sold out.` });
    setLines((ls) => {
      const i = ls.findIndex((l) => l.d.id === d.id);
      if (i >= 0) return ls.map((l, j) => (j === i ? { ...l, qty: Math.min(l.qty + 1, d.current_stock) } : l));
      return [...ls, { d, qty: 1, price: d.selling_price }];
    });
  };
  const upd = (i: number, patch: Partial<Line>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  const subtotal = lines.reduce((a, l) => a + l.qty * l.price, 0);
  const disc = Math.min(Math.max(discount || 0, 0), subtotal);
  const taxable = subtotal - disc;
  const gstAmt = Math.round(taxable * (gst || 0)) / 100;
  const total = taxable + gstAmt;
  const tooMany = lines.some((l) => l.qty > l.d.current_stock || l.qty < 1);

  const save = async () => {
    if (!lines.length) return notifications.show({ color: "orange", message: "Add at least one design." });
    try {
      const b = await create.mutateAsync({
        customer_id: customer, bill_date: date, payment_mode: mode, discount: disc, gst_pct: gst, notes: notes || null,
        items: lines.map((l) => ({ design_id: l.d.id, quantity: l.qty, unit_price: l.price })),
      });
      milestone("first_sale");
      notifications.show({
        color: "teal", title: `Bill ${b.number} saved`, autoClose: 8000,
        message: <Anchor size="sm" component="button" onClick={() => download(`/bills/${b.id}/pdf`, undefined, `${b.number}.pdf`)}>Download PDF</Anchor>,
      });
      navigate(`/app/sales/bills/${b.id}`);
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    }
  };

  return (
    <>
      <Breadcrumbs mb="sm">
        <Anchor component={Link} to="/app/sales" size="sm">Sales</Anchor>
        <Text size="sm">New bill</Text>
      </Breadcrumbs>
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Paper className="soft-card" p="lg" radius="lg">
            <Stack gap="md">
              <CustomerPicker value={customer} onChange={setCustomer} label="Customer (empty = walk-in)" />
              <Box>
                <Text size="sm" fw={500} mb={4}>Add designs</Text>
                <DesignPicker key={pickerKey} value={picker} onPick={add} size="md" placeholder="Type or scan a label… e.g. ER-1012" autoFocus />
              </Box>
              {lines.length > 0 ? (
                <Table verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr><Table.Th>Design</Table.Th><Table.Th>Qty</Table.Th><Table.Th>Price / piece</Table.Th><Table.Th ta="right">Amount</Table.Th><Table.Th /></Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {lines.map((l, i) => (
                      <Table.Tr key={l.d.id}>
                        <Table.Td>
                          <Group gap="sm" wrap="nowrap">
                            <PhotoThumb url={l.d.photo_url} size={36} />
                            <Box><LabelCode>{l.d.label}</LabelCode><Text size="xs" c={l.qty > l.d.current_stock ? "red" : "dimmed"}>{l.d.name ?? l.d.category_name} · {l.d.current_stock} in stock</Text></Box>
                          </Group>
                        </Table.Td>
                        <Table.Td><NumberInput size="xs" w={76} min={1} max={l.d.current_stock} value={l.qty} onChange={(v) => upd(i, { qty: Math.max(0, Math.floor(Number(v) || 0)) })} /></Table.Td>
                        <Table.Td><NumberInput size="xs" w={130} min={0} prefix="₹" thousandSeparator="," thousandsGroupStyle="lakh" value={l.price} onChange={(v) => upd(i, { price: Number(v) || 0 })} /></Table.Td>
                        <Table.Td ta="right"><Text fw={700} className="num">{formatINR(l.qty * l.price)}</Text></Table.Td>
                        <Table.Td><ActionIcon variant="subtle" color="gray" aria-label="Remove" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}><IconTrash size={14} /></ActionIcon></Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              ) : (
                <Text size="sm" c="dimmed" ta="center" py="lg">No designs yet. Search above to add.</Text>
              )}
            </Stack>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper className="soft-card" p="lg" radius="lg" style={{ position: "sticky", top: 80 }}>
            <Stack gap="sm">
              <DateInput label="Date" value={date} onChange={(v) => setDate(v ? dayjs(v).format("YYYY-MM-DD") : todayISO())} maxDate={new Date()} valueFormat="D MMM YYYY" />
              <Box>
                <Text size="sm" fw={500} mb={4}>Paid by</Text>
                <SegmentedControl fullWidth size="xs" value={mode} onChange={setMode} data={PAYMENT_MODES.slice(0, 4)} />
              </Box>
              <Group grow>
                <NumberInput label="Discount" prefix="₹" min={0} thousandSeparator="," thousandsGroupStyle="lakh" value={discount} onChange={(v) => setDiscount(Number(v) || 0)} />
                <NumberInput label="GST" suffix="%" min={0} max={28} decimalScale={2} value={gst} onChange={(v) => setGst(Number(v) || 0)} />
              </Group>
              <Textarea label="Note" placeholder="Optional" autosize minRows={1} value={notes} onChange={(e) => setNotes(e.currentTarget.value)} />
              <Divider />
              {[["Subtotal", subtotal], ["Discount", -disc], [`CGST ${gst / 2}%`, gstAmt / 2], [`SGST ${gst / 2}%`, gstAmt / 2]].map(([l, v]) => (
                <Group key={l as string} justify="space-between"><Text size="sm" c="dimmed">{l}</Text><Text size="sm" className="num">{formatINR(v as number)}</Text></Group>
              ))}
              <Group justify="space-between">
                <Text fw={700}>Total</Text>
                <Text className="serif" fw={800} fz={28}>{formatINR(total)}</Text>
              </Group>
              <Button size="md" leftSection={<IconDeviceFloppy size={18} />} onClick={save} loading={create.isPending} disabled={!lines.length || tooMany}>
                Save bill
              </Button>
            </Stack>
          </Paper>
        </Grid.Col>
      </Grid>
    </>
  );
}
