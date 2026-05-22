import { DatePicker } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import "./date-field.scss";

dayjs.extend(customParseFormat);

const { RangePicker } = DatePicker;

export const ISO_DATE_FORMAT = "YYYY-MM-DD";
export const RU_DATE_FORMAT = "DD.MM.YYYY";

type BaseFieldProps = {
  label?: string;
  className?: string;
  disabled?: boolean;
  allowClear?: boolean;
};

type SingleDateFieldProps = BaseFieldProps & {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

type DateRangeFieldProps = BaseFieldProps & {
  startValue?: string;
  endValue?: string;
  onChange: (startValue: string, endValue: string) => void;
  placeholders?: [string, string];
};

function parseIsoDate(value?: string): Dayjs | null {
  if (!value) return null;
  const parsed = dayjs(value, ISO_DATE_FORMAT, true);
  return parsed.isValid() ? parsed : null;
}

function toIsoDate(value: Dayjs | null | undefined) {
  return value?.isValid() ? value.format(ISO_DATE_FORMAT) : "";
}

function joinClassName(baseClassName: string, className?: string) {
  return [baseClassName, className].filter(Boolean).join(" ");
}

export default function DateField({
  value,
  onChange,
  label,
  placeholder = "Выберите дату",
  className,
  disabled = false,
  allowClear = false,
}: SingleDateFieldProps) {
  return (
    <label className={joinClassName("app-date-field", className)}>
      {label && <span className="text-small">{label}</span>}
      <DatePicker
        className="app-date-picker"
        value={parseIsoDate(value)}
        onChange={(nextValue) => onChange(toIsoDate(nextValue))}
        format={RU_DATE_FORMAT}
        placeholder={placeholder}
        disabled={disabled}
        allowClear={allowClear}
        variant="outlined"
      />
    </label>
  );
}

export function DateRangeField({
  startValue,
  endValue,
  onChange,
  label,
  className,
  placeholders = ["Дата начала", "Дата завершения"],
  disabled = false,
  allowClear = false,
}: DateRangeFieldProps) {
  return (
    <label className={joinClassName("app-date-range-field", className)}>
      {label && <span className="text-small">{label}</span>}
      <RangePicker
        className="app-date-picker app-date-picker--range"
        value={[parseIsoDate(startValue), parseIsoDate(endValue)]}
        onChange={(nextValues) => onChange(toIsoDate(nextValues?.[0]), toIsoDate(nextValues?.[1]))}
        format={RU_DATE_FORMAT}
        placeholder={placeholders}
        disabled={disabled}
        allowClear={allowClear}
        variant="outlined"
        separator={<span className="app-date-range-separator">→</span>}
      />
    </label>
  );
}
