import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "../styles/StatisticsTest.css";
import LogoutButton from "../components/LogoutButton.jsx";
import BackIcon from "../assets/back.svg?react";

export default function StatisticsTest() {
    const { testId } = useParams();
    const navigate = useNavigate();
    const [attempts, setAttempts] = useState([]);
    const [selectedAttempt, setSelectedAttempt] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAttempts = async () => {
            if (!testId) {
                setLoading(false);
                return;
            }

            try {
                const token = localStorage.getItem("token");
                if (!token) {
                    navigate("/login");
                    return;
                }

                const response = await fetch(
                    `http://localhost:8080/api/manager/tests/${testId}/attempts`,
                    {
                        headers: {
                            "Authorization": `Bearer ${token}`
                        }
                    }
                );

                if (response.ok) {
                    const data = await response.json();
                    let attemptsArray = [];
                    
                    if (Array.isArray(data)) {
                        attemptsArray = data;
                    } else if (data.attempts && Array.isArray(data.attempts)) {
                        attemptsArray = data.attempts;
                    } else if (data.data && Array.isArray(data.data)) {
                        attemptsArray = data.data;
                    }

                    setAttempts(attemptsArray);
                    console.log("Полученные попытки:", attemptsArray);
                } else {
                    console.warn("Не удалось загрузить статистику с сервера");
                    setAttempts([]);
                }
            } catch (error) {
                console.error("Ошибка загрузки статистики:", error);
                setAttempts([]);
            } finally {
                setLoading(false);
            }
        };

        fetchAttempts();
    }, [testId, navigate]);

    const handleBack = () => {
        navigate("/tests");
    };

    const handleOpenDetails = (attempt) => {
        setSelectedAttempt(attempt);
    };

    const handleCloseDetails = () => {
        setSelectedAttempt(null);
    };

    return (
        <div className="tests-page">
            <div
                className="test-page"
                style={{ position: "absolute", left: "1430px", top: "0px" }}
            >
                <LogoutButton />
            </div>
            <div className="create-wrapper2">
                <div className="test2">
                    <div className="stat-top-bar2">
                        <button className="stat-back-btn2" onClick={handleBack}>
                            <BackIcon />
                        </button>
                        <h1>Статистика теста</h1>

                    </div>
                    <div className="tests-line"></div>
                    {attempts.length === 0 ? (
                        <p className="stat-empty">
                            По этому тесту ещё нет попыток.
                        </p>
                    ) : (
                        <div className="stat-attempts-table">
                            <table>
                                <thead>
                                <tr>
                                    <th>Участник</th>
                                    <th>Результат</th>
                                    <th>Время прохождения</th>
                                    <th>Подробная статистика</th>
                                </tr>
                                </thead>
                                <tbody>
                                {attempts.map((a) => (
                                    <tr key={a.id}>
                                        <td className="stat-cell-name">{a.userName}</td>
                                        <td className="stat-cell-score">
                                            {a.passed ? "Пройден" : "Не пройден"}
                                        </td>

                                        <td className="stat-cell-time">
                                            {a.durationMinutes != null
                                                ? `${a.durationMinutes} мин`
                                                : ""}
                                        </td>
                                        <td className="stat-cell-button">
                                            <button
                                                className="stat-details-btn"
                                                onClick={() => handleOpenDetails(a)}
                                            >
                                                Открыть подробную статистику
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        </div>

                    )}

                    {selectedAttempt && (
                        <div className="stat-modal-overlay">
                            <div className="stat-modal">
                                <h3>Подробная статистика</h3>

                                <div className="stat-details-user">
                                    <p>
                                        <strong>Участник:</strong>{" "}
                                        {selectedAttempt.userName}
                                    </p>
                                    <p>
                                        <strong>Почта:</strong>{" "}
                                        {selectedAttempt.userEmail}
                                    </p>
                                    <p>
                                        <strong>Результат теста:</strong>{" "}
                                        {selectedAttempt.score}/{selectedAttempt.totalMax}
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
                                        {(selectedAttempt.perQuestion || []).map((q) => (
                                            <tr key={q.questionIndex}>
                                                <td>{q.questionText}</td>
                                                <td>
                                                    {q.score}/{q.maxScore}
                                                </td>
                                            </tr>
                                        ))}
                                        </tbody>
                                    </table>
                                </div>

                                <button
                                    className="stat-hide-btn"
                                    onClick={handleCloseDetails}
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
