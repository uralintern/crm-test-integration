import { useEffect, useRef, useState } from "react";
import LogoutButton from "../components/LogoutButton.jsx";
import "../styles/PassingTestStudent.css";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { testsAPI } from "../services/api.js";

import { DndContext, closestCenter } from "@dnd-kit/core";
import {
    SortableContext,
    arrayMove,
    useSortable,
    verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";


function SortableMatchAnswer({ id, text }) {
    const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
    const style = { transform: CSS.Transform.toString(transform), transition };

    return (
        <div ref={setNodeRef} style={style} className="match-answer-inner">
            <div className="match-input">{text}</div>
            <button className="match-answer-handle" type="button" {...attributes} {...listeners}>
                · ·<br />· ·<br />· ·
            </button>
        </div>
    );
}

function SortableOrderingItem({ id, text }) {
    const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
    const style = { transform: CSS.Transform.toString(transform), transition };

    return (
        <div ref={setNodeRef} style={style} className="ordering-inner">
            <button className="match-answer-handle ordering-handle-right" type="button" {...attributes} {...listeners}>
                · ·<br />· ·<br />· ·
            </button>
            <div className="match-input">{text}</div>
        </div>
    );
}

const apiTypeToUiType = {
    text_input: "shortText",
    single_choice: "singleChoice",
    multiple_choice: "multipleChoice",
    matching: "matching",
    correct_order: "ordering",
};

function normalizeApiTest(payload) {
    return {
        apiMode: true,
        id: payload.test_id,
        configId: payload.config_id,
        applicationId: payload.application_id,
        title: payload.title,
        description: payload.description,
        completetime: payload.time_limit,
        threshold: payload.threshold,
        questions: (payload.questions || []).map((q, idx) => {
            const type = apiTypeToUiType[q.type] || "shortText";
            const options = q.options || {};
            const base = {
                id: q.question_id,
                order: q.order_number || idx + 1,
                type,
                text: q.text,
                maxScore: q.points,
                points: q.points,
                caseSensitive: options.case_sensitive || false,
            };

            if (type === "singleChoice" || type === "multipleChoice") {
                return {
                    ...base,
                    options: (options.choice || []).map((choice, visualIndex) => ({
                        text: choice.text,
                        originalIndex: typeof choice.index === "number" ? choice.index : visualIndex,
                    })),
                };
            }

            if (type === "matching") {
                const matching = options.matching || {};
                const left = matching.left || [];
                const right = matching.right || [];
                return {
                    ...base,
                    rows: left.map((item, index) => ({ option: item, answer: right[index] || "" })),
                };
            }

            if (type === "ordering") {
                return {
                    ...base,
                    items: (options.sequence || []).map((item) => ({ text: item })),
                };
            }

            return base;
        }),
    };
}

function buildInitialAnswers(test) {
    const initial = {};
    (test.questions || []).forEach((q, idx) => {
        const qId = q.id ?? idx;
        if (q.type === "matching") {
            initial[qId] = (q.rows || []).map((_, i) => `a-${i}`);
        }
        if (q.type === "ordering") {
            initial[qId] = (q.items || []).map((_, i) => `i-${i}`);
        }
    });
    return initial;
}

export default function PassingTestStudent() {
    const { test_link } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const startedRef = useRef(false);
    const submittingRef = useRef(false);
    const handleSubmitRef = useRef(null);

    const [test, setTest] = useState(null);
    const [answers, setAnswers] = useState({});
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState("");
    const [startTime, setStartTime] = useState(null);
    const [timeLeft, setTimeLeft] = useState(null);

    useEffect(() => {
        if (startedRef.current) return;
        startedRef.current = true;
        const start = async () => {
            try {
                const token = localStorage.getItem("token");
                if (!token) {
                    setErrorMessage("Требуется авторизация для прохождения теста.");
                    return;
                }

                const applicationId = Number(searchParams.get("application_id") || 0) || undefined;
                const response = await testsAPI.startAttempt(test_link, applicationId);
                const apiTest = normalizeApiTest(response.data);

                setAnswers(buildInitialAnswers(apiTest));
                setTest(apiTest);
                setStartTime(Date.now());
                if (typeof apiTest.completetime === "number" && apiTest.completetime > 0) {
                    setTimeLeft(apiTest.completetime);
                }
            } catch (error) {
                console.error("Failed to start test", error);
                const detail = error?.response?.data || "Не удалось загрузить тест.";
                setErrorMessage(typeof detail === "string" ? detail : "Не удалось загрузить тест.");
            } finally {
                setLoading(false);
            }
        };

        start();
    }, [searchParams, test_link]);

    useEffect(() => {
        if (timeLeft == null) return;
        if (timeLeft <= 0) {
            handleSubmitRef.current?.();
            return;
        }

        const id = setInterval(() => {
            setTimeLeft((prev) => (prev != null ? prev - 1 : prev));
        }, 1000);

        return () => clearInterval(id);
    }, [timeLeft]);

    const formatTime = (sec) => {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    };

    const handleAnswerChange = (questionId, value) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    const handleOptionToggle = (questionId, optionIndex) => {
        setAnswers((prev) => {
            const current = prev[questionId] || [];
            if (current.includes(optionIndex)) {
                return { ...prev, [questionId]: current.filter((i) => i !== optionIndex) };
            }
            return { ...prev, [questionId]: [...current, optionIndex] };
        });
    };

    const handleMatchingDragEnd = (qId, event) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        setAnswers((prev) => {
            const rows = test.questions.find((q) => q.id === qId)?.rows || [];
            const current = prev[qId] || rows.map((_, idx) => `a-${idx}`);
            return {
                ...prev,
                [qId]: arrayMove(current, current.indexOf(active.id), current.indexOf(over.id)),
            };
        });
    };

    const handleOrderingDragEnd = (qId, event) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        setAnswers((prev) => {
            const items = test.questions.find((q) => q.id === qId)?.items || [];
            const current = prev[qId] || items.map((_, idx) => `i-${idx}`);
            return {
                ...prev,
                [qId]: arrayMove(current, current.indexOf(active.id), current.indexOf(over.id)),
            };
        });
    };

    const calculateScoreWithDetails = () => {
        if (!test || !Array.isArray(test.questions)) {
            return { totalScore: 0, totalMax: 0, perQuestion: [] };
        }

        let totalScore = 0;
        let totalMax = 0;
        const perQuestion = [];

        test.questions.forEach((q, index) => {
            const qId = q.id || index;
            const userAnswer = answers[qId];
            const max = q.maxScore || q.points || 0;
            let score = 0;

            switch (q.type) {
                case "shortText": {
                    const correct = (q.correctAnswers || q.correct_input || []).map((s) =>
                        q.caseSensitive || q.case_sensitive ? s : s.toLowerCase().trim()
                    );
                    if (userAnswer) {
                        const normUser = q.caseSensitive || q.case_sensitive ? userAnswer : userAnswer.toLowerCase().trim();
                        if (correct.includes(normUser)) score = max;
                    }
                    break;
                }
                case "singleChoice": {
                    const options = q.options || q.choice || [];
                    const correctIndex = options.findIndex((o) => o.isCorrect || o.is_true);
                    if (correctIndex !== -1 && userAnswer === correctIndex) score = max;
                    break;
                }
                case "multipleChoice": {
                    const options = q.options || q.choice || [];
                    const correctIndexes = options.map((o, i) => (o.isCorrect || o.is_true ? i : -1)).filter((i) => i !== -1);
                    const user = Array.isArray(userAnswer) ? userAnswer.slice().sort() : [];
                    const correctSorted = correctIndexes.slice().sort();
                    const equal = user.length === correctSorted.length && user.every((val, idx) => val === correctSorted[idx]);
                    if (equal) score = max;
                    break;
                }
                case "matching": {
                    const rows = q.rows || [];
                    const userOrder = userAnswer || [];
                    const correctOrder = rows.map((_, idx) => `a-${idx}`);
                    const equal = Array.isArray(userOrder) && userOrder.length === correctOrder.length && userOrder.every((v, i) => v === correctOrder[i]);
                    if (equal && rows.length > 0) score = max;
                    break;
                }
                case "ordering": {
                    const items = q.items || [];
                    const userOrder = userAnswer || [];
                    const correctOrder = items.map((_, idx) => `i-${idx}`);
                    const equal = Array.isArray(userOrder) && userOrder.length === correctOrder.length && userOrder.every((v, i) => v === correctOrder[i]);
                    if (equal && items.length > 0) score = max;
                    break;
                }
            }

            totalScore += score;
            totalMax += max;
            perQuestion.push({ questionIndex: index + 1, questionText: q.text || "", score, maxScore: max });
        });

        return { totalScore, totalMax, perQuestion };
    };

    const buildApiAnswers = () => {
        return (test.questions || []).map((q) => {
            const qId = q.id;
            const userAnswer = answers[qId];
            const answer = {};

            if (q.type === "singleChoice" || q.type === "multipleChoice") {
                const maxOriginalIndex = Math.max(...(q.options || []).map((opt) => opt.originalIndex ?? 0), 0);
                const choices = Array(maxOriginalIndex + 1).fill(false);
                const selected = q.type === "singleChoice" ? [userAnswer] : Array.isArray(userAnswer) ? userAnswer : [];
                selected.forEach((visualIndex) => {
                    const originalIndex = q.options?.[visualIndex]?.originalIndex;
                    if (typeof originalIndex === "number") choices[originalIndex] = true;
                });
                answer.choices = choices;
            }

            if (q.type === "shortText") {
                answer.user_input = userAnswer || "";
            }

            if (q.type === "matching") {
                const order = userAnswer || (q.rows || []).map((_, idx) => `a-${idx}`);
                answer.matching = (q.rows || []).map((row, leftIndex) => {
                    const answerIndex = Number(String(order[leftIndex] || "a-0").split("-")[1]);
                    return {
                        left: row.option,
                        right: q.rows?.[answerIndex]?.answer || "",
                    };
                });
            }

            if (q.type === "ordering") {
                const order = userAnswer || (q.items || []).map((_, idx) => `i-${idx}`);
                answer.sequence = order.map((itemId, idx) => {
                    const itemIndex = Number(String(itemId).split("-")[1]);
                    return {
                        text: q.items?.[itemIndex]?.text || "",
                        order: idx + 1,
                    };
                });
            }

            return { question_id: qId, answer };
        });
    };

    const saveLocalAttempt = (passed, message, totalScore, totalMax, perQuestion) => {
        const userRaw = localStorage.getItem("user");
        let userEmail = null;
        let userName = null;
        try {
            if (userRaw) {
                const user = JSON.parse(userRaw);
                userEmail = user.email || user.username || user.login || null;
                userName = `${user.surname || ""} ${user.name || ""}`.trim() || "Участник";
            }
        } catch (e) {
            console.error("Failed to parse user", e);
        }

        const testId = test.id || test.test_id || test_link;
        const durationMs = startTime ? Date.now() - startTime : 0;
        const durationMinutes = Math.round(durationMs / 60000);
        const attempt = {
            id: Date.now(),
            testId,
            userEmail: userEmail || "unknown",
            userName,
            finishedAt: new Date().toISOString(),
            passed,
            message,
            score: totalScore,
            totalMax,
            perQuestion,
            durationMinutes,
        };

        const keyAttempts = `attempts_${testId}`;
        const rawAttempts = localStorage.getItem(keyAttempts);
        const attemptsList = rawAttempts ? JSON.parse(rawAttempts) : [];
        localStorage.setItem(keyAttempts, JSON.stringify(Array.isArray(attemptsList) ? [...attemptsList, attempt] : [attempt]));
    };

    const getReturnPath = () => {
        const params = new URLSearchParams();
        for (const key of ["event_id", "specialization_id", "application_id"]) {
            const value = searchParams.get(key);
            if (value) params.set(key, value);
        }
        return `/myTestStudent${params.toString() ? `?${params.toString()}` : ""}`;
    };

    const handleSubmit = async () => {
        if (!test || submittingRef.current) return;
        submittingRef.current = true;

        try {
            if (test.apiMode) {
                const response = await testsAPI.finishAttempt({ userAnswers: buildApiAnswers() });
                const result = response.data;
                alert(result.result || (result.passed ? "Тест пройден." : "Тест не пройден."));
                navigate(getReturnPath());
                return;
            }

            const { totalScore, totalMax, perQuestion } = calculateScoreWithDetails();
            const threshold = test.threshold || 0;
            const passed = test.is_percentage ? (totalMax > 0 ? (totalScore / totalMax) * 100 : 0) >= threshold : totalScore >= threshold;
            const message = passed ? test.success_text || "Тест успешно пройден." : test.fail_text || "Тест не пройден.";
            saveLocalAttempt(passed, message, totalScore, totalMax, perQuestion);
            alert(message);
            navigate(getReturnPath());
        } catch (error) {
            console.error("Failed to finish test", error);
            alert("Не удалось завершить тест. Попробуйте ещё раз.");
            submittingRef.current = false;
        }
    };

    handleSubmitRef.current = handleSubmit;

    if (loading) return <div>Загрузка...</div>;
    if (!test) return <div>{errorMessage || "Тест не найден или ссылка недействительна."}</div>;

    const questions = test.questions || [];

    return (
        <div className="tests-page">
            <div className="test-page" style={{ position: "absolute", left: "1430px", top: "0px" }}>
                <LogoutButton />
            </div>

            <div className="create-wrapper">
                <div className="test">
                    <header className="passing-test-header">
                        <h1 className="passing-title">{test.title || "Без названия"}</h1>
                        {test.description && <p className="passing-description">{test.description}</p>}
                        {timeLeft != null && <div className="passing-timer">Осталось времени: {formatTime(timeLeft)}</div>}
                    </header>
                    <div className="tests-line"></div>
                    <div className="passing-questions">
                        {questions.map((q, index) => {
                            const qId = q.id || index;
                            const qType = q.type;

                            return (
                                <div key={qId} className="passing-question-block">
                                    <div className="passing-question-header">
                                        <span className="passing-question-number">{index + 1}.</span>
                                        <span className="passing-question-text">{q.text || "Без текста"}</span>
                                    </div>

                                    {qType === "shortText" && (
                                        <div className="options-row12">
                                            <input
                                                type="text"
                                                className="answer-input"
                                                placeholder="Введите ответ..."
                                                value={answers[qId] || ""}
                                                onChange={(e) => handleAnswerChange(qId, e.target.value)}
                                            />
                                        </div>
                                    )}

                                    {qType === "singleChoice" && (
                                        <div className="passing-question-body passing-options-single">
                                            {(q.options || []).map((opt, idx) => (
                                                <label key={idx} className="passing-option-row">
                                                    <input
                                                        type="radio"
                                                        className="options-row1"
                                                        name={`q-${qId}`}
                                                        checked={answers[qId] === idx}
                                                        onChange={() => handleAnswerChange(qId, idx)}
                                                    />
                                                    <span className="answer-input">{opt.text || ""}</span>
                                                </label>
                                            ))}
                                        </div>
                                    )}

                                    {qType === "multipleChoice" && (
                                        <div className="passing-question-body passing-options-multiple">
                                            {(q.options || []).map((opt, idx) => (
                                                <label key={idx} className="options-row">
                                                    <input
                                                        type="checkbox"
                                                        checked={(answers[qId] || []).includes(idx)}
                                                        onChange={() => handleOptionToggle(qId, idx)}
                                                    />
                                                    <span className="answer-input">{opt.text || ""}</span>
                                                </label>
                                            ))}
                                        </div>
                                    )}

                                    {qType === "matching" && (
                                        <div className="passing-question-body passing-matching">
                                            <div className="match-panel">
                                                <div className="match-rows">
                                                    <div className="match-column match-column-left">
                                                        {(q.rows || []).map((row, idx) => (
                                                            <div key={idx} className="match-row-outer">
                                                                <div className="match-row-inner">{row.option || ""}</div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                    <div className="match-column match-column-right">
                                                        <DndContext collisionDetection={closestCenter} onDragEnd={(event) => handleMatchingDragEnd(qId, event)}>
                                                            <SortableContext items={answers[qId] || (q.rows || []).map((_, idx) => `a-${idx}`)} strategy={verticalListSortingStrategy}>
                                                                {(answers[qId] || (q.rows || []).map((_, idx) => `a-${idx}`)).map((answerId) => {
                                                                    const idx = Number(answerId.split("-")[1]);
                                                                    const row = (q.rows || [])[idx] || {};
                                                                    return (
                                                                        <div key={answerId} className="match-row-outer">
                                                                            <SortableMatchAnswer id={answerId} text={row.answer || ""} />
                                                                        </div>
                                                                    );
                                                                })}
                                                            </SortableContext>
                                                        </DndContext>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {qType === "ordering" && (
                                        <div className="block-questions12">
                                            <div className="block-questions-container1">
                                                <div className="section-title12">№</div>
                                                <div className="section-title24">Ответ</div>
                                            </div>
                                            <DndContext collisionDetection={closestCenter} onDragEnd={(event) => handleOrderingDragEnd(qId, event)}>
                                                <SortableContext items={answers[qId] || (q.items || []).map((_, idx) => `i-${idx}`)} strategy={verticalListSortingStrategy}>
                                                    {(answers[qId] || (q.items || []).map((_, idx) => `i-${idx}`)).map((itemId, visualIndex) => {
                                                        const idx = Number(itemId.split("-")[1]);
                                                        const item = (q.items || [])[idx] || {};
                                                        return (
                                                            <div key={itemId} className="passing-ordering-row">
                                                                <span className="passing-ordering-index">{visualIndex + 1}</span>
                                                                <div className="ordering-row-outer">
                                                                    <SortableOrderingItem id={itemId} text={item.text || ""} />
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </SortableContext>
                                            </DndContext>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    <div className="passing-footer">
                        <button className="passing-submit-btn" onClick={handleSubmit}>
                            Завершить тестирование
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
