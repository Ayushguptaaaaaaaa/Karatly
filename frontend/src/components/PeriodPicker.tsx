import { Group, SegmentedControl, Select } from "@mantine/core";
import { usePeriodOptions } from "../api/hooks";
import type { PeriodType } from "../api/types";
import { usePeriod } from "../stores";

/** Month | Quarter + select. Bound to the shared period store unless value/onChange are given. */
export function PeriodPicker({
  compact = false, value, onChange,
}: {
  compact?: boolean;
  value?: { period_type: PeriodType; anchor: string | null };
  onChange?: (v: { period_type: PeriodType; anchor: string | null }) => void;
}) {
  const store = usePeriod();
  const cur = value ?? { period_type: store.period_type, anchor: store.anchor };
  const set = onChange ?? ((v: { period_type: PeriodType; anchor: string | null }) => store.setPeriod(v.period_type, v.anchor));
  const { data } = usePeriodOptions();
  const opts = (cur.period_type === "quarter" ? data?.quarters : data?.months) ?? [];
  const selected = cur.anchor ?? opts[0]?.anchor ?? null;

  return (
    <Group gap="xs" wrap="nowrap">
      <SegmentedControl
        size={compact ? "xs" : "sm"}
        value={cur.period_type}
        onChange={(t) => set({ period_type: t as PeriodType, anchor: null })}
        data={[
          { value: "month", label: "Month" },
          { value: "quarter", label: "Quarter" },
        ]}
      />
      <Select
        size={compact ? "xs" : "sm"}
        w={compact ? 170 : 230}
        allowDeselect={false}
        aria-label="Choose period"
        value={selected}
        data={opts.map((o, i) => ({ value: o.anchor, label: i === 0 ? `${o.label} (current)` : o.label }))}
        onChange={(a) => set({ period_type: cur.period_type, anchor: a && a !== opts[0]?.anchor ? a : null })}
        comboboxProps={{ withinPortal: true }}
      />
    </Group>
  );
}
