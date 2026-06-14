import { useRef, useState } from "react";
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from "@dnd-kit/core";
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import EditIcon from "../assets/edit.svg?react";

import { useNavigate, useLocation } from "react-router-dom";
import SortableQuestion from "../components/Question";
import PassingCriteria from "../components/questions/PassingCriteria.jsx";
import ResultMessages from "../components/questions/ResultMessages";
import "../styles/createTest.css";
import LogoutButton from "../components/LogoutButton.jsx";
import TimeBox from "../components/details/TimeBox.jsx";
import BackIcon from "../assets/back.svg?react";
import { testsAPI } from "../services/api.js";


function useAppSensors() {
    const pointerSensor = useSensor(PointerSensor);
    const keyboardSensor = useSensor(KeyboardSensor, {
        coordinateGetter: sortableKeyboardCoordinates,
    });

    return useSensors(pointerSensor, keyboardSensor);
}

export default function CreateTest() {
    const navigate = useNavigate();
    const location = useLocation();

    const isEditing = location.state?.editing || false;

    const storedEditingTest = (() => {
        try {
            const raw = localStorage.getItem("editingTest");
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    })();

    const editingTest =
        isEditing && location.state?.test && location.state.test.questions
            ? location.state.test
            : storedEditingTest || null;


    const [title, setTitle] = useState(
        isEditing ? editingTest?.title || "" : ""
    );

    const [description, setDescription] = useState(
        isEditing ? editingTest?.description || "" : ""
    );
    const [showQuestionMenu, setShowQuestionMenu] = useState(null);
    const [questionMenuMode, setQuestionMenuMode] = useState("add");
    const [selectedQuestionId, setSelectedQuestionId] = useState(null);
    const nextQuestionId = useRef(0);


    const [time] = useState(
        isEditing && editingTest?.complete_time
            ? {
                hours: Math.floor(editingTest.complete_time / 3600),
                minutes: Math.floor(
                    (editingTest.complete_time % 3600) / 60
                ),
                seconds: editingTest.complete_time % 60,
            }
            : {
                hours: 0,
                minutes: 0,
                seconds: 0,
            }
    );

    const [passingCriteria] = useState(
        isEditing && editingTest
            ? {
                type: editingTest?.is_percentage ? "percentage" : "points",
                percentage: editingTest?.is_percentage
                    ? editingTest.threshold
                    : 75,
                points: editingTest?.is_percentage
                    ? 0
                    : editingTest.threshold,
            }
            : {
                type: "percentage",
                percentage: 75,
                points: 0,
            }
    );

    const [resultMessages] = useState(
        isEditing
            ? {
                success: editingTest?.success_text || "",
                failure: editingTest?.fail_text || "",
            }
            : {
                success: "",
                failure: "",
            }
    );

    const [questions, setQuestions] = useState(() => {
        if (isEditing && editingTest && Array.isArray(editingTest.questions)) {
            const typeMap = {
                single_choice: "singleChoice",
                multiple_choice: "multipleChoice",
                text_input: "shortText",
                correct_order: "ordering",
            };

            return editingTest.questions.map((q, idx) => {
                const legacyOptionsArray = Array.isArray(q.options) ? q.options : [];
                const apiOptions = Array.isArray(q.options) ? {} : q.options || {};
                const uiType = typeMap[q.type] || q.type || "shortText";
                const asArray = (value) => Array.isArray(value) ? value : [];
                const firstNonEmptyArray = (...values) => values.find((value) => Array.isArray(value) && value.length > 0) || [];
                const normalizeChoices = (choices = []) =>
                    asArray(choices).map((item) => ({
                        text: item.text || "",
                        isCorrect: Boolean(item.isCorrect ?? item.is_true),
                        points: item.points || 0,
                    }));

                const base = {
                    id: `q-${q.question_id || q.id || idx}-${Date.now()}`,
                    order: q.order || q.order_number || idx + 1,
                    type: uiType,
                    text: q.text || "",
                    maxScore: q.maxScore || q.points || 15,
                };

                switch (uiType) {
                    case "shortText":
                        return {
                            ...base,
                            correctAnswers: q.correctAnswers || q.correct_input || apiOptions.correct_input || [""],
                            caseSensitive:
                                q.caseSensitive !== undefined
                                    ? q.caseSensitive
                                    : Boolean(q.case_sensitive ?? apiOptions.case_sensitive),
                        };
                    case "singleChoice":
                        return {
                            ...base,
                            options: normalizeChoices(firstNonEmptyArray(q.choice, legacyOptionsArray, apiOptions.choice, [{ text: "", isCorrect: false }])),
                        };
                    case "multipleChoice":
                        return {
                            ...base,
                            options: normalizeChoices(firstNonEmptyArray(q.choice, legacyOptionsArray, apiOptions.choice, [{ text: "", isCorrect: false }])),
                            scoringType: q.scoringType || "allOrNothing",
                        };
                    case "matching": {
                        const matchingSource = q.rows || q.matching || apiOptions.matching || [];
                        const rows = Array.isArray(matchingSource)
                            ? matchingSource
                            : asArray(matchingSource.left || matchingSource.leftColumn).map((left, index) => ({
                                  option: left,
                                  answer: asArray(matchingSource.right || matchingSource.rightColumn)[index] || "",
                              }));
                        return {
                            ...base,
                            rows: rows.length
                                ? rows.map((row) => ({
                                      option: row.option || row.left || row.leftColumn || "",
                                      answer: row.answer || row.right || row.rightColumn || "",
                                  }))
                                : [{ option: "", answer: "" }],
                        };
                    }
                    case "ordering": {
                        const sequenceSource = q.items || q.sequence || apiOptions.sequence || [];
                        const items = asArray(sequenceSource).map((item) => typeof item === "string" ? item : item.text || "");
                        return {
                            ...base,
                            items: items.length ? items : [""],
                        };
                    }
                    default:
                        return base;
                }
            });
        }

        return [
            {
                id: "1",
                order: 1,
                type: "shortText",
                text: "",
                correctAnswers: [""],
                caseSensitive: false,
                maxScore: 15,
            },
        ];
    });

    const calculateCompleteTime = () => {
        return time.hours * 3600 + time.minutes * 60 + time.seconds;
    };

    const sensors = useAppSensors();

    const changeQuestionType = (questionId) => {
        setSelectedQuestionId(questionId);
        setQuestionMenuMode("change");
        setShowQuestionMenu("icon_click");
    };

    const addQuestion = (type) => {
        if (questionMenuMode === "change" && selectedQuestionId) {
            const currentQuestion = questions.find(q => q.id === selectedQuestionId);
            if (!currentQuestion) {
                setShowQuestionMenu(false);
                setQuestionMenuMode("add");
                setSelectedQuestionId(null);
                return;
            }

            const newQuestion = {
                id: currentQuestion.id,
                order: currentQuestion.order,
                type,
                text: currentQuestion.text,
                maxScore: currentQuestion.maxScore || 15,
            };

            switch (type) {
                case "shortText":
                    newQuestion.correctAnswers = [""];
                    newQuestion.caseSensitive = false;
                    break;
                case "singleChoice":
                    newQuestion.options = [{ text: "", isCorrect: false, points: 0 }];
                    break;
                case "multipleChoice":
                    newQuestion.options = [{ text: "", isCorrect: false, points: 0 }];
                    newQuestion.scoringType = "allOrNothing";
                    break;
                case "matching":
                    newQuestion.rows = [{ option: "", answer: "", points: 0 }];
                    break;
                case "ordering":
                    newQuestion.items = [{ text: "", points: 0 }];
                    break;
            }

            setQuestions(
                questions.map(q => q.id === selectedQuestionId ? newQuestion : q)
            );
            setSelectedQuestionId(null);
        } else {
            const baseQuestion = {
                id: `new-question-${++nextQuestionId.current}`,
                order: questions.length + 1,
                type,
                text: "",
                maxScore: 15,
            };

            switch (type) {
                case "shortText":
                    baseQuestion.correctAnswers = [""];
                    baseQuestion.caseSensitive = false;
                    break;
                case "singleChoice":
                    baseQuestion.options = [{ text: "", isCorrect: false, points: 0 }];
                    break;
                case "multipleChoice":
                    baseQuestion.options = [{ text: "", isCorrect: false, points: 0 }];
                    baseQuestion.scoringType = "allOrNothing";
                    break;
                case "matching":
                    baseQuestion.rows = [{ option: "", answer: "", points: 0 }];
                    break;
                case "ordering":
                    baseQuestion.items = [{ text: "", points: 0 }];
                    break;
            }

            setQuestions([...questions, baseQuestion]);
        }
        setShowQuestionMenu(false);
        setQuestionMenuMode("add");
    };

    const updateQuestion = (id, field, value) => {
        setQuestions(
            questions.map((q) =>
                q.id === id ? { ...q, [field]: value } : q
            )
        );
    };

    const deleteQuestion = (id) => {
        setQuestions(questions.filter((q) => q.id !== id));
    };

    const handleDragEnd = (event) => {
        const { active, over } = event;

        if (over && active.id !== over.id) {
            setQuestions((items) => {
                const oldIndex = items.findIndex(
                    (item) => item.id === active.id
                );
                const newIndex = items.findIndex(
                    (item) => item.id === over.id
                );
                const newItems = arrayMove(items, oldIndex, newIndex);

                return newItems.map((item, idx) => ({
                    ...item,
                    order: idx + 1,
                }));
            });
        }
    };

    const handleSave = async () => {
        if (!title.trim()) {
            alert("Введите название теста!");
            return;
        }

        const testData = {
            title: title.trim(),
            description: description.trim(),
            is_percentage: passingCriteria.type === "percentage",
            fail_text: resultMessages.failure || "",
            success_text: resultMessages.success || "",
            complete_time: calculateCompleteTime() || 3600,
            threshold:
                passingCriteria.type === "percentage"
                    ? passingCriteria.percentage
                    : passingCriteria.points,
            questions: questions.map((q, index) => {
                let options = {};
                let questionType;

                switch (q.type) {
                    case "singleChoice":
                        questionType = "single_choice";
                        options = {
                            choice:
                                q.options?.map((opt) => ({
                                    text: opt.text,
                                    is_true: opt.isCorrect,
                                    points: opt.points || 0,
                                })) || [],
                        };
                        break;
                    case "multipleChoice":
                        questionType = "multiple_choice";
                        options = {
                            choice:
                                q.options?.map((opt) => ({
                                    text: opt.text,
                                    is_true: opt.isCorrect,
                                    points: opt.points || 0,
                                })) || [],
                        };
                        break;
                    case "shortText":
                        questionType = "text_input";
                        options = {
                            correct_input: q.correctAnswers || [],
                            case_sensitive: q.caseSensitive || false,
                        };
                        break;
                    case "matching":
                        questionType = "matching";
                        options = {
                            matching:
                                q.rows?.map((row) => ({
                                    left: row.option,
                                    right: row.answer,
                                    points: row.points || 0,
                                })) || [],
                        };
                        break;
                    case "ordering":
                        questionType = "correct_order";
                        options = {
                            sequence:
                                q.items?.map((item, itemIdx) => ({
                                    text: typeof item === "string" ? item : item.text,
                                    order: itemIdx + 1,
                                    points: typeof item === "string" ? 0 : item.points || 0,
                                })) || [],
                        };
                        break;
                    default:
                        questionType = "text_input";
                }

                return {
                    text: q.text || "",
                    points: q.maxScore || 0,
                    type: questionType,
                    order_number: index + 1,
                    options: options,
                };
            }),
        };

        console.log(
            "Отправляемые данные на бэкенд:",
            JSON.stringify(testData, null, 2)
        );

        try {
            const token = localStorage.getItem("token");
            if (!token) {
                alert("Требуется авторизация!");
                navigate("/login");
                return;
            }

            const testId = editingTest?.ID || editingTest?.id || editingTest?.Id;
            const response = isEditing && testId
                ? await testsAPI.updateTest(testId, testData)
                : await testsAPI.createTest(testData);
            const result = response.data;

            console.log("Успешный ответ от сервера:", result);

            localStorage.removeItem("editingTest");

            alert(
                isEditing
                    ? "Тест успешно обновлен!"
                    : "Тест успешно создан на сервере!"
            );
            navigate("/tests", { replace: true });

        } catch (error) {
            console.error("Ошибка при создании теста:", error);
            alert(
                `Не удалось ${
                    isEditing ? "обновить" : "создать"
                } тест на сервере: ${error.message}\n\nПроверьте консоль для деталей.`
            );
        }
    };

    const handleBack = () => {
        navigate("/tests");
    };

    const questionTypes = [
        { key: "shortText", label: "Задания на ручной ввод" },
        { key: "singleChoice", label: "Одиночный выбор" },
        { key: "multipleChoice", label: "Множественный выбор" },
        { key: "matching", label: "На соотношение" },
        {
            key: "ordering",
            label: "На расположение в правильном порядке",
        },
    ];

    return (
        <div className="tests-page">
            <div
                className="test-page"
                style={{ position: "absolute", left: "1430px", top: "0px" }}
            >
                <LogoutButton />
            </div>

            <div className="create-wrapper">
                <div className="create-left">
                    <div className="stat-top-bar2">
                        <button className="stat-back-btn2" onClick={handleBack}>
                            <BackIcon />
                        </button>
                        <h1>Создание теста</h1>

                    </div>
                    <div className="tests-line"></div>
                    <div className="title-input-container">
                        <input
                            className="test-desk1"
                            placeholder="Название"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                        />
                        <EditIcon />
                    </div>
                    <div className="title-input-container-desk">
                        <input
                            className="test-desk"
                            placeholder="Описание теста"
                            value={description}
                            onChange={(e) =>
                                setDescription(e.target.value)
                            }
                        />
                        <EditIcon />
                    </div>
                    <DndContext
                        sensors={sensors}
                        collisionDetection={closestCenter}
                        onDragEnd={handleDragEnd}
                    >
                        <SortableContext
                            items={questions.map((q) => q.id)}
                            strategy={verticalListSortingStrategy}
                        >
                            {questions.map((question) => (
                                <SortableQuestion
                                    key={question.id}
                                    question={question}
                                    updateQuestion={updateQuestion}
                                    deleteQuestion={deleteQuestion}
                                    onChangeType={changeQuestionType}
                                />
                            ))}
                        </SortableContext>
                    </DndContext>

                    <div className="questions-bottom-buttons">
                        <button
                            className="add-question-btn"
                            onClick={() => {
                                setQuestionMenuMode("add");
                                setSelectedQuestionId(null);
                                setShowQuestionMenu("add_button");
                            }}
                        >
                            Добавить вопрос
                        </button>
                        <button
                            className="save-btn"
                            onClick={handleSave}
                        >
                            {isEditing
                                ? "Сохранить изменения"
                                : "СОЗДАТЬ ТЕСТ"}
                        </button>
                    </div>

                </div>


            </div>
            {showQuestionMenu && (
                <div className="modal-overlay" onClick={() => setShowQuestionMenu(false)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>
                                {questionMenuMode === "change"
                                    ? "Выберите новый тип вопроса"
                                    : "Выберите тип вопроса"}
                            </h3>
                            <button
                                className="modal-close"
                                onClick={() => setShowQuestionMenu(false)}
                            >
                                ×
                            </button>
                        </div>

                        {showQuestionMenu === "icon_click" && (
                            <div className="modal-mode-switcher">
                                <label>
                                    <input
                                        type="radio"
                                        name="question-mode"
                                        value="add"
                                        checked={questionMenuMode === "add"}
                                        onChange={() => {
                                            setQuestionMenuMode("add");
                                            setSelectedQuestionId(null);
                                        }}
                                    />
                                    Добавить новый вопрос
                                </label>
                                <label>
                                    <input
                                        type="radio"
                                        name="question-mode"
                                        value="change"
                                        checked={questionMenuMode === "change"}
                                        onChange={() => setQuestionMenuMode("change")}
                                        disabled={questions.length === 0}
                                    />
                                    Изменить тип текущего вопроса
                                </label>
                            </div>
                        )}

                        <div className="modal-body">
                            {questionTypes.map((type) => (
                                <button
                                    key={type.key}
                                    className="modal-option"
                                    onClick={() => {
                                        addQuestion(type.key);
                                    }}
                                >
                                    {type.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
