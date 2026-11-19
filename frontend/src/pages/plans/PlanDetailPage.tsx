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
import { DonutChart } from "@mantine/charts";
import { DateInput } from "@mantine/dates";
import { useDebouncedCallback, useDisclosure, useMediaQuery } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconDownload, IconInfoCircle, IconPrinter, IconSend, IconTrash, IconTruckDelivery, IconX } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { download, errorMessage } from "../../api/client";
import { useDecidePlan, useDeletePlan, usePatchPlan, usePatchPlanItem, usePlan, useReceivePlan, useRemovePlanItem, useSubmitPlan } from "../../api/hooks";
import type { Decision, PlanDetail, PlanItem } from "../../api/types";
import { DemandBadge, EmptyBox, LabelCode, Money, PhotoThumb, StatusBadge } from "../../components/ui";
import { milestone } from "../../lib/confetti";
import { CATEGORY_COLORS } from "../../lib/constants";
import { formatINR, todayISO } from "../../lib/format";
import { useAuth } from "../../stores";
import { PLAN_STATUS } from "./PlansListPage";

const PRIO: Record<string, string> = { HIGH: "red", MEDIUM: "orange", LOW: "gray" };
const STEP_INDEX = { DRAFT: 0, SUBMITTED: 1, DECIDED: 2, RECEIVED: 3 } as const;

function QtyInput({ plan, item }: { plan: PlanDetail; item: PlanItem }) {
  const patch = usePatchPlanItem();
  const [v, setV] = useState<number | string>(item.final_qty);
  useEffect(() => setV(item.final_qty), [item.final_qty]);
  const save = useDebouncedCallback((q: number) => {
    patch.mutateAsync({ planId: plan.id, itemId: item.id, final_qty: q }).catch((e) => notifications.show({ color: "red", message: errorMessage(e) }));
  }, 500);
  const editable = plan.status === "DRAFT" || plan.status === "SUBMITTED";
  if (!editable) return <Text fw={700} className="num">{item.final_qty}</Text>;
  return (
    <NumberInput
      size="xs"
      w={80}
      min={0}
      max={10000}
      value={v}
      onChange={(x) => {
        setV(x);
        const n = Math.max(0, Math.floor(Number(x) || 0));
        save(n);
      }}
      aria-label={`Quantity for ${item.design.label}`}
    />
  );
}

function DecisionToggle({ value, onChange, disabled }: { value: Decision; onChange: (d: Decision) => void; disabled?: boolean }) {
  return (
    <SegmentedControl
      size="xs"
      value={value}
      disabled={disabled}
      onChange={(v) => onChange(v as Decision)}
      color={value === "APPROVED" ? "teal" : value === "REJECTED" ? "red" : "gray"}
      data={[
        { value: "APPROVED", label: <Tooltip label="Approve"><IconCheck size={14} aria-label="Approve" /></Tooltip> },
        { value: "PENDING", label: "–" },
        { value: "REJECTED", label: <Tooltip label="Reject"><IconX size={14} aria-label="Reject" /></Tooltip> },
      ]}
    />
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
  const patchItem = usePatchPlanItem();
  const removeItem = useRemovePlanItem();
  const submit = useSubmitPlan();
  const decide = useDecidePlan();
  const del = useDeletePlan();
  const [recvOpen, { open: openRecv, close: closeRecv }] = useDisclosure(false);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [highlight, setHighlight] = useState<number[]>([]);
  useEffect(() => {
    if (plan) {
      setTitle(plan.title);
      setNotes(plan.notes ?? "");
    }
  }, [plan?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const sums = useMemo(() => {
    const s = { approved: 0, pending: 0, rejected: 0 };
    plan?.items.forEach((i) => {
      if (i.decision === "APPROVED") s.approved += i.line_total;
      else if (i.decision === "REJECTED") s.rejected += i.line_total;
      else s.pending += i.line_total;
    });
    return s;
  }, [plan]);

  if (isError) return <EmptyBox title="Plan not found" action={<Button onClick={() => navigate("/app/purchase-plans")}>Back to plans</Button>} />;
  if (isLoading || !plan) return <Skeleton h={300} radius="md" />;

  const editable = plan.status === "DRAFT" || plan.status === "SUBMITTED";
  const canDecide = owner && editable;
  const err = (e: unknown) => notifications.show({ color: "red", message: errorMessage(e) });
  const setDecision = (item: PlanItem, d: Decision) => patchItem.mutateAsync({ planId: plan.id, itemId: item.id, decision: d }).catch(err);

  const saveDecisions = () =>
    decide.mutateAsync({ id: plan.id }).then(() => {
      milestone("first_plan_approved");
      notifications.show({ color: "teal", message: "Decisions saved" });
    }).catch((e) => {
      const ids = (e?.details?.pending_item_ids as number[]) ?? [];
      setHighlight(ids);
      err(e);
    });

  const approveAll = () =>
    modals.openConfirmModal({
      title: "Approve all pending lines?",
      children: <Text size="sm">Every line still pending will be approved. Total to approve: <b>{formatINR(sums.approved + sums.pending)}</b>.</Text>,
      labels: { confirm: "Approve all", cancel: "Cancel" },
      onConfirm: () => decide.mutateAsync({ id: plan.id, approve_all: true }).then(() => {
        milestone("first_plan_approved");
        notifications.show({ color: "teal", title: "Plan approved ✨", message: "You can mark stock as received when it arrives." });
      }).catch(err),
    });

  return (
    <>
      <Breadcrumbs mb="sm">
        <Anchor component={Link} to="/app/purchase-plans" size="sm">Purchase Plans</Anchor>
        <Text size="sm">#{plan.id}</Text>
      </Breadcrumbs>
      <Paper className="soft-card" p="lg" radius="lg" mb="lg">
        <Group justify="space-between" wrap="wrap" gap="md" align="flex-start">
          <Box style={{ flex: 1, minWidth: 260 }}>
            <Group gap="xs" mb={4}>
              <Badge color={PLAN_STATUS[plan.status].color}>{PLAN_STATUS[plan.status].label}</Badge>
              {plan.source === "AI" && <Badge variant="outline" color="gold">AI ✨</Badge>}
              {plan.period_label && <Badge variant="light" color="gray">{plan.period_label}</Badge>}
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
          </Box>
          <Stepper active={STEP_INDEX[plan.status] + (plan.status === "RECEIVED" ? 1 : 0)} size="xs" w={isMobile ? "100%" : 480} orientation={isMobile ? "vertical" : "horizontal"}>
            <Stepper.Step label="Draft" />
            <Stepper.Step label="Submitted" />
            <Stepper.Step label="Decided" />
            <Stepper.Step label="Received" />
          </Stepper>
        </Group>
        <SimpleGrid cols={{ base: 2, md: 4 }} mt="lg">
          <Paper p="sm" withBorder radius="md"><Text size="xs" c="dimmed">Estimated total</Text><Text className="serif" fw={700} fz="xl"><Money value={plan.total_estimated} compact /></Text></Paper>
          <Paper p="sm" withBorder radius="md"><Text size="xs" c="dimmed">Approved</Text><Text className="serif" fw={700} fz="xl" c="teal.7"><Money value={plan.total_approved} compact /></Text></Paper>
          <Paper p="sm" withBorder radius="md"><Text size="xs" c="dimmed">Lines</Text><Text fw={700} fz="xl">{plan.item_count} <Text span size="xs" c="dimmed">({plan.pending_count} pending)</Text></Text></Paper>
          <Paper p="sm" withBorder radius="md">
            <Group justify="space-between" wrap="nowrap">
              <Text size="xs" c="dimmed">By category</Text>
              {plan.by_category.length > 0 && (
                <DonutChart size={56} thickness={10} withTooltip valueFormatter={(v) => formatINR(v, { compact: true })}
                  data={plan.by_category.map((b, i) => ({ name: b.category, value: b.amount_estimated, color: `${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}.6` }))} />
              )}
            </Group>
          </Paper>
        </SimpleGrid>
        {editable ? (
          <Textarea mt="md" label="Notes" placeholder="Add a note for the owner…" value={notes} onChange={(e) => setNotes(e.currentTarget.value)} onBlur={() => notes !== (plan.notes ?? "") && patchPlan.mutateAsync({ id: plan.id, notes }).catch(err)} autosize minRows={1} />
        ) : plan.notes ? <Text mt="md" size="sm" c="dimmed">{plan.notes}</Text> : null}
      </Paper>

      {!owner && editable && plan.status === "SUBMITTED" && (
        <Alert mb="md" color="blue" icon={<IconInfoCircle size={18} />}>Waiting for owner approval. You can still adjust quantities.</Alert>
      )}

      <Paper className="soft-card" radius="lg" style={{ overflow: "hidden" }} mb={100}>
        <Box style={{ overflowX: "auto" }}>
          <Table verticalSpacing="sm" highlightOnHover miw={1000}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Design</Table.Th>
                <Table.Th>Now</Table.Th>
                <Table.Th ta="right">Suggested</Table.Th>
                <Table.Th>Qty</Table.Th>
                <Table.Th ta="right">Unit cost</Table.Th>
                <Table.Th ta="right">Line total</Table.Th>
                <Table.Th>Priority</Table.Th>
                <Table.Th>Why</Table.Th>
                <Table.Th>{plan.status === "DECIDED" || plan.status === "RECEIVED" ? "Received" : "Decision"}</Table.Th>
                {plan.status === "DRAFT" && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {plan.items.map((i) => (
                <Table.Tr key={i.id} className={highlight.includes(i.id) ? "flash-row" : undefined} bg={i.decision === "REJECTED" ? "var(--mantine-color-red-light)" : undefined}>
                  <Table.Td>
                    <Group gap="sm" wrap="nowrap">
                      <PhotoThumb url={i.design.photo_url} size={34} />
                      <Box>
                        <Anchor component={Link} to={`/app/designs/${i.design.id}`}><LabelCode>{i.design.label}</LabelCode></Anchor>
                        <Text size="xs" c="dimmed" truncate maw={160}>{i.design.name ?? i.design.category_name}</Text>
                      </Box>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={600} className="num">{i.current_stock} pcs</Text>
                    <Stack gap={3} align="flex-start"><StatusBadge status={i.status} size="xs" /><DemandBadge demand={i.demand_class} size="xs" /></Stack>
                  </Table.Td>
                  <Table.Td ta="right"><Text size="sm" c="dimmed" className="num">{i.suggested_qty}</Text></Table.Td>
                  <Table.Td><QtyInput plan={plan} item={i} /></Table.Td>
                  <Table.Td ta="right">
                    <Tooltip label={i.formula_text} multiline w={280}>
                      <Text size="sm" className="num" style={{ cursor: "help", textDecoration: "underline dotted" }}>{formatINR(i.expected_unit_cost)}</Text>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td ta="right"><Text fw={700} className="num">{formatINR(i.line_total, { compact: true })}</Text></Table.Td>
                  <Table.Td><Badge color={PRIO[i.priority]} variant="light" size="sm">{i.priority.toLowerCase()}</Badge></Table.Td>
                  <Table.Td maw={260}><Tooltip label={i.reason} multiline w={320} disabled={!i.reason}><Text size="xs" c="dimmed" lineClamp={2}>{i.reason}</Text></Tooltip></Table.Td>
                  <Table.Td>
                    {plan.status === "DECIDED" || plan.status === "RECEIVED" ? (
                      i.decision === "APPROVED" ? <Text size="sm" className="num">{i.received_qty}/{i.final_qty}</Text> : <Badge color="red" variant="light">Rejected</Badge>
                    ) : canDecide ? (
                      <DecisionToggle value={i.decision} onChange={(d) => setDecision(i, d)} />
                    ) : (
                      <Badge color="gray" variant="light">Pending</Badge>
                    )}
                  </Table.Td>
                  {plan.status === "DRAFT" && (
                    <Table.Td>
                      <ActionIcon variant="subtle" color="gray" aria-label="Remove line" onClick={() => removeItem.mutateAsync({ planId: plan.id, itemId: i.id }).catch(err)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
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
            <Text size="sm">Approved <b className="num">{formatINR(sums.approved, { compact: true })}</b></Text>
            <Text size="sm" c="dimmed">Pending <b className="num">{formatINR(sums.pending, { compact: true })}</b></Text>
            {sums.rejected > 0 && <Text size="sm" c="red">Rejected <b className="num">{formatINR(sums.rejected, { compact: true })}</b></Text>}
          </Group>
          <Group gap="xs">
            <Tooltip label="Export to Excel"><ActionIcon variant="default" size="lg" aria-label="Export" onClick={() => download(`/purchase-plans/${plan.id}/export`)}><IconDownload size={16} /></ActionIcon></Tooltip>
            <Tooltip label="Print"><ActionIcon variant="default" size="lg" aria-label="Print" onClick={() => window.print()}><IconPrinter size={16} /></ActionIcon></Tooltip>
            {plan.status === "DRAFT" && (
              <Button variant="subtle" color="red" onClick={() => modals.openConfirmModal({ title: "Delete this draft?", labels: { confirm: "Delete", cancel: "Cancel" }, confirmProps: { color: "red" }, onConfirm: () => del.mutateAsync(plan.id).then(() => navigate("/app/purchase-plans")).catch(err) })}>
                Delete
              </Button>
            )}
            {plan.status === "DRAFT" && !owner && (
              <Button leftSection={<IconSend size={16} />} onClick={() => submit.mutateAsync(plan.id).then(() => notifications.show({ color: "teal", message: "Sent to the owner for approval" })).catch(err)} loading={submit.isPending}>
                Submit for approval
              </Button>
            )}
            {canDecide && (
              <>
                <Button variant="default" onClick={saveDecisions} loading={decide.isPending}>Save decisions</Button>
                <Button color="teal" leftSection={<IconCheck size={16} />} onClick={approveAll} loading={decide.isPending}>Approve all</Button>
              </>
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
