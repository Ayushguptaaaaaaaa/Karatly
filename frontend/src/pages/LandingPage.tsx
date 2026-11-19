import { Box, Group, SimpleGrid, Stack, Text, ThemeIcon, Title, UnstyledButton } from "@mantine/core";
import { IconBrain, IconChartLine, IconChevronRight, IconCrown, IconMessageChatbot, IconShield } from "@tabler/icons-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";

const SPARKLES = [
  { top: "12%", left: "14%", d: 0 }, { top: "22%", left: "78%", d: 1.2 }, { top: "38%", left: "8%", d: 2.1 },
  { top: "55%", left: "70%", d: 0.6 }, { top: "68%", left: "22%", d: 3 }, { top: "80%", left: "84%", d: 1.8 },
  { top: "30%", left: "45%", d: 2.6 }, { top: "88%", left: "40%", d: 0.3 }, { top: "8%", left: "58%", d: 3.4 },
  { top: "62%", left: "48%", d: 4.2 }, { top: "46%", left: "90%", d: 2.2 }, { top: "18%", left: "30%", d: 5 },
];

export function BrandPanel({ slim = false }: { slim?: boolean }) {
  return (
    <Box
      style={{
        position: "relative", overflow: "hidden", color: "#f3efe6",
        background: "radial-gradient(1200px 600px at 20% 10%, rgba(207,166,54,.22), transparent 60%), radial-gradient(800px 500px at 90% 90%, rgba(207,166,54,.12), transparent 60%), #16140f",
      }}
      p={{ base: 28, sm: 48, md: 64 }}
      h="100%"
      mih={{ base: slim ? 200 : 300, md: "100vh" }}
    >
      {SPARKLES.map((s, i) => (
        <span key={i} className="sparkle" style={{ top: s.top, left: s.left, animationDelay: `${s.d}s` }} />
      ))}
      <Stack justify="center" h="100%" gap="xl" style={{ position: "relative", maxWidth: 560 }}>
        <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4 }}>
          <Group gap="md" wrap="nowrap">
            <img src="/gem.svg" alt="" width={56} height={56} />
            <Title order={1} className="gold-text" fz={{ base: 32, sm: 44 }} lh={1.1}>
              Jeweler AI Accountant
            </Title>
          </Group>
          <Text mt="md" fz={{ base: "md", sm: "lg" }} c="rgba(243,239,230,.8)">
            Your AI accountant &amp; inventory partner for jewellery.
          </Text>
        </motion.div>
        {!slim && (
          <Stack gap="md">
            {[
              { icon: IconChartLine, text: "Know every label's stock, live" },
              { icon: IconBrain, text: "AI insights & purchase plans in minutes" },
              { icon: IconMessageChatbot, text: "Ask questions in plain language" },
            ].map((f, i) => (
              <motion.div key={f.text} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 + i * 0.1 }}>
                <Group gap="sm" wrap="nowrap">
                  <ThemeIcon radius="xl" size={36} variant="light" color="gold">
                    <f.icon size={18} />
                  </ThemeIcon>
                  <Text c="rgba(243,239,230,.9)">{f.text}</Text>
                </Group>
              </motion.div>
            ))}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

function RoleCard({ icon, color, title, subtitle, onClick, delay }: {
  icon: ReactNode; color: string; title: string; subtitle: string; onClick: () => void; delay: number;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay }}>
      <UnstyledButton
        onClick={onClick}
        className="soft-card lift"
        w="100%"
        p="lg"
        style={{ borderRadius: 20, display: "block" }}
        aria-label={`Sign in as ${title}`}
      >
        <Group wrap="nowrap" justify="space-between">
          <Group wrap="nowrap" gap="md">
            <ThemeIcon size={56} radius="xl" color={color} variant="light">
              {icon}
            </ThemeIcon>
            <Box>
              <Text fw={700} fz="xl" className="serif">
                {title}
              </Text>
              <Text size="sm" c="dimmed">
                {subtitle}
              </Text>
            </Box>
          </Group>
          <IconChevronRight color="var(--jaa-muted)" />
        </Group>
      </UnstyledButton>
    </motion.div>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();
  return (
    <SimpleGrid cols={{ base: 1, md: 2 }} spacing={0} mih="100vh">
      <BrandPanel />
      <Stack justify="center" p={{ base: 24, sm: 48, md: 72 }} style={{ background: "var(--jaa-page)" }}>
        <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4 }}>
          <Title order={2} fz={34}>
            Welcome back
          </Title>
          <Text c="dimmed" mt={4} mb="xl">
            Choose how you want to sign in
          </Text>
        </motion.div>
        <Stack gap="md" maw={480}>
          <RoleCard
            icon={<IconCrown size={28} />}
            color="gold"
            title="Owner"
            subtitle="Full access, approvals and AI insights"
            onClick={() => navigate("/login/owner")}
            delay={0.15}
          />
          <RoleCard
            icon={<IconShield size={28} />}
            color="blue"
            title="Admin"
            subtitle="Manage stock, reports and purchase plans"
            onClick={() => navigate("/login/admin")}
            delay={0.23}
          />
        </Stack>
        <Text size="xs" c="dimmed" mt="xl">
          Demo version · Data stays on this computer
        </Text>
      </Stack>
    </SimpleGrid>
  );
}
