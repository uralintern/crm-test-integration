import { Button as AntButton } from "antd";
import type { ButtonProps } from "antd";
import "../../styles/ui.scss";

type AppButtonProps = Omit<ButtonProps, "type" | "htmlType"> & {
  type?: "button" | "submit" | "reset";
  variant?: ButtonProps["type"];
};

export default function Button({ className = "", type = "button", variant, ...props }: AppButtonProps) {
  return (
    <AntButton
      {...props}
      htmlType={type}
      type={variant ?? "text"}
      className={`app-button ${className}`.trim()}
    />
  );
}
