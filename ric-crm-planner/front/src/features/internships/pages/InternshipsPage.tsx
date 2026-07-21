import { useEffect, useMemo, useState } from "react";
import {
    getInternships,
    WORK_FORMAT_OPTIONS,
    type InternshipListItem,
    type WorkFormatCode,
} from "../api";
import "./internships.scss";

const DIRECTIONS = ["Разработка", "Тестирование", "Безопасность", "Аналитика"];
const PAGE_SIZE = 20;

export default function InternshipsPage() {
    const [allItems, setAllItems] = useState<InternshipListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const [search, setSearch] = useState("");
    const [selectedDirections, setSelectedDirections] = useState<string[]>([]);
    const [selectedFormats, setSelectedFormats] = useState<WorkFormatCode[]>([]);
    const [city, setCity] = useState("");
    const [sort, setSort] = useState<"new" | "salary">("new");
    const [page, setPage] = useState(1);

    useEffect(() => {
        let cancelled = false;

        async function loadAll() {
            setLoading(true);
            setError("");
            try {
                const collected: InternshipListItem[] = [];
                let currentPage = 1;
                let totalPages = 1;

                do {
                    const response = await getInternships({
                        page: currentPage,
                        format: selectedFormats.length ? selectedFormats : undefined,
                        city: city.trim() ? [city.trim()] : undefined,
                    });
                    if (cancelled) return;
                    collected.push(...response.data);
                    totalPages = response.pagination.total_pages;
                    currentPage += 1;
                } while (currentPage <= totalPages);

                if (!cancelled) setAllItems(collected);
            } catch {
                if (!cancelled) setError("Не удалось загрузить список стажировок");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        void loadAll();
        return () => {
            cancelled = true;
        };
    }, [selectedFormats, city]);

    useEffect(() => {
        setPage(1);
    }, [selectedFormats, city, search, selectedDirections, sort]);

    const toggleDirection = (direction: string) => {
        setSelectedDirections((prev) =>
            prev.includes(direction) ? prev.filter((d) => d !== direction) : [...prev, direction]
        );
    };

    const toggleFormat = (code: WorkFormatCode) => {
        setSelectedFormats((prev) => (prev.includes(code) ? prev.filter((f) => f !== code) : [...prev, code]));
    };

    const filteredAndSorted = useMemo(() => {
        const filtered = allItems.filter((item) => {
            const matchesSearch =
                !search.trim() ||
                item.title.toLowerCase().includes(search.trim().toLowerCase()) ||
                item.company.toLowerCase().includes(search.trim().toLowerCase());
            const matchesDirection = selectedDirections.length === 0 || selectedDirections.includes(item.direction);
            return matchesSearch && matchesDirection;
        });

        return [...filtered].sort((a, b) => {
            if (sort === "salary") return (b.salary_from ?? 0) - (a.salary_from ?? 0);
            return 0;
        });
    }, [allItems, search, selectedDirections, sort]);

    const totalPages = Math.max(1, Math.ceil(filteredAndSorted.length / PAGE_SIZE));
    const visibleItems = filteredAndSorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    const avatarLetter = (company: string) => company.trim().charAt(0).toUpperCase() || "?";

    return (
        <div className="internships-page">
            <div className="container">
                <header className="top-block" />

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
                            {WORK_FORMAT_OPTIONS.map((opt) => (
                                <button
                                    key={opt.code}
                                    type="button"
                                    className={`format-option${selectedFormats.includes(opt.code) ? " active" : ""}`}
                                    onClick={() => toggleFormat(opt.code)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>

                        <hr className="divider" />

                        <div className="sidebar-label">ГОРОД</div>
                        <input
                            type="text"
                            className="city-input"
                            placeholder="Например, Екатеринбург"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                        />
                    </aside>

                    <section className="main-content">
                        <div className="sort-block">
                            <span className="sort-label">Сортировка:</span>
                            <button
                                type="button"
                                className={`sort-option${sort === "new" ? " active" : ""}`}
                                onClick={() => setSort("new")}
                            >
                                Новые
                            </button>
                            <button
                                type="button"
                                className={`sort-option${sort === "salary" ? " active" : ""}`}
                                onClick={() => setSort("salary")}
                            >
                                По зарплате
                            </button>
                        </div>

                        <div className="cards-wrapper">
                            {loading && <div>Загрузка...</div>}
                            {!loading && error && <div>{error}</div>}
                            {!loading && !error && visibleItems.length === 0 && <div>Ничего не найдено по заданным фильтрам</div>}

                            {!loading && !error && visibleItems.length > 0 && (
                                <>
                                    <div className="cards">
                                        {visibleItems.map((item) => (
                                            <div className="card" key={item.id}>
                                                <div className="card-top">
                                                    <div className="avatar yandex">{avatarLetter(item.company)}</div>
                                                    <div className="card-heading">
                                                        <span className="company">{item.company}</span>
                                                        <span className="job-title">{item.title}</span>
                                                    </div>
                                                </div>
                                                <div className="tags">
                                                    <span>{item.direction}</span>
                                                    {item.work_format && <span>{item.work_format}</span>}
                                                    {item.city && <span>{item.city}</span>}
                                                </div>
                                                {item.salary_from != null && (
                                                    <div className="salary">от {item.salary_from.toLocaleString("ru-RU")} ₽</div>
                                                )}
                                                <div className="card-bottom">
                                                    <a className="source-btn source-link" href={item.link} target="_blank" rel="noopener noreferrer">
                                                        К источнику
                                                    </a>
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="pagination-controls">
                                        <button
                                            type="button"
                                            className="format-option"
                                            disabled={page <= 1}
                                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                                        >
                                            Назад
                                        </button>
                                        <span className="pagination-label">
                                            Страница {page} из {totalPages}
                                        </span>
                                        <button
                                            type="button"
                                            className="format-option"
                                            disabled={page >= totalPages}
                                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                        >
                                            Вперёд
                                        </button>
                                    </div>
                                </>
                            )}
                        </div>
                    </section>
                </main>
            </div>
        </div>
    );
}