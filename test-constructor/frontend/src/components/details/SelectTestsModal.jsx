import React, { useState } from 'react';
import './modal.css';

export default function SelectTestsModal({ open, tests, selected, onSelect, onApply, onClose }) {
    const [searchTerm, setSearchTerm] = useState('');

    if (!open) return null;

    const filteredTests = tests.filter(test =>
        test.title?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="select-tests-modal-overlay" onClick={onClose}>
            <div className="select-tests-modal" onClick={(e) => e.stopPropagation()}>
                {/* Заголовок */}
                <div className="select-tests-modal-header">
                    <h3>Выберите тесты</h3>
                    <button className="select-tests-modal-close" onClick={onClose}>✕</button>
                </div>

                {/* Поиск */}
                <div className="select-tests-modal-search">
                    <input
                        type="text"
                        placeholder="Введите название теста"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>

                {/* Сетка тестов */}
                <div className="select-tests-modal-list-wrapper">
                    {filteredTests.length === 0 ? (
                        <div className="select-tests-empty">
                            Тесты не найдены
                        </div>
                    ) : (
                        <div className="select-tests-grid">
                            {filteredTests.map((test) => (
                                <div
                                    key={test.id}
                                    className="select-tests-card"
                                    onClick={() => onSelect(test.id)}
                                >
                                    <input
                                        type="checkbox"
                                        className="select-tests-checkbox"
                                        checked={selected.includes(test.id)}
                                        onChange={() => onSelect(test.id)}
                                        onClick={(e) => e.stopPropagation()}
                                    />
                                    <span className="select-tests-card-title">
                                        {test.title && test.title.length > 15
                                            ? `${test.title.substring(0, 15)}...`
                                            : test.title || "Без названия"
                                        }
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Кнопка сохранения */}
                <div className="select-tests-modal-footer">
                    <button onClick={onApply}>Сохранить
                    </button>
                </div>
            </div>
        </div>
    );
}