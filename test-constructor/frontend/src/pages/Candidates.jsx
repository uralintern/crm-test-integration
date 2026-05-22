import "../styles/tests.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useNavigate } from "react-router-dom";

import TaskIcon from "../assets/task.svg?react";
import EventIcon from "../assets/event.svg?react";
import CandidatesIcon from "../assets/Candidates.svg?react";
export default function Candidates() {
    const navigate = useNavigate();

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
                            className="tab-btn"
                            onClick={() => navigate("/events")}
                        >
                            <EventIcon />
                            Мероприятия
                        </button>
                        <button
                            className="tab-btn tab-btn-active"
                            onClick={() => navigate("/candidates")}
                        >
                            <CandidatesIcon />
                            Кандидаты
                        </button>
                    </div>
                    {/* <div className="tests-line"></div> */}

                </div>
            </div>
        </div>
    );
}
