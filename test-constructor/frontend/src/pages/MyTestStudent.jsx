import "../styles/MyTestStudent.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { testsAPI } from "../services/api.js";

const statusLabels = {
    passed: "Пройден",
    failed: "Не пройден",
    in_progress: "В процессе",
};

function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function normalizeAttempts(data) {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.attempts)) return data.attempts;
    if (Array.isArray(data?.tests)) return data.tests;
    if (Array.isArray(data?.data)) return data.data;
    return [];
}

export default function MyTestStudent() {
    const navigate = useNavigate();
    const [attempts, setAttempts] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState("");

    useEffect(() => {
        const fetchAttempts = async () => {
            try {
                const token = localStorage.getItem("token");
                if (!token) {
                    navigate("/login");
                    return;
                }

                const response = await testsAPI.getAttempts();
                setAttempts(normalizeAttempts(response.data));
                setErrorMessage("");
            } catch (error) {
                console.error("Ошибка при загрузке попыток:", error);
                setAttempts([]);
                setErrorMessage("Не удалось загрузить список тестов.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchAttempts();
    }, [navigate]);

    const completedCount = useMemo(
        () => attempts.filter((attempt) => attempt.status === "passed" || attempt.status === "failed").length,
        [attempts]
    );

    const handleContinue = (attempt) => {
        const link = attempt.test_link || attempt.testLink;
        if (!link) return;

        const params = new URLSearchParams();
        const applicationId = attempt.application_id || attempt.applicationId;
        if (applicationId) params.set("application_id", String(applicationId));
        navigate(`/test/${link}${params.toString() ? `?${params.toString()}` : ""}`);
    };

    return (
        <div className="tests-page">
            <div className="test-page" style={{ position: "absolute", left: "1430px", top: "0px" }}>
                <LogoutButton />
            </div>
            <div className="create-wrapper2">
                <div className="test">
                    <div className="mytests-header">
                        <div>
                            <h2>Мои тесты</h2>
                            <p className="mytests-subtitle">
                                Завершено: {completedCount} из {attempts.length}
                            </p>
                        </div>
                    </div>
                    <div className="tests-line"></div>

                    {isLoading ? (
                        <p className="mytests-empty">Загружаем тесты...</p>
                    ) : errorMessage ? (
                        <p className="mytests-empty">{errorMessage}</p>
                    ) : attempts.length === 0 ? (
                        <p className="mytests-empty">Вы ещё не проходили ни одного теста.</p>
                    ) : (
                        <div className="mytests-list">
                            {attempts.map((attempt, index) => {
                                const status = attempt.status || (attempt.passed ? "passed" : "failed");
                                const statusClass = `mytests-status mytests-status-${status}`;
                                return (
                                    <div key={`${attempt.attempt_id || attempt.id}-${index}`} className="mytests-card">
                                        <div className="mytests-card-header">
                                            <div>
                                                <h3 className="mytests-card-title">
                                                    {attempt.title || attempt.test_title || "Тест"}
                                                </h3>
                                                <p className="mytests-card-meta">
                                                    Заявка #{attempt.application_id || "-"} · Попытка #{attempt.attempt_id || attempt.id}
                                                </p>
                                            </div>
                                            <span className={statusClass}>{statusLabels[status] || "Статус неизвестен"}</span>
                                        </div>

                                        <p className="mytests-card-message">
                                            {attempt.message || attempt.result_text || "Результат ещё не сформирован"}
                                        </p>
                                        {status === "in_progress" && (attempt.test_link || attempt.testLink) && (
                                            <button className="mytests-continue-btn" type="button" onClick={() => handleContinue(attempt)}>
                                                Продолжить тест
                                            </button>
                                        )}
                                        <div className="mytests-card-footer">
                                            <span>Баллы: {attempt.score ?? 0}</span>
                                            <span>Начало: {formatDate(attempt.started_at)}</span>
                                            <span>Завершение: {formatDate(attempt.finished_at)}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
