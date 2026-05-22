import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import "../styles/StatisticsEvent.css";

import LogoutButton from "../components/LogoutButton.jsx";
import BackIcon from "../assets/back.svg?react";

export default function StatisticsEvent() {
    const navigate = useNavigate();
    const { eventId } = useParams();

    const [selectedStatistic, setSelectedStatistic] = useState(null);

    const participants = [
        {
            id: 1,
            userName: "Иван Иванов",
            email: "ivan@test.com",
            tests: [
                {
                    id: 11,
                    testName: "React",
                    score: "8/10",
                    questions: [
                        {
                            questionIndex: 1,
                            questionText: "Что такое useState?",
                            score: 2,
                            maxScore: 2,
                        },
                        {
                            questionIndex: 2,
                            questionText: "Что такое props?",
                            score: 1,
                            maxScore: 2,
                        },
                    ],
                },
                {
                    id: 12,
                    testName: "Java",
                    score: "7/10",
                    questions: [
                        {
                            questionIndex: 1,
                            questionText: "Что такое JVM?",
                            score: 2,
                            maxScore: 2,
                        },
                    ],
                },
                {
                    id: 13,
                    testName: "SQL",
                    score: "10/10",
                    questions: [
                        {
                            questionIndex: 1,
                            questionText: "Что делает JOIN?",
                            score: 2,
                            maxScore: 2,
                        },
                    ],
                },
            ],
        },
        {
            id: 2,
            userName: "Петр Петров",
            email: "petr@test.com",
            tests: [
                {
                    id: 21,
                    testName: "React",
                    score: "5/10",
                    questions: [
                        {
                            questionIndex: 1,
                            questionText: "Что такое JSX?",
                            score: 1,
                            maxScore: 2,
                        },
                    ],
                },
                {
                    id: 22,
                    testName: "Java",
                    score: "9/10",
                    questions: [
                        {
                            questionIndex: 1,
                            questionText: "Что такое класс?",
                            score: 2,
                            maxScore: 2,
                        },
                    ],
                },
                {
                    id: 23,
                    testName: "SQL",
                    score: "6/10",
                    questions: [
                        {
                            questionIndex: 1,
                            questionText: "Что такое SELECT?",
                            score: 1,
                            maxScore: 2,
                        },
                    ],
                },
            ],
        },
    ];

    const testHeaders = ["React", "Java", "SQL"];

    const handleBack = () => {
        navigate("/events");
    };

    const handleOpenStatistics = (participant, test) => {
        setSelectedStatistic({
            participant,
            test,
        });
    };

    const handleCloseStatistics = () => {
        setSelectedStatistic(null);
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
                        <button
                            className="stat-back-btn2"
                            onClick={handleBack}
                        >
                            <BackIcon />
                        </button>

                        <h1>Статистика мероприятия</h1>
                    </div>

                    <div className="tests-line"></div>

                    <div className="stat-attempts-table">
                        <table>
                            <thead>
                            <tr>
                                <th>Участник</th>

                                {testHeaders.map((test) => (
                                    <th key={test}>{test}</th>
                                ))}
                            </tr>
                            </thead>

                            <tbody>
                            {participants.map((participant) => (
                                <tr key={participant.id}>
                                    <td className="stat-cell-name">
                                        {participant.userName}
                                    </td>

                                    {participant.tests.map((test) => (
                                        <td
                                            key={test.id}
                                            className="event-test-cell"
                                        >
                                            <div className="event-test-result">
                                                <span>{test.score}</span>

                                                <button
                                                    className="event-stat-btn"
                                                    onClick={() =>
                                                        handleOpenStatistics(
                                                            participant,
                                                            test
                                                        )
                                                    }
                                                >
                                                    ▼
                                                </button>
                                            </div>
                                        </td>
                                    ))}
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>

                    {selectedStatistic && (
                        <div className="stat-modal-overlay">
                            <div className="stat-modal">
                                <h3>Подробная статистика</h3>

                                <div className="stat-details-user">
                                    <p>
                                        <strong>Участник:</strong>{" "}
                                        {
                                            selectedStatistic.participant
                                                .userName
                                        }
                                    </p>

                                    <p>
                                        <strong>Почта:</strong>{" "}
                                        {
                                            selectedStatistic.participant.email
                                        }
                                    </p>

                                    <p>
                                        <strong>Тест:</strong>{" "}
                                        {
                                            selectedStatistic.test.testName
                                        }
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
                                        {selectedStatistic.test.questions.map(
                                            (question) => (
                                                <tr
                                                    key={
                                                        question.questionIndex
                                                    }
                                                >
                                                    <td>
                                                        {
                                                            question.questionText
                                                        }
                                                    </td>

                                                    <td>
                                                        {question.score}/
                                                        {
                                                            question.maxScore
                                                        }
                                                    </td>
                                                </tr>
                                            )
                                        )}
                                        </tbody>
                                    </table>
                                </div>

                                <button
                                    className="stat-hide-btn"
                                    onClick={handleCloseStatistics}
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