import {Link} from "react-router-dom";
import Button from "../Button.jsx";

const LoginForm = (props) => {
    const {
        formData,
        loginUser,
        onFormChange,
        error,
    } = props;

    return (
        <form onSubmit={loginUser}>
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
            <Button className="auth-button" type="submit">Войти</Button>
            {error && (
                <div className="error-message-form">
                    {error}
                </div>
            )}
            <p className="auth-question">Ещё нет аккаунта? <Link to="/registration">Зарегистрируйтесь</Link></p>
        </form>
    );
}

export default LoginForm