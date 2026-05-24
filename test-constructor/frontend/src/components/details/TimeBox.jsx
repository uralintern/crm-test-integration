import React, { useState } from 'react';
import timeIcon from "../../assets/time.svg";

export default function TimeBox({ time, setTime }) {
    const [touched, setTouched] = useState({
        hours: false,
        minutes: false,
        seconds: false
    });

    const handleFocus = (field) => {
        setTouched({ ...touched, [field]: true });
    };

    const handleBlur = (field, value) => {
        if (value === 0 || value === '' || isNaN(value)) {
            setTouched({ ...touched, [field]: false });
        }
    };

    return (
        <div className="time-box">
            <div className="time-box1">
                <img src={timeIcon} alt="время" />
                <p>Ограничение по времени</p>
            </div>
            <div className="time-box-inner1">
                <div className="time-input-box">
                    <input
                        type="number"
                        min="0"
                        placeholder="0 часов"
                        value={time.hours || ''}
                        onFocus={() => handleFocus('hours')}
                        onBlur={(e) => handleBlur('hours', time.hours)}
                        onChange={e => {
                            const value = e.target.value === '' ? 0 : parseInt(e.target.value);
                            setTime({ ...time, hours: value || 0 });
                        }}
                        style={{ textAlign: 'center' }}
                    />
                    <input
                        type="number"
                        min="0"
                        max="59"
                        placeholder="0 минут"
                        value={time.minutes || ''}
                        onFocus={() => handleFocus('minutes')}
                        onBlur={(e) => handleBlur('minutes', time.minutes)}
                        onChange={e => {
                            const value = e.target.value === '' ? 0 : parseInt(e.target.value);
                            setTime({ ...time, minutes: Math.min(59, value || 0) });
                        }}
                        style={{ textAlign: 'center' }}
                    />
                    <input
                        type="number"
                        min="0"
                        max="59"
                        placeholder="0 секунд"
                        value={time.seconds || ''}
                        onFocus={() => handleFocus('seconds')}
                        onBlur={(e) => handleBlur('seconds', time.seconds)}
                        onChange={e => {
                            const value = e.target.value === '' ? 0 : parseInt(e.target.value);
                            setTime({ ...time, seconds: Math.min(59, value || 0) });
                        }}
                        style={{ textAlign: 'center' }}
                    />
                </div>
            </div>
        </div>
    );
}