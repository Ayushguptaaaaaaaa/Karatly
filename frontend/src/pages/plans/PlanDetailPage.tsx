import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Box,
  Breadcrumbs,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Stepper,
  Table,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { useDebouncedCallback, useDisclosure, useMediaQuery } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconDownload, IconInfoCircle, IconPrinter, IconRefresh, IconSend, IconTruckDelivery } from "@tabler/icons-react";
import dayjs from "dayjs";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { download, errorMessage } from "../../api/client";
import { useCreatePlan, useDecidePlan, useDeletePlan, usePatchPlan, usePatchPlanItem, usePlan, useReceivePlan, useSubmitPlan } from "../../api/hooks";
import type { PlanDetail, PlanItem } from "../../api/types";
import { DemandBadge, EmptyBox, LabelCode, PhotoThumb, StatusBadge } from "../../components/ui";
import { milestone } from "../../lib/confetti";
import { formatINR, todayISO } from "../../lib/format";
import { useAuth } from "../../stores";
import { PLAN_STATUS } from "./PlansListPage";

const PRIO: Record<string, string> = { HIGH: "red", MEDIUM: "orange", LOW: "gray" };
const STEP_INDEX = { DRAFT: 0, SUBMITTED: 1, DECIDED: 2, RECEIVED: 3 } as const;

function QtyInput({ plan, item, value, onLocal }: { plan: PlanDetail; item: PlanItem; value: number; onLocal: (n: number) => void }) {
  const patch = usePatchPlanItem();
  const save = useDebouncedCallback((q: number) => {
    patch.mutateAsync({ planId: plan.id, itemId: item.id, final_qty: q }).catch((e) => notifications.show({ color: "red", message: errorMessage(e) }));
  }, 600);
  const set = (n: number) => {
    onLocal(n);
    save(n);
  };
  return (
    <Group gap={6} wrap="nowrap">
      <NumberInput
        size="sm"
        w={88}
        min={0}
        max={10000}
        value={value}
        onChange={(x) => set(Math.max(0, Math.floor(Number(x) || 0)))}
        aria-label={`Quantity for ${item.design.label}`}
        styles={{ input: { fontWeight: 700 } }}
      />
      <Stack gap={0}>
        {value > 0 && <Anchor component="button" size="xs" c="dimmed" onClick={() => set(0)}>skip</Anchor>}
        {value !== item.suggested_qty && (
          <Anchor component="button" size="xs" onClick={() => set(item.suggested_qty)}>use {item.suggested_qty}</Anchor>
        )}
      </Stack>
    </Group>
  );
}

function ReceiveModal({ plan, opened, onClose }: { plan: PlanDetail; opened: boolean; onClose: () => void }) {
  const receive = useReceivePlan();
  const approved = plan.items.filter((i) => i.decision === "APPROVED" && i.received_qty < i.final_qty);
  const [rows, setRows] = useState<Record<number, { q: number | string; c: number | string }>>({});
  const [date, setDate] = useState(todayISO());
  useEffect(() => {
    if (opened) setRows(Object.fromEntries(approved.map((i) => [i.id, { q: i.final_qty - i.received_qty, c: i.expected_unit_cost }])));
  }, [opened]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async () => {
    try {
      await receive.mutateAsync({
        id: plan.id, occurred_on: date,
        items: approved.map((i) => ({ item_id: i.id, quantity: Number(rows[i.id]?.q) || 0, unit_cost: Number(rows[i.id]?.c) || undefined })),
      });
      milestone("first_plan_received");
      notifications.show({ color: "teal", title: "Stock received ✨", message: "Stock is updated everywhere." });
      onClose();
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    }
  };
  return (
    <Modal opened={opened} onClose={onClose} size="xl" title={<Text fw={700}>Mark stock as received</Text>}>
      <Stack>
        <DateInput label="Received on" value={date} onChange={(v) => setDate(v ? dayjs(v).format("YYYY-MM-DD") : todayISO())} maxDate={new Date()} valueFormat="D MMM YYYY" w={220} />
        <Table fz="sm">
          <Table.Thead><Table.Tr><Table.Th>Design</Table.Th><Table.Th>Qty received</Table.Th><Table.Th>Actual cost / piece</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {approved.map((i) => (
              <Table.Tr key={i.id}>
                <Table.Td><LabelCode>{i.design.label}</LabelCode><Text size="xs" c="dimmed">ordered {i.final_qty}</Text></Table.Td>
                <Table.Td><NumberInput size="xs" w={90} min={0} value={rows[i.id]?.q ?? 0} onChange={(v) => setRows((r) => ({ ...r, [i.id]: { ...r[i.id], q: v } }))} /></Table.Td>
                <Table.Td><NumberInput size="xs" w={140} min={0} prefix="₹" value={rows[i.id]?.c ?? ""} onChange={(v) => setRows((r) => ({ ...r, [i.id]: { ...r[i.id], c: v } }))} /></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button leftSection={<IconTruckDelivery size={16} />} onClick={submit} loading={receive.isPending}>Add to stock</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function PlanDetailPage() {
  const id = Number(useParams().planId);
  const navigate = useNavigate();
  const owner = useAuth((s) => s.user?.role === "OWNER");
  const isMobile = useMediaQuery("(max-width: 48em)");
  const { data: plan, isLoading, isError } = usePlan(id);
  const patchPlan = usePatchPlan();
  const refresh = useCreatePlan();
  const submit = useSubmitPlan();
  const decide = useDecidePlan();
  const del = useDeletePlan();
  const [recvOpen, { open: openRecv, close: closeRecv }] = useDisclosure(false);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [cat, setCat] = useState("ALL");
  // quantities typed but not yet confirmed by the server: totals update instantly
  const [local, setLocal] = useState<Record<number, number>>({});
  useEffect(() => {
    if (plan) {
      setTitle(plan.title);
      setNotes(plan.notes ?? "");
    }
  }, [plan?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!plan) return;
    setLocal((prev) => {
      const next: Record<number, number> = {};
      for (const it of plan.items) if (prev[it.id] !== undefined && prev[it.id] !== it.final_qty) next[it.id] = prev[it.id];
      return next;
    });
  }, [plan]);

  const q = (i: PlanItem) => local[i.id] ?? i.final_qty;
  const lineTotal = (i: PlanItem) => q(i) * i.expected_unit_cost;

  const cats = useMemo(() => {
    const m: Record<string, { lines: number; buying: number; total: number }> = {};
    plan?.items.forEach((i) => {
      const c = (m[i.design.category_name] ??= { lines: 0, buying: 0, total: 0 });
      c.lines += 1;
      if ((local[i.id] ?? i.final_qty) > 0) c.buying += 1;
      c.total += (local[i.id] ?? i.final_qty) * i.expected_unit_cost;
    });
    return m;
  }, [plan, local]);

  if (isError) return <EmptyBox title="This plan no longer exists" text="It was replaced by the current plan." action={<Button onClick={() => navigate("/app/purchase-plans")}>Go to purchase plans</Button>} />;
  if (isLoading || !plan) return <Skeleton h={300} radius="md" />;

  const editable = plan.status === "DRAFT" || plan.status === "SUBMITTED";
  const done = plan.status === "DECIDED" || plan.status === "RECEIVED";
  const total = Object.values(cats).reduce((a, c) => a + c.total, 0);
  const buying = Object.values(cats).reduce((a, c) => a + c.buying, 0);
  const overBudget = !!plan.budget_limit && total > plan.budget_limit + 0.5;
  const err = (e: unknown) => notifications.show({ color: "red", message: errorMessage(e) });
  const pendingQty = () => Object.entries(local).map(([itemId, final_qty]) => ({ item_id: Number(itemId), final_qty }));
  const rows = plan.items.filter((i) => cat === "ALL" || i.design.category_name === cat);

  const approve = () =>
    modals.openConfirmModal({
      title: "Approve this plan?",
      children: (
        <Stack gap={6}>
          <Text size="sm">You will buy <b>{buying}</b> designs for <b>{formatINR(total)}</b>.</Text>
          {plan.item_count - buying > 0 && <Text size="sm" c="dimmed">{plan.item_count - buying} designs set to 0 will not be bought this month.</Text>}
          {overBudget && <Text size="sm" c="red">This is above your monthly budget of {formatINR(plan.budget_limit!)}.</Text>}
        </Stack>
      ),
      labels: { confirm: "Approve plan", cancel: "Cancel" },
      confirmProps: { color: "teal" },
      onConfirm: () => decide.mutateAsync({ id: plan.id, approve_all: true, decisions: pendingQty() }).then(() => {
        milestone("first_plan_approved");
        notifications.show({ color: "teal", title: "Plan approved ✨", message: "Mark stock as received when it arrives." });
      }).catch(err),
    });

  const refreshPlan = () =>
    refresh.mutateAsync().then((p) => {
      notifications.show({ color: "teal", message: "Suggestions updated. Quantities you changed were kept." });
      if (p.id !== plan.id) navigate(`/app/purchase-plans/${p.id}`);
    }).catch(err);

  const removePlan = () =>
    modals.openConfirmModal({
      title: done ? "Cancel this approved plan?" : "Delete this plan?",
      children: <Text size="sm">{done ? "Nothing has been received yet. The order is cancelled and these designs will be suggested again." : "You can create a fresh plan any time."}</Text>,
      labels: { confirm: done ? "Cancel plan" : "Delete", cancel: "Keep" },
      confirmProps: { color: "red" },
      onConfirm: () => del.mutateAsync(plan.id).then(() => navigate("/app/purchase-plans")).catch(err),
    });

  return (
    <>
      <Breadcrumbs mb="sm">
        <Anchor component={Link} to="/app/purchase-plans" size="sm">Purchase Plans</Anchor>
        <Text size="sm">{plan.title}</Text>
      </Breadcrumbs>
      <Paper className="soft-card" p="lg" radius="lg" mb="lg">
        <Group justify="space-between" wrap="wrap" gap="md" align="flex-start">
          <Box style={{ flex: 1, minWidth: 260 }}>
            <Group gap="xs" mb={4}>
              <Badge color={PLAN_STATUS[plan.status].color}>{PLAN_STATUS[plan.status].label}</Badge>
              {plan.source === "AI" && <Badge variant="outline" color="gold">AI suggested ✨</Badge>}
            </Group>
            {editable ? (
              <TextInput
                variant="unstyled"
                value={title}
                onChange={(e) => setTitle(e.currentTarget.value)}
                onBlur={() => title.trim() && title !== plan.title && patchPlan.mutateAsync({ id: plan.id, title }).catch(err)}
                styles={{ input: { fontFamily: "Playfair Display, serif", fontSize: 26, fontWeight: 700, height: 40 } }}
                aria-label="Plan title"
              />
            ) : (
              <Text className="serif" fz={26} fw={700}>{plan.title}</Text>
            )}
            {editable && (
              <Text size="sm" c="dimmed">Change any quantity (0 = don't buy this month). The total updates as you type.</Text>
            )}
          </Box>
          <Stepper active={STEP_INDEX[plan.status] + (plan.status === "RECEIVED" ? 1 : 0)} size="xs" w={isMobile ? "100%" : 440} orientation={isMobile ? "vertical" : "horizontal"}>
            <Stepper.Step label="Draft" />
            <Stepper.Step label="With owner" />
            <Stepper.Step label="Approved" />
            <Stepper.Step label="Received" />
          </Stepper>
        </Group>
        <SimpleGrid cols={{ base: 2, md: 4 }} mt="lg">
          <Paper p="sm" withBorder radius="md" style={{ borderColor: "var(--mantine-color-gold-5)" }}>
            <Text size="xs" c="dimmed">{done ? "Approved spend" : "Total capital required"}</Text>
            <Text className="serif" fw={800} fz={24}>{formatINR(done ? plan.total_approved : total, { compact: true })}</Text>
          </Paper>
          <Paper p="sm" withBorder radius="md">
            <Text size="xs" c="dimmed">AI suggested</Text>
            <Text className="serif" fw={700} fz={24} c="dimmed">{formatINR(plan.suggested_total, { compact: true })}</Text>
          </Paper>
          <Paper p="sm" withBorder radius="md">
            <Text size="xs" c="dimmed">Designs to buy</Text>
            <Text fw={700} fz={24}>{buying}<Text span size="sm" c="dimmed"> / {plan.item_count}</Text></Text>
          </Paper>
          <Paper p="sm" withBorder radius="md">
            <Text size="xs" c="dimmed">Monthly budget</Text>
            {plan.budget_limit ? (
              <>
                <Text fw={700} fz={24} className="serif">{formatINR(plan.budget_limit, { compact: true })}</Text>
                <Badge size="sm" variant="light" color={overBudget ? "red" : "teal"}>
                  {overBudget ? `Over by ${formatINR(total - plan.budget_limit, { compact: true })}` : `${formatINR(plan.budget_limit - total, { compact: true })} left`}
                </Badge>
              </>
            ) : (
              <Anchor component={Link} to="/app/settings" size="sm">No limit · set one</Anchor>
            )}
          </Paper>
        </SimpleGrid>
        {editable ? (
          <Textarea mt="md" label="Notes" placeholder="Add a note…" value={notes} onChange={(e) => setNotes(e.currentTarget.value)} onBlur={() => notes !== (plan.notes ?? "") && patchPlan.mutateAsync({ id: plan.id, notes }).catch(err)} autosize minRows={1} />
        ) : plan.notes ? <Text mt="md" size="sm" c="dimmed">{plan.notes}</Text> : null}
      </Paper>

      {plan.budget_note && editable && (
        <Alert mb="md" color={plan.budget_note.startsWith("Fits") ? "teal" : "orange"} icon={<IconInfoCircle size={18} />}>
          {plan.budget_note}
        </Alert>
      )}

      {Object.keys(cats).length > 1 && (
        <SegmentedControl
          mb="sm"
          value={cat}
          onChange={setCat}
          data={[
            { value: "ALL", label: `All · ${formatINR(total, { compact: true })}` },
            ...Object.entries(cats).map(([c, v]) => ({ value: c, label: `${c} · ${formatINR(v.total, { compact: true })}` })),
          ]}
        />
      )}

      <Paper className="soft-card" radius="lg" style={{ overflow: "hidden" }} mb={100}>
        <Box style={{ overflowX: "auto" }}>
          <Table verticalSpacing="sm" highlightOnHover miw={900}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Design</Table.Th>
                <Table.Th>Stock now</Table.Th>
                <Table.Th ta="right">AI suggests</Table.Th>
                <Table.Th>{editable ? "Your quantity" : "Quantity"}</Table.Th>
                <Table.Th ta="right">Cost / piece</Table.Th>
                <Table.Th ta="right">Line total</Table.Th>
                <Table.Th>Why</Table.Th>
                {done && <Table.Th>Received</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((i, idx) => (
                <Fragment key={i.id}>
                  {(idx === 0 || rows[idx - 1].design.category_name !== i.design.category_name) && (
                    <Table.Tr bg="var(--mantine-color-gold-light)">
                      <Table.Td colSpan={done ? 8 : 7}>
                        <Group justify="space-between">
                          <Text fw={700}>{i.design.category_name}</Text>
                          <Text size="sm" fw={600}>
                            {cats[i.design.category_name]?.buying} of {cats[i.design.category_name]?.lines} designs · subtotal{" "}
                            <span className="num">{formatINR(cats[i.design.category_name]?.total ?? 0)}</span>
                          </Text>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  )}
                  <Table.Tr style={q(i) === 0 ? { opacity: 0.55 } : undefined}>
                    <Table.Td>
                      <Group gap="sm" wrap="nowrap">
                        <PhotoThumb url={i.design.photo_url} size={34} />
                        <Box>
                          <Group gap={6} wrap="nowrap">
                            <Anchor component={Link} to={`/app/designs/${i.design.id}`}><LabelCode>{i.design.label}</LabelCode></Anchor>
                            <Tooltip label={`${i.priority.toLowerCase()} priority`}><Badge circle size="xs" color={PRIO[i.priority]}> </Badge></Tooltip>
                          </Group>
                          <Text size="xs" c="dimmed" truncate maw={160}>{i.design.name ?? i.design.category_name}</Text>
                        </Box>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={600} className="num">{i.current_stock} pcs</Text>
                      <Stack gap={3} align="flex-start"><StatusBadge status={i.status} size="xs" /><DemandBadge demand={i.demand_class} size="xs" /></Stack>
                    </Table.Td>
                    <Table.Td ta="right"><Text size="sm" c="dimmed" className="num">{i.suggested_qty}</Text></Table.Td>
                    <Table.Td>
                      {editable ? (
                        <QtyInput plan={plan} item={i} value={q(i)} onLocal={(n) => setLocal((m) => ({ ...m, [i.id]: n }))} />
                      ) : q(i) === 0 || i.decision === "REJECTED" ? (
                        <Badge color="gray" variant="light">Not bought</Badge>
                      ) : (
                        <Text fw={700} className="num">{i.final_qty}</Text>
                      )}
                      {editable && q(i) === 0 && <Text size="xs" c="dimmed">not buying</Text>}
                    </Table.Td>
                    <Table.Td ta="right">
                      <Tooltip label={i.formula_text} multiline w={280}>
                        <Text size="sm" className="num" style={{ cursor: "help", textDecoration: "underline dotted" }}>{formatINR(i.expected_unit_cost)}</Text>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td ta="right"><Text fw={700} className="num">{formatINR(lineTotal(i), { compact: true })}</Text></Table.Td>
                    <Table.Td maw={280}><Tooltip label={i.reason} multiline w={320} disabled={!i.reason}><Text size="xs" c="dimmed" lineClamp={2}>{i.reason}</Text></Tooltip></Table.Td>
                    {done && (
                      <Table.Td>{i.decision === "APPROVED" ? <Text size="sm" className="num">{i.received_qty}/{i.final_qty}</Text> : null}</Table.Td>
                    )}
                  </Table.Tr>
                </Fragment>
              ))}
            </Table.Tbody>
          </Table>
        </Box>
        <Box p="lg" style={{ borderTop: "2px solid var(--mantine-color-gold-5)" }}>
          <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
            <Stack gap={4}>
              {Object.entries(cats).map(([c, v]) => (
                <Group key={c} gap="xl" justify="space-between" miw={320}>
                  <Text size="sm" c="dimmed">{c} ({v.buying} designs)</Text>
                  <Text size="sm" className="num">{formatINR(v.total)}</Text>
                </Group>
              ))}
            </Stack>
            <Box ta="right">
              <Text size="sm" c="dimmed">Total capital required</Text>
              <Text className="serif" fw={800} fz={34} lh={1.1}>{formatINR(total)}</Text>
              <Text size="xs" c="dimmed">AI suggested {formatINR(plan.suggested_total, { compact: true })} · {buying} designs to buy</Text>
            </Box>
          </Group>
        </Box>
      </Paper>

      <Paper
        className="no-print"
        shadow="lg"
        p="sm"
        radius={0}
        style={{ position: "fixed", left: isMobile ? 0 : "var(--app-shell-navbar-offset, 0px)", right: 0, bottom: isMobile ? 64 : 0, zIndex: 110, borderTop: "1px solid var(--jaa-border)", background: "var(--jaa-surface)" }}
      >
        <Group justify="space-between" wrap="wrap" gap="xs" px={{ base: 0, sm: "md" }}>
          <Group gap="lg">
            <Text size="sm">Total <b className="num" style={{ fontSize: 18 }}>{formatINR(done ? plan.total_approved : total, { compact: true })}</b></Text>
            {plan.budget_limit ? (
              <Text size="sm" c={overBudget ? "red" : "teal"}>{overBudget ? "over" : "within"} budget {formatINR(plan.budget_limit, { compact: true })}</Text>
            ) : null}
          </Group>
          <Group gap="xs">
            <Tooltip label="Export to Excel"><ActionIcon variant="default" size="lg" aria-label="Export" onClick={() => download(`/purchase-plans/${plan.id}/export`)}><IconDownload size={16} /></ActionIcon></Tooltip>
            <Tooltip label="Print"><ActionIcon variant="default" size="lg" aria-label="Print" onClick={() => window.print()}><IconPrinter size={16} /></ActionIcon></Tooltip>
            {(editable || (plan.status === "DECIDED" && !plan.items.some((i) => i.received_qty > 0))) && (
              <Button variant="subtle" color="red" onClick={removePlan}>{done ? "Cancel plan" : "Delete"}</Button>
            )}
            {editable && (
              <Tooltip label="Recalculate from today's stock and sales. Quantities you changed are kept." multiline w={260}>
                <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={refreshPlan} loading={refresh.isPending}>Refresh suggestions</Button>
              </Tooltip>
            )}
            {plan.status === "DRAFT" && !owner && (
              <Button leftSection={<IconSend size={16} />} onClick={() => submit.mutateAsync(plan.id).then(() => notifications.show({ color: "teal", message: "Sent to the owner for approval" })).catch(err)} loading={submit.isPending}>
                Send to owner
              </Button>
            )}
            {owner && editable && (
              <Button color="teal" leftSection={<IconCheck size={16} />} onClick={approve} loading={decide.isPending}>
                Approve plan · {formatINR(total, { compact: true })}
              </Button>
            )}
            {plan.status === "DECIDED" && plan.approved_count > 0 && (
              <Button leftSection={<IconTruckDelivery size={16} />} onClick={openRecv}>Mark as received</Button>
            )}
          </Group>
        </Group>
      </Paper>
      <ReceiveModal plan={plan} opened={recvOpen} onClose={closeRecv} />
    </>
  );
}
