import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Group,
  Paper,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
  type MantineColor,
} from "@mantine/core";
import { Sparkline } from "@mantine/charts";
import { useReducedMotion } from "@mantine/hooks";
import {
  IconAlertTriangle,
  IconArrowDownRight,
  IconArrowUpRight,
  IconChevronRight,
  IconCircle,
  IconCircleDot,
  IconCoin,
  IconDiamond,
  IconDroplet,
  IconHeart,
  IconLink,
  IconPoint,
  IconRefresh,
  IconSparkles,
  IconStack2,
  type Icon,
} from "@tabler/icons-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { DemandClass, StockStatus } from "../api/types";
import { DEMAND_META, STATUS_META } from "../lib/constants";
import { formatINR, formatNumber, formatPct } from "../lib/format";
import { useUi } from "../stores";

// ---- icons -------------------------------------------------------------------------------
export const CATEGORY_ICON: Record<string, Icon> = {
  necklace: IconDiamond,
  earring: IconDroplet,
  ring: IconCircleDot,
  bangle: IconCircle,
  bracelet: IconLink,
  anklet: IconLink,
  chain: IconLink,
  pendant: IconHeart,
  nosepin: IconPoint,
  set: IconStack2,
  coin: IconCoin,
  other: IconSparkles,
};

export function CategoryIcon({ icon, size = 20 }: { icon: string; size?: number }) {
  const I = CATEGORY_ICON[icon] ?? IconSparkles;
  return <I size={size} stroke={1.6} />;
}

// ---- layout bits --------------------------------------------------------------------------
export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <Group justify="space-between" align="flex-end" mb="lg" gap="md" wrap="wrap">
      <Box style={{ minWidth: 0 }}>
        {eyebrow}
        <Title order={1} fz={{ base: 26, sm: 32 }} lh={1.15}>
          {title}
        </Title>
        {subtitle && (
          <Text c="dimmed" mt={4} size="sm">
            {subtitle}
          </Text>
        )}
      </Box>
      {actions && <Group gap="sm">{actions}</Group>}
    </Group>
  );
}

export function SectionCard({
  title, icon, actions, children, className, padding = "lg", id,
}: { title?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; padding?: string; id?: string }) {
  return (
    <Card className={`soft-card ${className ?? ""}`} withBorder={false} padding={padding} id={id}>
      {(title || actions) && (
        <Group justify="space-between" mb="md" wrap="nowrap" gap="sm">
          <Group gap={10} wrap="nowrap" style={{ minWidth: 0 }}>
            {icon && (
              <ThemeIcon variant="light" radius="xl" size={34} color="gold">
                {icon}
              </ThemeIcon>
            )}
            <Text fw={650} size="md" truncate>
              {title}
            </Text>
          </Group>
          {actions}
        </Group>
      )}
      {children}
    </Card>
  );
}

export function EmptyBox({
  icon, title, text, action, secondary, children,
}: { icon?: ReactNode; title: string; text?: ReactNode; action?: ReactNode; secondary?: ReactNode; children?: ReactNode }) {
  return (
    <Paper className="soft-card" p={{ base: "lg", sm: 40 }} radius="lg">
      <Stack align="center" gap="sm" ta="center" maw={520} mx="auto">
        <Center
          w={84}
          h={84}
          style={{ borderRadius: "50%", background: "radial-gradient(circle, rgba(207,166,54,.22), rgba(207,166,54,.05) 70%)" }}
        >
          <ThemeIcon size={56} radius="xl" variant="light" color="gold">
            {icon ?? <IconSparkles size={30} />}
          </ThemeIcon>
        </Center>
        <Title order={3}>{title}</Title>
        {text && (
          <Text c="dimmed" size="sm">
            {text}
          </Text>
        )}
        {(action || secondary) && (
          <Group mt="xs" justify="center">
            {action}
            {secondary}
          </Group>
        )}
        {children}
      </Stack>
    </Paper>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <Paper className="soft-card" p="lg" radius="md">
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <ThemeIcon color="red" variant="light" radius="xl">
            <IconAlertTriangle size={18} />
          </ThemeIcon>
          <Text size="sm">{message ?? "Couldn't load this."}</Text>
        </Group>
        {onRetry && (
          <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} onClick={onRetry}>
            Retry
          </Button>
        )}
      </Group>
    </Paper>
  );
}

export function CardSkeleton({ h = 120 }: { h?: number }) {
  return <Skeleton height={h} radius="md" />;
}

// ---- numbers ------------------------------------------------------------------------------
export function CountUp({ value, format = "number", duration = 700 }: { value: number; format?: "number" | "inr" | "inr-compact"; duration?: number }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(value);
  const prev = useRef(value);
  useEffect(() => {
    if (reduce) {
      setShown(value);
      prev.current = value;
      return;
    }
    const from = prev.current;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - k, 3);
      setShown(from + (value - from) * eased);
      if (k < 1) raf = requestAnimationFrame(tick);
      else prev.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduce]);
  const v = Math.round(shown);
  const text = format === "inr" ? formatINR(v) : format === "inr-compact" ? formatINR(v, { compact: true }) : formatNumber(v);
  return <span className="num">{text}</span>;
}

export function DeltaChip({ pct, suffix = "vs last period" }: { pct: number | null | undefined; suffix?: string }) {
  if (pct === null || pct === undefined) return null;
  const up = pct >= 0;
  return (
    <Badge
      variant="light"
      color={up ? "teal" : "red"}
      leftSection={up ? <IconArrowUpRight size={12} /> : <IconArrowDownRight size={12} />}
      title={suffix}
    >
      {formatPct(pct)}
    </Badge>
  );
}

export function KpiCard({
  icon, label, value, format = "number", sub, delta, spark, color = "gold", onClick, valueColor,
}: {
  icon: ReactNode; label: string; value: number; format?: "number" | "inr" | "inr-compact"; sub?: ReactNode;
  delta?: number | null; spark?: number[]; color?: MantineColor; onClick?: () => void; valueColor?: string;
}) {
  return (
    <Card
      className="soft-card lift"
      withBorder={false}
      onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default", minWidth: 220 }}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => onClick && (e.key === "Enter" || e.key === " ") && onClick()}
    >
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <ThemeIcon variant="light" color={color} radius="xl" size={40}>
          {icon}
        </ThemeIcon>
        <Group gap={6}>
          {delta !== undefined && <DeltaChip pct={delta} />}
          {onClick && <IconChevronRight size={16} color="var(--jaa-muted)" />}
        </Group>
      </Group>
      <Text c="dimmed" size="sm" mt="md" fw={500}>
        {label}
      </Text>
      <Text className="serif" fz={30} fw={700} lh={1.2} c={valueColor}>
        <CountUp value={value} format={format} />
      </Text>
      {sub && (
        <Text size="xs" c="dimmed" mt={4}>
          {sub}
        </Text>
      )}
      {spark && spark.some((v) => v > 0) && (
        <Sparkline mt="sm" h={36} data={spark} curveType="natural" color={`${color}.6`} fillOpacity={0.25} strokeWidth={2} />
      )}
    </Card>
  );
}

// ---- badges ------------------------------------------------------------------------------
export function StatusBadge({ status, size = "sm" }: { status: StockStatus; size?: string }) {
  const m = STATUS_META[status];
  const I = m.icon;
  return (
    <Badge color={m.color} variant="light" size={size} leftSection={<I size={12} />}>
      {m.label}
    </Badge>
  );
}

export function DemandBadge({ demand, size = "sm" }: { demand: DemandClass; size?: string }) {
  const m = DEMAND_META[demand];
  const I = m.icon;
  return (
    <Badge color={m.color} variant="outline" size={size} leftSection={<I size={12} />}>
      {m.label}
    </Badge>
  );
}

export function LabelCode({ children, size = "sm" }: { children: ReactNode; size?: string }) {
  return (
    <Text span className="label-code" size={size}>
      {children}
    </Text>
  );
}

export function PhotoThumb({ url, icon = "other", size = 40, radius = 10 }: { url: string | null | undefined; icon?: string; size?: number; radius?: number }) {
  if (url) {
    return (
      <img
        src={url}
        alt=""
        loading="lazy"
        style={{ width: size, height: size, borderRadius: radius, objectFit: "cover", flexShrink: 0, border: "1px solid var(--jaa-border)" }}
      />
    );
  }
  return (
    <Center
      w={size}
      h={size}
      style={{ borderRadius: radius, background: "var(--mantine-color-gold-light)", color: "var(--mantine-color-gold-7)", flexShrink: 0 }}
    >
      <CategoryIcon icon={icon} size={Math.round(size * 0.5)} />
    </Center>
  );
}

export function Money({ value, compact, decimals }: { value: number | null | undefined; compact?: boolean; decimals?: 0 | 2 }) {
  const full = formatINR(value, { decimals: 2 });
  return (
    <Tooltip label={full} disabled={!compact}>
      <span className="num">{formatINR(value, { compact, decimals })}</span>
    </Tooltip>
  );
}

export function LiveIndicator({ compact = false }: { compact?: boolean }) {
  const live = useUi((s) => s.live);
  const last = useUi((s) => s.lastUpdatedAt);
  const [, force] = useState(0);
  useEffect(() => {
    const t = setInterval(() => force((x) => x + 1), 15000);
    return () => clearInterval(t);
  }, []);
  const ok = live === "connected";
  const ago = last ? Math.round((Date.now() - last) / 1000) : null;
  const when = ago === null ? "" : ago < 10 ? " · updated just now" : ago < 60 ? ` · updated ${ago}s ago` : ` · updated ${Math.round(ago / 60)}m ago`;
  return (
    <Tooltip label={ok ? "Changes appear instantly" : "Reconnecting to live updates…"}>
      <Group gap={8} wrap="nowrap">
        <span className={`live-dot ${ok ? "" : "offline"}`} />
        {!compact && (
          <Text size="xs" c="dimmed">
            {ok ? `Live${when}` : "Offline – retrying"}
          </Text>
        )}
      </Group>
    </Tooltip>
  );
}

export function IconBtn({ label, children, onClick, color, variant = "subtle", size = "lg", disabled }: {
  label: string; children: ReactNode; onClick?: () => void; color?: string; variant?: string; size?: string; disabled?: boolean;
}) {
  return (
    <Tooltip label={label}>
      <ActionIcon aria-label={label} onClick={onClick} color={color} variant={variant} size={size} disabled={disabled}>
        {children}
      </ActionIcon>
    </Tooltip>
  );
}
