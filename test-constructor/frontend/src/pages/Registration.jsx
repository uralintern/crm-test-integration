import registerIcon from "../assets/registration.svg";
import RegistrationForm from "../components/registration/RegistrationForm.jsx";
import {useState} from "react";
import {authAPI} from "../services/api.js";
import {useNavigate} from "react-router-dom";

function Registration() {
    const [formData, setFormData] = useState({
        name: '',
        surname: '',
        email: '',
        password: '',
        confirmPassword: '',
    })
    const [error, setError] = useState('');
    const nav = useNavigate();

    const onFormChange = (e) => {
        setFormData({
                ...formData,
                [e.target.name]: e.target.value,
            });
    };

    const addUser = async (e) => {
        e.preventDefault();
        setError('');

        if (formData.password !== formData.confirmPassword) {
            setError('Пароли не совпадают');
            return;
        }

        if (formData.password.length < 8) {
            setError('Пароль должен быть не менее 8 символов');
            return;
        }

        try {
            const response = await authAPI.register(formData.name, formData.surname, formData.email, formData.password);
            const { token, user_id, email, name, surname, role } = response.data;
            const userData = { id: user_id, email: email, name: name, surname: surname, role: role };

            localStorage.setItem('token', token);
            localStorage.setItem('user', JSON.stringify(userData));
            nav('/')
        } catch (error) {
            setError(error.response.data);
        }
    }

    return (
        <>
            <main className="auth-block">
                <div className="auth-form">
                    <h1>Регистрация</h1>
                    <RegistrationForm
                        formData={formData}
                        addUser={addUser}
                        onFormChange={onFormChange}
                        error={error}
                    />
                </div>
                <div className="auth-icon">
                    <img src={registerIcon}/>
                </div>
            </main>
        </>
    )
}

export default Registration;