import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import DeleteIcon from "../../assets/delete.svg?react";
import DeleteIconSub from "../../assets/delete_sub.svg?react";
import MultipIcon from "../../assets/MultipleСhoice.svg";
import ScoreInput2 from "../details/ScoreInput2.jsx";

function MultipleChoiceQuestion({ question, updateQuestion, deleteQuestion, onChangeType }) {
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

    const addOption = () => {
        const newOptions = [...question.options, { text: "", isCorrect: false, points: 0 }];
        updateQuestion(question.id, "options", newOptions);
    };

    const updateOption = (index, field, value) => {
        const newOptions = [...question.options];
        newOptions[index][field] = value;
        updateQuestion(question.id, "options", newOptions);
    };

    const deleteOption = (index) => {
        const newOptions = question.options.filter((_, i) => i !== index);
        updateQuestion(question.id, "options", newOptions);
    };

    const handleChangeType = () => {
        onChangeType?.(question.id);
    };

    return (
        <div ref={setNodeRef} style={style} className="question-block multiple-choice">
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
                     <span
                         onClick={handleChangeType}
                         style={{ cursor: "pointer" }}
                     >
                             <img
                                 src={MultipIcon}
                                 alt="multu"
                                 style={{ width: '36px', height: '36px' }}
                             />
                     </span>
                    Множественный выбор
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
            <div className="options-list">
                {question.options?.map((option, index) => (
                    <div key={index} className="options-row">
                        <label className="option-label">
                            <input
                                type="checkbox"
                                checked={option.isCorrect}
                                onChange={(e) => updateOption(index, "isCorrect", e.target.checked)}
                            />

                            <input
                                type="text"
                                className="answer-input"
                                placeholder="Введите вариант..."
                                value={option.text}
                                onChange={(e) => updateOption(index, "text", e.target.value)}
                            />
                        </label>
                        <ScoreInput2
                            value={option.points || 0}
                            onChange={val => updateOption(index, "points", val)}
                        />
                        <button
                            className="delete-answer-btn"
                            onClick={() => deleteOption(index)}
                        >
                            <DeleteIconSub  />
                        </button>
                    </div>
                ))}
            </div>

            <button className="add-answer-btn" onClick={addOption}>
                + Добавить вариант
            </button>
        </div>
    );
}

export default MultipleChoiceQuestion;