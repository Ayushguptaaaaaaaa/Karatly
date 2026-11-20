import {
  Accordion,
  Alert,
  Badge,
  Box,
  Button,
  Chip,
  Group,
  Modal,
  NumberInput,
  Paper,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Stepper,
  Table,
  TagsInput,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { Dropzone } from "@mantine/dropzone";
import { useMediaQuery } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle, IconCheck, IconDownload, IconFileSpreadsheet, IconPlus, IconTrash, IconUpload } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, download, errorMessage } from "../../api/client";
import {
  checkLabel,
  nextLabels,
  suggestPrefix,
  useBulkCreateDesigns,
  useCategory,
  useCreateCategory,
  useCreateSubcategory,
  useImportDesigns,
  useUpdateCategory,
  useUpdateDesign,
} from "../../api/hooks";
import type { CategoryCard, CategoryDetail, DesignCreateRow, DesignDetail } from "../../api/types";
import { CategoryIcon, CATEGORY_ICON } from "../../components/ui";
import { milestone } from "../../lib/confetti";
import { METAL_OPTIONS, PURITY_OPTIONS } from "../../lib/constants";
import { formatINR, formatNumber, todayISO } from "../../lib/format";

// ---------------------------------------------------------------------------------------------
// Add / edit category
// ---------------------------------------------------------------------------------------------
export function AddCategoryModal({
  opened, onClose, initial, editing, onSaved,
}: {
  opened: boolean; onClose: () => void; initial?: { name?: string; icon?: string };
  editing?: CategoryCard | CategoryDetail | null; onSaved?: (c: CategoryDetail) => void;
}) {
  const create = useCreateCategory();
  const update = useUpdateCategory();
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("other");
  const [prefix, setPrefix] = useState("");
  const [prefixTouched, setPrefixTouched] = useState(false);
  const [subs, setSubs] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [inflation, setInflation] = useState<number | string>("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!opened) return;
    setName(editing?.name ?? initial?.name ?? "");
    setIcon(editing?.icon ?? initial?.icon ?? "other");
    setPrefix(editing?.label_prefix ?? "");
    setPrefixTouched(!!editing);
    setSubs([]);
    setDescription(editing?.description ?? "");
    setInflation(editing?.inflation_pct_override ?? "");
    setErrors({});
    if (!editing && initial?.name) suggestPrefix(initial.name).then((r) => setPrefix(r.prefix)).catch(() => undefined);
  }, [opened]); // eslint-disable-line react-hooks/exhaustive-deps

  const onNameBlur = () => {
    if (!prefixTouched && name.trim()) suggestPrefix(name.trim()).then((r) => setPrefix(r.prefix)).catch(() => undefined);
  };

  const save = async () => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Please enter a name";
    if (!/^[A-Z]{1,5}$/.test(prefix)) errs.label_prefix = "1–5 letters (A–Z)";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const body = {
      name: name.trim(), icon, label_prefix: prefix, description: description || null,
      inflation_pct_override: inflation === "" ? null : Number(inflation),
    };
    try {
      const res = editing
        ? await update.mutateAsync({ id: editing.id, ...body })
        : await create.mutateAsync({ ...body, subcategories: subs });
      notifications.show({ color: "teal", message: editing ? "Category updated" : `${res.name} created ✨` });
      if (!editing) milestone("first_category");
      onSaved?.(res);
      onClose();
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.fields).length) setErrors(e.fields);
      else notifications.show({ color: "red", title: "Couldn't save", message: errorMessage(e) });
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={700} size="lg">{editing ? "Edit category" : "Add a category"}</Text>} size="lg">
      <Stack gap="md">
        <TextInput
          label="Name"
          placeholder="e.g. Earrings"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          onBlur={onNameBlur}
          error={errors.name}
          data-autofocus
          maxLength={60}
        />
        <Box>
          <Text size="sm" fw={500} mb={6}>
            Icon
          </Text>
          <SimpleGrid cols={{ base: 4, sm: 6 }} spacing="xs">
            {Object.keys(CATEGORY_ICON).map((k) => (
              <Tooltip key={k} label={k}>
                <UnstyledButton
                  onClick={() => setIcon(k)}
                  aria-label={`Icon ${k}`}
                  aria-pressed={icon === k}
                  style={{
                    height: 52, borderRadius: 12, display: "grid", placeItems: "center",
                    border: `2px solid ${icon === k ? "var(--mantine-color-gold-6)" : "var(--jaa-border)"}`,
                    background: icon === k ? "var(--mantine-color-gold-light)" : "transparent",
                    color: icon === k ? "var(--mantine-color-gold-8)" : "var(--jaa-muted)",
                  }}
                >
                  <CategoryIcon icon={k} size={24} />
                </UnstyledButton>
              </Tooltip>
            ))}
          </SimpleGrid>
        </Box>
        <TextInput
          label="Label prefix"
          description={`Labels will look like ${prefix || "ER"}-1001`}
          value={prefix}
          onChange={(e) => {
            setPrefixTouched(true);
            setPrefix(e.currentTarget.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 5));
          }}
          error={errors.label_prefix}
          w={220}
          styles={{ input: { fontFamily: "ui-monospace, monospace", fontWeight: 700, letterSpacing: 2 } }}
        />
        {!editing && (
          <TagsInput
            label="Subcategories (optional)"
            description="Type a name and press Enter, e.g. Studs, Jhumkas, Hoops"
            value={subs}
            onChange={setSubs}
            placeholder="Add subcategory"
            clearable
          />
        )}
        <Accordion variant="contained" radius="md">
          <Accordion.Item value="more">
            <Accordion.Control>More options</Accordion.Control>
            <Accordion.Panel>
              <Stack gap="sm">
                <Textarea label="Description" value={description} onChange={(e) => setDescription(e.currentTarget.value)} autosize minRows={2} maxLength={300} />
                <NumberInput
                  label="Inflation % for purchase estimates"
                  placeholder="Uses shop default"
                  value={inflation}
                  onChange={setInflation}
                  min={0}
                  max={50}
                  suffix="%"
                  w={220}
                />
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} loading={create.isPending || update.isPending}>
            {editing ? "Save changes" : "Create category"}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------------------------
// Add designs wizard: "how many designs?" → grid of labels → review
// ---------------------------------------------------------------------------------------------
type Row = Record<"label" | "name" | "opening_stock" | "cost_price" | "selling_price" | "weight_g" | "purity" | "metal" | "min_stock", string>;
const COLS: { key: keyof Row; label: string; width: number; type: "text" | "num" | "select"; required?: boolean }[] = [
  { key: "label", label: "Label *", width: 120, type: "text", required: true },
  { key: "name", label: "Name", width: 170, type: "text" },
  { key: "opening_stock", label: "Opening stock *", width: 110, type: "num", required: true },
  { key: "cost_price", label: "Cost ₹ *", width: 120, type: "num", required: true },
  { key: "selling_price", label: "Selling ₹ *", width: 120, type: "num", required: true },
  { key: "weight_g", label: "Weight g", width: 90, type: "num" },
  { key: "purity", label: "Purity", width: 90, type: "select" },
  { key: "metal", label: "Metal", width: 110, type: "select" },
  { key: "min_stock", label: "Min stock", width: 90, type: "num" },
];

function emptyRow(label: string, d: Partial<Row>): Row {
  return {
    label, name: "", opening_stock: d.opening_stock ?? "0", cost_price: d.cost_price ?? "", selling_price: d.selling_price ?? "",
    weight_g: "", purity: d.purity ?? "", metal: d.metal ?? "GOLD", min_stock: d.min_stock ?? "",
  };
}

export function AddDesignsWizard({ opened, onClose, categoryId, defaultSubId }: {
  opened: boolean; onClose: () => void; categoryId: number; defaultSubId?: number | null;
}) {
  const isMobile = useMediaQuery("(max-width: 48em)");
  const { data: cat } = useCategory(opened ? categoryId : undefined);
  const createSub = useCreateSubcategory();
  const bulk = useBulkCreateDesigns();
  const [step, setStep] = useState(0);
  const [subId, setSubId] = useState<string | null>(null);
  const [newSub, setNewSub] = useState("");
  const [count, setCount] = useState<number | string>(10);
  const [openingDate, setOpeningDate] = useState(todayISO());
  const [defaults, setDefaults] = useState<Partial<Row>>({ metal: "GOLD", opening_stock: "1" });
  const [rows, setRows] = useState<Row[]>([]);
  const [taken, setTaken] = useState<Record<string, string>>({});
  const [serverErr, setServerErr] = useState<Record<string, string>>({});
  const [loadingLabels, setLoadingLabels] = useState(false);
  const tableRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!opened) return;
    setStep(0);
    setSubId(defaultSubId ? String(defaultSubId) : null);
    setNewSub("");
    setCount(10);
    setOpeningDate(todayISO());
    setRows([]);
    setTaken({});
    setServerErr({});
  }, [opened, defaultSubId]);

  const dupes = useMemo(() => {
    const seen: Record<string, number> = {};
    const d = new Set<number>();
    rows.forEach((r, i) => {
      const k = r.label.trim().toUpperCase();
      if (!k) return;
      if (k in seen) {
        d.add(i);
        d.add(seen[k]);
      } else seen[k] = i;
    });
    return d;
  }, [rows]);

  const cellError = (i: number, key: keyof Row): string | null => {
    const r = rows[i];
    const se = serverErr[`${i}.${key}`];
    if (se) return se;
    if (key === "label") {
      const v = r.label.trim().toUpperCase();
      if (!v) return "Required";
      if (!/^[A-Z0-9][A-Z0-9\-/]{1,19}$/.test(v)) return "Use letters, numbers, - or /";
      if (dupes.has(i)) return "Duplicate label";
      if (taken[v]) return taken[v];
    }
    if ((key === "cost_price" || key === "selling_price") && r[key] === "") return "Required";
    if (key === "opening_stock" && (r.opening_stock === "" || Number(r.opening_stock) < 0)) return "Required";
    return null;
  };
  const rowValid = (i: number) => COLS.every((c) => !cellError(i, c.key));
  const validCount = rows.filter((_, i) => rowValid(i)).length;

  const goToGrid = async () => {
    const n = Math.max(1, Math.min(100, Number(count) || 1));
    let sid = subId;
    if (newSub.trim()) {
      try {
        const s = await createSub.mutateAsync({ categoryId, name: newSub.trim() });
        sid = String(s.id);
        setSubId(sid);
        setNewSub("");
      } catch (e) {
        notifications.show({ color: "red", message: errorMessage(e) });
        return;
      }
    }
    setLoadingLabels(true);
    try {
      const { labels } = await nextLabels(categoryId, n);
      setRows(labels.map((l) => emptyRow(l, defaults)));
      setStep(1);
    } finally {
      setLoadingLabels(false);
    }
  };

  const setCell = (i: number, key: keyof Row, value: string) => {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
    setServerErr((e) => {
      const n = { ...e };
      delete n[`${i}.${key}`];
      return n;
    });
  };

  const verifyLabel = async (label: string) => {
    const v = label.trim().toUpperCase();
    if (!v) return;
    try {
      const r = await checkLabel(v);
      setTaken((t) => ({ ...t, [v]: r.valid && !r.available ? "Already used" : "" }));
    } catch {
      /* ignore */
    }
  };

  const fillDown = (key: keyof Row) => setRows((rs) => rs.map((r) => ({ ...r, [key]: rs[0][key] })));

  const onPaste = (i: number, colIdx: number, e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData("text");
    if (!text.includes("\t") && !text.includes("\n")) return;
    e.preventDefault();
    const lines = text.replace(/\r/g, "").split("\n").filter((l, k, arr) => l !== "" || k < arr.length - 1);
    setRows((rs) => {
      const next = [...rs];
      lines.forEach((line, li) => {
        const cells = line.split("\t");
        const ri = i + li;
        if (ri >= next.length) next.push(emptyRow("", defaults));
        cells.forEach((cell, ci) => {
          const col = COLS[colIdx + ci];
          if (!col) return;
          let v = cell.trim();
          if (col.type === "num") v = v.replace(/[₹,\s]/g, "");
          if (col.key === "metal") v = v.toUpperCase();
          next[ri] = { ...next[ri], [col.key]: v };
        });
      });
      return next;
    });
  };

  const submit = async () => {
    const payload: DesignCreateRow[] = rows.map((r) => ({
      label: r.label.trim().toUpperCase(), name: r.name || null, metal: r.metal || "GOLD", purity: r.purity || null,
      weight_g: r.weight_g || null, cost_price: r.cost_price, selling_price: r.selling_price,
      min_stock: r.min_stock || null, opening_stock: r.opening_stock || 0,
    }));
    try {
      const res = await bulk.mutateAsync({ category_id: categoryId, subcategory_id: subId ? Number(subId) : null, opening_date: openingDate, designs: payload });
      milestone("first_designs");
      notifications.show({ color: "teal", title: `${res.created.length} designs added to ${cat?.name ?? "category"} ✨`, message: "You can now record sales with − / +." });
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.rows.length) {
        const m: Record<string, string> = {};
        e.rows.forEach((r) => (m[`${r.index}.${r.field}`] = r.message));
        setServerErr(m);
        setStep(1);
      }
      notifications.show({ color: "red", title: "Couldn't create designs", message: errorMessage(e) });
    }
  };

  const totals = useMemo(() => {
    const pieces = rows.reduce((s, r) => s + (Number(r.opening_stock) || 0), 0);
    const value = rows.reduce((s, r) => s + (Number(r.opening_stock) || 0) * (Number(r.cost_price) || 0), 0);
    const belowCost = rows.filter((r) => r.selling_price !== "" && r.cost_price !== "" && Number(r.selling_price) < Number(r.cost_price));
    return { pieces, value, belowCost };
  }, [rows]);

  const subOptions = (cat?.subcategories ?? []).map((s) => ({ value: String(s.id), label: s.name }));

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="90%"
      fullScreen={isMobile}
      title={
        <Group gap="sm">
          {cat && <CategoryIcon icon={cat.icon} />}
          <Text fw={700} size="lg">
            Add designs to {cat?.name ?? "…"}
          </Text>
        </Group>
      }
      closeOnClickOutside={false}
    >
      <Stepper active={step} size="sm" mb="lg" allowNextStepsSelect={false}>
        <Stepper.Step label="Setup" description="How many designs?" />
        <Stepper.Step label="Labels & details" description="Fill the grid" />
        <Stepper.Step label="Review" description="Create" />
      </Stepper>

      {step === 0 && (
        <Stack gap="lg" maw={720}>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <Select
              label="Subcategory (optional)"
              placeholder={subOptions.length ? "Choose subcategory" : "No subcategories yet"}
              data={subOptions}
              value={subId}
              onChange={setSubId}
              clearable
            />
            <TextInput label="…or create a new subcategory" placeholder="e.g. Jhumkas" value={newSub} onChange={(e) => setNewSub(e.currentTarget.value)} />
          </SimpleGrid>
          <Box>
            <NumberInput
              label="How many designs are you adding?"
              size="lg"
              min={1}
              max={100}
              value={count}
              onChange={setCount}
              w={220}
              data-autofocus
            />
            <Chip.Group>
              <Group gap="xs" mt="xs">
                {[5, 10, 20, 50].map((n) => (
                  <Chip key={n} checked={Number(count) === n} onChange={() => setCount(n)} size="sm">
                    {n}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
          </Box>
          <DateInput
            label="Opening stock date"
            description="Use an earlier date if this stock was already in your shop"
            value={openingDate}
            onChange={(v) => setOpeningDate(v ? dayjs(v).format("YYYY-MM-DD") : todayISO())}
            maxDate={new Date()}
            valueFormat="D MMM YYYY"
            w={260}
          />
          <Accordion variant="contained" radius="md">
            <Accordion.Item value="defaults">
              <Accordion.Control>Defaults for every row (optional)</Accordion.Control>
              <Accordion.Panel>
                <SimpleGrid cols={{ base: 2, sm: 3 }}>
                  <Box>
                    <Text size="sm" fw={500} mb={4}>
                      Metal
                    </Text>
                    <SegmentedControl size="xs" data={METAL_OPTIONS} value={defaults.metal ?? "GOLD"} onChange={(v) => setDefaults((d) => ({ ...d, metal: v }))} />
                  </Box>
                  <Select label="Purity" data={PURITY_OPTIONS} value={defaults.purity ?? null} onChange={(v) => setDefaults((d) => ({ ...d, purity: v ?? "" }))} clearable />
                  <NumberInput label="Opening stock" min={0} value={defaults.opening_stock ?? ""} onChange={(v) => setDefaults((d) => ({ ...d, opening_stock: String(v) }))} />
                  <NumberInput label="Cost ₹" min={0} prefix="₹" value={defaults.cost_price ?? ""} onChange={(v) => setDefaults((d) => ({ ...d, cost_price: String(v) }))} />
                  <NumberInput label="Selling ₹" min={0} prefix="₹" value={defaults.selling_price ?? ""} onChange={(v) => setDefaults((d) => ({ ...d, selling_price: String(v) }))} />
                  <NumberInput label="Min stock" min={0} value={defaults.min_stock ?? ""} onChange={(v) => setDefaults((d) => ({ ...d, min_stock: String(v) }))} />
                </SimpleGrid>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={goToGrid} loading={loadingLabels || createSub.isPending}>
              Next: fill labels
            </Button>
          </Group>
        </Stack>
      )}

      {step === 1 && (
        <Stack gap="sm">
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Tip: paste rows straight from Excel into any cell. Labels are pre-filled. Change them to match the tags on your
              jewellery.
            </Text>
            <Badge color={validCount === rows.length ? "teal" : "orange"} size="lg">
              {validCount}/{rows.length} rows ready
            </Badge>
          </Group>
          <ScrollArea type="auto" offsetScrollbars ref={tableRef} mah={isMobile ? undefined : "56vh"}>
            <Table stickyHeader withTableBorder withColumnBorders verticalSpacing={4} horizontalSpacing={6} miw={1100}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={36}>#</Table.Th>
                  {COLS.map((c) => (
                    <Table.Th key={c.key} w={c.width}>
                      <Group gap={4} wrap="nowrap" justify="space-between">
                        <Text size="xs" fw={700}>
                          {c.label}
                        </Text>
                        {c.key !== "label" && c.key !== "name" && (
                          <Tooltip label="Copy first row's value to all rows">
                            <Text size="10px" c="gold.8" style={{ cursor: "pointer" }} onClick={() => fillDown(c.key)}>
                              fill ↓
                            </Text>
                          </Tooltip>
                        )}
                      </Group>
                    </Table.Th>
                  ))}
                  <Table.Th w={36} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((r, i) => (
                  <Table.Tr key={i} bg={rowValid(i) ? undefined : "var(--mantine-color-red-light)"}>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {i + 1}
                      </Text>
                    </Table.Td>
                    {COLS.map((c, ci) => {
                      const err = cellError(i, c.key);
                      const common = {
                        size: "xs" as const,
                        error: !!err,
                        onPaste: (e: React.ClipboardEvent) => onPaste(i, ci, e),
                        "aria-label": `${c.label} row ${i + 1}`,
                      };
                      return (
                        <Table.Td key={c.key}>
                          <Tooltip label={err} disabled={!err} color="red" position="top">
                            <Box>
                              {c.type === "select" ? (
                                <Select
                                  {...common}
                                  data={c.key === "metal" ? METAL_OPTIONS : PURITY_OPTIONS}
                                  value={r[c.key] || null}
                                  onChange={(v) => setCell(i, c.key, v ?? "")}
                                  comboboxProps={{ withinPortal: true }}
                                />
                              ) : (
                                <TextInput
                                  {...common}
                                  value={r[c.key]}
                                  inputMode={c.type === "num" ? "decimal" : undefined}
                                  onChange={(e) => {
                                    let v = e.currentTarget.value;
                                    if (c.key === "label") v = v.toUpperCase();
                                    if (c.type === "num") v = v.replace(/[^0-9.]/g, "");
                                    setCell(i, c.key, v);
                                  }}
                                  onBlur={c.key === "label" ? (e) => verifyLabel(e.currentTarget.value) : undefined}
                                  styles={c.key === "label" ? { input: { fontFamily: "ui-monospace, monospace", fontWeight: 600 } } : undefined}
                                />
                              )}
                            </Box>
                          </Tooltip>
                        </Table.Td>
                      );
                    })}
                    <Table.Td>
                      <Tooltip label="Remove row">
                        <UnstyledButton aria-label="Remove row" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))} disabled={rows.length === 1}>
                          <IconTrash size={14} color="var(--jaa-muted)" />
                        </UnstyledButton>
                      </Tooltip>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
          <Group justify="space-between">
            <Button variant="subtle" leftSection={<IconPlus size={14} />} onClick={() => setRows((rs) => [...rs, emptyRow("", defaults)])}>
              Add row
            </Button>
            <Group>
              <Button variant="default" onClick={() => setStep(0)}>
                Back
              </Button>
              <Button onClick={() => setStep(2)} disabled={validCount !== rows.length || rows.length === 0}>
                Review
              </Button>
            </Group>
          </Group>
        </Stack>
      )}

      {step === 2 && (
        <Stack gap="md" maw={760}>
          <Paper p="lg" radius="md" className="gold-border">
            <SimpleGrid cols={3}>
              <Box>
                <Text size="sm" c="dimmed">
                  Designs
                </Text>
                <Text className="serif" fz={28} fw={700}>
                  {rows.length}
                </Text>
              </Box>
              <Box>
                <Text size="sm" c="dimmed">
                  Pieces
                </Text>
                <Text className="serif" fz={28} fw={700}>
                  {formatNumber(totals.pieces)}
                </Text>
              </Box>
              <Box>
                <Text size="sm" c="dimmed">
                  Stock value (cost)
                </Text>
                <Text className="serif" fz={28} fw={700}>
                  {formatINR(totals.value, { compact: true })}
                </Text>
              </Box>
            </SimpleGrid>
          </Paper>
          <Group gap={6}>
            {rows.map((r) => (
              <Badge key={r.label} variant="light" color="gold" className="label-code">
                {r.label.toUpperCase()}
              </Badge>
            ))}
          </Group>
          {totals.belowCost.length > 0 && (
            <Alert color="orange" icon={<IconAlertTriangle size={18} />}>
              {totals.belowCost.length} design(s) have a selling price below cost: {totals.belowCost.map((r) => r.label).join(", ")}. You can still continue.
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button leftSection={<IconCheck size={16} />} onClick={submit} loading={bulk.isPending}>
              Create {rows.length} designs
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------------------------
// Excel import
// ---------------------------------------------------------------------------------------------
export function ImportExcelModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const imp = useImportDesigns();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Awaited<ReturnType<typeof imp.mutateAsync>> | null>(null);

  useEffect(() => {
    if (opened) {
      setFile(null);
      setResult(null);
    }
  }, [opened]);

  const check = async (f: File) => {
    setFile(f);
    try {
      setResult(await imp.mutateAsync({ file: f, dryRun: true }));
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    }
  };

  const doImport = async () => {
    if (!file) return;
    try {
      const r = await imp.mutateAsync({ file, dryRun: false });
      if (r.imported) {
        milestone("first_import");
        notifications.show({ color: "teal", title: "Import complete ✨", message: `${r.will_create.designs} designs imported.` });
        onClose();
      } else setResult(r);
    } catch (e) {
      notifications.show({ color: "red", message: errorMessage(e) });
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={700} size="lg">Import from Excel</Text>} size="lg">
      <Stack>
        <Group justify="space-between">
          <Text size="sm" c="dimmed">
            1. Download the template, fill one row per design. 2. Upload it here.
          </Text>
          <Button variant="light" size="xs" leftSection={<IconDownload size={14} />} onClick={() => download("/designs/import-template", undefined, "designs_import_template.xlsx")}>
            Template
          </Button>
        </Group>
        <Dropzone onDrop={(f) => f[0] && check(f[0])} accept={[".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]} maxFiles={1} loading={imp.isPending}>
          <Group justify="center" gap="md" mih={110} style={{ pointerEvents: "none" }}>
            <ThemeIcon size={48} radius="xl" variant="light">
              {file ? <IconFileSpreadsheet size={26} /> : <IconUpload size={26} />}
            </ThemeIcon>
            <Box>
              <Text fw={600}>{file ? file.name : "Drop your .xlsx file here or click to choose"}</Text>
              <Text size="xs" c="dimmed">
                Missing categories and subcategories are created automatically.
              </Text>
            </Box>
          </Group>
        </Dropzone>
        {result && (
          <Paper p="md" radius="md" withBorder>
            <Group gap="lg">
              <Text size="sm">
                <b>{result.valid_rows}</b> rows ready
              </Text>
              <Text size="sm" c={result.errors.length ? "red" : "dimmed"}>
                <b>{result.errors.length}</b> errors
              </Text>
              <Text size="sm" c="dimmed">
                Will create {result.will_create.categories} categories, {result.will_create.subcategories} subcategories,{" "}
                {result.will_create.designs} designs{result.will_create.dealers ? `, ${result.will_create.dealers} dealers` : ""}
                {result.will_create.pieces ? ` (${result.will_create.pieces} pieces in stock)` : ""}
              </Text>
            </Group>
            {result.errors.length > 0 && (
              <ScrollArea.Autosize mah={200} mt="sm">
                <Table fz="xs" striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Row</Table.Th>
                      <Table.Th>Field</Table.Th>
                      <Table.Th>Problem</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {result.errors.map((e, i) => (
                      <Table.Tr key={i}>
                        <Table.Td>{e.row}</Table.Td>
                        <Table.Td>{e.field}</Table.Td>
                        <Table.Td>{e.message}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea.Autosize>
            )}
          </Paper>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={doImport} disabled={!result || result.errors.length > 0} loading={imp.isPending}>
            Import
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// ---------------------------------------------------------------------------------------------
// Edit design
// ---------------------------------------------------------------------------------------------
export function EditDesignModal({ design, opened, onClose }: { design: DesignDetail; opened: boolean; onClose: () => void }) {
  const upd = useUpdateDesign();
  const { data: cat } = useCategory(opened ? design.category.id : undefined);
  const [v, setV] = useState<Record<string, string | number | null>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!opened) return;
    setErrors({});
    setV({
      label: design.label, name: design.name ?? "", subcategory_id: design.subcategory ? String(design.subcategory.id) : null,
      metal: design.metal, purity: design.purity ?? null, weight_g: design.weight_g ?? "", cost_price: design.cost_price,
      selling_price: design.selling_price, min_stock: design.min_stock, supplier: design.supplier ?? "",
      inflation_pct_override: design.inflation_pct_override ?? "", description: design.description ?? "",
    });
  }, [opened, design]);

  const set = (k: string) => (val: string | number | null) => setV((s) => ({ ...s, [k]: val }));
  const save = async () => {
    try {
      await upd.mutateAsync({
        id: design.id, label: String(v.label), name: v.name || null, subcategory_id: v.subcategory_id ? Number(v.subcategory_id) : null,
        metal: v.metal, purity: v.purity || null, weight_g: v.weight_g === "" ? null : Number(v.weight_g),
        cost_price: Number(v.cost_price), selling_price: Number(v.selling_price), min_stock: Number(v.min_stock),
        supplier: v.supplier || null, description: v.description || null,
        inflation_pct_override: v.inflation_pct_override === "" ? null : Number(v.inflation_pct_override),
      });
      notifications.show({ color: "teal", message: "Design updated" });
      onClose();
    } catch (e) {
      if (e instanceof ApiError) setErrors(e.fields);
      notifications.show({ color: "red", title: "Couldn't save", message: errorMessage(e) });
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={700} size="lg">Edit {design.label}</Text>} size="lg">
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <TextInput label="Label" value={String(v.label ?? "")} onChange={(e) => set("label")(e.currentTarget.value.toUpperCase())} error={errors.label} />
        <TextInput label="Name" value={String(v.name ?? "")} onChange={(e) => set("name")(e.currentTarget.value)} />
        <Select label="Subcategory" data={(cat?.subcategories ?? []).map((s) => ({ value: String(s.id), label: s.name }))} value={(v.subcategory_id as string) ?? null} onChange={set("subcategory_id")} clearable />
        <Select label="Metal" data={METAL_OPTIONS} value={(v.metal as string) ?? "GOLD"} onChange={set("metal")} allowDeselect={false} />
        <Select label="Purity" data={PURITY_OPTIONS} value={(v.purity as string) ?? null} onChange={set("purity")} clearable />
        <NumberInput label="Weight (g)" value={v.weight_g ?? ""} onChange={set("weight_g")} min={0} decimalScale={3} />
        <NumberInput label="Cost per piece" prefix="₹" value={v.cost_price ?? ""} onChange={set("cost_price")} min={0} />
        <NumberInput label="Selling price" prefix="₹" value={v.selling_price ?? ""} onChange={set("selling_price")} min={0} />
        <NumberInput label="Minimum stock (alert level)" value={v.min_stock ?? ""} onChange={set("min_stock")} min={0} />
        <TextInput label="Supplier / karigar" value={String(v.supplier ?? "")} onChange={(e) => set("supplier")(e.currentTarget.value)} />
        <NumberInput label="Inflation % override" placeholder="Uses category / shop default" suffix="%" value={v.inflation_pct_override ?? ""} onChange={set("inflation_pct_override")} min={0} max={50} />
      </SimpleGrid>
      <Textarea mt="sm" label="Description" value={String(v.description ?? "")} onChange={(e) => set("description")(e.currentTarget.value)} autosize minRows={2} />
      <Group justify="flex-end" mt="lg">
        <Button variant="default" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={save} loading={upd.isPending}>
          Save changes
        </Button>
      </Group>
    </Modal>
  );
}
