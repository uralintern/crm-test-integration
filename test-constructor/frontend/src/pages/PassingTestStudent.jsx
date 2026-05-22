import { useEffect, useState } from "react";
import LogoutButton from "../components/LogoutButton.jsx";
import "../styles/PassingTestStudent.css";
import { useParams, useNavigate } from "react-router-dom";

import {
    DndContext,
    closestCenter,
} from "@dnd-kit/core";
import {
    SortableContext,
    verticalListSortingStrategy,
    arrayMove,
    useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";


function shuffleArray(array) {
    const arr = array.slice();
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
}


function SortableMatchAnswer({ id, text }) {
    const { attributes, listeners, setNodeRef, transform, transition } =
        useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="match-answer-inner"
        >
            <div className="match-input">
                {text}
            </div>

            <button
                className="match-answer-handle"
                type="button"
                {...attributes}
                {...listeners}
            >
                · ·
                <br />
                · ·
                <br />
                · ·
            </button>
        </div>
    );
}




function SortableOrderingItem({ id, text }) {
    const { attributes, listeners, setNodeRef, transform, transition } =
        useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="ordering-inner"
        >

            <button
                className="match-answer-handle ordering-handle-right"
                type="button"
                {...attributes}
                {...listeners}
            >
                · ·
                <br />
                · ·
                <br />
                · ·
            </button>

            <div className="match-input">
                {text}
            </div>
        </div>
    );
}




export default function PassingTestStudent() {
    const { test_link } = useParams();
    const navigate = useNavigate();

    const [test, setTest] = useState(null);
    const [answers, setAnswers] = useState({});
    const [loading, setLoading] = useState(true);

    const [startTime, setStartTime] = useState(null);
    const [timeLeft, setTimeLeft] = useState(null);

    useEffect(() => {
        const key = `shared_test_${test_link}`;
        const saved = localStorage.getItem(key);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);


                const shuffledTest = {
                    ...parsed,
                    questions: (parsed.questions || []).map((q, idx) => {
                        const qId = q.id ?? idx;


                        if (q.type === "matching") {
                            const rows = q.rows || q.matching || [];
                            const initialIds = rows.map((_, i) => `a-${i}`);
                            const shuffledIds = shuffleArray(initialIds);



                            setAnswers(prev => ({
                                ...prev,
                                [qId]: shuffledIds,
                            }));

                            return q;
                        }


                        if (q.type === "ordering") {
                            const items = q.items || [];
                            const initialIds = items.map((_, i) => `i-${i}`);
                            const shuffledIds = shuffleArray(initialIds);

                            setAnswers(prev => ({
                                ...prev,
                                [qId]: shuffledIds,
                            }));

                            return q;
                        }

                        return q;
                    }),
                };

                setTest(shuffledTest);
                setStartTime(Date.now());
                if (parsed && typeof parsed.completetime === "number") {
                    setTimeLeft(parsed.completetime);
                }
            } catch (e) {
                console.error("Ошибка парсинга теста", e);
            }
        }
        setLoading(false);
    }, [test_link]);


    useEffect(() => {
        if (timeLeft == null) return;
        if (timeLeft <= 0) {
            handleSubmit();
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
        return `${m.toString().padStart(2, "0")}:${s
            .toString()
            .padStart(2, "0")}`;
    };

    if (loading) {
        return <div>Загрузка...</div>;
    }

    if (!test) {
        return <div>Тест не найден или ссылка недействительна.</div>;
    }

    const handleAnswerChange = (questionId, value) => {
        setAnswers((prev) => ({
            ...prev,
            [questionId]: value,
        }));
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
                    const correct = (q.correctAnswers || q.correct_input || [])
                        .map((s) =>
                            q.caseSensitive || q.case_sensitive
                                ? s
                                : s.toLowerCase().trim()
                        );
                    if (userAnswer) {
                        const normUser =
                            q.caseSensitive || q.case_sensitive
                                ? userAnswer
                                : userAnswer.toLowerCase().trim();
                        if (correct.includes(normUser)) {
                            score = max;
                        }
                    }
                    break;
                }

                case "singleChoice": {
                    const options = q.options || q.choice || [];
                    const correctIndex = options.findIndex(
                        (o) => o.isCorrect || o.is_true
                    );
                    if (correctIndex !== -1 && userAnswer === correctIndex) {
                        score = max;
                    }
                    break;
                }

                case "multipleChoice": {
                    const options = q.options || q.choice || [];
                    const correctIndexes = options
                        .map((o, i) => (o.isCorrect || o.is_true ? i : -1))
                        .filter((i) => i !== -1);

                    const user = Array.isArray(userAnswer)
                        ? userAnswer.slice().sort()
                        : [];

                    const scoringType = q.scoringType || "allOrNothing";

                    if (scoringType === "allOrNothing") {

                        const correctSorted = correctIndexes.slice().sort();
                        const equal =
                            user.length === correctSorted.length &&
                            user.every((val, idx) => val === correctSorted[idx]);

                        if (equal) {
                            score = max;
                        }
                    } else if (scoringType === "partial") {

                        const totalCorrect = correctIndexes.length;

                        if (totalCorrect > 0 && user.length > 0) {

                            const correctSelected = user.filter((idx) =>
                                correctIndexes.includes(idx)
                            ).length;

                            const fraction = correctSelected / totalCorrect;
                            const rawScore = max * fraction;


                            score = Math.round(rawScore);
                        } else {
                            score = 0;
                        }
                    }

                    break;
                }

                case "matching": {
                    const rows = q.rows || q.matching || [];
                    const userOrder = userAnswer || [];

                    const correctOrder = rows.map((_, idx) => `a-${idx}`);

                    const equal =
                        Array.isArray(userOrder) &&
                        userOrder.length === correctOrder.length &&
                        userOrder.every((v, i) => v === correctOrder[i]);

                    if (equal && rows.length > 0) {
                        score = max;
                    }
                    break;
                }

                case "ordering": {
                    const items = q.items || [];
                    const userOrder = userAnswer || [];

                    const correctOrder = items.map((_, idx) => `i-${idx}`);

                    const equal =
                        Array.isArray(userOrder) &&
                        userOrder.length === correctOrder.length &&
                        userOrder.every((v, i) => v === correctOrder[i]);

                    if (equal && items.length > 0) {
                        score = max;
                    }
                    break;
                }

                default:
                    break;
            }

            totalScore += score;
            totalMax += max;

            perQuestion.push({
                questionIndex: index + 1,
                questionText: q.text || "",
                score,
                maxScore: max,
            });
        });

        return { totalScore, totalMax, perQuestion };
    };


    const handleOptionToggle = (questionId, optionIndex) => {
        setAnswers((prev) => {
            const current = prev[questionId] || [];
            if (current.includes(optionIndex)) {
                return {
                    ...prev,
                    [questionId]: current.filter((i) => i !== optionIndex),
                };
            }
            return {
                ...prev,
                [questionId]: [...current, optionIndex],
            };
        });
    };


    const handleMatchingDragEnd = (qId, event) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        setAnswers((prev) => {
            const rows =
                test.questions.find((q) => (q.id || 0) === qId)?.rows || [];
            const initial = rows.map((_, idx) => `a-${idx}`);

            const current = prev[qId] || initial;

            const oldIndex = current.indexOf(active.id);
            const newIndex = current.indexOf(over.id);
            const newOrder = arrayMove(current, oldIndex, newIndex);

            return {
                ...prev,
                [qId]: newOrder,
            };
        });
    };


    const handleOrderingDragEnd = (qId, event) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        setAnswers((prev) => {
            const items =
                test.questions.find((q) => (q.id || 0) === qId)?.items || [];
            const initial = items.map((_, idx) => `i-${idx}`);

            const current = prev[qId] || initial;

            const oldIndex = current.indexOf(active.id);
            const newIndex = current.indexOf(over.id);
            const newOrder = arrayMove(current, oldIndex, newIndex);

            return {
                ...prev,
                [qId]: newOrder,
            };
        });
    };

    const handleSubmit = () => {
        if (!test) return;

        const { totalScore, totalMax, perQuestion } =
            calculateScoreWithDetails();

        const isPercentage = test.is_percentage;
        const threshold = test.threshold || 0;

        let passed = false;

        if (isPercentage) {
            const percent = totalMax > 0 ? (totalScore / totalMax) * 100 : 0;
            passed = percent >= threshold;
        } else {
            passed = totalScore >= threshold;
        }

        const message = passed
            ? test.success_text || "Тест успешно пройден."
            : test.fail_text || "Тест не пройден.";


        const userRaw = localStorage.getItem("user");
        let userEmail = null;
        let userName = null;
        try {
            if (userRaw) {
                const user = JSON.parse(userRaw);
                userEmail =
                    user.email || user.username || user.login || null;

                const lastName = user.surname || "";
                const firstName = user.name || "";
                userName = `${lastName} ${firstName}`.trim() || "Участник";
            }
        } catch (e) {
            console.error("Не удалось распарсить user", e);
        }

        const testId = test.id || test.test_id || test_link;
        const finishedAt = new Date().toISOString();
        const durationMs = startTime ? Date.now() - startTime : 0;
        const durationMinutes = Math.round(durationMs / 60000);

        try {
            const keyAttempts = `attempts_${testId}`;
            const rawAttempts = localStorage.getItem(keyAttempts);
            const attemptsList = rawAttempts
                ? JSON.parse(rawAttempts)
                : [];

            const attempt = {
                id: Date.now(),
                testId,
                userEmail: userEmail || "unknown",
                userName,
                finishedAt,
                passed,
                message,
                score: totalScore,
                totalMax,
                perQuestion,
                durationMinutes,
            };

            const updatedAttempts = Array.isArray(attemptsList)
                ? [...attemptsList, attempt]
                : [attempt];
            localStorage.setItem(
                keyAttempts,
                JSON.stringify(updatedAttempts)
            );
        } catch (e) {
            console.error("Не удалось сохранить попытку теста", e);
        }


        if (userEmail) {
            try {
                const keyUser = `savedTests_${userEmail}`;
                const raw = localStorage.getItem(keyUser);
                const list = raw ? JSON.parse(raw) : [];

                const record = {
                    id: testId,
                    title: test.title || "Без названия",
                    passed,
                    message,
                    score: totalScore,
                    totalMax,
                    finishedAt,
                    durationMinutes,
                };

                const updated = Array.isArray(list) ? [...list, record] : [record];
                localStorage.setItem(keyUser, JSON.stringify(updated));
            } catch (e) {
                console.error("Не удалось сохранить результат теста", e);
            }
        }

        alert(message);
        navigate("/myTestStudent");
    };

    const questions = test.questions || [];

    return (
        <div className="tests-page">
            <div
                className="test-page"
                style={{ position: "absolute", left: "1430px", top: "0px" }}
            >
                <LogoutButton />
            </div>

            <div className="create-wrapper">
                <div className="test">
                    <header className="passing-test-header">
                        <h1 className="passing-title">
                            {test.title || "Без названия"}
                        </h1>
                        {test.description && (
                            <p className="passing-description">
                                {test.description}
                            </p>
                        )}
                        {timeLeft != null && (
                            <div className="passing-timer">
                                Осталось времени: {formatTime(timeLeft)}
                            </div>
                        )}
                    </header>
                    <div className="tests-line"></div>
                    <div className="passing-questions">
                        {questions.map((q, index) => {
                            const qId = q.id || index;
                            const qType = q.type;

                            return (
                                <div key={qId} className="passing-question-block">
                                    <div className="passing-question-header">
                                        <span className="passing-question-number">
                                            {index + 1}.
                                        </span>
                                        <span className="passing-question-text">
                                            {q.text || "Без текста"}
                                        </span>
                                    </div>

                                    {qType === "shortText" && (
                                        <div className="options-row12">
                                            <input
                                                type="text"
                                                className="answer-input"
                                                placeholder="Введите ответ..."
                                                value={answers[qId] || ""}
                                                onChange={(e) =>
                                                    handleAnswerChange(
                                                        qId,
                                                        e.target.value
                                                    )
                                                }
                                            />
                                        </div>
                                    )}

                                    {qType === "singleChoice" && (
                                        <div className="passing-question-body passing-options-single">
                                            {(q.options || []).map(
                                                (opt, idx) => (
                                                    <label
                                                        key={idx}
                                                        className="passing-option-row"
                                                    >
                                                        <input
                                                            type="radio"
                                                            className="options-row1"
                                                            name={`q-${qId}`}
                                                            checked={
                                                                answers[qId] ===
                                                                idx
                                                            }
                                                            onChange={() =>
                                                                handleAnswerChange(
                                                                    qId,
                                                                    idx
                                                                )
                                                            }
                                                        />
                                                        <span className="answer-input">
                                                            {opt.text || ""}
                                                        </span>
                                                    </label>
                                                )
                                            )}
                                        </div>
                                    )}

                                    {qType === "multipleChoice" && (
                                        <div className="passing-question-body passing-options-multiple">
                                            {(q.options || []).map(
                                                (opt, idx) => {
                                                    const selected =
                                                        (answers[qId] ||
                                                            []).includes(idx);

                                                    return (
                                                        <label
                                                            key={idx}
                                                            className="options-row"
                                                        >
                                                            <input
                                                                type="checkbox"
                                                                checked={
                                                                    selected
                                                                }
                                                                onChange={() =>
                                                                    handleOptionToggle(
                                                                        qId,
                                                                        idx
                                                                    )
                                                                }
                                                            />
                                                            <span className="answer-input">
                                                                {opt.text || ""}
                                                            </span>
                                                        </label>
                                                    );
                                                }
                                            )}
                                        </div>
                                    )}

                                    {qType === "matching" && (
                                        <div className="passing-question-body passing-matching">
                                            <div className="match-panel">
                                                <div className="match-header">
                                                    <div className="match-header-col"></div>
                                                    <div className="match-header-col"></div>
                                                </div>

                                                <div className="match-rows">
                                                    {/* левая колонка */}
                                                    <div className="match-column match-column-left">
                                                        {(q.rows || []).map((row, idx) => (
                                                            <div key={idx} className="match-row-outer">
                                                                <div className="match-row-inner">
                                                                    {row.option || ""}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>

                                                    {/* правая колонка */}
                                                    <div className="match-column match-column-right">
                                                        <DndContext
                                                            collisionDetection={closestCenter}
                                                            onDragEnd={(event) =>
                                                                handleMatchingDragEnd(qId, event)
                                                            }
                                                        >
                                                            <SortableContext
                                                                items={
                                                                    answers[qId] ||
                                                                    (q.rows || []).map((_, idx) => `a-${idx}`)
                                                                }
                                                                strategy={verticalListSortingStrategy}
                                                            >
                                                                {(() => {
                                                                    const order =
                                                                        answers[qId] ||
                                                                        (q.rows || []).map((_, idx) => `a-${idx}`);

                                                                    return order.map((answerId) => {
                                                                        const idx = parseInt(
                                                                            answerId.split("-")[1],
                                                                            10
                                                                        );
                                                                        const row =
                                                                            (q.rows || [])[idx] || {};
                                                                        return (
                                                                            <div
                                                                                key={answerId}
                                                                                className="match-row-outer"
                                                                            >
                                                                                <SortableMatchAnswer
                                                                                    id={answerId}
                                                                                    text={row.answer || ""}
                                                                                />
                                                                            </div>
                                                                        );
                                                                    });
                                                                })()}
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
                                            <DndContext
                                                collisionDetection={closestCenter}
                                                onDragEnd={(event) =>
                                                    handleOrderingDragEnd(qId, event)
                                                }
                                            >
                                                <SortableContext
                                                    items={
                                                        answers[qId] ||
                                                        (q.items || []).map((_, idx) => `i-${idx}`)
                                                    }
                                                    strategy={verticalListSortingStrategy}
                                                >
                                                    {(() => {
                                                        const order =
                                                            answers[qId] ||
                                                            (q.items || []).map(
                                                                (_, idx) => `i-${idx}`
                                                            );

                                                        return order.map(
                                                            (itemId, visualIndex) => {
                                                                const idx = parseInt(
                                                                    itemId.split("-")[1],
                                                                    10
                                                                );
                                                                const item =
                                                                    (q.items || [])[idx] ||
                                                                    {};
                                                                return (
                                                                    <div
                                                                        key={itemId}
                                                                        className="passing-ordering-row"
                                                                    >
                                                                        <span className="passing-ordering-index">
                                                                            {visualIndex + 1}
                                                                        </span>

                                                                        {/* бежевый прямоугольник */}
                                                                        <div className="ordering-row-outer">
                                                                            <SortableOrderingItem
                                                                                id={itemId}
                                                                                text={item.text || ""}
                                                                            />
                                                                        </div>
                                                                    </div>
                                                                );

                                                            }
                                                        );
                                                    })()}
                                                </SortableContext>
                                            </DndContext>
                                        </div>
                                    )}


                                </div>
                            );
                        })}
                    </div>

                    <div className="passing-footer">
                        <button
                            className="passing-submit-btn"
                            onClick={handleSubmit}
                        >
                            Завершить тестирование
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
