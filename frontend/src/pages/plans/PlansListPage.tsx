import { Badge, Box, Button, Drawer, Group, Paper, SimpleGrid, Skeleton, Stack, Table, Text, ThemeIcon, UnstyledButton } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconCategory, IconChevronRight, IconListCheck, IconPlus, IconShoppingCart, IconSparkles } from "@tabler/icons-react";
import { motion } from "motion/react";
import { useNavigate } from "react-router";
import { errorMessage } from "../../api/client";
import { useCreatePlan, useCreatePlansByCategory, usePlans, useReorderBaseline } from "../../api/hooks";
import type { PlanStatus, PlanSummary } from "../../api/types";
import { DemandBadge, EmptyBox, ErrorState, LabelCode, Money, PageHeader, StatusBadge } from "../../components/ui";
import { formatINR, formatRelative } from "../../lib/format";
import { useAuth } from "../../stores";

export const PLAN_STATUS: Record<PlanStatus, { label: string; color: string }> = {
  DRAFT: { label: "Draft", color: "gray" },
  SUBMITTED: { label: "Waiting for owner", color: "blue" },
  DECIDED: { label: "Approved", color: "teal" },
  RECEIVED: { label: "Received", color: "gold" },
};

function PlanRow({ p, i }: { p: PlanSummary; i: number }) {
  const navigate = useNavigate();
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.04 }}>
      <UnstyledButton onClick={() => navigate(`/app/purchase-plans/${p.id}`)} w="100%">
        <Paper className="soft-card lift" p="md" radius="md">
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
              <ThemeIcon size={44} radius="xl" variant="light" color={p.source === "AI" ? "gold" : "gray"}>
                {p.source === "AI" ? <IconSparkles size={22} /> : <IconShoppingCart size={22} />}
              </ThemeIcon>
              <Box style={{ minWidth: 0 }}>
                <Group gap="xs">
                  <Text fw={700} truncate>{p.title}</Text>
                  <Badge variant="light" color={p.scope === "ALL" ? "grape" : "blue"}>
                    {p.scope === "ALL" ? "Final · all categories" : p.category_name ?? "Category"}
                  </Badge>
                  <Badge color={PLAN_STATUS[p.status].color}>{PLAN_STATUS[p.status].label}</Badge>
                  {p.source === "AI" && <Badge variant="outline" color="gold">AI ✨</Badge>}
                </Group>
                <Text size="xs" c="dimmed">
                  {p.item_count} designs · created {formatRelative(p.created_at)} by {p.created_by ?? "AI"}
                  {p.status !== "DRAFT" && p.status !== "SUBMITTED" ? ` · ${p.approved_count} approved, ${p.rejected_count} rejected` : ""}
                </Text>
              </Box>
            </Group>
            <Group gap="lg" wrap="nowrap">
              <Box ta="right">
                <Text size="xs" c="dimmed">{p.status === "DRAFT" || p.status === "SUBMITTED" ? "Estimated" : "Approved"}</Text>
                <Text className="serif" fw={700} fz="lg">
                  <Money value={p.status === "DRAFT" || p.status === "SUBMITTED" ? p.total_estimated : p.total_approved} compact />
                </Text>
              </Box>
              <IconChevronRight color="var(--jaa-muted)" />
            </Group>
          </Group>
        </Paper>
      </UnstyledButton>
    </motion.div>
  );
}

export default function PlansListPage() {
  const navigate = useNavigate();
  const owner = useAuth((s) => s.user?.role === "OWNER");
  const { data, isLoading, isError, refetch } = usePlans();
  const create = useCreatePlan();
  const byCat = useCreatePlansByCategory();
  const [baseOpen, { open: openBase, close: closeBase }] = useDisclosure(false);
  const { data: base } = useReorderBaseline();

  const createPlan = () =>
    create.mutateAsync({})
      .then((p) => navigate(`/app/purchase-plans/${p.id}`))
      .catch((e) => notifications.show({ color: "orange", message: errorMessage(e) }));
  const createByCategory = () =>
    byCat.mutateAsync()
      .then((ps) => notifications.show({ color: "teal", title: `${ps.length} category plans created`,
        message: ps.map((p) => `${p.category_name}: ${formatINR(p.total_estimated, { compact: true })}`).join(" · ") }))
      .catch((e) => notifications.show({ color: "orange", message: errorMessage(e) }));

  const waiting = (data ?? []).filter((p) => p.status === "SUBMITTED" || (p.status === "DRAFT" && p.source === "AI"));
  const rest = (data ?? []).filter((p) => !waiting.includes(p));
  const finals = rest.filter((p) => p.scope === "ALL");
  const cats = rest.filter((p) => p.scope === "CATEGORY");
  const openCats = cats.filter((p) => p.status === "DRAFT" || p.status === "SUBMITTED");
  const catTotal = openCats.reduce((a, p) => a + p.total_estimated, 0);

  return (
    <>
      <PageHeader
        title="Purchase Plans"
        subtitle="What to restock, how many, and the budget. The AI suggests, the owner approves."
        actions={
          <>
            <Button variant="default" leftSection={<IconListCheck size={16} />} onClick={openBase}>View reorder suggestions</Button>
            <Button variant="default" leftSection={<IconCategory size={16} />} onClick={createByCategory} loading={byCat.isPending}>Create plans by category</Button>
            <Button leftSection={<IconPlus size={16} />} onClick={createPlan} loading={create.isPending}>Create final plan (all categories)</Button>
          </>
        }
      />
      {isError && <ErrorState onRetry={() => refetch()} />}
      {isLoading && <Stack>{[1, 2, 3].map((i) => <Skeleton key={i} h={76} radius="md" />)}</Stack>}
      {data && data.length === 0 && (
        <EmptyBox
          icon={<IconShoppingCart size={30} />}
          title="No purchase plans yet"
          text="Generate AI insights to get a smart plan, or create one from current reorder needs."
          action={<Button onClick={() => navigate("/app/insights")} leftSection={<IconSparkles size={16} />}>Generate AI insights</Button>}
          secondary={<Button variant="default" onClick={createPlan}>Create from current needs</Button>}
        />
      )}
      {waiting.length > 0 && (
        <Box mb="xl">
          <Text fw={700} mb="sm">{owner ? "Waiting for your approval" : "Waiting for owner approval"}</Text>
          <Stack gap="sm">{waiting.map((p, i) => <PlanRow key={p.id} p={p} i={i} />)}</Stack>
        </Box>
      )}
      {finals.length > 0 && (
        <Box mb="xl">
          <Text fw={700} mb="sm">Final plans (all categories)</Text>
          <Stack gap="sm">{finals.map((p, i) => <PlanRow key={p.id} p={p} i={i} />)}</Stack>
        </Box>
      )}
      {cats.length > 0 && (
        <Box>
          <Group justify="space-between" mb="sm">
            <Text fw={700}>Category plans</Text>
            {openCats.length > 0 && (
              <Text size="sm" c="dimmed">
                Open category plans need <b className="num">{formatINR(catTotal, { compact: true })}</b> in total
                {base && base.budget > 0 ? ` · monthly budget ${formatINR(base.budget, { compact: true })}` : ""}
              </Text>
            )}
          </Group>
          <Stack gap="sm">{cats.map((p, i) => <PlanRow key={p.id} p={p} i={i} />)}</Stack>
        </Box>
      )}

      <Drawer opened={baseOpen} onClose={closeBase} position="right" size="xl" title={<Text fw={700}>Reorder suggestions (live, no AI)</Text>}>
        {base && (
          <Stack>
            <SimpleGrid cols={2}>
              <Paper p="sm" withBorder radius="md"><Text size="xs" c="dimmed">Designs to restock</Text><Text fw={700} fz="xl">{base.items.length}</Text></Paper>
              <Paper p="sm" withBorder radius="md"><Text size="xs" c="dimmed">Estimated budget</Text><Text fw={700} fz="xl">{formatINR(base.total_estimated, { compact: true })}</Text></Paper>
            </SimpleGrid>
            <Table fz="sm" striped>
              <Table.Thead><Table.Tr><Table.Th>Design</Table.Th><Table.Th>Now</Table.Th><Table.Th ta="right">Qty</Table.Th><Table.Th ta="right">Total</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {base.items.map((i) => (
                  <Table.Tr key={i.design.id}>
                    <Table.Td>
                      <LabelCode>{i.design.label}</LabelCode> <Text span size="xs" c="dimmed">usual stock {i.usual_stock}</Text>
                      <Text size="xs" c="dimmed" lineClamp={2}>{i.reason}</Text>
                    </Table.Td>
                    <Table.Td><Stack gap={2}><StatusBadge status={i.status} size="xs" /><DemandBadge demand={i.demand_class} size="xs" /></Stack></Table.Td>
                    <Table.Td ta="right" className="num">{i.suggested_qty}</Table.Td>
                    <Table.Td ta="right" className="num">{formatINR(i.line_total, { compact: true })}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {base.items.length > 0 && <Button onClick={createPlan} loading={create.isPending}>Turn into a purchase plan</Button>}
          </Stack>
        )}
      </Drawer>
    </>
  );
}
