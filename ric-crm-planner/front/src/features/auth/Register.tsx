import { useContext, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "../../components/Toast/ToastProvider";
import { AuthContext } from "../../context/AuthContext";
import "../../styles/auth.scss";
import AppButton from "../../components/UI/Button";
import AppInput, { AppPassword } from "../../components/UI/Input";

export default function Register() {
  const { register } = useContext(AuthContext);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [form, setForm] = useState({
    email: "",
    vk: "",
    name: "",
    surname: "",
    password: "",
    confirm: "",
    role: "student",
  });

  const update = (key: string, value: string) => setForm({ ...form, [key]: value });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) {
      showToast("error", "Пароли не совпадают");
      return;
    }

    const result = await register({
      email: form.email.trim().toLowerCase(),
      vk: form.vk.trim(),
      name: form.name.trim(),
      surname: form.surname.trim(),
      role: form.role,
      password: form.password,
      confirm: form.confirm,
    });

    if (!result.ok) {
      showToast("error", result.error || "Не удалось зарегистрироваться");
      return;
    }

    navigate("/events");
  };

  return (
    <div className="auth-container">
      <h2 className="h1">Регистрация</h2>

      <form onSubmit={handleSubmit} className="auth-form">
        <label className="text-small">Email</label>
        <AppInput type="email" required value={form.email} onChange={(e) => update("email", e.target.value)} className="text-regular" />

        <label className="text-small">Аккаунт VK</label>
        <AppInput
          required
          value={form.vk}
          onChange={(e) => update("vk", e.target.value)}
          placeholder="https://vk.com/id123456 или @username"
          className="text-regular"
        />

        <label className="text-small">Имя</label>
        <AppInput required value={form.name} onChange={(e) => update("name", e.target.value)} className="text-regular" />

        <label className="text-small">Фамилия</label>
        <AppInput required value={form.surname} onChange={(e) => update("surname", e.target.value)} className="text-regular" />

        <label className="text-small">Пароль</label>
        <AppPassword required value={form.password} onChange={(e) => update("password", e.target.value)} className="text-regular" />

        <label className="text-small">Подтвердите пароль</label>
        <AppPassword required value={form.confirm} onChange={(e) => update("confirm", e.target.value)} className="text-regular" />

        <AppButton type="submit" className="auth-submit text-regular">
          Зарегистрироваться
        </AppButton>
      </form>

      <p className="switch-link text-small">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </p>
    </div>
  );
}
