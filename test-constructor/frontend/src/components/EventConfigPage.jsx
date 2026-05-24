import React, { useEffect, useMemo, useState } from 'react';
import SelectTestsModal from './details/SelectTestsModal';
import CriteriaTable from './details/CriteriaTable';
import TimeBox from './details/TimeBox';
import ShareLinkBox from './details/ShareLinkBox';
import SpecializationSelect from './details/SpecializationSelect';
import { eventsAPI, testsAPI } from '../services/api.js';
import '../styles/event-config.css';
import back2 from '../assets/back2.svg';
import { useLocation, useNavigate } from 'react-router-dom';
import plusIcon from '../assets/plus.svg';
import korzinaIcon from '../assets/korzina.svg';
import massageIcon from '../assets/message.svg';

const DEFAULT_CRITERIA = [
    { threshold: 75, message: 'Тест пройден', extraTests: [] },
    { threshold: 50, message: 'Назначить дополнительный тест', extraTests: [] },
];

function createDefaultConfig(selectedSpec = '') {
    return {
        selectedSpec,
        criteria: DEFAULT_CRITERIA.map((item) => ({ ...item, extraTests: [...item.extraTests] })),
        failMessage: '',
        time: { hours: 1, minutes: 0, seconds: 0 },
        shareLink: '',
    };
}

function normalizeTestsPayload(data) {
    let testsArray = [];
    if (Array.isArray(data)) testsArray = data;
    else if (Array.isArray(data?.tests)) testsArray = data.tests;
    else if (Array.isArray(data?.data)) testsArray = data.data;

    return testsArray.map(test => ({
        ...test,
        id: Number(test.test_id || test.id),
        creator_id: test.creator_id ?? test.creatorId ?? test.CreatorID ?? test.creatorID,
        title: test.title || test.name || test.description || `Тест ${test.test_id || test.id}`,
    })).filter(test => Number.isFinite(test.id));
}

function normalizeSpecializationsPayload(data) {
    const items = Array.isArray(data) ? data : data?.specializations;
    return (Array.isArray(items) ? items : [])
        .map(spec => ({
            id: Number(spec.id),
            name: spec.name || spec.title || `Специализация ${spec.id}`,
        }))
        .filter(spec => Number.isFinite(spec.id));
}

function normalizeEventConfigsPayload(data) {
    const items = Array.isArray(data) ? data : data?.configs || data?.data || [];
    return (Array.isArray(items) ? items : [])
        .map(config => ({
            configId: Number(config.config_id || config.configId || config.id),
            eventId: Number(config.event_id || config.eventId),
            specializationId: Number(config.specialization_id || config.specializationId),
            testId: Number(config.test_id || config.testId),
            successText: config.success_text || config.successText || '',
            failText: config.fail_text || config.failText || '',
            timeLimit: Number(config.time_limit || config.timeLimit || 0),
            threshold: Number(config.threshold || 75),
            testLink: config.test_link || config.testLink || '',
            extraThreshold: Array.isArray(config.extra_threshold) ? config.extra_threshold : (config.extraThreshold || []),
        }))
        .filter(config => Number.isFinite(config.configId) && Number.isFinite(config.testId));
}

function timeToSeconds(time) {
    return Number(time.hours || 0) * 3600 + Number(time.minutes || 0) * 60 + Number(time.seconds || 0);
}

function secondsToTime(seconds) {
    const value = Math.max(0, Number(seconds || 0));
    return {
        hours: Math.floor(value / 3600),
        minutes: Math.floor((value % 3600) / 60),
        seconds: value % 60,
    };
}

function configFromBackend(config, defaultSpec) {
    const extraRows = (config.extraThreshold || []).map(item => ({
        threshold: Number(item.threshold || item.test_threshold || item.testThreshold || 0),
        message: item.message || '',
        extraTests: [Number(item.test_id || item.testId)].filter(Number.isFinite),
    }));

    return {
        selectedSpec: String(config.specializationId || defaultSpec || ''),
        criteria: [
            {
                threshold: Number(config.threshold || 75),
                message: config.successText || 'Тест пройден',
                extraTests: [],
            },
            ...extraRows,
        ],
        failMessage: config.failText || '',
        time: secondsToTime(config.timeLimit || 3600),
        shareLink: config.testLink ? `${window.location.origin}/test/${config.testLink}` : '',
    };
}

export default function EventConfigPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const eventId = useMemo(() => new URLSearchParams(location.search).get('eventId'), [location.search]);

    const [tests, setTests] = useState([]);
    const [selectedTestIds, setSelectedTestIds] = useState([]);
    const [selectedTestId, setSelectedTestId] = useState(null);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalTarget, setModalTarget] = useState(null);
    const [modalSelected, setModalSelected] = useState([]);
    const [specializations, setSpecializations] = useState([]);
    const [testConfigs, setTestConfigs] = useState({});
    const [saving, setSaving] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');

    const defaultSpec = specializations[0] ? String(specializations[0].id) : '';

    useEffect(() => {
        const fetchTests = async () => {
            try {
                const response = await testsAPI.getTests();
                const normalized = normalizeTestsPayload(response.data);
                setTests(normalized);
            } catch (err) {
                console.error('Ошибка загрузки тестов:', err);
                setTests([]);
            }
        };

        fetchTests();
    }, []);

    useEffect(() => {
        const fetchSpecializations = async () => {
            if (!eventId) {
                setSpecializations([]);
                return;
            }

            try {
                const response = await eventsAPI.getEventSpecializations(eventId);
                const normalized = normalizeSpecializationsPayload(response.data);
                setSpecializations(normalized);
                const firstSpec = normalized[0] ? String(normalized[0].id) : '';
                setTestConfigs(prev => Object.fromEntries(
                    Object.entries(prev).map(([testId, config]) => [
                        testId,
                        { ...config, selectedSpec: config.selectedSpec || firstSpec },
                    ])
                ));
            } catch (err) {
                console.error('Ошибка загрузки специализаций мероприятия:', err);
                setSpecializations([]);
            }
        };

        fetchSpecializations();
    }, [eventId]);

    useEffect(() => {
        const fetchEventConfigs = async () => {
            if (!eventId) {
                setSelectedTestIds([]);
                setSelectedTestId(null);
                setTestConfigs({});
                return;
            }

            try {
                const response = await eventsAPI.getEventConfigs(eventId);
                const configs = normalizeEventConfigsPayload(response.data);
                if (configs.length === 0) return;

                const ids = [...new Set(configs.map(config => Number(config.testId)).filter(Number.isFinite))];
                const nextConfigs = {};
                configs.forEach(config => {
                    nextConfigs[config.testId] = configFromBackend(config, defaultSpec);
                });

                setSelectedTestIds(ids);
                setSelectedTestId(current => current && ids.includes(Number(current)) ? current : ids[0] || null);
                setTestConfigs(nextConfigs);
            } catch (err) {
                console.error('Ошибка загрузки сохраненных настроек мероприятия:', err);
            }
        };

        fetchEventConfigs();
    }, [eventId, defaultSpec]);

    const getCurrentConfig = () => {
        if (!selectedTestId || !testConfigs[selectedTestId]) {
            return createDefaultConfig(defaultSpec);
        }
        return testConfigs[selectedTestId];
    };

    const updateConfig = (testId, updater) => {
        setTestConfigs(prev => {
            const current = prev[testId] || createDefaultConfig(defaultSpec);
            const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
            return { ...prev, [testId]: next };
        });
    };

    const updateCurrentConfig = (field, value) => {
        if (!selectedTestId) return;
        updateConfig(selectedTestId, { [field]: value });
    };

    const openModal = (target) => {
        setModalTarget(target);
        if (target === 'main') {
            setModalSelected([...selectedTestIds]);
        } else {
            const currentConfig = getCurrentConfig();
            setModalSelected([...(currentConfig.criteria[target]?.extraTests || [])]);
        }
        setModalOpen(true);
    };

    const handleApplyModal = () => {
        if (modalTarget === 'main') {
            const normalizedIds = modalSelected.map(Number).filter(Number.isFinite);
            setSelectedTestIds(normalizedIds);
            setTestConfigs(prev => {
                const next = {};
                normalizedIds.forEach(testId => {
                    next[testId] = prev[testId] || createDefaultConfig(defaultSpec);
                });
                return next;
            });
            if (!normalizedIds.includes(Number(selectedTestId))) {
                setSelectedTestId(normalizedIds[0] || null);
            }
        } else {
            const selectedExtraIds = modalSelected.map(Number).filter(Number.isFinite);
            updateCurrentConfig('criteria', getCurrentConfig().criteria.map((row, idx) =>
                idx === modalTarget ? { ...row, extraTests: selectedExtraIds } : row
            ));
        }
        setModalOpen(false);
    };

    const handleCriteriaChange = (idx, newRow) => {
        updateCurrentConfig('criteria', getCurrentConfig().criteria.map((row, i) => (i === idx ? newRow : row)));
    };

    const handleAddCriteria = () => {
        updateCurrentConfig('criteria', [...getCurrentConfig().criteria, { threshold: 0, message: '', extraTests: [] }]);
    };

    const handleRemoveSelected = (idToRemove) => {
        const testId = Number(idToRemove);
        const newSelected = selectedTestIds.filter(id => Number(id) !== testId);
        setSelectedTestIds(newSelected);
        if (Number(selectedTestId) === testId) {
            setSelectedTestId(newSelected[0] || null);
        }
        setTestConfigs(prev => {
            const next = { ...prev };
            delete next[testId];
            return next;
        });
    };

    const handleDeleteCriteria = (index) => {
        updateCurrentConfig('criteria', getCurrentConfig().criteria.filter((_, i) => i !== index));
    };

    const handleDeleteTest = (criteriaIndex, testIndex) => {
        updateCurrentConfig('criteria', getCurrentConfig().criteria.map((item, i) => {
            if (i !== criteriaIndex) return item;
            return { ...item, extraTests: item.extraTests.filter((_, idx) => idx !== testIndex) };
        }));
    };

    const handleToggleModalSelected = (id) => {
        const testId = Number(id);
        if (!Number.isFinite(testId)) return;

        setModalSelected(prev => {
            const normalized = prev.map(Number).filter(Number.isFinite);
            return normalized.includes(testId)
                ? normalized.filter(item => item !== testId)
                : [...normalized, testId];
        });
    };

    const buildPayload = (testId, config) => {
        const mainThreshold = Number(config.criteria[0]?.threshold || 75);
        const successText = config.criteria[0]?.message || 'Тест пройден';
        const extraThreshold = config.criteria.slice(1).flatMap(row =>
            (row.extraTests || []).map(extraTestId => ({
                threshold: Number(row.threshold || 0),
                message: row.message || '',
                test_id: Number(extraTestId),
                test_threshold: Number(row.threshold || mainThreshold),
            })).filter(item => item.threshold > 0 && item.test_id > 0)
        );

        return {
            event_id: Number(eventId),
            specialization_id: Number(config.selectedSpec),
            test_id: Number(testId),
            success_text: successText,
            fail_text: config.failMessage || 'Тест не пройден',
            time_limit: timeToSeconds(config.time),
            threshold: mainThreshold,
            extra_threshold: extraThreshold,
        };
    };

    const handleSave = async () => {
        setStatusMessage('');
        if (!eventId) {
            setStatusMessage('Не найдено мероприятие CRM.');
            return;
        }
        if (selectedTestIds.length === 0) {
            setStatusMessage('Выберите хотя бы один тест.');
            return;
        }

        const invalidConfig = selectedTestIds.some(testId => !(testConfigs[testId]?.selectedSpec || defaultSpec));
        if (invalidConfig) {
            setStatusMessage('Выберите специализацию для каждого теста.');
            return;
        }

        setSaving(true);
        try {
            const responses = [];
            for (const testId of selectedTestIds) {
                const config = testConfigs[testId] || createDefaultConfig(defaultSpec);
                const payload = buildPayload(testId, config);
                const response = await eventsAPI.saveEventConfig(payload);
                responses.push({ testId, data: response.data });
            }

            responses.forEach(({ testId, data }) => {
                if (data?.test_link) {
                    updateConfig(testId, { shareLink: `${window.location.origin}/test/${data.test_link}` });
                }
            });
            setStatusMessage('Настройки тестирования сохранены.');
        } catch (err) {
            console.error('Ошибка сохранения настроек мероприятия:', err);
            setStatusMessage('Не удалось сохранить настройки тестирования.');
        } finally {
            setSaving(false);
        }
    };

    const currentConfig = getCurrentConfig();

    return (
        <div className="event-config-page">
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
                    {selectedTestIds.map(id => {
                        const test = tests.find(t => Number(t.id) === Number(id));
                        const isActive = Number(selectedTestId) === Number(id);
                        return test ? (
                            <li
                                key={id}
                                className={`event-config-test-item ${isActive ? 'active-red' : ''}`}
                                onClick={() => setSelectedTestId(id)}
                            >
                                <span className="test-title">{test.title}</span>
                                <button
                                    className="test-delete-btn"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        handleRemoveSelected(id);
                                    }}
                                    aria-label={`Удалить тест ${test.title}`}
                                    type="button"
                                >
                                    <img src={korzinaIcon} alt="" className="test-delete-icon" />
                                </button>
                            </li>
                        ) : null;
                    })}
                </ul>
            </div>

            <div className="event-config-main">
                {selectedTestId ? (
                    <>
                        <SpecializationSelect
                            specializations={specializations}
                            selected={currentConfig.selectedSpec || defaultSpec}
                            onChange={(value) => updateCurrentConfig('selectedSpec', value)}
                        />
                        <div className="criteria-table-title">Критерий прохождения теста</div>
                        <CriteriaTable
                            criteria={currentConfig.criteria}
                            onChange={handleCriteriaChange}
                            onAdd={handleAddCriteria}
                            onAddTest={idx => openModal(idx)}
                            tests={tests}
                            selectedTests={currentConfig.criteria.flatMap(row => row.extraTests || [])}
                            onDelete={handleDeleteCriteria}
                            onDeleteTest={handleDeleteTest}
                        />
                        <div className="fail-message-label">
                            <img src={massageIcon} alt="" className="fail-message-icon" />
                            Сообщение при провальном прохождении теста
                        </div>
                        <div className="fail-message-input-wrap">
                            <input
                                type="text"
                                placeholder="Введите текст сообщения при провальном прохождении..."
                                value={currentConfig.failMessage}
                                onChange={event => updateCurrentConfig('failMessage', event.target.value)}
                            />
                        </div>
                        <TimeBox
                            time={currentConfig.time}
                            setTime={(newTime) => updateCurrentConfig('time', newTime)}
                        />
                        <ShareLinkBox link={currentConfig.shareLink} />
                    </>
                ) : (
                    <div className="event-config-empty-state">
                        Выберите тест для настройки или добавьте новый тест.
                    </div>
                )}
                {statusMessage && <div className="event-config-status">{statusMessage}</div>}
                <button className="save-btn" onClick={handleSave} disabled={saving || selectedTestIds.length === 0}>
                    {saving ? 'Сохранение...' : 'Сохранить'}
                </button>
            </div>

            <SelectTestsModal
                open={modalOpen}
                tests={tests}
                selected={modalSelected}
                onSelect={handleToggleModalSelected}
                onClose={() => setModalOpen(false)}
                onApply={handleApplyModal}
            />
        </div>
    );
}
