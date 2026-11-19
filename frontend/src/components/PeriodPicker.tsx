import { Group, SegmentedControl, Select } from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { IconCalendar } from "@tabler/icons-react";
import dayjs from "dayjs";
import { usePeriodOptions } from "../api/hooks";
import type { PeriodType } from "../api/types";
import { usePeriod } from "../stores";

/** Day | Month | Quarter + a date / period select. Bound to the shared period store unless value/onChange are given. */
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
  const size = compact ? "xs" : "sm";
  const today = dayjs().format("YYYY-MM-DD");

  const toggle = (
    <SegmentedControl
      size={size}
      value={cur.period_type}
      onChange={(t) => set({ period_type: t as PeriodType, anchor: null })}
      data={[
        { value: "day", label: "Day" },
        { value: "month", label: "Month" },
        { value: "quarter", label: "Quarter" },
      ]}
    />
  );

  if (cur.period_type === "day") {
    const selected = cur.anchor ?? today;
    return (
      <Group gap="xs" wrap="nowrap">
        {toggle}
        <DateInput
          size={size}
          w={compact ? 170 : 210}
          aria-label="Choose day"
          leftSection={<IconCalendar size={14} />}
          value={selected}
          maxDate={new Date()}
          valueFormat={selected === today ? "[Today], D MMM YYYY" : "ddd, D MMM YYYY"}
          onChange={(v) => {
            const d = v ? dayjs(v).format("YYYY-MM-DD") : today;
            set({ period_type: "day", anchor: d === today ? null : d });
          }}
          popoverProps={{ withinPortal: true }}
        />
      </Group>
    );
  }

  const opts = (cur.period_type === "quarter" ? data?.quarters : data?.months) ?? [];
  const selected = cur.anchor ?? opts[0]?.anchor ?? null;
  return (
    <Group gap="xs" wrap="nowrap">
      {toggle}
      <Select
        size={size}
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
