import "../styles/MyTestStudent.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { testsAPI } from "../services/api.js";
import notebookIcon from "../assets/bloknot.svg";
import timeIcon from "../assets/time2.svg";

function formatTime(seconds) {
    const value = Number(seconds || 0);
    if (value <= 0) return "Не ограничено";
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    if (hours > 0) return `${hours} ч ${minutes} мин`;
    if (minutes > 0) return `${minutes} мин`;
    return `${value} сек`;
}

const statusText = {
    available: "Доступен",
    in_progress: "Начат",
    locked: "Пока недоступен",
};

export default function MyTestStudent() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [selection, setSelection] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const eventId = Number(searchParams.get("event_id") || searchParams.get("eventId") || 0);
    const specializationId = Number(searchParams.get("specialization_id") || searchParams.get("specializationId") || 0);
    const applicationId = Number(searchParams.get("application_id") || searchParams.get("applicationId") || 0);

    useEffect(() => {
        let cancelled = false;

        const fetchSelection = async () => {
            if (!localStorage.getItem("token")) {
                navigate("/login", { replace: true });
                return;
            }
            if (!eventId) {
                setError("Не выбрано мероприятие. Вернитесь к списку мероприятий.");
                setLoading(false);
                return;
            }

            try {
                const response = await testsAPI.getTestSelection(eventId, specializationId, applicationId);
                if (!cancelled) setSelection(response.data);
            } catch (requestError) {
                console.error("Не удалось загрузить тесты мероприятия", requestError);
                if (!cancelled) setError("Не удалось загрузить тесты мероприятия.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchSelection();
        return () => {
            cancelled = true;
        };
    }, [applicationId, eventId, navigate, specializationId]);

    const tests = useMemo(() => Array.isArray(selection?.tests) ? selection.tests : [], [selection]);
    const activeTests = tests.filter((test) => test.status !== "completed");
    const completedTests = tests.filter((test) => test.status === "completed");

    const openTest = (test) => {
        if (test.status === "locked" || !test.test_link) return;
        const params = new URLSearchParams();
        if (eventId) params.set("event_id", String(eventId));
        if (specializationId) params.set("specialization_id", String(specializationId));
        if (applicationId) params.set("application_id", String(applicationId));
        navigate(`/test-preview/${test.test_link}?${params.toString()}`, { state: { test } });
    };

    return (
        <div className="tests-page">
            <div className="test-page student-logout"><LogoutButton /></div>
            <div className="create-wrapper2">
                <div className="test">
                    <div className="mytests-header">
                        <div>
                            <h2>Тестирование</h2>
                            <p className="mytests-subtitle">Мероприятие #{eventId}</p>
                        </div>
                        <button type="button" className="mytests-start-btn" onClick={() => navigate("/StudentHome")}>
                            К мероприятиям
                        </button>
                    </div>
                    <div className="tests-line" />

                    {loading ? (
                        <p className="mytests-empty">Загрузка тестов...</p>
                    ) : error ? (
                        <p className="mytests-empty">{error}</p>
                    ) : tests.length === 0 ? (
                        <p className="mytests-empty">Для этого мероприятия тесты не назначены.</p>
                    ) : (
                        <>
                            <div className="mytests-list">
                                {activeTests.map((test) => (
                                    <article key={test.config_id} className={`mytests-card-new ${test.status === "locked" ? "is-locked" : ""}`}>
                                        <div className="mytests-card-left">
                                            <div className="mytests-card-icon"><img src={notebookIcon} alt="" /></div>
                                            <div className="mytests-card-info">
                                                <p className="mytests-label">Название теста</p>
                                                <h3 className="mytests-card-title">{test.title || "Тест"}</h3>
                                                {test.description && <p className="mytests-card-description">{test.description}</p>}
                                                {test.message && <p className="mytests-card-description">{test.message}</p>}
                                            </div>
                                        </div>
                                        <div className="mytests-card-divider" />
                                        <div className="mytests-card-right">
                                            <div className="mytests-time-content">
                                                <div className="mytests-time-icon"><img src={timeIcon} alt="" /></div>
                                                <div>
                                                    <p className="mytests-time-label">Время прохождения</p>
                                                    <p className="mytests-time-value">{formatTime(test.time_limit)}</p>
                                                </div>
                                            </div>
                                            <span className={`mytests-status-badge status-${test.status}`}>{statusText[test.status] || test.status}</span>
                                            <button
                                                type="button"
                                                className="mytests-start-btn"
                                                disabled={test.status === "locked"}
                                                onClick={() => openTest(test)}
                                            >
                                                {test.status === "in_progress" ? "Продолжить" : "Перейти к тестированию"}
                                            </button>
                                        </div>
                                    </article>
                                ))}
                            </div>

                            {completedTests.length > 0 && (
                                <section className="mytests-completed">
                                    <h3 className="mytests-completed-title">Завершённые тесты</h3>
                                    <div className="mytests-list-completed">
                                        {completedTests.map((test) => (
                                            <article key={test.config_id} className="mytests-card-completed">
                                                <div className="mytests-completed-info">
                                                    <h4 className="mytests-completed-title-card">{test.title || "Тест"}</h4>
                                                    <span className={`mytests-status-badge ${test.passed ? "status-passed" : "status-failed"}`}>
                                                        {test.passed ? "Пройден" : "Не пройден"}
                                                    </span>
                                                </div>
                                                <div className="mytests-completed-stats">
                                                    <div className="stat-item">
                                                        <span className="stat-label">Баллы</span>
                                                        <span className="stat-value">{test.score ?? 0} / {test.max_score ?? 0}</span>
                                                    </div>
                                                </div>
                                            </article>
                                        ))}
                                    </div>
                                </section>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}