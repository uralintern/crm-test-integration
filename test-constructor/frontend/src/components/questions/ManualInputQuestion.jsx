import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import DeleteIcon from "../../assets/delete.svg?react";
import DeleteIconSub from "../../assets/delete_sub.svg?react";
import ScoreInput from "../details/ScoreInput.jsx";
import ManualIcon from "../../assets/Manual.svg";
function ManualInputQuestion({ question, updateQuestion, deleteQuestion }) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: question.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    const addAnswer = () => {
        const newAnswers = [...question.correctAnswers, ""];
        updateQuestion(question.id, "correctAnswers", newAnswers);
    };

    const updateAnswer = (index, value) => {
        const newAnswers = [...question.correctAnswers];
        newAnswers[index] = value;
        updateQuestion(question.id, "correctAnswers", newAnswers);
    };

    const deleteAnswer = (index) => {
        const newAnswers = question.correctAnswers.filter((_, i) => i !== index);
        updateQuestion(question.id, "correctAnswers", newAnswers);
    };

    return (
        <div ref={setNodeRef} style={style} className="question-block manual-input">
            <div className = "">

                <div className = "question-up">
                    <span {...attributes} {...listeners} className="drag-handle">
                        <div style={{lineHeight: '0.2'}}>
                            <div>···</div>
                            <div style={{marginTop: '2px'}}>···</div>
                        </div>
                    </span>



                    <div className="q-icons">
                            <span onClick={() => deleteQuestion(question.id)}>
                                <DeleteIcon style={{ width: '24px', height: '24px' }}/>
                            </span>
                    </div>
                </div>
                <div className="q-header1">
                    <span>
                            <img
                                 src={ManualIcon}
                                alt="manual"
                                style={{ width: '36px', height: '36px' }}
                            />
                    </span>
                    Задание на ручной ввод
                </div>

                <div className="q-header">
                    <span>
                        {question.order}. <input
                        className="q-text-input"
                        placeholder="Введите текст вопроса..."
                        value={question.text}
                        onChange={(e) => updateQuestion(question.id, "text", e.target.value)}
                    />
                    </span>
                </div>

            </div>

            <div className="block-questions99">
            <div className="section-title">Правильные ответы</div>
                <div className="answers-list">
                    {question.correctAnswers?.map((answer, index) => (
                        <div key={index} className="answer-row99">
                            <input
                                type="text"
                                className="answer-input"
                                placeholder="Введите ответ..."
                                value={answer}
                                onChange={(e) => updateAnswer(index, e.target.value)}
                            />
                            <button className="delete-answer-btn" onClick={() => deleteAnswer(index)}>
                                <DeleteIconSub  />
                            </button>
                        </div>
                    ))}
                </div>
                <button className="add-answer-btn" onClick={addAnswer}>
                + Добавить ответ
                </button>
                <div className="section-settings">Настройки</div>
                    <div className="setting-row">
                        <label>
                            <input
                                type="checkbox"
                                checked={question.caseSensitive || false}
                                onChange={(e) => updateQuestion(question.id, "caseSensitive", e.target.checked)}
                            />
                            Учитывать регистр ответов
                        </label>
                    </div>
            </div>
            <ScoreInput
                value={question.maxScore}
                onChange={val => updateQuestion(question.id, "maxScore", val)}
            />

        </div>
    );
}

export default ManualInputQuestion;