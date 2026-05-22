import React from 'react';

import plusIcon from '../../assets/plus.svg';
import basketIcon from '../../assets/korzina.svg';

export default function CriteriaTable({
                                          criteria,
                                          onChange,
                                          onAdd,
                                          onAddTest,
                                          onDelete,
                                          onDeleteTest,
                                          testsList = []
                                      }) {
    // Функция для получения названия теста по ID
    const getTestTitle = (id) => {
        const test = testsList.find(t => t.id === id);
        return test ? test.title : `Тест №${id}`;
    };

    return (
        <div className="criteria-table-block">

            <div className="criteria-table-header">
                <div>Нижняя граница</div>
                <div>Сообщение</div>
                <div>Дополнительный тест</div>
                <div></div>
            </div>

            {criteria.map((row, idx) => (
                <div
                    className="criteria-table-row"
                    key={idx}
                >

                    <div>
                        <textarea
                            value={row.threshold}
                            onChange={e => {
                                const onlyNumbers = e.target.value.replace(/\D/g, '');

                                e.target.style.height = 'auto';
                                e.target.style.height = `${e.target.scrollHeight}px`;

                                onChange(idx, {
                                    ...row,
                                    threshold: onlyNumbers
                                });
                            }}
                            className="criteria-threshold-input"
                        />
                    </div>

                    {/* MESSAGE */}
                    <div>
                        <textarea
                            value={row.message}
                            onChange={e => {
                                e.target.style.height = 'auto';
                                e.target.style.height = `${e.target.scrollHeight}px`;

                                onChange(idx, {
                                    ...row,
                                    message: e.target.value
                                });
                            }}
                            className="criteria-message-input"
                        />
                    </div>

                    <div className="criteria-tests-cell">

                        {row.extraTests?.map((test, testIdx) => (
                            <div
                                className="criteria-test-item"
                                key={testIdx}
                            >
                                <span>
                                    {getTestTitle(test)}  {}
                                 </span>

                                <button
                                    className="criteria-delete-test-btn"
                                    onClick={() =>
                                        onDeleteTest(idx, testIdx)
                                    }
                                >
                                    <img
                                        src={basketIcon}
                                        alt="delete"
                                    />
                                </button>

                            </div>
                        ))}

                        <button
                            className="criteria-add-test-btn"
                            onClick={() => onAddTest(idx)}
                        >

                            <img
                                src={plusIcon}
                                alt="plus"
                            />

                            <span>
                                Добавить тесты
                            </span>

                        </button>

                    </div>

                    <div className="criteria-delete-cell">

                        <button
                            className="criteria-delete-btn"
                            onClick={() => onDelete(idx)}
                        >
                            <img
                                src={basketIcon}
                                alt="delete"
                            />
                        </button>

                    </div>

                </div>
            ))}

            <button
                className="criteria-add-btn"
                onClick={onAdd}
            >

                <img
                    src={plusIcon}
                    alt="plus"
                />

                <span>
                    Добавить критерий
                </span>

            </button>

        </div>
    );
}