import { CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { Switch as AntSwitch } from "antd";
import type { SwitchProps } from "antd";
import "../../styles/ui.scss";

type AppSwitchProps = SwitchProps & {
  compact?: boolean;
};

export default function AppSwitch({ className = "", compact = false, ...props }: AppSwitchProps) {
  return (
    <AntSwitch
      {...props}
      checkedChildren={<CheckOutlined />}
      unCheckedChildren={<CloseOutlined />}
      className={`app-switch ${compact ? "app-switch--compact" : ""} ${className}`.trim()}
    />
  );
}
