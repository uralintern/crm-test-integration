import {
  BellOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  MailOutlined,
  MessageOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { RuleKind } from "../types";

export function getRuleIcon(kind: RuleKind, code: string) {
  if (kind === "trigger") return <ThunderboltOutlined />;
  if (code.includes("vk") || code.includes("message")) return <MessageOutlined />;
  if (code.includes("mail")) return <MailOutlined />;
  if (code.includes("task")) return <BranchesOutlined />;
  if (code.includes("testing")) return <CheckCircleOutlined />;
  return <BellOutlined />;
}
