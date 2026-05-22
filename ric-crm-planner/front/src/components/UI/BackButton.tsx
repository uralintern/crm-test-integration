import { ArrowLeftOutlined } from "@ant-design/icons";
import "./back-button.scss";
import AppButton from "./Button";

interface Props {
  onClick: () => void;
}

export default function BackButton({ onClick }: Props) {
  return (
    <AppButton className="back-btn--icon" onClick={onClick}>
      <ArrowLeftOutlined />
    </AppButton>
  );
}
