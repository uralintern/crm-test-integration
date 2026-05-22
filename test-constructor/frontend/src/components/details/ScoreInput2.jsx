export default function ScoreInput({ value, onChange }) {
    return (
        <div className="score-section">
            <span className="score-container">
                <input
                    type="number"
                    className="score-input"
                    value={value || 0}
                    onChange={e => onChange(parseInt(e.target.value) || 0)}
                />{" "}
                б
            </span>
        </div>
    );
}
