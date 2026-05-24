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
    testsList = [],
    tests = []
}) {
    const availableTests = testsList.length > 0 ? testsList : tests;

    const getTestTitle = (id) => {
        const test = availableTests.find(t => Number(t.id) === Number(id));
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
                <div className="criteria-table-row" key={idx}>
                    <div>
                        <textarea
                            value={row.threshold}
                            onChange={e => {
                                const onlyNumbers = e.target.value.replace(/\D/g, '');
                                e.target.style.height = 'auto';
                                e.target.style.height = `${e.target.scrollHeight}px`;
                                onChange(idx, { ...row, threshold: onlyNumbers });
                            }}
                            className="criteria-threshold-input"
                        />
                    </div>

                    <div>
                        <textarea
                            value={row.message}
                            onChange={e => {
                                e.target.style.height = 'auto';
                                e.target.style.height = `${e.target.scrollHeight}px`;
                                onChange(idx, { ...row, message: e.target.value });
                            }}
                            className="criteria-message-input"
                        />
                    </div>

                    <div className="criteria-tests-cell">
                        {row.extraTests?.map((test, testIdx) => (
                            <div className="criteria-test-item" key={testIdx}>
                                <span>{getTestTitle(test)}</span>
                                <button className="criteria-delete-test-btn" onClick={() => onDeleteTest(idx, testIdx)}>
                                    <img src={basketIcon} alt="Удалить" />
                                </button>
                            </div>
                        ))}

                        <button className="criteria-add-test-btn" onClick={() => onAddTest(idx)}>
                            <img src={plusIcon} alt="Добавить" />
                            <span>Добавить тесты</span>
                        </button>
                    </div>

                    <div className="criteria-delete-cell">
                        <button className="criteria-delete-btn" onClick={() => onDelete(idx)}>
                            <img src={basketIcon} alt="Удалить" />
                        </button>
                    </div>
                </div>
            ))}

            <button className="criteria-add-btn" onClick={onAdd}>
                <img src={plusIcon} alt="Добавить" />
                <span>Добавить критерий</span>
            </button>
        </div>
    );
}
