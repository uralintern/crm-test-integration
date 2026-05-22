export default function PassingCriteria({ criteria, updateCriteria, totalPoints }) {
    const handlePercentageChange = (e) => {
        const value = Math.min(100, Math.max(0, parseInt(e.target.value) || 0));
        updateCriteria({
            ...criteria,
            percentage: value
        });
    };

    const handlePointsChange = (e) => {
        const value = Math.max(0, parseFloat(e.target.value) || 0);
        updateCriteria({
            ...criteria,
            points: value
        });
    };

    const handleCriteriaSelect = (type) => {
        updateCriteria({
            ...criteria,
            type: type
        });
    };

    return (
        <div className="passing-criteria">
            <div className="section-header">
                <h3>Критерий прохождения теста</h3>
            </div>

            <div className="criteria-grid">
                <div className="criteria-column left-column">
                    <div className="criteria-option">
                        <div className="option-header">
                            <label className="checkbox-label">
                                <div className="setting-row">
                                        <input
                                            type="checkbox"
                                            name="passingCriteria"
                                            checked={criteria.type === "percentage"}
                                            onChange={() => handleCriteriaSelect("percentage")}
                                        />
                                </div>
                                <span className="option-title">По проценту</span>
                            </label>
                        </div>

                        <div className="option-details">
                            <div className="input-group">
                                <span className="input-label">Верно ответить на</span>
                                <div className="percentage-input">
                                    <input
                                        type="number"
                                        className="score-input"
                                        min="0"
                                        max="100"
                                        value={criteria.percentage || 75}
                                        onChange={handlePercentageChange}
                                        />

                                    <span className="percent-sign">%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="criteria-column right-column">
                    <div className="criteria-option">
                        <div className="option-header">
                            <label className="checkbox-label">
                                <div className="setting-row">
                                    <input
                                        type="checkbox"
                                        name="passingCriteria"
                                        checked={criteria.type === "points"}
                                        onChange={() => handleCriteriaSelect("points")}
                                    />
                                </div>
                                <span className="option-title">По баллам</span>
                            </label>
                        </div>

                        <div className="option-details">
                            <div className="input-group">
                                <span className="input-label">Не менее</span>
                                <div className="percentage-input">
                                    <input
                                        type="number"
                                        min="0"
                                        className="score-input"
                                        step="0.1"
                                        value={criteria.points || 0}
                                        onChange={handlePointsChange}
                                    />
                                    <span className="percent-sign">б</span>
                                </div>
                                <span className="">из </span>
                                <span className="hint">{totalPoints || 0} б</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}