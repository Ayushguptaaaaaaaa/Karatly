import { Alert, Anchor, Badge, Box, Button, Checkbox, Group, PasswordInput, SimpleGrid, Stack, Text, TextInput, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { IconArrowLeft, IconCrown, IconInfoCircle, IconShield } from "@tabler/icons-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { LoginResponse, Role } from "../api/types";
import { useAuth } from "../stores";
import { BrandPanel } from "./LandingPage";

export default function LoginPage({ role }: { role: Role }) {
  const owner = role === "OWNER";
  const word = owner ? "Owner" : "Admin";
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuth((s) => s.setAuth);
  const [error, setError] = useState<{ message: string; mismatch?: boolean } | null>(null);
  const [shakeKey, setShakeKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const showHint = import.meta.env.VITE_SHOW_DEMO_HINT === "true";
  const demo = owner ? "owner" : "admin";

  const form = useForm({
    initialValues: { username: "", password: "", remember: true },
    validate: {
      username: (v) => (v.trim() ? null : "Please enter your username"),
      password: (v) => (v ? null : "Please enter your password"),
    },
  });

  const submit = form.onSubmit(async (v) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<LoginResponse>("/auth/login", {
        method: "POST",
        body: { username: v.username.trim(), password: v.password, role },
      });
      setAuth(res.access_token, res.expires_at, res.user, v.remember);
      notifications.show({ color: "gold", title: `Welcome, ${res.user.display_name} ✨`, message: "You're signed in." });
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from.startsWith("/app") ? from : "/app", { replace: true });
    } catch (e) {
      const err = e as ApiError;
      setError({ message: err.message, mismatch: err.code === "ROLE_MISMATCH" });
      setShakeKey((k) => k + 1);
    } finally {
      setLoading(false);
    }
  });

  return (
    <SimpleGrid cols={{ base: 1, md: 2 }} spacing={0} mih="100vh">
      <BrandPanel slim />
      <Stack justify="center" p={{ base: 24, sm: 48, md: 72 }} style={{ background: "var(--jaa-page)" }}>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Box maw={420} w="100%">
            <Anchor component={Link} to="/" size="sm" c="dimmed">
              <Group gap={4}>
                <IconArrowLeft size={14} /> Back
              </Group>
            </Anchor>
            <Badge
              mt="lg"
              size="lg"
              color={owner ? "gold" : "blue"}
              leftSection={owner ? <IconCrown size={14} /> : <IconShield size={14} />}
            >
              {word} login
            </Badge>
            <Title order={2} mt="sm" fz={32}>
              Sign in as {word}
            </Title>
            <Text c="dimmed" size="sm" mb="lg">
              {owner ? "Full access to your shop, AI insights and approvals." : "Manage stock, reports and purchase plans."}
            </Text>
            <form onSubmit={submit} noValidate>
              <Stack gap="md">
                <TextInput label="Username" autoComplete="username" size="md" data-autofocus autoFocus {...form.getInputProps("username")} />
                <PasswordInput label="Password" autoComplete="current-password" size="md" {...form.getInputProps("password")} />
                <Checkbox label="Remember me on this computer" {...form.getInputProps("remember", { type: "checkbox" })} />
                {error && (
                  <div key={shakeKey} className="shake">
                    <Alert color="red" variant="light" icon={<IconInfoCircle size={18} />}>
                      {error.message}
                      {error.mismatch && (
                        <>
                          {" "}
                          <Anchor component={Link} to={owner ? "/login/admin" : "/login/owner"} size="sm">
                            Switch to {owner ? "Admin" : "Owner"} login
                          </Anchor>
                        </>
                      )}
                    </Alert>
                  </div>
                )}
                <Button type="submit" size="md" loading={loading} fullWidth color="gold">
                  Sign in
                </Button>
                {showHint && (
                  <Text size="xs" c="dimmed" ta="center">
                    Demo login: <b>{demo}</b> / <b>{demo}</b> ·{" "}
                    <Anchor size="xs" component="button" type="button" onClick={() => form.setValues({ username: demo, password: demo })}>
                      Fill
                    </Anchor>
                  </Text>
                )}
              </Stack>
            </form>
          </Box>
        </motion.div>
      </Stack>
    </SimpleGrid>
  );
}
