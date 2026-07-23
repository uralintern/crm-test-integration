import { useMemo, useState } from "react";
import { useToast } from "../../../components/Toast/ToastProvider";
import { exportInternships } from "../api";
import "./internshipsAdmin.scss";

interface InternshipRow {
    id: number;
    title: string;
    company: string;
    direction: string;
    format: string;
    salary: number;
    dateRange: string;
}

const MOCK_ROWS: InternshipRow[] = [
    { id: 1, title: "Стажёр-аналитик данных (ETL)", company: "Яндекс", direction: "Data Science", format: "Офис", salary: 25000, dateRange: "04.07.2026 - 04.08.2026" },
    { id: 2, title: "ML-инженер (NLP / парсинг)", company: "Сбер", direction: "Backend", format: "Гибрид", salary: 30000, dateRange: "04.07.2026 - 04.08.2026" },
    { id: 3, title: "Frontend-разработчик (React)", company: "ВКонтакте", direction: "Frontend", format: "Удалённо", salary: 25000, dateRange: "04.07.2026 - 04.08.2026" },
    { id: 4, title: "DevOps-инженер", company: "Т-банк", direction: "DevOps", format: "Офис", salary: 30000, dateRange: "04.07.2026 - 04.08.2026" },
];

export default function InternshipsAdminPage() {
    const { showToast } = useToast();

    const [vkGroupId, setVkGroupId] = useState("");
    const [vkToken, setVkToken] = useState("");
    const [savingVk, setSavingVk] = useState(false);

    const [rows, setRows] = useState<InternshipRow[]>(MOCK_ROWS);
    const [selectedIds, setSelectedIds] = useState<number[]>([]);

    const allSelected = selectedIds.length > 0 && selectedIds.length === rows.length;

    const toggleRow = (id: number) => {
        setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
    };

    const toggleAll = () => {
        setSelectedIds(allSelected ? [] : rows.map((r) => r.id));
    };

    const handleSaveVkSettings = async () => {
        setSavingVk(true);
        try {
            await new Promise((resolve) => setTimeout(resolve, 400));
            showToast("success", "Настройки ВКонтакте сохранены");
        } catch {
            showToast("error", "Не удалось сохранить настройки");
        } finally {
            setSavingVk(false);
        }
    };

    const handleDeleteSelected = () => {
        if (selectedIds.length === 0) return;
        setRows((prev) => prev.filter((row) => !selectedIds.includes(row.id)));
        setSelectedIds([]);
        showToast("success", "Выбранные стажировки удалены");
    };

    const handleExport = async (format: "word" | "csv" | "excel") => {
        try {
            await exportInternships(format);
            showToast("success", `Файл ${format.toUpperCase()} сформирован`);
        } catch (error) {
            showToast("error", `Ошибка экспорта в ${format.toUpperCase()}`);
        }
    };

    const exportButtons = useMemo(
        () => [
            { key: "word" as const, label: "Скачать Word", color: "#5493F2" },
            { key: "csv" as const, label: "Скачать CSV", color: "#7BFB9F" },
            { key: "excel" as const, label: "Скачать Excel", color: "#14DA0D" },
        ],
        []
    );

    return (
        <div className="internships-admin-page">
            <div className="container">
                <div className="card title-card">
                    <h1>Панель администратора</h1>
                </div>

                <div className="row">
                    <div className="card disabled-block">
                        <h2 className="section-title">ВКонтакте - интеграция</h2>
                        <hr className="divider" />
                        <label className="field-label" htmlFor="vk-group-id">ID группы ВКонтакте</label>
                        <input
                            type="text"
                            id="vk-group-id"
                            value={vkGroupId}
                            onChange={(e) => setVkGroupId(e.target.value)}
                        />

                        <label className="field-label" htmlFor="vk-token">Токен пользователя</label>
                        <input
                            type="text"
                            id="vk-token"
                            value={vkToken}
                            onChange={(e) => setVkToken(e.target.value)}
                        />

                        <button
                            className="btn-save"
                            type="button"
                            onClick={handleSaveVkSettings}
                            disabled={true}
                        >
                            {savingVk ? "Сохранение..." : "Сохранить настройки"}
                        </button>
                    </div>

                    <div className="card">
                        <h2 className="section-title">Экспорт данных</h2>
                        <hr className="divider" />
                        <div className="export-body">
                            {exportButtons.map((btn) => (
                                <button
                                    key={btn.key}
                                    className="export-item"
                                    type="button"
                                    onClick={() => handleExport(btn.key)}
                                >
                                    <span className="icon-box">
                                        <svg
                                            width="38"
                                            height="48"
                                            viewBox="0 0 38 48"
                                            fill="none"
                                            xmlns="http://www.w3.org/2000/svg"
                                        >
                                            <path
                                                d="M4.5 44.9286C3.39543 44.9286 2.5 44.0331 2.5 42.9286V2.5H23.7143L35.5 14.2857V42.9286C35.5 44.0331 34.6046 44.9286 33.5 44.9286H4.5Z"
                                                stroke={btn.color}
                                                strokeWidth="5"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            />
                                            <path
                                                d="M21.3569 2.5V16.6429H35.4998"
                                                stroke={btn.color}
                                                strokeWidth="5"
                                                strokeLinejoin="round"
                                            />
                                            <path
                                                d="M11.9287 26.0714H26.0716"
                                                stroke={btn.color}
                                                strokeWidth="5"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            />
                                            <path
                                                d="M11.9287 35.5H26.0716"
                                                stroke={btn.color}
                                                strokeWidth="5"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            />
                                        </svg>
                                    </span>
                                    {btn.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="card table-card disabled-block">
                    <div className="table-header">
                        <h2 className="section-title" style={{ margin: 0 }}>Управление стажировками</h2>
                        <button
                            className="btn-delete"
                            type="button"
                            onClick={handleDeleteSelected}
                            disabled={true}
                        >
                            Удалить выбранное
                        </button>
                    </div>

                    <table>
                        <thead>
                            <tr>
                                <th>
                                    <input
                                        type="checkbox"
                                        checked={allSelected}
                                        onChange={toggleAll}
                                    />
                                </th>
                                <th>Стажировка</th>
                                <th>Компания</th>
                                <th>Направление</th>
                                <th>Формат</th>
                                <th>Зарплата</th>
                                <th>Даты</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((row) => (
                                <tr key={row.id}>
                                    <td>
                                        <input
                                            type="checkbox"
                                            checked={selectedIds.includes(row.id)}
                                            onChange={() => toggleRow(row.id)}
                                        />
                                    </td>
                                    <td className="job-title">{row.title}</td>
                                    <td>{row.company}</td>
                                    <td>{row.direction}</td>
                                    <td>{row.format}</td>
                                    <td>{row.salary.toLocaleString("ru-RU")} ₽</td>
                                    <td>{row.dateRange}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}