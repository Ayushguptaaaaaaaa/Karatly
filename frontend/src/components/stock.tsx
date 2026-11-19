import {
  ActionIcon,
  Anchor,
  Avatar,
  Box,
  Button,
  Combobox,
  Drawer,
  Group,
  InputBase,
  Loader,
  NumberInput,
  Paper,
  Popover,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  Tooltip,
  UnstyledButton,
  useCombobox,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { useDebouncedValue, useHotkeys, useMediaQuery } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconArrowDown, IconArrowUp, IconCheck, IconMinus, IconPlus, IconSearch } from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { api, notifyError } from "../api/client";
import { invalidateData, useDesignSearch, useRecordMovement } from "../api/hooks";
import type { DesignSearchHit, MovementResult, MovementType, StockStatus } from "../api/types";
import { IN_REASONS, MOVEMENT_META, OUT_REASONS, STATUS_META } from "../lib/constants";
import { milestone } from "../lib/confetti";
import { formatINR, todayISO } from "../lib/format";
import { useUi } from "../stores";
import { LabelCode, PhotoThumb, StatusBadge } from "./ui";

export interface StockTarget {
  id: number;
  label: string;
  name: string | null;
  current_stock: number;
  selling_price: number;
  cost_price: number; // last unit cost
  photo_url?: string | null;
  status?: StockStatus;
}

// ---- toast with Undo -------------------------------------------------------------------
export function useUndoToast() {
  const qc = useQueryClient();
  return (res: MovementResult) => {
    const m = res.movement;
    const meta = MOVEMENT_META[m.type];
    const verb = m.type === "SALE" ? "Sold" : meta.dir === "IN" ? "Added" : "Removed";
    const id = `mv-${m.id}`;
    notifications.show({
      id,
      color: meta.dir === "IN" ? "teal" : "gold",
      icon: <IconCheck size={16} />,
      autoClose: 8000,
      title: `${verb} ${m.quantity} × ${m.design.label}`,
      message: (
        <Group justify="space-between" gap="xs" wrap="nowrap">
          <Text size="sm" c="dimmed">
            {meta.label} · {res.design.current_stock} left
          </Text>
          <Button
            size="compact-xs"
            variant="light"
            onClick={async () => {
              notifications.hide(id);
              try {
                await api(`/stock/movements/${m.id}/void`, { method: "POST", body: { reason: "Undo" } });
                invalidateData(qc);
                notifications.show({ color: "gray", message: `Undone: ${m.design.label} is back to its previous stock.` });
              } catch (e) {
                notifyError(e, "Couldn't undo");
              }
            }}
          >
            Undo
          </Button>
        </Group>
      ),
    });
  };
}

// ---- the core add/subtract form ------------------------------------------------------------
export function QuickStockForm({
  target, mode, onDone, onCancel, compact = false, autoFocusQty = true,
}: {
  target: StockTarget; mode: "IN" | "OUT"; onDone?: (r: MovementResult) => void; onCancel?: () => void;
  compact?: boolean; autoFocusQty?: boolean;
}) {
  const reasons = mode === "IN" ? IN_REASONS : OUT_REASONS;
  const [type, setType] = useState<MovementType>(reasons[0]);
  const [qty, setQty] = useState<number>(1);
  const [price, setPrice] = useState<number | string>(mode === "IN" ? target.cost_price : target.selling_price);
  const [date, setDate] = useState<string>(todayISO());
  const [showDate, setShowDate] = useState(false);
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);
  const rec = useRecordMovement();
  const undoToast = useUndoToast();

  useEffect(() => {
    setType(reasons[0]);
    setPrice(mode === "IN" ? target.cost_price : target.selling_price);
    setQty(1);
  }, [mode, target.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const showPrice = type === "SALE" || type === "PURCHASE";
  const after = target.current_stock + (mode === "IN" ? qty : -qty);
  const invalid = qty < 1 || after < 0;
  const submitLabel =
    type === "SALE" ? `Record sale${qty > 1 ? ` (${qty})` : ""}` : type === "PURCHASE" ? `Add ${qty} piece${qty > 1 ? "s" : ""}` : "Save";

  const submit = async () => {
    if (invalid || rec.isPending) return;
    try {
      const res = await rec.mutateAsync({
        design_id: target.id, type, quantity: qty, occurred_on: date,
        unit_price: showPrice && price !== "" ? Number(price) : null, note: note || null,
      });
      undoToast(res);
      if (type === "SALE") milestone("first_sale");
      onDone?.(res);
    } catch (e) {
      notifyError(e, "Couldn't record");
    }
  };

  return (
    <Stack gap="sm" onKeyDown={(e) => { if (e.key === "Enter" && !(e.target instanceof HTMLTextAreaElement)) { e.preventDefault(); submit(); } }}>
      {!compact && (
        <Group gap="sm" wrap="nowrap">
          <PhotoThumb url={target.photo_url} size={44} />
          <Box style={{ minWidth: 0 }}>
            <LabelCode>{target.label}</LabelCode>
            <Text size="xs" c="dimmed" truncate>
              {target.name ?? "—"} · In stock: <b>{target.current_stock}</b>
            </Text>
          </Box>
        </Group>
      )}
      <SegmentedControl
        size="xs"
        fullWidth
        value={type}
        onChange={(v) => setType(v as MovementType)}
        data={reasons.map((r) => ({ value: r, label: MOVEMENT_META[r].short }))}
        color={mode === "IN" ? "teal" : "red"}
      />
      <Group justify="center" gap="md" wrap="nowrap">
        <ActionIcon size={42} radius="xl" variant="light" color="gray" aria-label="Less" onClick={() => setQty((q) => Math.max(1, q - 1))}>
          <IconMinus size={18} />
        </ActionIcon>
        <NumberInput
          value={qty}
          onChange={(v) => setQty(Math.max(0, Math.floor(Number(v) || 0)))}
          min={1}
          max={mode === "OUT" ? target.current_stock : 100000}
          hideControls
          w={90}
          size="lg"
          styles={{ input: { textAlign: "center", fontWeight: 700, fontSize: 24 } }}
          aria-label="Quantity"
          data-autofocus={autoFocusQty || undefined}
        />
        <ActionIcon size={42} radius="xl" variant="light" color="gray" aria-label="More" onClick={() => setQty((q) => q + 1)}>
          <IconPlus size={18} />
        </ActionIcon>
      </Group>
      {showPrice && (
        <NumberInput
          label={type === "SALE" ? "Price per piece" : "Cost per piece"}
          prefix="₹"
          value={price}
          onChange={setPrice}
          min={0}
          size="sm"
          thousandSeparator=","
          thousandsGroupStyle="lakh"
        />
      )}
      <Group gap="xs" justify="space-between">
        {showDate ? (
          <DateInput
            size="xs"
            value={date}
            onChange={(v) => setDate(v ? dayjs(v).format("YYYY-MM-DD") : todayISO())}
            maxDate={new Date()}
            valueFormat="D MMM YYYY"
            label="Date"
            style={{ flex: 1 }}
          />
        ) : (
          <Anchor size="xs" component="button" type="button" onClick={() => setShowDate(true)}>
            Date: Today ▾
          </Anchor>
        )}
        {!showNote && (
          <Anchor size="xs" component="button" type="button" onClick={() => setShowNote(true)}>
            + Add note
          </Anchor>
        )}
      </Group>
      {showNote && (
        <Textarea size="xs" placeholder={type.startsWith("ADJUSTMENT") ? "e.g. damaged, count fix" : "Optional note"} value={note} onChange={(e) => setNote(e.currentTarget.value)} autosize minRows={1} maxLength={300} />
      )}
      <Text size="xs" c={after < 0 ? "red" : "dimmed"} ta="center">
        {after < 0 ? `Only ${target.current_stock} in stock` : `After this: ${after} left`}
      </Text>
      <Group grow gap="xs">
        {onCancel && (
          <Button variant="default" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button color={mode === "IN" ? "teal" : "red"} onClick={submit} loading={rec.isPending} disabled={invalid}>
          {submitLabel}
        </Button>
      </Group>
    </Stack>
  );
}

// ---- − [n] + stepper used in every list --------------------------------------------------
export function StockStepper({ target, size = "md" }: { target: StockTarget; size?: "sm" | "md" | "lg" }) {
  const [open, setOpen] = useState<"IN" | "OUT" | null>(null);
  const [shown, setShown] = useState(target.current_stock);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const rec = useRecordMovement();
  const undoToast = useUndoToast();
  const isMobile = useMediaQuery("(max-width: 48em)");
  const btn = size === "lg" ? 40 : isMobile ? 36 : 30;
  const statusColor = STATUS_META[target.status ?? (target.current_stock === 0 ? "OUT" : "IN")].hex;

  useEffect(() => {
    if (target.current_stock !== shown) {
      setFlash(target.current_stock > shown ? "up" : "down");
      setShown(target.current_stock);
      const t = setTimeout(() => setFlash(null), 900);
      return () => clearTimeout(t);
    }
  }, [target.current_stock]); // eslint-disable-line react-hooks/exhaustive-deps

  const quick = async (mode: "IN" | "OUT") => {
    try {
      setShown((s) => s + (mode === "IN" ? 1 : -1));
      const res = await rec.mutateAsync({ design_id: target.id, type: mode === "IN" ? "PURCHASE" : "SALE", quantity: 1 });
      undoToast(res);
      if (mode === "OUT") milestone("first_sale");
    } catch (e) {
      setShown(target.current_stock);
      notifyError(e, "Couldn't record");
    }
  };

  const click = (mode: "IN" | "OUT", e: React.MouseEvent) => {
    e.stopPropagation();
    if (e.shiftKey) quick(mode);
    else setOpen(open === mode ? null : mode);
  };

  return (
    <Popover opened={open !== null} onChange={(o) => !o && setOpen(null)} width={300} position="bottom" shadow="lg" withArrow trapFocus>
      <Popover.Target>
        <Group gap={6} wrap="nowrap" data-stop-row onClick={(e) => e.stopPropagation()}>
          <Tooltip disabled={open !== null} label={target.current_stock <= 0 ? "Nothing to sell, stock is 0" : "Record a sale or remove stock (Shift+click: quick −1)"}>
            <ActionIcon
              size={btn}
              radius="xl"
              variant="light"
              color="red"
              aria-label={`Remove stock for ${target.label}`}
              disabled={target.current_stock <= 0}
              onClick={(e) => click("OUT", e)}
            >
              <IconMinus size={16} />
            </ActionIcon>
          </Tooltip>
          <Box
            miw={size === "lg" ? 64 : 46}
            px={8}
            py={2}
            style={{
              borderRadius: 999,
              textAlign: "center",
              overflow: "hidden",
              background: flash === "up" ? "rgba(43,138,62,.18)" : flash === "down" ? "rgba(201,42,42,.14)" : "var(--mantine-color-default-hover)",
              color: statusColor,
              transition: "background 300ms",
            }}
          >
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.div
                key={shown}
                initial={{ y: flash === "down" ? -14 : 14, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: flash === "down" ? 14 : -14, opacity: 0 }}
                transition={{ duration: 0.22 }}
                className="num"
                style={{ fontWeight: 700, fontSize: size === "lg" ? 22 : 15 }}
              >
                {shown}
              </motion.div>
            </AnimatePresence>
          </Box>
          <Tooltip disabled={open !== null} label="Add stock (Shift+click: quick +1)">
            <ActionIcon size={btn} radius="xl" variant="light" color="teal" aria-label={`Add stock for ${target.label}`} onClick={(e) => click("IN", e)}>
              <IconPlus size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Popover.Target>
      <Popover.Dropdown data-stop-row onClick={(e) => e.stopPropagation()}>
        {open && (
          <QuickStockForm
            target={{ ...target, current_stock: target.current_stock }}
            mode={open}
            onCancel={() => setOpen(null)}
            onDone={(r) => {
              setShown(r.design.current_stock);
              setOpen(null);
            }}
          />
        )}
      </Popover.Dropdown>
    </Popover>
  );
}

// ---- design autocomplete (search label/name; barcode friendly) --------------------------
export function DesignPicker({ value, onPick, autoFocus, placeholder = "Type a label or name… e.g. ER-1012", size = "lg" }: {
  value: DesignSearchHit | null; onPick: (d: DesignSearchHit | null) => void; autoFocus?: boolean; placeholder?: string; size?: string;
}) {
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() });
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 180);
  const { data, isFetching } = useDesignSearch(debounced, true);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!value) setSearch("");
  }, [value]);

  const options = (data ?? []).map((d) => (
    <Combobox.Option value={String(d.id)} key={d.id}>
      <Group gap="sm" wrap="nowrap">
        <PhotoThumb url={d.photo_url} size={34} />
        <Box style={{ flex: 1, minWidth: 0 }}>
          <LabelCode>{d.label}</LabelCode>
          <Text size="xs" c="dimmed" truncate>
            {d.name ?? d.category_name}
          </Text>
        </Box>
        <StatusBadge status={d.status} size="xs" />
        <Text size="sm" fw={700} className="num">
          {d.current_stock}
        </Text>
      </Group>
    </Combobox.Option>
  ));

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={(id) => {
        const d = data?.find((x) => String(x.id) === id) ?? null;
        onPick(d);
        setSearch(d ? d.label : "");
        combobox.closeDropdown();
      }}
    >
      <Combobox.Target>
        <InputBase
          ref={ref}
          size={size}
          leftSection={<IconSearch size={18} />}
          rightSection={isFetching ? <Loader size="xs" /> : null}
          value={search}
          placeholder={placeholder}
          autoFocus={autoFocus}
          aria-label="Find design"
          onChange={(e) => {
            setSearch(e.currentTarget.value);
            if (value) onPick(null);
            combobox.openDropdown();
            combobox.updateSelectedOptionIndex();
          }}
          onClick={() => combobox.openDropdown()}
          onFocus={() => combobox.openDropdown()}
          onBlur={() => combobox.closeDropdown()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              const exact = data?.find((d) => d.label.toLowerCase() === search.trim().toLowerCase());
              if (exact) {
                e.preventDefault();
                onPick(exact);
                setSearch(exact.label);
                combobox.closeDropdown();
              }
            }
          }}
        />
      </Combobox.Target>
      <Combobox.Dropdown>
        <Combobox.Options mah={340} style={{ overflowY: "auto" }}>
          {options.length ? options : <Combobox.Empty>{debounced ? "No design found" : "Start typing…"}</Combobox.Empty>}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}

export function hitToTarget(d: DesignSearchHit): StockTarget {
  return { id: d.id, label: d.label, name: d.name, current_stock: d.current_stock, selling_price: d.selling_price,
    cost_price: d.cost_price, photo_url: d.photo_url, status: d.status };
}

// ---- quick entry panel (Stock page + global drawer) ----------------------------------------
export function QuickEntryPanel({ initialMode = "OUT", initialDesignId, onRecorded }: {
  initialMode?: "IN" | "OUT"; initialDesignId?: number | null; onRecorded?: () => void;
}) {
  const [mode, setMode] = useState<"IN" | "OUT">(initialMode);
  const [picked, setPicked] = useState<DesignSearchHit | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => setMode(initialMode), [initialMode]);
  useEffect(() => {
    if (!initialDesignId) return;
    api<{ id: number; label: string; name: string | null; current_stock: number; selling_price: number; last_unit_cost: number; photo_url: string | null; status: StockStatus; category: { name: string }; min_stock: number }>(
      `/designs/${initialDesignId}`,
    ).then((d) => setPicked({ id: d.id, label: d.label, name: d.name, current_stock: d.current_stock, selling_price: d.selling_price,
      cost_price: d.last_unit_cost, photo_url: d.photo_url, status: d.status, category_name: d.category.name, min_stock: d.min_stock }))
      .catch(() => undefined);
  }, [initialDesignId]);

  useHotkeys([
    ["alt+o", () => setMode("OUT")],
    ["alt+i", () => setMode("IN")],
  ]);

  return (
    <Stack gap="md">
      <Group grow gap="sm">
        {(["OUT", "IN"] as const).map((m) => (
          <UnstyledButton
            key={m}
            onClick={() => setMode(m)}
            className="lift"
            style={{
              borderRadius: 14,
              padding: "14px 16px",
              border: `2px solid ${mode === m ? (m === "OUT" ? "var(--mantine-color-red-5)" : "var(--mantine-color-teal-6)") : "var(--jaa-border)"}`,
              background: mode === m ? (m === "OUT" ? "rgba(201,42,42,.07)" : "rgba(43,138,62,.08)") : "var(--jaa-surface)",
            }}
            aria-pressed={mode === m}
          >
            <Group gap="sm" wrap="nowrap">
              <Avatar color={m === "OUT" ? "red" : "teal"} radius="xl" variant="light">
                {m === "OUT" ? <IconArrowDown size={20} /> : <IconArrowUp size={20} />}
              </Avatar>
              <Box>
                <Text fw={700}>{m === "OUT" ? "Stock OUT" : "Stock IN"}</Text>
                <Text size="xs" c="dimmed">
                  {m === "OUT" ? "Sale, return to supplier…" : "New stock, customer return…"}
                </Text>
              </Box>
            </Group>
          </UnstyledButton>
        ))}
      </Group>
      <DesignPicker value={picked} onPick={(d) => { setPicked(d); setDone(false); }} autoFocus={!initialDesignId} />
      <AnimatePresence mode="wait">
        {done && !picked && (
          <motion.div key="done" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
            <Paper p="md" radius="md" bg="var(--mantine-color-teal-light)">
              <Group gap="sm">
                <IconCheck color="var(--mantine-color-teal-7)" />
                <Text size="sm" fw={600} c="teal.8">
                  Saved! Ready for the next one.
                </Text>
              </Group>
            </Paper>
          </motion.div>
        )}
        {picked && (
          <motion.div key={picked.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Paper p="md" radius="md" className="soft-card">
              <Group gap="md" mb="sm" wrap="nowrap">
                <PhotoThumb url={picked.photo_url} size={56} />
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <LabelCode size="md">{picked.label}</LabelCode>
                  <Text size="sm" c="dimmed" truncate>
                    {picked.name ?? picked.category_name}
                  </Text>
                </Box>
                <Box ta="right">
                  <Text size="xs" c="dimmed">
                    In stock
                  </Text>
                  <Text className="serif num" fz={28} fw={700} lh={1}>
                    {picked.current_stock}
                  </Text>
                </Box>
              </Group>
              <QuickStockForm
                compact
                target={hitToTarget(picked)}
                mode={mode}
                autoFocusQty={false}
                onDone={() => {
                  setPicked(null);
                  setDone(true);
                  onRecorded?.();
                }}
              />
            </Paper>
          </motion.div>
        )}
      </AnimatePresence>
      {!picked && (
        <Text size="xs" c="dimmed">
          Tip: type the full label and press Enter (works with barcode scanners). Alt+O = Stock OUT, Alt+I = Stock IN. Today's
          sale value so far is shown on the Stock page.
        </Text>
      )}
    </Stack>
  );
}

export function QuickStockDrawer() {
  const { quickStockOpen, quickStockMode, quickStockDesignId, closeQuickStock } = useUi();
  return (
    <Drawer opened={quickStockOpen} onClose={closeQuickStock} position="right" size="md" title={<Text fw={700}>Quick stock</Text>}>
      {quickStockOpen && <QuickEntryPanel initialMode={quickStockMode} initialDesignId={quickStockDesignId} />}
    </Drawer>
  );
}

export function formatMovementValue(v: number | null) {
  return v === null ? "" : formatINR(v);
}
