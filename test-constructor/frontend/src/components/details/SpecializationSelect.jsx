import React, { useState, useRef, useEffect } from 'react';

export default function SpecializationSelect({ specializations, selected, onChange }) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);
    const listRef = useRef(null);

    const selectedSpec = specializations.find(s => String(s.id) === String(selected));
    const selectedName = selectedSpec ? selectedSpec.name : 'Выберите специализацию';

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                closeInstant();
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);


    const openAnimated = () => {
        if (!listRef.current) {
            setIsOpen(true);
            return;
        }

        setIsOpen(true);
        listRef.current.style.transition = 'max-height 0.35s ease, opacity 0.25s ease';
        requestAnimationFrame(() => {
            listRef.current.style.maxHeight = `${listRef.current.scrollHeight}px`;
            listRef.current.style.opacity = '1';
        });
    };

    const closeInstant = () => {
        if (!listRef.current) {
            setIsOpen(false);
            return;
        }

        listRef.current.style.transition = 'none';
        listRef.current.style.maxHeight = '0px';
        listRef.current.style.opacity = '0';

        setIsOpen(false);


        setTimeout(() => {
            if (listRef.current) {
                listRef.current.style.transition = '';
            }
        }, 0);
    };

    const toggleOpen = () => {
        if (isOpen) {
            closeInstant();
        } else {
            openAnimated();
        }
    };

    const handleSelect = (specId) => {
        onChange(String(specId));
        closeInstant();
    };

    useEffect(() => {
        const handleResize = () => {
            if (isOpen && listRef.current) {
                listRef.current.style.maxHeight = `${listRef.current.scrollHeight}px`;
            }
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [isOpen]);

    useEffect(() => {
        if (listRef.current) {
            listRef.current.style.maxHeight = '0px';
            listRef.current.style.opacity = '0';
            listRef.current.style.overflow = 'hidden';
        }
    }, []);

    return (
        <div
            className={`specialization-select ${isOpen ? 'open' : ''}`}
            ref={containerRef}
        >
            <button
                type="button"
                className="specialization-select-button"
                onClick={toggleOpen}
                aria-expanded={isOpen}
                aria-haspopup="listbox"
            >
                <span className="specialization-select-value">{selectedName}</span>
                <div className="select-arrow" aria-hidden="true" />
            </button>

            <div
                className="specialization-select-list"
                ref={listRef}
                role="listbox"
            >
                <div className="specialization-select-options">
                    {specializations.length === 0 ? (
                        <div className="specialization-option disabled">Нет специализаций</div>
                    ) : (
                        specializations.map(spec => (
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
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
