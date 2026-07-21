import { useMemo, useState } from "react";
import "./internships.scss";

interface Internship {
    id: number;
    company: string;
    avatarLetter: string;
    avatarClass: "yandex" | "sber" | "vk" | "tbank";
    title: string;
    direction: string;
    format: "Офис" | "Удалённо" | "Гибрид";
    salary: number;
    publishedAt: string;
    deadline: string;
}

const MOCK_INTERNSHIPS: Internship[] = [
    { id: 1, company: "Яндекс", avatarLetter: "Я", avatarClass: "yandex", title: "Стажёр-аналитик данных (ETL)", direction: "Data science", format: "Офис", salary: 25000, publishedAt: "2026-07-04", deadline: "2026-08-04" },
    { id: 2, company: "Сбер", avatarLetter: "С", avatarClass: "sber", title: "ML-инженер (NLP / парсинг)", direction: "Backend-разработка", format: "Гибрид", salary: 30000, publishedAt: "2026-07-04", deadline: "2026-08-04" },
    { id: 3, company: "ВКонтакте", avatarLetter: "VK", avatarClass: "vk", title: "Frontend-разработчик (React)", direction: "Frontend-разработка", format: "Удалённо", salary: 25000, publishedAt: "2026-07-04", deadline: "2026-08-04" },
    { id: 4, company: "Т-банк", avatarLetter: "Т", avatarClass: "tbank", title: "DevOps-инженер", direction: "DevOps", format: "Офис", salary: 30000, publishedAt: "2026-07-04", deadline: "2026-08-04" },
];

const DIRECTIONS = ["Data science", "Backend-разработка", "Frontend-разработка", "DevOps", "Продуктовый менеджмент"];
const FORMATS: Internship["format"][] = ["Офис", "Удалённо", "Гибрид"];
type SortKey = "new" | "deadline" | "salary";

export default function InternshipsPage() {
    const [search, setSearch] = useState("");
    const [selectedDirections, setSelectedDirections] = useState<string[]>(["Data science"]);
    const [format, setFormat] = useState<Internship["format"] | null>("Офис");
    const [city, setCity] = useState("Екатеринбург");
    const [sort, setSort] = useState<SortKey>("new");

    const toggleDirection = (direction: string) => {
        setSelectedDirections((prev) =>
            prev.includes(direction) ? prev.filter((d) => d !== direction) : [...prev, direction]
        );
    };

    const filtered = useMemo(() => {
        let list = MOCK_INTERNSHIPS.filter((item) => {
            const matchesSearch =
                !search.trim() ||
                item.title.toLowerCase().includes(search.trim().toLowerCase()) ||
                item.company.toLowerCase().includes(search.trim().toLowerCase());
            const matchesDirection = selectedDirections.length === 0 || selectedDirections.includes(item.direction);
            const matchesFormat = !format || item.format === format;
            return matchesSearch && matchesDirection && matchesFormat;
        });

        list = [...list].sort((a, b) => {
            if (sort === "salary") return b.salary - a.salary;
            if (sort === "deadline") return a.deadline.localeCompare(b.deadline);
            return b.publishedAt.localeCompare(a.publishedAt);
        });

        return list;
    }, [search, selectedDirections, format, sort]);

    return (
        <div className="internships-page">
            <div className="container">

                <section className="title-block">
                    <h1>Стажировки</h1>
                </section>

                <main className="content">
                    <aside className="sidebar">
                        <div className="sidebar-label">ПОИСК</div>
                        <div className="search-box">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="11" cy="11" r="7" />
                                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                            </svg>
                            <input
                                type="text"
                                placeholder="Название, компания..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                            />
                        </div>

                        <hr className="divider" />

                        <div className="sidebar-label">НАПРАВЛЕНИЕ</div>
                        <div className="checkbox-list">
                            {DIRECTIONS.map((direction) => (
                                <label className="checkbox-item" key={direction}>

                                    <input
                                        type="checkbox"
                                        checked={selectedDirections.includes(direction)}
                                        onChange={() => toggleDirection(direction)}
                                    />
                                    {direction}
                                </label>
                            ))}
                        </div>

                        <hr className="divider" />

                        <div className="sidebar-label">ФОРМАТ</div>
                        <div className="format-list">
                            {FORMATS.map((f) => (
                                <button
                                    key={f}
                                    type="button"
                                    className={`format-option${format === f ? " active" : ""}`}
                                    onClick={() => setFormat(format === f ? null : f)}
                                >
                                    {f}
                                </button>
                            ))}
                        </div>

                        <hr className="divider" />

                        <div className="sidebar-label">ГОРОД</div>
                        <input
                            type="text"
                            className="city-input"
                            placeholder="Введите город"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                        />
                        <button type="button" className="format-option active">
                            {city || "Екатеринбург"}
                        </button>
                    </aside>

                    <section className="main-content">
                        <div className="sort-block">
                            <span className="sort-label">Сортировка:</span>
                            <button type="button" className={`sort-option${sort === "new" ? " active" : ""}`} onClick={() => setSort("new")}>
                                Новые
                            </button>
                            <button type="button" className={`sort-option${sort === "deadline" ? " active" : ""}`} onClick={() => setSort("deadline")}>
                                По дедлайну
                            </button>
                            <button type="button" className={`sort-option${sort === "salary" ? " active" : ""}`} onClick={() => setSort("salary")}>
                                По зарплате
                            </button>
                        </div>

                        <div className="cards-wrapper">
                            {filtered.length === 0 ? (
                                <div>Ничего не найдено по заданным фильтрам</div>
                            ) : (
                                <div className="cards">
                                    {filtered.map((item) => (
                                        <div className="card" key={item.id}>
                                            <div className="card-top">
                                                <div className={`avatar ${item.avatarClass}`}>{item.avatarLetter}</div>
                                                <div className="card-heading">
                                                    <span className="company">{item.company}</span>
                                                    <span className="job-title">{item.title}</span>
                                                </div>
                                            </div>
                                            <div className="tags">
                                                <span>{item.direction}</span>
                                                <span>{item.format}</span>
                                            </div>
                                            <div className="salary">{item.salary.toLocaleString("ru-RU")} ₽</div>
                                            <div className="card-bottom">
                                                <span className="date-badge">{item.publishedAt}</span>
                                                <span className="date-badge">{item.deadline}</span>
                                                <button type="button" className="source-btn">
                                                    К источнику
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </section>
                </main>
            </div>
        </div>
    );
}