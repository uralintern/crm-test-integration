import timeIcon from "../../assets/time.svg";

export default function TimeBox({ time, setTime, isTimeEnabled, setIsTimeEnabled }) {
    const handleToggleTimeLimit = () => {
        const nextValue = !isTimeEnabled;
        setIsTimeEnabled(nextValue);
        if (!nextValue) {
            setTime({ hours: 0, minutes: 0, seconds: 0 });
        } else if (!time.hours && !time.minutes && !time.seconds) {
            setTime({ hours: 1, minutes: 0, seconds: 0 });
        }
    };

    const updatePart = (field, rawValue, maxValue) => {
        const parsed = rawValue === "" ? 0 : Number.parseInt(rawValue, 10);
        const safeValue = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
        setTime({
            ...time,
            [field]: typeof maxValue === "number" ? Math.min(maxValue, safeValue) : safeValue,
        });
    };

    return (
        <div className="time-box">
            <div className="time-box1">
                <img src={timeIcon} alt="" />
                <p>Ограничение по времени</p>
                <label className="time-checkbox">
                    <input type="checkbox" checked={isTimeEnabled} onChange={handleToggleTimeLimit} />
                    <span className="checkmark" />
                </label>
            </div>
            <div className="time-box-inner1">
                {isTimeEnabled ? (
                    <div className="time-input-box">
                        <input
                            type="number"
                            min="0"
                            placeholder="0 часов"
                            value={time.hours || ""}
                            onChange={(event) => updatePart("hours", event.target.value)}
                        />
                        <input
                            type="number"
                            min="0"
                            max="59"
                            placeholder="0 минут"
                            value={time.minutes || ""}
                            onChange={(event) => updatePart("minutes", event.target.value, 59)}
                        />
                        <input
                            type="number"
                            min="0"
                            max="59"
                            placeholder="0 секунд"
                            value={time.seconds || ""}
                            onChange={(event) => updatePart("seconds", event.target.value, 59)}
                        />
                    </div>
                ) : (
                    <div className="time-box-unlimited"><p>Время не ограничено</p></div>
                )}
            </div>
        </div>
    );
}