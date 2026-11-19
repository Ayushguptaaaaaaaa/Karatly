import {
  ActionIcon,
  AppShell,
  Avatar,
  Badge,
  Box,
  Burger,
  Button,
  Drawer,
  Group,
  Loader,
  Menu,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import {
  IconArrowsExchange,
  IconChartBar,
  IconChevronsLeft,
  IconChevronsRight,
  IconCrown,
  IconDiamond,
  IconDots,
  IconLayoutDashboard,
  IconLogout,
  IconMoon,
  IconPlusMinus,
  IconSettings,
  IconShield,
  IconShoppingCart,
  IconSparkles,
  IconSun,
} from "@tabler/icons-react";
import { motion } from "motion/react";
import { Suspense, useCallback } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { api } from "../api/client";
import { useDashboard, useInsightsLatest, useRunningInsights, useSettings } from "../api/hooks";
import { notifyInsightsReady, useLiveEvents } from "../api/sse";
import { LabelSearchSpotlight, SearchTrigger } from "../components/LabelSearch";
import { QuickStockDrawer } from "../components/stock";
import { CardSkeleton, LiveIndicator } from "../components/ui";
import { milestone } from "../lib/confetti";
import { useAuth, useUi } from "../stores";

const NAV = [
  { to: "/app", label: "Dashboard", icon: IconLayoutDashboard, exact: true },
  { to: "/app/inventory", label: "Inventory", icon: IconDiamond },
  { to: "/app/stock", label: "Stock", icon: IconArrowsExchange },
  { to: "/app/insights", label: "Insights", icon: IconSparkles },
  { to: "/app/purchase-plans", label: "Purchase Plans", icon: IconShoppingCart },
  { to: "/app/reports", label: "Reports", icon: IconChartBar },
  { to: "/app/settings", label: "Settings", icon: IconSettings },
];

function useActive() {
  const { pathname } = useLocation();
  return (to: string, exact?: boolean) =>
    exact ? pathname === to : pathname === to || pathname.startsWith(`${to}/`) || (to === "/app/inventory" && pathname.startsWith("/app/designs"));
}

export function RoleBadge() {
  const user = useAuth((s) => s.user);
  if (!user) return null;
  const owner = user.role === "OWNER";
  return (
    <Badge color={owner ? "gold" : "blue"} variant="light" leftSection={owner ? <IconCrown size={12} /> : <IconShield size={12} />}>
      {owner ? "Owner" : "Admin"}
    </Badge>
  );
}

function Logo({ collapsed }: { collapsed?: boolean }) {
  const { data } = useSettings();
  return (
    <Group gap={10} wrap="nowrap" px={collapsed ? 0 : 4} justify={collapsed ? "center" : "flex-start"}>
      <img src="/gem.svg" alt="" width={30} height={30} />
      {!collapsed && (
        <Box style={{ minWidth: 0 }}>
          <Text className="serif" fw={700} size="lg" lh={1.1} truncate>
            {data?.shop_name ?? "Jeweler"}
          </Text>
          <Text size="xs" c="dimmed">
            AI Accountant
          </Text>
        </Box>
      )}
    </Group>
  );
}

function NavItems({ collapsed, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const navigate = useNavigate();
  const isActive = useActive();
  const { data: dash } = useDashboard();
  const { data: running } = useRunningInsights();
  const { data: latest } = useInsightsLatest();
  const seen = useUi((s) => s.insightsSeenRunId);
  const owner = useAuth((s) => s.user?.role === "OWNER");

  const badge = (to: string) => {
    if (to === "/app/insights") {
      if (running) return <Loader size={12} />;
      if (latest && latest.id !== seen) return <Badge size="xs" color="gold" variant="filled">New</Badge>;
    }
    if (to === "/app/purchase-plans" && owner && dash?.pending_approvals) {
      return <Badge size="xs" color="red" variant="filled" circle>{dash.pending_approvals}</Badge>;
    }
    return null;
  };

  return (
    <Stack gap={4}>
      {NAV.map((n) => {
        const active = isActive(n.to, n.exact);
        const I = n.icon;
        const item = (
          <NavLink
            key={n.to}
            href={n.to}
            active={active}
            label={collapsed ? undefined : n.label}
            leftSection={<I size={20} stroke={1.7} />}
            rightSection={collapsed ? undefined : badge(n.to)}
            onClick={(e) => {
              e.preventDefault();
              navigate(n.to);
              onNavigate?.();
            }}
            variant="light"
            styles={{
              root: {
                borderRadius: 10,
                borderLeft: active ? "3px solid var(--mantine-color-gold-6)" : "3px solid transparent",
                justifyContent: collapsed ? "center" : undefined,
                paddingInline: collapsed ? 0 : undefined,
              },
              label: { fontWeight: active ? 650 : 500 },
              section: collapsed ? { marginInlineEnd: 0 } : undefined,
            }}
          />
        );
        return collapsed ? (
          <Tooltip key={n.to} label={n.label} position="right">
            <Box>{item}</Box>
          </Tooltip>
        ) : (
          item
        );
      })}
    </Stack>
  );
}

function UserMenu() {
  const { user, clear } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <Menu position="bottom-end" width={200} shadow="md">
      <Menu.Target>
        <UnstyledButton aria-label="Account menu">
          <Avatar color={user.role === "OWNER" ? "gold" : "blue"} radius="xl">
            {user.display_name[0]}
          </Avatar>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>
          Signed in as {user.display_name} ({user.username})
        </Menu.Label>
        <Menu.Item leftSection={<IconSettings size={16} />} onClick={() => navigate("/app/settings")}>
          Settings
        </Menu.Item>
        <Menu.Item
          color="red"
          leftSection={<IconLogout size={16} />}
          onClick={async () => {
            try {
              await api("/auth/logout", { method: "POST" });
            } catch {
              /* ignore */
            }
            clear();
            navigate("/");
          }}
        >
          Log out
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function ThemeToggle() {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const dark = colorScheme === "dark";
  return (
    <Tooltip label={dark ? "Light mode" : "Dark mode"}>
      <ActionIcon variant="subtle" size="lg" aria-label="Toggle colour scheme" onClick={() => setColorScheme(dark ? "light" : "dark")}>
        {dark ? <IconSun size={20} /> : <IconMoon size={20} />}
      </ActionIcon>
    </Tooltip>
  );
}

function MobileTabBar({ onMore }: { onMore: () => void }) {
  const navigate = useNavigate();
  const isActive = useActive();
  const openQuick = useUi((s) => s.openQuickStock);
  const tabs = [
    { to: "/app", label: "Home", icon: IconLayoutDashboard, exact: true },
    { to: "/app/inventory", label: "Inventory", icon: IconDiamond },
    null,
    { to: "/app/insights", label: "Insights", icon: IconSparkles },
  ];
  return (
    <Box
      className="no-print"
      style={{
        position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 150, height: 64,
        paddingBottom: "env(safe-area-inset-bottom)", background: "var(--jaa-surface)",
        borderTop: "1px solid var(--jaa-border)", display: "flex", alignItems: "center", justifyContent: "space-around",
      }}
    >
      {tabs.map((t) =>
        t === null ? (
          <ActionIcon
            key="fab"
            size={54}
            radius="xl"
            variant="gradient"
            gradient={{ from: "gold.4", to: "gold.8", deg: 135 }}
            aria-label="Quick stock"
            onClick={() => openQuick("OUT")}
            style={{ marginTop: -26, boxShadow: "0 6px 18px rgba(157,122,24,.4)" }}
          >
            <IconPlusMinus size={26} />
          </ActionIcon>
        ) : (
          <UnstyledButton key={t.to} onClick={() => navigate(t.to)} style={{ textAlign: "center", minWidth: 60 }} aria-label={t.label}>
            <t.icon size={22} color={isActive(t.to, t.exact) ? "var(--mantine-color-gold-7)" : "var(--jaa-muted)"} />
            <Text size="10px" fw={isActive(t.to, t.exact) ? 700 : 500} c={isActive(t.to, t.exact) ? "gold.7" : "dimmed"}>
              {t.label}
            </Text>
          </UnstyledButton>
        ),
      )}
      <UnstyledButton onClick={onMore} style={{ textAlign: "center", minWidth: 60 }} aria-label="More">
        <IconDots size={22} color="var(--jaa-muted)" />
        <Text size="10px" c="dimmed">
          More
        </Text>
      </UnstyledButton>
    </Box>
  );
}

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useMediaQuery("(max-width: 48em)");
  const [drawer, { open: openDrawer, close: closeDrawer }] = useDisclosure(false);
  const collapsed = useUi((s) => s.navCollapsed);
  const toggleNav = useUi((s) => s.toggleNav);
  const openQuick = useUi((s) => s.openQuickStock);

  const onReady = useCallback(() => {
    milestone("first_insights");
    if (!window.location.pathname.startsWith("/app/insights")) notifyInsightsReady(() => navigate("/app/insights"));
  }, [navigate]);
  useLiveEvents(onReady);

  const navWidth = collapsed ? 80 : 260;
  const hideFab = ["/app/stock", "/app/insights", "/app/purchase-plans/"].some((p) => location.pathname.startsWith(p));

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{ width: navWidth, breakpoint: "sm", collapsed: { mobile: true } }}
      padding={{ base: "md", sm: "lg" }}
    >
      <AppShell.Header className="no-print" style={{ backdropFilter: "blur(8px)", background: "color-mix(in srgb, var(--jaa-surface) 85%, transparent)" }}>
        <Group h="100%" px={{ base: "sm", sm: "lg" }} justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            {isMobile && <Burger opened={drawer} onClick={openDrawer} size="sm" aria-label="Open menu" />}
            {isMobile ? <Logo /> : <SearchTrigger />}
          </Group>
          <Group gap={6} wrap="nowrap">
            {isMobile && <SearchTrigger compact />}
            {!isMobile && <RoleBadge />}
            <ThemeToggle />
            <UserMenu />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" className="no-print" style={{ background: "var(--jaa-surface)", borderRight: "1px solid var(--jaa-border)" }}>
        <AppShell.Section mb="lg">
          <Logo collapsed={collapsed} />
        </AppShell.Section>
        <AppShell.Section grow component={ScrollArea}>
          <NavItems collapsed={collapsed} />
        </AppShell.Section>
        <AppShell.Section>
          <Stack gap="xs" align={collapsed ? "center" : "stretch"}>
            <LiveIndicator compact={collapsed} />
            <Tooltip label={collapsed ? "Expand menu" : "Collapse menu"}>
              <ActionIcon variant="subtle" onClick={toggleNav} aria-label="Collapse menu" style={{ alignSelf: collapsed ? "center" : "flex-end" }}>
                {collapsed ? <IconChevronsRight size={18} /> : <IconChevronsLeft size={18} />}
              </ActionIcon>
            </Tooltip>
          </Stack>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main style={{ paddingBottom: isMobile ? 90 : undefined }}>
        <Box maw={1480} mx="auto">
          <Suspense fallback={<Stack><CardSkeleton h={60} /><CardSkeleton h={240} /></Stack>}>
            <motion.div key={location.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <Outlet />
            </motion.div>
          </Suspense>
        </Box>
      </AppShell.Main>

      {isMobile ? (
        <MobileTabBar onMore={openDrawer} />
      ) : (
        !hideFab && (
          <Button
            className="no-print"
            onClick={() => openQuick("OUT")}
            leftSection={<IconPlusMinus size={18} />}
            radius="xl"
            size="md"
            variant="gradient"
            gradient={{ from: "gold.5", to: "gold.8", deg: 135 }}
            style={{ position: "fixed", right: 28, bottom: 28, zIndex: 120, boxShadow: "0 8px 24px rgba(157,122,24,.35)" }}
          >
            Quick stock
          </Button>
        )
      )}

      <Drawer opened={drawer} onClose={closeDrawer} size={280} title={<Logo />} padding="md">
        <Stack justify="space-between" h="calc(100% - 20px)">
          <NavItems onNavigate={closeDrawer} />
          <Group justify="space-between">
            <LiveIndicator />
            <RoleBadge />
          </Group>
        </Stack>
      </Drawer>
      <QuickStockDrawer />
      <LabelSearchSpotlight />
    </AppShell>
  );
}
