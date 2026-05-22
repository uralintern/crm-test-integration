import type { ComponentProps, ReactNode } from "react";
import { Input as AntInput } from "antd";
import "../../styles/ui.scss";

type AppInputProps = ComponentProps<typeof AntInput>;
type AppPasswordProps = ComponentProps<typeof AntInput.Password>;
type AppSearchProps = ComponentProps<typeof AntInput.Search> & {
  suffixIcon?: ReactNode;
};
type AppTextAreaProps = ComponentProps<typeof AntInput.TextArea>;

export default function Input({ className = "", variant = "filled", ...props }: AppInputProps) {
  return <AntInput {...props} variant={variant} className={`app-input ${className}`.trim()} />;
}

export function AppPassword({ className = "", variant = "filled", ...props }: AppPasswordProps) {
  return <AntInput.Password {...props} variant={variant} className={`app-input app-input-password ${className}`.trim()} />;
}

export function AppSearch({ className = "", variant = "outlined", allowClear = true, suffixIcon: _suffixIcon, enterButton = true, ...props }: AppSearchProps) {
  return <AntInput.Search {...props} allowClear={allowClear} enterButton={enterButton} variant={variant} className={`app-search ${className}`.trim()} />;
}

export function AppTextArea({ className = "", variant = "filled", ...props }: AppTextAreaProps) {
  return <AntInput.TextArea {...props} variant={variant} className={`app-input app-textarea ${className}`.trim()} />;
}
