import "../../styles/table-header.scss";
import { useContext } from "react";
import { PlusOutlined } from "@ant-design/icons";
import { AuthContext } from "../../context/AuthContext";
import AppButton from "../UI/Button";
import { AppSearch } from "../UI/Input";

interface Props {
  title: React.ReactNode;
  search?: string;
  onSearch?: (v: string) => void;
  onSearchSubmit?: (v: string) => void;
  onCreate?: () => void;
}

export default function TableHeader({
  title,
  search,
  onSearch,
  onSearchSubmit,
  onCreate
}: Props) {
  const { user } = useContext(AuthContext);
  const isOrganizer = user?.role === "organizer";

  return (
    <div className="table-header">
      <div className="left-side">
        <h1 className="h1">{title}</h1>

        {isOrganizer && onCreate && (
          <AppButton className="create-btn" onClick={onCreate}>
            <PlusOutlined />
          </AppButton>
        )}
      </div>

      {search !== undefined && (
        <div className="right-side">
          <AppSearch
            className="search-box"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => onSearch?.(e.target.value)}
            onSearch={(value) => onSearchSubmit?.(value)}
          />
        </div>
      )}
    </div>
  );
}

