import "../styles/MyTestStudent.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { internAPI, testsAPI } from "../services/api.js";

function normalizeAttempts(data) {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.attempts)) return data.attempts;
    if (Array.isArray(data?.tests)) return data.tests;
    return [];
}

function getStoredApplication() {
    try {
        return JSON.parse(localStorage.getItem("testingApplication") || "null");
    } catch {
        return null;
    }
}

export default function StudentHome() {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState("applications");
    const [applications, setApplications] = useState([]);
    const [attempts, setAttempts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;

        const fetchData = async () => {
            if (!localStorage.getItem("token")) {
                navigate("/login", { replace: true });
                return;
            }

            try {
                const [eventsResponse, attemptsResponse] = await Promise.all([
                    internAPI.getUserEvents(),
                    testsAPI.getAttempts(),
                ]);
                if (cancelled) return;
                setApplications(Array.isArray(eventsResponse.data) ? eventsResponse.data : []);
                setAttempts(normalizeAttempts(attemptsResponse.data));
            } catch (requestError) {
                console.error("Не удалось загрузить данные участника", requestError);
                if (!cancelled) setError("Не удалось загрузить мероприятия и результаты тестирования.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchData();
        return () => {
            cancelled = true;
        };
    }, [navigate]);

    const completedTests = useMemo(
        () => attempts.filter((attempt) => attempt.status === "passed" || attempt.status === "failed"),
        [attempts]
    );

    const openEvent = (item) => {
        const stored = getStoredApplication();
        const storedEventId = Number(stored?.event?.id || 0);
        const specializationId = storedEventId === Number(item.event_id)
            ? Number(stored?.specialization?.id || 0)
            : 0;
        const params = new URLSearchParams({
            event_id: String(item.event_id),
            application_id: String(item.application_id),
        });
        if (specializationId) params.set("specialization_id", String(specializationId));
        navigate(`/myTestStudent?${params.toString()}`);
    };

    return (
        <div className="tests-page">
            <div className="test-page student-logout"><LogoutButton /></div>
            <div className="create-wrapper2">
                <div className="test">
                    <div className="tests-tabs">
                        <button
                            type="button"
                            className={`tab-btn ${activeTab === "applications" ? "tab-btn-active" : ""}`}
                            onClick={() => setActiveTab("applications")}
                        >
                            Мероприятия
                        </button>
                        <button
                            type="button"
                            className={`tab-btn ${activeTab === "tests" ? "tab-btn-active" : ""}`}
                            onClick={() => setActiveTab("tests")}
                        >
                            Результаты тестов
                        </button>
                    </div>

                    {loading ? (
                        <p className="mytests-empty">Загрузка данных...</p>
                    ) : error ? (
                        <p className="mytests-empty">{error}</p>
                    ) : activeTab === "applications" ? (
                        applications.length === 0 ? (
                            <p className="mytests-empty">Нет мероприятий, доступных для тестирования.</p>
                        ) : (
                            <div className="mytests-list">
                                {applications.map((item) => (
                                    <article key={`${item.event_id}-${item.application_id}`} className="mytests-card event-card">
                                        <div>
                                            <h3 className="mytests-card-title">Мероприятие #{item.event_id}</h3>
                                            <p className="mytests-card-meta">Заявка #{item.application_id}</p>
                                        </div>
                                        <button type="button" className="mytests-start-btn" onClick={() => openEvent(item)}>
                                            Открыть тесты
                                        </button>
                                    </article>
                                ))}
                            </div>
                        )
                    ) : completedTests.length === 0 ? (
                        <p className="mytests-empty">Завершённых тестов пока нет.</p>
                    ) : (
                        <div className="mytests-list-completed">
                            {completedTests.map((attempt) => (
                                <article key={attempt.attempt_id || attempt.id} className="mytests-card-completed">
                                    <div className="mytests-completed-info">
                                        <h3 className="mytests-completed-title-card">{attempt.test_title || attempt.title || "Тест"}</h3>
                                        <span className={`mytests-status-badge ${attempt.passed ? "status-passed" : "status-failed"}`}>
                                            {attempt.passed ? "Пройден" : "Не пройден"}
                                        </span>
                                    </div>
                                    <div className="mytests-completed-stats">
                                        <div className="stat-item">
                                            <span className="stat-label">Баллы</span>
                                            <span className="stat-value">
                                                {attempt.score ?? 0}{attempt.max_score ? ` / ${attempt.max_score}` : ""}
                                            </span>
                                        </div>
                                    </div>
                                </article>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}