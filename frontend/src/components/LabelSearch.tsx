import { ActionIcon, Box, Group, Kbd, Text, UnstyledButton } from "@mantine/core";
import { Spotlight, spotlight } from "@mantine/spotlight";
import { useDebouncedValue } from "@mantine/hooks";
import { IconMinus, IconPlus, IconSearch } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useDesignSearch } from "../api/hooks";
import { useUi } from "../stores";
import { LabelCode, PhotoThumb, StatusBadge } from "./ui";

export function SearchTrigger({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <ActionIcon variant="subtle" size="lg" aria-label="Search designs" onClick={() => spotlight.open()}>
        <IconSearch size={20} />
      </ActionIcon>
    );
  }
  return (
    <UnstyledButton
      onClick={() => spotlight.open()}
      aria-label="Search designs"
      style={{
        border: "1px solid var(--jaa-border)", borderRadius: 12, padding: "7px 12px", width: 360, maxWidth: "100%",
        background: "var(--jaa-surface)",
      }}
    >
      <Group justify="space-between" wrap="nowrap">
        <Group gap={8} wrap="nowrap">
          <IconSearch size={16} color="var(--jaa-muted)" />
          <Text size="sm" c="dimmed">
            Search label or design…
          </Text>
        </Group>
        <Kbd size="xs">Ctrl K</Kbd>
      </Group>
    </UnstyledButton>
  );
}

export function LabelSearchSpotlight() {
  const [query, setQuery] = useState("");
  const [debounced] = useDebouncedValue(query, 200);
  const { data } = useDesignSearch(debounced);
  const navigate = useNavigate();
  const openQuick = useUi((s) => s.openQuickStock);

  return (
    <Spotlight.Root query={query} onQueryChange={setQuery} shortcut={["mod + K", "/"]} scrollable maxHeight={460}>
      <Spotlight.Search placeholder="Search label or design name…" leftSection={<IconSearch size={18} />} />
      <Spotlight.ActionsList>
        {(data ?? []).map((d) => (
          <Spotlight.Action key={d.id} onClick={() => navigate(`/app/designs/${d.id}`)}>
            <Group wrap="nowrap" w="100%" gap="sm">
              <PhotoThumb url={d.photo_url} size={36} />
              <Box style={{ flex: 1, minWidth: 0 }}>
                <LabelCode>{d.label}</LabelCode>
                <Text size="xs" c="dimmed" truncate>
                  {d.name ?? "—"} · {d.category_name}
                </Text>
              </Box>
              <StatusBadge status={d.status} size="xs" />
              <Text fw={700} className="num" w={32} ta="right">
                {d.current_stock}
              </Text>
              <ActionIcon
                component="span"
                variant="light"
                color="red"
                radius="xl"
                aria-label="Record sale"
                onClick={(e) => {
                  e.stopPropagation();
                  spotlight.close();
                  openQuick("OUT", d.id);
                }}
              >
                <IconMinus size={14} />
              </ActionIcon>
              <ActionIcon
                component="span"
                variant="light"
                color="teal"
                radius="xl"
                aria-label="Add stock"
                onClick={(e) => {
                  e.stopPropagation();
                  spotlight.close();
                  openQuick("IN", d.id);
                }}
              >
                <IconPlus size={14} />
              </ActionIcon>
            </Group>
          </Spotlight.Action>
        ))}
        {data && data.length === 0 && <Spotlight.Empty>No design found</Spotlight.Empty>}
      </Spotlight.ActionsList>
    </Spotlight.Root>
  );
}
