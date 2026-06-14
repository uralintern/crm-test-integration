import "../styles/tests.css";
import "../styles/confirm-modal.css";
import "../styles/tests-share-modal.css";

import LogoutButton from "../components/LogoutButton.jsx";
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import EditIcon from "../assets/edit.svg?react";
import ShareIcon from "../assets/share.svg?react";
import StatisticsIcon from "../assets/statistics.svg?react";
import CloseIcon from "../assets/close.svg?react";
import DeleteIcon from "../assets/delete.svg?react";
import CopyIcon from "../assets/copy_sub.svg?react";
import { testsAPI } from "../services/api.js";
import BackIcon from "../assets/back.svg?react";
import TaskIcon from "../assets/task.svg?react";
import EventIcon from "../assets/event.svg?react";
import CandidatesIcon from "../assets/Candidates.svg?react";
export default function Tests() {
    const [statsTest, setStatsTest] = useState(null);
    const navigate = useNavigate();


    const [tests, setTests] = useState([]);
    const [openMenuId, setOpenMenuId] = useState(null);
    const menuRefs = useRef({});
    const [shareModalOpen, setShareModalOpen] = useState(false);
    const [shareLink, setShareLink] = useState("");
    const [confirmModalOpen, setConfirmModalOpen] = useState(false);
    const [testToDelete, setTestToDelete] = useState(null);

    useEffect(() => {
        const fetchTests = async () => {
            try {
                const token = localStorage.getItem("token");
                if (!token) {
                    navigate("/login");
                    return;
                }

                const response = await testsAPI.getTests();
                const data = response.data;
                console.log("Полученные тесты:", data);

                let testsArray = [];
                if (Array.isArray(data)) {
                    testsArray = data;
                } else if (data.tests && Array.isArray(data.tests)) {
                    testsArray = data.tests;
                } else if (data.data && Array.isArray(data.data)) {
                    testsArray = data.data;
                } else {
                    console.error("Неизвестная структура ответа:", data);
                }

                const normalizedTests = testsArray.map(test => ({
                    ...test,
                    id: test.test_id || test.id,
                }));

                setTests(normalizedTests);
                console.log('ids:', normalizedTests.map(t => t.id));

            } catch (error) {
                console.error("Ошибка:", error);
                alert("Не удалось загрузить тесты");
            }
        };

        fetchTests();
    }, [navigate]);

    const toggleMenu = (id, e) => {
        if (e) e.stopPropagation();
        setOpenMenuId(openMenuId === id ? null : id);
    };

    useEffect(() => {
        const handleClickOutside = (e) => {
            let clickedInsideMenu = false;

            Object.values(menuRefs.current).forEach(ref => {
                if (ref && ref.contains(e.target)) {
                    clickedInsideMenu = true;
                }
            });

            if (!clickedInsideMenu) {
                setOpenMenuId(null);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const editTest = async (test) => {
        console.log("Тест для редактирования:", test);

        try {
            const testId = test.test_id || test.id;
            const response = await testsAPI.getTest(testId);
            const fullTest = response.data?.test || response.data;

            localStorage.setItem("editingTest", JSON.stringify(fullTest));

            navigate("/create", {
                state: { editing: true, test: fullTest, deleteOnSave: false },
            });
            setOpenMenuId(null);
        } catch (error) {
            console.error("Ошибка при редактировании теста:", error);
            alert("Ошибка при загрузке теста для редактирования");
        }
    };


    const deleteTest = async (id) => {
        try {
            const token = localStorage.getItem("token");
            if (!token) {
                alert("Требуется авторизация");
                navigate("/login");
                return;
            }

            console.log("Удаление теста с ID:", id);
            await testsAPI.deleteTest(id);

            const updatedTests = tests.filter(test => {
                const testId = test.id;
                return testId !== id;
            });

            setTests(updatedTests);
            setOpenMenuId(null);
            setConfirmModalOpen(false);

        } catch (error) {
            console.error("Ошибка при удалении теста:", error);
            alert("Не удалось удалить тест на сервере. Проверьте консоль для деталей.");
        }
    };


    const openDeleteConfirm = (test) => {
        setTestToDelete(test);
        setConfirmModalOpen(true);
        setOpenMenuId(null);
    };


    const closeDeleteConfirm = () => {
        setConfirmModalOpen(false);
        setTestToDelete(null);
    };;

    const shareTest = async (test) => {
        try {
            const testLink = test.test_link;
            const link = `${window.location.origin}/test/${testLink}`;
            setShareLink(link);
            setShareModalOpen(true);
        } catch (error) {
            console.error("Ошибка при подготовке ссылки:", error);
            alert("Не удалось подготовить ссылку");
        }
        setOpenMenuId(null);
    };

    const viewStatistics = (test) => {
        navigate(`/statistics/${test.id}`);
        setOpenMenuId(null);
    };



    return (
        <div className="tests-page">
            <>
                <LogoutButton />
            </>
            <div className="tests-wrapper">
                <div className="tests-left">
                    {/* Навигационные вкладки */}
                    <div className="tests-tabs">
                        <button
                            className="tab-btn tab-btn-active"
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
                            className="tab-btn"
                            onClick={() => navigate("/candidates")}
                        >
                            <CandidatesIcon />
                            Кандидаты
                        </button>
                    </div>
                    {/* <div className="tests-line"></div> */}


                    {tests.length === 0 ? (
                        <div className="no-tests">
                            Пока нет тестов. Создайте первый тест →
                        </div>
                    ) : (
                        <div className="tests-grid">
                            {tests.map((test) => {

                                const testId = test.id;
                                const testTitle = test.Title || test.title;
                                const isActive = test.IsActive !== false;

                                return (
                                    <div key={testId} className="test-card"
                                         style={{
                                             zIndex: openMenuId === testId ? 100 : 1,
                                             opacity: isActive ? 1 : 0.6
                                         }}
                                    >
                                        <div
                                            className="test-menu-container"
                                            ref={el => menuRefs.current[testId] = el}
                                        >
                                            <button
                                                className="dots-btn"
                                                onClick={(e) => toggleMenu(testId, e)}
                                            >
                                                ⋮
                                            </button>

                                            {openMenuId === testId && (
                                                <div className="dropdown-menu">
                                                    <button className="menu-item" onClick={() => editTest(test)}>
                                                        <EditIcon className="menu-icon" />
                                                        <span>Редактировать</span>
                                                    </button>
                                                                                                        <button className="menu-item share" onClick={() => shareTest(test)}>
                                                        <ShareIcon className="menu-icon" />
                                                        <span>Поделиться</span>
                                                    </button>
                                                    <button className="menu-item" onClick={() => viewStatistics(test)}>
                                                        <StatisticsIcon className="menu-icon" />
                                                        <span>Статистика</span>
                                                    </button>


                                                    <button className="menu-item" onClick={() => openDeleteConfirm(test)}>
                                                        <DeleteIcon className="menu-icon" />
                                                        <span>Удалить тест</span>
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                        <span className="test-titles">
                                            {testTitle && testTitle.length > 15
                                                ? `${testTitle.substring(0, 15)}...`
                                                : testTitle || "Без названия"
                                            }
                                        </span>
                                        {!isActive && (
                                            <div className="test-status">ЗАКРЫТ</div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                <div className="tests-right">
                    <button className="create-test-btn" onClick={() => navigate("/create")}>
                        Создать тест
                    </button>
                </div>
            </div>
            {shareModalOpen && (
                <div className="share-modal-overlay" onClick={() => setShareModalOpen(false)}>
                    <div
                        className="share-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 className="share-modal-title">Поделиться ссылкой</h3>

                        <div className="share-modal-body">
                            <input
                                type="text"
                                className="share-modal-input"
                                value={shareLink}
                                readOnly
                            />
                            <button
                                className="share-modal-copy-btn"
                                onClick={async () => {
                                    try {
                                        await navigator.clipboard.writeText(shareLink);
                                    } catch (e) {
                                        console.error("Ошибка копирования:", e);
                                        alert("Не удалось скопировать ссылку");
                                    }
                                }}
                            >
                                <CopyIcon className="share-modal-copy-icon" />
                            </button>

                        </div>
                    </div>
                </div>
            )}
            {confirmModalOpen && testToDelete && (
                <div className="confirm-modal-overlay" onClick={closeDeleteConfirm}>
                    <div
                        className="confirm-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 className="confirm-modal-title">Удалить тест</h3>
                        <p className="confirm-modal-message">
                            Вы уверены, что хотите удалить тест
                            <strong> "{testToDelete.Title || testToDelete.title || "Без названия"}"</strong>?
                            <br />
                        </p>
                        <div className="confirm-modal-buttons">
                            <button
                                className="confirm-modal-btn confirm-modal-btn-cancel"
                                onClick={closeDeleteConfirm}
                            >
                                Отмена
                            </button>
                            <button
                                className="confirm-modal-btn confirm-modal-btn-delete"
                                onClick={() => deleteTest(testToDelete.id)}
                            >
                                Удалить
                            </button>
                        </div>
                    </div>
                </div>
            )}
            {statsTest && (
                <StatisticsTest
                    testId={statsTest.id}
                    onClose={() => setStatsTest(null)}
                />
            )}

        </div>
    );
}