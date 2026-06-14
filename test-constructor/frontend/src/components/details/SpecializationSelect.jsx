import { useEffect, useRef, useState } from 'react';

export default function SpecializationSelect({ specializations, selected, onChange, disabled = false }) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);
    const selectedSpec = specializations.find(item => String(item.id) === String(selected));
    const selectedName = selectedSpec ? selectedSpec.name : 'Выберите специализацию';

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (specId) => {
        onChange(String(specId));
        setIsOpen(false);
    };

    return (
        <div className={`specialization-select ${isOpen ? 'open' : ''}`} ref={containerRef}>
            <button
                type="button"
                className="specialization-select-button"
                onClick={() => !disabled && setIsOpen(value => !value)}
                aria-expanded={isOpen}
                aria-haspopup="listbox"
                disabled={disabled}
            >
                <span className="specialization-select-value">{selectedName}</span>
                <div className="select-arrow" aria-hidden="true" />
            </button>
            <div
                className="specialization-select-list"
                role="listbox"
                style={{ maxHeight: isOpen ? '320px' : '0', opacity: isOpen ? 1 : 0, overflow: 'hidden' }}
            >
                <div className="specialization-select-options">
                    {specializations.length === 0 ? (
                        <div className="specialization-option disabled">Нет специализаций</div>
                    ) : specializations.map(spec => (
                        <button
                            key={spec.id}
                            type="button"
                            className={`specialization-option ${String(spec.id) === String(selected) ? 'selected' : ''}`}
                            onClick={() => handleSelect(spec.id)}
                            role="option"
                            aria-selected={String(spec.id) === String(selected)}
                        >
                            {spec.name}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}