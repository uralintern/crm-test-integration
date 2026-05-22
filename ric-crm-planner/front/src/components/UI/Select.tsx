import { Select as AntSelect } from "antd";
import type { SelectProps } from "antd";
import "../../styles/ui.scss";

type AppSelectTone = "event" | "directions" | "projects";
type AppSelectValue = string | number | Array<string | number>;

type AppSelectProps = SelectProps<AppSelectValue> & {
  tone?: AppSelectTone;
};

export default function Select({
  className = "",
  classNames,
  tone,
  popupMatchSelectWidth = false,
  listHeight = 260,
  showSearch = false,
  ...props
}: AppSelectProps) {
  const toneClass = tone ? `app-select--${tone}` : "";
  const popupToneClass = tone ? `app-select-dropdown--${tone}` : "";
  const popupRootClass = ["app-select-dropdown", popupToneClass, classNames?.popup?.root].filter(Boolean).join(" ");

  return (
    <AntSelect
      {...props}
      popupMatchSelectWidth={popupMatchSelectWidth}
      listHeight={listHeight}
      showSearch={showSearch}
      className={`app-select ${toneClass} ${className}`.trim()}
      classNames={{
        ...classNames,
        popup: {
          ...classNames?.popup,
          root: popupRootClass,
        },
      }}
    />
  );
}
