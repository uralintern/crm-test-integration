import { LoadingOutlined } from "@ant-design/icons";
import "./page-loader.scss";

type PageLoaderProps = {
  label?: string;
  className?: string;
};

export default function PageLoader({ label = "Загрузка", className = "" }: PageLoaderProps) {
  return (
    <div className={`page-loader ${className}`.trim()} role="status" aria-live="polite">
      <LoadingOutlined className="page-loader__icon" spin />
      <span>{label}</span>
    </div>
  );
}
