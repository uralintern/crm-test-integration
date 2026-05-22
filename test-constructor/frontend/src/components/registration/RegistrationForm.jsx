import PersonalData from "./PersonalData.jsx";
import {Link} from "react-router-dom";
import Button from "../Button.jsx";

const RegistrationForm = (props) => {
    const {
        formData,
        addUser,
        onFormChange,
        error,
    } = props;

    return (
        <form onSubmit={addUser}>
            <input
                    type="text"
                    id="name"
                    name="name"
                    placeholder="Имя"
                    onChange={onFormChange}
                    required
                    value={formData.name}
            />
            <input
                    type="text"
                    id="surname"
                    name="surname"
                    placeholder="Фамилия"
                    onChange={onFormChange}
                    required
                    value={formData.surname}
            />
            <input
                    type="email"
                    id="email"
                    name="email"
                    placeholder="Электронная почта"
                    onChange={onFormChange}
                    required
                    value={formData.email}
            />
            <input
                    type="password"
                    id="password"
                    name="password"
                    placeholder="Пароль"
                    onChange={onFormChange}
                    required
                    value={formData.password}
            />
            <input
                    type="password"
                    id="confirmPassword"
                    name="confirmPassword"
                    placeholder="Подтверждение пароля"
                    onChange={onFormChange}
                    required
                    value={formData.confirmPassword}
            />
            <PersonalData />
            <Button className="auth-button" type="submit">Зарегистрироваться</Button>
            {error && (
                <div className="error-message-form">
                    {error}
                </div>
            )}
            <p className="auth-question">Уже есть аккаунт? <Link to="/login">Войти</Link></p>
        </form>
    );
}

export default RegistrationForm