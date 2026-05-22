import "../styles/MyTestStudent.css";
import LogoutButton from "../components/LogoutButton.jsx";
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { testsAPI } from "../services/api.js";

export default function MyTestStudent() {
    const navigate = useNavigate();
    const [tests, setTests] = useState([]);
    const [openMenuId, setOpenMenuId] = useState(null);
    const menuRefs = useRef({});

    useEffect(() => {
        const fetchAttempts = async () => {
            try {
                const token = localStorage.getItem("token");
                if (!token) {
                    navigate("/login");
                    return;
                }

                const response = await testsAPI.getAttempts();
                const data = response.data;
                console.log("Полученные попытки тестов:", data);

                let testsArray = [];
                if (Array.isArray(data)) {
                    testsArray = data;
                } else if (data.tests && Array.isArray(data.tests)) {
                    testsArray = data.tests;
                } else if (data.data && Array.isArray(data.data)) {
                    testsArray = data.data;
                }

                setTests(testsArray);
            } catch (error) {
                console.error("Ошибка при загрузке попыток:", error);
                setTests([]);
            }
        };

        fetchAttempts();
    }, [navigate]);


    const toggleMenu = (id, e) => {
        if (e) e.stopPropagation();
        setOpenMenuId(openMenuId === id ? null : id);
    };

    useEffect(() => {
        const handleClickOutside = (e) => {
            let clickedInsideMenu = false;
            Object.values(menuRefs.current).forEach((ref) => {
                if (ref && ref.contains(e.target)) {
                    clickedInsideMenu = true;
                }
            });
            if (!clickedInsideMenu) {
                setOpenMenuId(null);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () =>
            document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className="tests-page">
            <div
                className="test-page"
                style={{ position: "absolute", left: "1430px", top: "0px" }}
            >
                <LogoutButton />
            </div>
            <div className="create-wrapper2">
                <div className="test">
                    <h2>Мои тесты</h2>
                    <div className="tests-line"></div>

                    {tests.length === 0 ? (
                        <p className="mytests-empty">
                            Вы ещё не проходили ни одного теста.
                        </p>
                    ) : (
                        <div className="mytests-list">
                            {tests.map((t, index) => (
                                <div
                                    key={`${t.id}-${index}`}
                                    className="mytests-card"
                                >
                                    <h3 className="mytests-card-title">
                                        {t.title}
                                    </h3>

                                    <p className="mytests-card-message">
                                        {t.message}
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );

}