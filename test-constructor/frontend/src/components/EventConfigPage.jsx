import React, { useState, useEffect } from 'react';
import SelectTestsModal from './details/SelectTestsModal';
import CriteriaTable from './details/CriteriaTable';
import TimeBox from './details/TimeBox';
import ShareLinkBox from './details/ShareLinkBox';
import SpecializationSelect from './details/SpecializationSelect';
import { testsAPI } from '../services/api.js';
import '../styles/event-config.css';
import back2 from '../assets/back2.svg';
import { useNavigate } from 'react-router-dom';
import plusIcon from '../assets/plus.svg';
import korzinaIcon from '../assets/korzina.svg';
import massageIcon from '../assets/message.svg';
// Моки для специализаций (замени на загрузку из API, если нужно)
const allSpecsMock = [
    { id: 1, name: 'Frontend' },
    { id: 2, name: 'Backend' },
];

export default function EventConfigPage() {
    // Состояния
    const [tests, setTests] = useState([]);
    const [selectedTests, setSelectedTests] = useState([]);
    const [criteria, setCriteria] = useState([
        { threshold: 50, message: 'Успешно пройден', extraTests: [] },
        { threshold: 30, message: 'Пройдите дополнительный тест', extraTests: [] },
        { threshold: 25, message: 'Пройдите дополнительный тест', extraTests: [] },
    ]);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalTarget, setModalTarget] = useState(null); // null | 'main' | index
    const [modalSelected, setModalSelected] = useState([]);
    const [specializations, setSpecializations] = useState(allSpecsMock);
    const [selectedSpec, setSelectedSpec] = useState('');
    const [failMessage, setFailMessage] = useState('');
    const [time, setTime] = useState({ hours: 0, minutes: 0, seconds: 0 });
    const [shareLink, setShareLink] = useState('https://newforms-novaya-forma-konstruktion');

    // Загрузка тестов из API при монтировании, только тесты текущего организатора
    useEffect(() => {
        const fetchTests = async () => {
            try {
                const response = await testsAPI.getTests();
                const data = response.data;

                // Поддерживаем несколько форматов ответа (как в других страницах)
                let testsArray = [];
                if (Array.isArray(data)) {
                    testsArray = data;
                } else if (data.tests && Array.isArray(data.tests)) {
                    testsArray = data.tests;
                } else if (data.data && Array.isArray(data.data)) {
                    testsArray = data.data;
                } else {
                    console.error('Неизвестная структура ответа testsAPI.getTests():', data);
                }

                const normalized = testsArray.map(test => ({
                    ...test,
                    id: test.test_id || test.id,
                    creator_id: test.creator_id ?? test.creatorId ?? test.CreatorID ?? test.creatorID,
                    title: test.title || test.name || test.description || `Тест ${test.test_id || test.id}`,
                }));

                // Получаем id текущего пользователя из localStorage (устанавливается при логине)
                const userStr = localStorage.getItem('user');
                const currentUserId = userStr ? (JSON.parse(userStr).id) : null;

                // Фильтруем по creator_id, если есть currentUserId
                const filtered = currentUserId != null
                    ? normalized.filter(t => Number(t.creator_id) === Number(currentUserId))
                    : normalized;

                setTests(filtered);
            } catch (err) {
                console.error('Ошибка загрузки тестов:', err);
                setTests([]);
            }
        };

        fetchTests();
    }, []);

    // Модалка для выбора тестов
    const openModal = (target) => {
        setModalTarget(target);
        if (target === 'main') setModalSelected(selectedTests);
        else setModalSelected(criteria[target].extraTests || []);
        setModalOpen(true);
    };
    const handleApplyModal = () => {
        if (modalTarget === 'main') setSelectedTests(modalSelected);
        else {
            setCriteria(criteria.map((row, idx) =>
                idx === modalTarget ? { ...row, extraTests: modalSelected } : row
            ));
        }
        setModalOpen(false);
    };
    const handleCriteriaChange = (idx, newRow) => {
        setCriteria(criteria.map((row, i) => (i === idx ? newRow : row)));
    };
    const handleAddCriteria = () => {
        setCriteria([...criteria, { threshold: 0, message: '', extraTests: [] }]);
    };
    const navigate = useNavigate();

    const handleRemoveSelected = (idToRemove) => {
        setSelectedTests(prev => prev.filter(id => id !== idToRemove));
    };
    const handleDeleteCriteria = (index) => {
        setCriteria(prev =>
            prev.filter((_, i) => i !== index)
        );
    };

    const handleDeleteTest = (criteriaIndex, testIndex) => {
        setCriteria(prev =>
            prev.map((item, i) => {
                if (i !== criteriaIndex) return item;

                return {
                    ...item,
                    extraTests: item.extraTests.filter(
                        (_, idx) => idx !== testIndex
                    )
                };
            })
        );
    };
    return (
        <div className="event-config-page">
            {/* Левая панель */}
            <div className="event-config-sidebar">
                <div className="event-config-header">
                    <button
                        type="button"
                        className="event-config-back-btn"
                        onClick={() => navigate('/events')}
                        aria-label="Вернуться к мероприятиям"
                    >
                        <img src={back2} alt="" className="event-config-back-icon" />
                    </button>
                    <p>Настройка тестов мероприятия</p>
                </div>

                <button className="add-tests-btn" onClick={() => openModal('main')}>
                    <span>Добавить тесты</span>
                    <img src={plusIcon} alt="Добавить" className="add-tests-plus" />
                </button>

                <ul className="event-config-tests-list">
                    {selectedTests.map(id => {
                        const test = tests.find(t => t.id === id);
                        return test ? (
                            <li key={id} className="event-config-test-item">
                                <span className="test-title">{test.title}</span>
                                <button
                                    className="test-delete-btn"
                                    onClick={() => handleRemoveSelected(id)}
                                    aria-label={`Удалить тест ${test.title}`}
                                    type="button"
                                >
                                    <img src={korzinaIcon} alt="Удалить" />
                                </button>
                            </li>
                        ) : null;
                    })}
                </ul>
            </div>

            {/* Центральная панель */}
            <div className="event-config-main">
                <SpecializationSelect
                    specializations={specializations}
                    selected={selectedSpec}
                    onChange={setSelectedSpec}
                />
                <div className="criteria-table-title">Критерий прохождения теста</div>
                <CriteriaTable
                    criteria={criteria}
                    onChange={handleCriteriaChange}
                    onAdd={handleAddCriteria}
                    onAddTest={idx => openModal(idx)}

                    onDelete={handleDeleteCriteria}
                    onDeleteTest={handleDeleteTest}
                    testsList={tests}
                />
                <div className="fail-message-block">
                    <div className="fail-message-header">
                        <img src={massageIcon} alt="" style={{ width: '32px', height: '32px' }} />
                        <p className="fail-message-title">Сообщение при провальном прохождении</p>
                    </div>
                    <input
                        type="text"
                        placeholder="Введите текст сообщения при провальном прохождении..."
                        value={failMessage}
                        onChange={e => setFailMessage(e.target.value)}
                    />
                </div>
                <TimeBox time={time} setTime={setTime} />
                <ShareLinkBox link={shareLink} />
                <button className="save-btn">Сохранить</button>
            </div>
            {/* Модальное окно */}
            <SelectTestsModal
                open={modalOpen}
                tests={tests}
                selected={modalSelected}
                onSelect={id =>
                    setModalSelected(
                        modalSelected.includes(id)
                            ? modalSelected.filter(i => i !== id)
                            : [...modalSelected, id]
                    )
                }
                onApply={handleApplyModal}
                onClose={() => setModalOpen(false)}
            />
        </div>
    );
}
