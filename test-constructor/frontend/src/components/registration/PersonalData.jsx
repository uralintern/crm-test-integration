const PersonalData = ({ checked, onChange }) => {
    return (
        <div className="process-personal-data">
            <div className="setting-row">
            <input
                type="checkbox"
                checked={checked}
                onChange={onChange}
            />
            </div>
            <p>Я согласен(а) на обработку персональных данных</p>
        </div>
    );
};

export default PersonalData;
