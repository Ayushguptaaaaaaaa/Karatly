import { Badge, Box, Button, Group, Paper, SimpleGrid, Skeleton, Stack, Text, ThemeIcon, UnstyledButton } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowRight, IconChevronRight, IconPlus, IconShoppingCart, IconSparkles } from "@tabler/icons-react";
import { motion } from "motion/react";
import { useNavigate } from "react-router";
import { errorMessage } from "../../api/client";
import { useCreatePlan, usePlans } from "../../api/hooks";
import type { PlanStatus, PlanSummary } from "../../api/types";
import { EmptyBox, ErrorState, Money, PageHeader } from "../../components/ui";
import { formatINR, formatRelative } from "../../lib/format";
import { useAuth } from "../../stores";

export const PLAN_STATUS: Record<PlanStatus, { label: string; color: string }> = {
  DRAFT: { label: "Draft", color: "gray" },
  SUBMITTED: { label: "Waiting for owner", color: "blue" },
  DECIDED: { label: "Approved", color: "teal" },
  RECEIVED: { label: "Received", color: "gold" },
};

const isOpen = (p: PlanSummary) => p.status === "DRAFT" || p.status === "SUBMITTED";

function PlanRow({ p, i }: { p: PlanSummary; i: number }) {
  const navigate = useNavigate();
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.04 }}>
      <UnstyledButton onClick={() => navigate(`/app/purchase-plans/${p.id}`)} w="100%">
        <Paper className="soft-card lift" p="md" radius="md">
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
              <ThemeIcon size={40} radius="xl" variant="light" color={p.source === "AI" ? "gold" : "gray"}>
                {p.source === "AI" ? <IconSparkles size={20} /> : <IconShoppingCart size={20} />}
              </ThemeIcon>
              <Box style={{ minWidth: 0 }}>
                <Group gap="xs">
                  <Text fw={700} truncate>{p.title}</Text>
                  <Badge color={PLAN_STATUS[p.status].color}>{PLAN_STATUS[p.status].label}</Badge>
                </Group>
                <Text size="xs" c="dimmed">
                  {isOpen(p) ? `${p.buying_count} of ${p.item_count} designs to buy` : `${p.approved_count} designs bought`}
                  {" · "}created {formatRelative(p.created_at)}
                </Text>
              </Box>
            </Group>
            <Group gap="lg" wrap="nowrap">
              <Box ta="right">
                <Text size="xs" c="dimmed">{isOpen(p) ? "Capital required" : "Approved"}</Text>
                <Text className="serif" fw={700} fz="lg">
                  <Money value={isOpen(p) ? p.total_estimated : p.total_approved} compact />
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

function CurrentPlanCard({ p }: { p: PlanSummary }) {
  const navigate = useNavigate();
  const owner = useAuth((s) => s.user?.role === "OWNER");
  const waiting = p.status === "SUBMITTED" || owner;
  return (
    <Paper className="soft-card" p="xl" radius="lg" mb="xl" style={{ borderLeft: "4px solid var(--mantine-color-gold-5)" }}>
      <Group justify="space-between" align="flex-start" wrap="wrap" gap="lg">
        <Box>
          <Group gap="xs" mb={6}>
            <Badge color={PLAN_STATUS[p.status].color}>{PLAN_STATUS[p.status].label}</Badge>
            {p.source === "AI" && <Badge variant="outline" color="gold">AI suggested ✨</Badge>}
          </Group>
          <Text className="serif" fw={700} fz={26}>{p.title}</Text>
          <Text size="sm" c="dimmed" mt={4}>
            {waiting
              ? "Check the quantities, change anything you like (0 = don't buy this month), then approve."
              : "Check the quantities, then send it to the owner for approval."}
          </Text>
        </Box>
        <SimpleGrid cols={2} spacing="xl">
          <Box>
            <Text size="xs" c="dimmed">Total capital required</Text>
            <Text className="serif" fw={800} fz={30} lh={1.15}>{formatINR(p.total_estimated, { compact: true })}</Text>
            {p.budget_limit ? <Text size="xs" c="dimmed">monthly budget {formatINR(p.budget_limit, { compact: true })}</Text> : null}
          </Box>
          <Box>
            <Text size="xs" c="dimmed">Designs to buy</Text>
            <Text fw={800} fz={30} lh={1.15}>{p.buying_count}<Text span size="sm" c="dimmed"> / {p.item_count}</Text></Text>
          </Box>
        </SimpleGrid>
      </Group>
      <Group justify="flex-end" mt="lg">
        <Button size="md" rightSection={<IconArrowRight size={18} />} onClick={() => navigate(`/app/purchase-plans/${p.id}`)}>
          {waiting ? "Review & approve" : "Open plan"}
        </Button>
      </Group>
    </Paper>
  );
}

export default function PlansListPage({ embedded = false }: { embedded?: boolean }) {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = usePlans();
  const create = useCreatePlan();

  const createPlan = () =>
    create.mutateAsync()
      .then((p) => navigate(`/app/purchase-plans/${p.id}`))
      .catch((e) => notifications.show({ color: "orange", message: errorMessage(e) }));

  const open = (data ?? []).filter(isOpen);
  const current = open[0];
  const olderOpen = open.slice(1);
  const history = (data ?? []).filter((p) => !isOpen(p));

  return (
    <>
      {!embedded && (
        <PageHeader title="Purchase plan" subtitle="The AI suggests what to buy. You change any quantity and approve." />
      )}
      {isError && <ErrorState onRetry={() => refetch()} />}
      {isLoading && <Stack>{[1, 2].map((i) => <Skeleton key={i} h={120} radius="md" />)}</Stack>}

      {data && current && <CurrentPlanCard p={current} />}
      {data && !current && (
        <EmptyBox
          icon={<IconShoppingCart size={30} />}
          title="No plan waiting"
          text="Create this month's plan from your current stock and sales. Running AI insights also creates it."
          action={<Button onClick={createPlan} loading={create.isPending} leftSection={<IconPlus size={16} />}>Create this month's plan</Button>}
          secondary={<Button variant="default" onClick={() => navigate("/app/insights")} leftSection={<IconSparkles size={16} />}>Generate AI insights</Button>}
        />
      )}

      {olderOpen.length > 0 && (
        <Box mb="xl">
          <Text fw={700}>Older open plans</Text>
          <Text size="xs" c="dimmed" mb="sm">These have your edits, so they were kept. Approve or delete them.</Text>
          <Stack gap="sm">{olderOpen.map((p, i) => <PlanRow key={p.id} p={p} i={i} />)}</Stack>
        </Box>
      )}

      {history.length > 0 && (
        <Box mt="xl">
          <Text fw={700} mb="sm">Past plans</Text>
          <Stack gap="sm">{history.map((p, i) => <PlanRow key={p.id} p={p} i={i} />)}</Stack>
        </Box>
      )}
    </>
  );
}
