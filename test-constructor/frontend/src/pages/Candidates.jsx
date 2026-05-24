import "../styles/tests.css";
import "../styles/candidates.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { candidatesAPI } from "../services/api.js";

import TaskIcon from "../assets/task.svg?react";
import EventIcon from "../assets/event.svg?react";
import CandidatesIcon from "../assets/Candidates.svg?react";

function normalizeCandidates(data) {
    const items = Array.isArray(data) ? data : data?.users || data?.data || [];
    return (Array.isArray(items) ? items : [])
        .map((candidate) => ({
            id: candidate.id ?? candidate.user_id,
            name: candidate.name ?? candidate.first_name ?? "",
            surname: candidate.surname ?? candidate.last_name ?? "",
            email: candidate.email ?? "",
        }))
        .filter((candidate) => candidate.id != null);
}

export default function Candidates() {
    const navigate = useNavigate();
    const [candidates, setCandidates] = useState([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState("");

    useEffect(() => {
        const fetchCandidates = async () => {
            try {
                const response = await candidatesAPI.getCandidates();
                setCandidates(normalizeCandidates(response.data));
                setErrorMessage("");
            } catch (error) {
                console.error("Ошибка при загрузке кандидатов:", error);
                setCandidates([]);
                setErrorMessage("Не удалось загрузить список кандидатов.");
            } finally {
                setLoading(false);
            }
        };

        fetchCandidates();
    }, []);

    const filteredCandidates = useMemo(() => {
        const query = searchQuery.trim().toLowerCase();
        if (!query) return candidates;
        return candidates.filter((candidate) => {
            const fullText = `${candidate.name} ${candidate.surname} ${candidate.email}`.toLowerCase();
            return fullText.includes(query);
        });
    }, [candidates, searchQuery]);

    return (
        <div className="tests-page">
            <LogoutButton />
            <div className="tests-wrapper">
                <div className="tests">
                    <div className="tests-tabs">
                        <button className="tab-btn" onClick={() => navigate("/tests")}>
                            <TaskIcon />
                            Тестовые задания
                        </button>
                        <button className="tab-btn" onClick={() => navigate("/events")}>
                            <EventIcon />
                            Мероприятия
                        </button>
                        <button className="tab-btn tab-btn-active" onClick={() => navigate("/candidates")}>
                            <CandidatesIcon />
                            Кандидаты
                        </button>
                    </div>

                    <div className="candidates-search-box">
                        <input
                            type="text"
                            placeholder="Поиск по кандидату..."
                            value={searchQuery}
                            onChange={(event) => setSearchQuery(event.target.value)}
                            className="candidates-search-input"
                        />
                    </div>

                    <div className="candidates-list">
                        {loading ? (
                            <p className="candidates-loading">Загрузка...</p>
                        ) : errorMessage ? (
                            <p className="candidates-empty">{errorMessage}</p>
                        ) : filteredCandidates.length === 0 ? (
                            <p className="candidates-empty">Кандидаты не найдены</p>
                        ) : (
                            filteredCandidates.map((candidate) => (
                                <button
                                    key={candidate.id}
                                    type="button"
                                    className="candidate-card"
                                    onClick={() => navigate(`/candidates/${candidate.id}`)}
                                >
                                    <div className="candidate-avatar">
                                        {(candidate.name || "?").charAt(0)}
                                        {(candidate.surname || "").charAt(0)}
                                    </div>
                                    <div className="candidate-info">
                                        <p className="candidate-name">
                                            {candidate.name} {candidate.surname}
                                        </p>
                                        {candidate.email && <p className="candidate-email-list">{candidate.email}</p>}
                                    </div>
                                    <div className="candidate-arrow">›</div>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
