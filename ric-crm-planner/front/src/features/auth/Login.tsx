import { useContext, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "../../components/Toast/ToastProvider";
import { AuthContext } from "../../context/AuthContext";
import "../../styles/auth.scss";
import AppButton from "../../components/UI/Button";
import AppInput, { AppPassword } from "../../components/UI/Input";

export default function Login() {
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await login(email.trim().toLowerCase(), password);
    if (!ok) {
      showToast("error", "Неверный email или пароль");
      return;
    }
    navigate("/events");
  };

  return (
    <div className="auth-container">
      <h2 className="h1">Вход</h2>

      <form onSubmit={handleSubmit} className="auth-form">
        <label className="text-small">Email</label>
        <AppInput
          type="email"
          placeholder="email@mail.ru"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="text-regular"
          required
        />

        <label className="text-small">Пароль</label>
        <AppPassword
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="text-regular"
          required
        />

        <AppButton type="submit" className="auth-submit text-regular">
          Войти
        </AppButton>
      </form>

      <p className="switch-link text-small">
        Еще нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
      </p>
    </div>
  );
}
