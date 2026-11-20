import { ActionIcon, Autocomplete, Button, Group, Modal, Select, SimpleGrid, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconPlus } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import {
  useCustomers, useDealers, useFacets, useSaveCustomer, useSaveDealer,
  type Customer, type CustomerInput, type Dealer, type DealerInput,
} from "../api/sales";

type Kind = "customer" | "dealer";
const COUNTRIES = ["India", "United Arab Emirates", "United States", "United Kingdom", "Singapore", "Canada", "Australia", "Nepal"];

/** Add or edit a customer / dealer. */
export function ContactModal({ kind, opened, onClose, initial, onSaved }: {
  kind: Kind; opened: boolean; onClose: () => void; initial?: Partial<Customer & Dealer> | null;
  onSaved?: (c: Customer | Dealer) => void;
}) {
  const saveC = useSaveCustomer();
  const saveD = useSaveDealer();
  const { data: f } = useFacets();
  const [v, setV] = useState<CustomerInput & DealerInput>({});
  useEffect(() => {
    if (opened) setV({ country: "India", ...(initial ?? {}) });
  }, [opened]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: keyof (CustomerInput & DealerInput)) => (val: string) => setV((x) => ({ ...x, [k]: val }));
  const cities = [...new Set([...(f?.cities ?? []), ...(f?.dealer_cities ?? [])])];
  const states = [...new Set([...(f?.states ?? []), ...(f?.dealer_states ?? [])])];
  const pending = saveC.isPending || saveD.isPending;

  const submit = async () => {
    if (!v.name?.trim()) return notifications.show({ color: "red", message: "Name is required" });
    try {
      const body = kind === "customer"
        ? { name: v.name, phone: v.phone, email: v.email, city: v.city, state: v.state, country: v.country, notes: v.notes }
        : { name: v.name, phone: v.phone, city: v.city, state: v.state, country: v.country, gstin: v.gstin, notes: v.notes };
      const saved = kind === "customer"
        ? await saveC.mutateAsync({ id: initial?.id, ...body })
        : await saveD.mutateAsync({ id: initial?.id, ...body });
      notifications.show({ color: "teal", message: `${saved.name} saved` });
      onSaved?.(saved);
      onClose();
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={700}>{initial?.id ? "Edit" : "New"} {kind}</Text>} size="md">
      <Stack gap="sm" onKeyDown={(e) => e.key === "Enter" && submit()}>
        <TextInput label="Name" required data-autofocus value={v.name ?? ""} onChange={(e) => set("name")(e.currentTarget.value)} />
        <SimpleGrid cols={2}>
          <TextInput label="Phone" value={v.phone ?? ""} onChange={(e) => set("phone")(e.currentTarget.value)} />
          {kind === "customer" ? (
            <TextInput label="Email" value={v.email ?? ""} onChange={(e) => set("email")(e.currentTarget.value)} />
          ) : (
            <TextInput label="GSTIN" value={v.gstin ?? ""} onChange={(e) => set("gstin")(e.currentTarget.value.toUpperCase())} />
          )}
          <Autocomplete label="City" data={cities} value={v.city ?? ""} onChange={set("city")} />
          <Autocomplete label="State" data={states} value={v.state ?? ""} onChange={set("state")} />
        </SimpleGrid>
        <Autocomplete label="Country" data={[...new Set([...COUNTRIES, ...(f?.countries ?? [])])]} value={v.country ?? ""} onChange={set("country")} />
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={pending}>Save</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/** Pick a customer (empty = walk-in) with a quick "+" to add a new one. */
export function CustomerPicker({ value, onChange, label = "Customer", size = "sm", inPopover = false }: {
  value: number | null; onChange: (id: number | null) => void; label?: string | null; size?: string; inPopover?: boolean;
}) {
  const { data } = useCustomers();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Group gap={6} align="flex-end" wrap="nowrap">
        <Select
          style={{ flex: 1 }}
          size={size}
          label={label ?? undefined}
          placeholder="Walk-in customer"
          searchable
          clearable
          data={(data ?? []).map((c) => ({ value: String(c.id), label: `${c.name}${c.city ? ` · ${c.city}` : ""}${c.phone ? ` · ${c.phone}` : ""}` }))}
          value={value ? String(value) : null}
          onChange={(v) => onChange(v ? Number(v) : null)}
          nothingFoundMessage={inPopover ? "Not found. Add customers in Sales." : "Not found. Use + to add."}
          comboboxProps={{ withinPortal: !inPopover }}
        />
        {!inPopover && (
          <Tooltip label="New customer">
            <ActionIcon size={size === "xs" ? 30 : 36} variant="light" aria-label="New customer" onClick={() => setOpen(true)}><IconPlus size={16} /></ActionIcon>
          </Tooltip>
        )}
      </Group>
      <ContactModal kind="customer" opened={open} onClose={() => setOpen(false)} onSaved={(c) => onChange(c.id)} />
    </>
  );
}

/** Pick the dealer a purchase came from, with a quick "+" to add a new one. */
export function DealerPicker({ value, onChange, label = "Dealer", size = "sm", inPopover = false }: {
  value: number | null; onChange: (id: number | null) => void; label?: string | null; size?: string; inPopover?: boolean;
}) {
  const { data } = useDealers();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Group gap={6} align="flex-end" wrap="nowrap">
        <Select
          style={{ flex: 1 }}
          size={size}
          label={label ?? undefined}
          placeholder="Choose dealer"
          searchable
          clearable
          data={(data ?? []).map((d) => ({ value: String(d.id), label: `${d.name}${d.city ? ` · ${d.city}` : ""}` }))}
          value={value ? String(value) : null}
          onChange={(v) => onChange(v ? Number(v) : null)}
          nothingFoundMessage={inPopover ? "Not found. Add dealers in Purchases." : "Not found. Use + to add."}
          comboboxProps={{ withinPortal: !inPopover }}
        />
        {!inPopover && (
          <Tooltip label="New dealer">
            <ActionIcon size={size === "xs" ? 30 : 36} variant="light" aria-label="New dealer" onClick={() => setOpen(true)}><IconPlus size={16} /></ActionIcon>
          </Tooltip>
        )}
      </Group>
      <ContactModal kind="dealer" opened={open} onClose={() => setOpen(false)} onSaved={(d) => onChange(d.id)} />
    </>
  );
}
