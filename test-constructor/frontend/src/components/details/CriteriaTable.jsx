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
    tests = [],
    maxScore = 100,
}) {
    const availableTests = testsList.length > 0 ? testsList : tests;

    const getTestTitle = (id) => {
        const test = availableTests.find(item => Number(item.id) === Number(id));
        return test ? test.title : `Тест №${id}`;
    };

    return (
        <div className="criteria-table-block">
            <div className="criteria-table-header">
                <div>Нижняя граница (балл)</div>
                <div>Сообщение</div>
                <div>Дополнительный тест</div>
                <div />
            </div>

            {criteria.map((row, index) => (
                <div className="criteria-table-row" key={index}>
                    <div>
                        <textarea
                            value={row.threshold}
                            onChange={(event) => {
                                const digits = event.target.value.replace(/\D/g, '');
                                const value = digits === '' ? '' : String(Math.min(maxScore, Number(digits)));
                                event.target.style.height = 'auto';
                                event.target.style.height = `${event.target.scrollHeight}px`;
                                onChange(index, { ...row, threshold: value });
                            }}
                            className="criteria-threshold-input"
                            placeholder="0"
                            title={`Максимум: ${maxScore} баллов`}
                        />
                    </div>
                    <div>
                        <textarea
                            value={row.message}
                            onChange={(event) => {
                                event.target.style.height = 'auto';
                                event.target.style.height = `${event.target.scrollHeight}px`;
                                onChange(index, { ...row, message: event.target.value });
                            }}
                            className="criteria-message-input"
                        />
                    </div>
                    <div className="criteria-tests-cell">
                        {row.extraTests?.map((testId, testIndex) => (
                            <div className="criteria-test-item" key={`${testId}-${testIndex}`}>
                                <span>{getTestTitle(testId)}</span>
                                <button type="button" className="criteria-delete-test-btn" onClick={() => onDeleteTest(index, testIndex)}>
                                    <img src={basketIcon} alt="Удалить" />
                                </button>
                            </div>
                        ))}
                        <button type="button" className="criteria-add-test-btn" onClick={() => onAddTest(index)}>
                            <img src={plusIcon} alt="" />
                            <span>Добавить тесты</span>
                        </button>
                    </div>
                    <div className="criteria-delete-cell">
                        <button type="button" className="criteria-delete-btn" onClick={() => onDelete(index)}>
                            <img src={basketIcon} alt="Удалить" />
                        </button>
                    </div>
                </div>
            ))}

            <button type="button" className="criteria-add-btn" onClick={onAdd}>
                <img src={plusIcon} alt="" />
                <span>Добавить критерий</span>
            </button>
        </div>
    );
}