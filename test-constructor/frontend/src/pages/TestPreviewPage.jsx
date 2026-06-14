import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { testsAPI } from "../services/api.js";
import "../styles/TestPreviewPage.css";
import LogoutButton from "../components/LogoutButton.jsx";

function formatTime(seconds) {
    const value = Number(seconds || 0);
    if (value <= 0) return "Не ограничено";
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    if (hours > 0) return `${hours} ч ${minutes} мин`;
    if (minutes > 0) return `${minutes} мин`;
    return `${value} сек`;
}

export default function TestPreviewPage() {
    const { test_link: testLink } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const hasInitialTest = Boolean(location.state?.test);
    const hasSelectionContext = Number(searchParams.get("event_id") || 0) > 0;
    const [test, setTest] = useState(location.state?.test || null);
    const [loading, setLoading] = useState(!hasInitialTest && hasSelectionContext);
    const [error, setError] = useState(!hasInitialTest && !hasSelectionContext ? "Откройте тест из списка мероприятия." : "");

    const eventId = Number(searchParams.get("event_id") || 0);
    const specializationId = Number(searchParams.get("specialization_id") || 0);
    const applicationId = Number(searchParams.get("application_id") || 0);

    useEffect(() => {
        if (test || !testLink || !eventId) return;

        let cancelled = false;
        testsAPI.getTestSelection(eventId, specializationId, applicationId)
            .then((response) => {
                if (cancelled) return;
                const item = (response.data?.tests || []).find((candidate) => candidate.test_link === testLink);
                if (item) setTest(item);
                else setError("Тест не найден или пока недоступен.");
            })
            .catch((requestError) => {
                console.error("Не удалось загрузить сведения о тесте", requestError);
                if (!cancelled) setError("Не удалось загрузить сведения о тесте.");
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [applicationId, eventId, specializationId, test, testLink]);

    const handleStartTest = () => {
        const params = new URLSearchParams();
        if (applicationId) params.set("application_id", String(applicationId));
        if (eventId) params.set("event_id", String(eventId));
        if (specializationId) params.set("specialization_id", String(specializationId));
        navigate(`/test/${testLink}${params.toString() ? `?${params.toString()}` : ""}`);
    };

    if (loading) return <div className="test-preview-page"><div className="test-preview-loading"><p>Загрузка теста...</p></div></div>;
    if (error || !test) {
        return (
            <div className="test-preview-page">
                <div className="test-preview-error">
                    <p>{error || "Тест не найден."}</p>
                    <button className="test-preview-back-btn" type="button" onClick={() => navigate(-1)}>Назад</button>
                </div>
            </div>
        );
    }

    return (
        <div className="test-preview-page">
            <div className="test-preview-header"><LogoutButton /></div>
            <div className="test-preview-wrapper">
                <div className="test-preview-container">
                    <div className="preview-title-section">
                        <h1 className="preview-title">Перед началом тестирования</h1>
                        <p className="preview-subtitle">Ознакомьтесь с информацией о тесте. Отсчёт времени начнётся после нажатия кнопки.</p>
                    </div>
                    <div className="preview-test-card">
                        <div className="preview-card-left">
                            <div className="preview-card-icon" aria-hidden="true">?</div>
                            <div className="preview-card-info">
                                <div className="preview-info-section">
                                    <span className="preview-info-label">Название</span>
                                    <h2 className="preview-info-title">{test.title || "Тест"}</h2>
                                </div>
                                {test.description && (
                                    <div className="preview-info-section">
                                        <span className="preview-info-label">Описание</span>
                                        <p className="preview-info-description">{test.description}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="preview-card-divider" />
                        <div className="preview-card-right">
                            <div className="preview-time-section">
                                <span className="preview-time-label">Время прохождения</span>
                                <p className="preview-time-value">{formatTime(test.time_limit)}</p>
                                {test.max_score > 0 && <p className="preview-info-description">Максимальный балл: {test.max_score}</p>}
                            </div>
                        </div>
                    </div>
                    <div className="preview-notice">
                        <p className="notice-text">После начала теста не закрывайте страницу до отправки ответов.</p>
                    </div>
                    <div className="preview-button-section">
                        <button className="preview-start-btn" type="button" onClick={handleStartTest}>
                            Начать тестирование
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}