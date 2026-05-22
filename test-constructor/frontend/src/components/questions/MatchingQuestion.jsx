import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import DeleteIcon from "../../assets/delete.svg?react";
import DeleteIconSub from "../../assets/delete_sub.svg?react";
import ScoreInput2 from "../details/ScoreInput2.jsx";
import RatioIcon from "../../assets/Ratio.svg";

function MatchingQuestion({ question, updateQuestion, deleteQuestion }) {
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

    const addRow = () => {
        const newRows = [...question.rows, { option: "", answer: "" }];
        updateQuestion(question.id, "rows", newRows);
    };

    const updateRow = (index, field, value) => {
        const newRows = [...question.rows];
        newRows[index][field] = value;
        updateQuestion(question.id, "rows", newRows);
    };

    const deleteRow = (index) => {
        const newRows = question.rows.filter((_, i) => i !== index);
        updateQuestion(question.id, "rows", newRows);
    };

    return (
        <div ref={setNodeRef} style={style} className="question-block matching">
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
                                src={RatioIcon}
                                alt="Ratio"
                                style={{ width: '36px', height: '36px' }}
                            />
                    </span>
                    На соотношение
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
                <div className="block-questions-container">
                    <div className="section-title999">Вариант</div>
                    <div className="section-title3">Ответ</div>
                </div>
                <div className="answers-list">
                {question.rows?.map((row, index) => (
                    <div key={index} className="answer-row">
                        <input
                            type="text"
                            className="answer-input"
                            placeholder="Введите вариант..."
                            value={row.option}
                            onChange={(e) => updateRow(index, "option", e.target.value)}
                        />
                        <div className="table-separator">:::</div>
                        <input
                            type="text"
                            className="answer-input"
                            placeholder="Введите ответ..."
                            value={row.answer}
                            onChange={(e) => updateRow(index, "answer", e.target.value)}
                        />
                        <ScoreInput2
                            value={question.maxScore}
                            onChange={val => updateQuestion(question.id, "maxScore", val)}
                        />
                        <button
                            className="delete-answer-btn"
                            onClick={() => deleteRow(index)}
                        >
                            <DeleteIconSub  />
                        </button>
                    </div>
                ))}
                </div>
            </div>

            <button className="add-answer-btn" onClick={addRow}>
                + Добавить ряд
            </button>
        </div>
    );
}

export default MatchingQuestion;