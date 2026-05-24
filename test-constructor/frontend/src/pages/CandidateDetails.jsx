import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import "../styles/CandidateDetails.css";
import LogoutButton from "../components/LogoutButton.jsx";
import BackIcon from "../assets/back.svg?react";
import StatisticsIcon from "../assets/statistics2.svg?react";
import { candidatesAPI } from "../services/api.js";

function normalizeCandidate(data) {
    if (!data) return null;
    return {
        id: data.user_id ?? data.id,
        first_name: data.first_name ?? data.name ?? "",
        last_name: data.last_name ?? data.surname ?? "",
        email: data.email ?? "",
        attempts: Array.isArray(data.attempts) ? data.attempts : [],
    };
}

export default function CandidateDetails() {
    const { candidateId } = useParams();
    const navigate = useNavigate();
    const [candidateData, setCandidateData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState("");
    const [selectedAttempt, setSelectedAttempt] = useState(null);

    useEffect(() => {
        const fetchCandidateData = async () => {
            try {
                const response = await candidatesAPI.getCandidateDetails(candidateId);
                setCandidateData(normalizeCandidate(response.data));
                setErrorMessage("");
            } catch (error) {
                console.error("Ошибка при загрузке данных кандидата:", error);
                setCandidateData(null);
                setErrorMessage("Не удалось загрузить данные кандидата.");
            } finally {
                setLoading(false);
            }
        };

        fetchCandidateData();
    }, [candidateId]);

    const fullName = useMemo(() => {
        if (!candidateData) return "";
        return `${candidateData.first_name} ${candidateData.last_name}`.trim();
    }, [candidateData]);

    if (loading) {
        return (
            <div className="tests-page">
                <LogoutButton />
                <p className="candidates-loading">Загрузка...</p>
            </div>
        );
    }

    if (!candidateData) {
        return (
            <div className="tests-page">
                <LogoutButton />
                <div className="create-wrapper2">
                    <div className="test2">
                        <button className="stat-back-btn2" onClick={() => navigate("/candidates")}>
                            <BackIcon />
                        </button>
                        <p className="candidates-empty">{errorMessage || "Данные кандидата не найдены"}</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="tests-page">
            <div className="test-page">
                <LogoutButton />
            </div>
            <div className="create-wrapper2">
                <div className="test2">
                    <div className="candidate-details-top">
                        <button className="stat-back-btn2" onClick={() => navigate("/candidates")}>
                            <BackIcon />
                        </button>
                        <div className="candidate-header-info">
                            <h1>{fullName || "Кандидат"}</h1>
                            <p className="candidate-email">{candidateData.email}</p>
                        </div>
                    </div>

                    <div className="tests-line"></div>

                    <h2 className="candidate-tests-title">Тестовые задания</h2>

                    <div className="candidate-tests-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Название теста</th>
                                    <th>Мероприятие</th>
                                    <th>Дополнительный тест</th>
                                    <th>Баллы</th>
                                    <th>Статистика</th>
                                </tr>
                            </thead>
                            <tbody>
                                {candidateData.attempts.length > 0 ? (
                                    candidateData.attempts.map((attempt, index) => (
                                        <tr key={`${attempt.attempt_id || index}-${attempt.test_title || "test"}`}>
                                            <td>{attempt.test_title || "Тест"}</td>
                                            <td>{attempt.event_name || "-"}</td>
                                            <td className="extra-test-cell">
                                                <span className={attempt.is_extra ? "badge-yes" : "badge-no"}>
                                                    {attempt.is_extra ? "Да" : "Нет"}
                                                </span>
                                            </td>
                                            <td className="score-cell">
                                                {attempt.score ?? 0}/{attempt.max_score ?? 0}
                                            </td>
                                            <td className="statistics-btn-cell">
                                                <button
                                                    type="button"
                                                    className="candidate-statistics-btn"
                                                    onClick={() => setSelectedAttempt(attempt)}
                                                >
                                                    <StatisticsIcon />
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr>
                                        <td colSpan="5" className="no-attempts">
                                            Тестов не найдено
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {selectedAttempt && (
                        <div className="stat-modal-overlay">
                            <div className="stat-modal">
                                <h3>Подробная статистика</h3>

                                <div className="stat-details-user">
                                    <p><strong>Участник:</strong> {fullName || "Кандидат"}</p>
                                    <p><strong>Почта:</strong> {candidateData.email || "-"}</p>
                                    <p>
                                        <strong>Результат теста:</strong>{" "}
                                        {selectedAttempt.score ?? 0}/{selectedAttempt.max_score ?? 0}
                                    </p>
                                </div>

                                <div className="stat-table-wrapper">
                                    <table className="stat-table">
                                        <thead>
                                            <tr>
                                                <th>Вопрос</th>
                                                <th>Баллы</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(selectedAttempt.questions || []).map((question, index) => (
                                                <tr key={`${question.text || "question"}-${index}`}>
                                                    <td>{question.text || question.question_text || "Вопрос"}</td>
                                                    <td>
                                                        {question.points_earned ?? question.score ?? 0}/
                                                        {question.max_points ?? question.maxScore ?? 0}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>

                                <button
                                    type="button"
                                    className="stat-hide-btn"
                                    onClick={() => setSelectedAttempt(null)}
                                >
                                    Скрыть подробную статистику
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
