import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import DeleteIcon from "../../assets/delete.svg?react";
import DeleteIconSub from "../../assets/delete_sub.svg?react";

import CorrectOrderIcon from "../../assets/CorrectOrder.svg";
import ScoreInput2 from "../details/ScoreInput2.jsx";

function OrderingQuestion({ question, updateQuestion, deleteQuestion }) {
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

    const addItem = () => {
        const newItems = [...question.items, { text: "", points: 0 }];
        updateQuestion(question.id, "items", newItems);
    };

    const updateItem = (index, field, value) => {
        const newItems = [...question.items];
        newItems[index][field] = value;
        updateQuestion(question.id, "items", newItems);
    };

    const deleteItem = (index) => {
        const newItems = question.items.filter((_, i) => i !== index);
        updateQuestion(question.id, "items", newItems);
    };

    return (
        <div ref={setNodeRef} style={style} className="question-block ordering">
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
                                src={CorrectOrderIcon}
                                alt="CorrectOrder"
                                style={{ width: '36px', height: '36px' }}
                            />
                    </span>
                    На расположения в правильном порядке
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
                <div className="block-questions-container33">
                    <div className="section-title222">№</div>
                    <div className="section-title2222">Ответ</div>
                </div>
                <div className="answers-list">
                    {question.items?.map((item, index) => (
                        <div key={index} className="answer-row">
                            <span className="item-number">{index + 1}</span>
                            <input
                                type="text"
                                className="answer-input"
                                placeholder="Введите ответ..."
                                value={item.text}
                                onChange={(e) => updateItem(index, "text", e.target.value)}
                            />
                            <ScoreInput2
                                value={item.points || 0}
                                onChange={val => updateItem(index, "points", val)}
                            />
                            <button
                                className="delete-answer-btn"
                                onClick={() => deleteItem(index)}
                            >
                                <DeleteIconSub  />
                            </button>
                        </div>
                    ))}
                </div>
            </div>
            <button className="add-answer-btn" onClick={addItem}>
                + Добавить ряд
            </button>
        </div>
    );
}

export default OrderingQuestion;