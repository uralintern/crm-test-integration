import { useState, useEffect } from "react";
import "../styles/tests.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useNavigate } from "react-router-dom";

import TaskIcon from "../assets/task.svg?react";
import EventIcon from "../assets/event.svg?react";
import CandidatesIcon from "../assets/Candidates.svg?react";
import SettingsIcon from "../assets/settings.svg?react";
import StatisticsIcon from "../assets/statistics2.svg?react";
import { eventsAPI } from "../services/api";

export default function Events() {
    const navigate = useNavigate();
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const emptyEvents = [
        { id: 1, name: "Мои мероприятие 1", start_date: "2000-01-01", end_date: "2050-01-01" },
        { id: 2, name: "Мои мероприятие 2", start_date: "2000-01-01", end_date: "2050-01-01" },
        { id: 3, name: "Мои мероприятие 3", start_date: "2000-01-01", end_date: "2050-01-01" },
        { id: 4, name: "Мои мероприятие 4", start_date: "2000-01-01", end_date: "2050-01-01" },
        { id: 5, name: "Мои мероприятие 5", start_date: "2000-01-01", end_date: "2050-01-01" },
    ];

    useEffect(() => {
        const fetchEvents = async () => {
            try {
                setLoading(true);
                const response = await eventsAPI.getEvents();
                setEvents(response.data || []);
            } catch (err) {
                console.error("Ошибка загрузки мероприятий:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchEvents();
    }, []);

    const formatDate = (dateString) => {
        if (!dateString) return "";
        const date = new Date(dateString);
        return date.toLocaleDateString("ru-RU");
    };

    return (
        <div className="tests-page">
            <>
                <LogoutButton />
            </>
            <div className="tests-wrapper">
                <div className="tests">
                    {/* Навигационные вкладки */}
                    <div className="tests-tabs">
                        <button
                            className="tab-btn"
                            onClick={() => navigate("/tests")}
                        >
                            <TaskIcon />
                            Тестовые задания
                        </button>
                        <button
                            className="tab-btn tab-btn-active"
                            onClick={() => navigate("/events")}
                        >
                            <EventIcon />
                            Мероприятия
                        </button>
                        <button
                            className="tab-btn"
                            onClick={() => navigate("/candidates")}
                        >
                            <CandidatesIcon />
                            Кандидаты
                        </button>
                    </div>

                    {/* Список мероприятий */}
                    <div className="events-container">
                        {!loading && (events.length > 0 ? events : emptyEvents).map((event) => (
                            <div key={event.id} className="event-card">
                                <div className="event-info">
                                    <h3 className="event-title">{event.name}</h3>
                                    <div className="event-dates">
                                        <span>Начало: {formatDate(event.start_date)}</span>
                                        <span className="event-separator">|</span>
                                        <span>Конец: {formatDate(event.end_date)}</span>
                                    </div>
                                </div>
                                <div className="event-actions">
                                    <button
                                        className="event-btn settings-btn"
                                        title="Настройка"
                                        onClick={() => navigate(`/event-config?eventId=${event.id}`)}
                                    >
                                        <SettingsIcon />
                                    </button>


                                    <button
                                        className="event-btn statistics-btn"
                                        title="Статистика"
                                        onClick={() => navigate(`/event-statistics/${event.id}`)}
                                    >
                                        <StatisticsIcon />
                                    </button>
                                </div>
                            </div>
                        ))}

                    </div>
                </div>
            </div>
        </div>
    );
}
