import {useState} from "react";
import {useNavigate} from "react-router-dom";
import {authAPI} from "../services/api.js";
import loginIcon from "../assets/login.svg";
import LoginForm from "../components/login/LoginForm.jsx";

function Login() {
    const [formData, setFormData] = useState({
        email: '',
        password: '',
    });
    const [error, setError] = useState('');
    const nav = useNavigate();

    const onFormChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    const loginUser = async (e) => {
        e.preventDefault();
        setError('');
        try {
            const response = await authAPI.login(formData.email, formData.password);
            const { token, user_id, email, name, surname, role } = response.data;
            const userData = { id: user_id, email: email, name: name, surname: surname, role: role };

            localStorage.setItem('token', token);
            localStorage.setItem('user', JSON.stringify(userData));

            if (role === "manager") {
                nav('/tests');
            } else if (role === "intern") {
                nav('/myTestStudent');
            }else if (role === "admin") {
                nav('/')
            }


        } catch (error) {
            setError(error.response.data);
            return;
        }
    };

    return (
        <>
            <main className="auth-block">
                <div className="auth-form login-form">
                    <h1>Вход</h1>
                    <LoginForm
                        formData={formData}
                        loginUser={loginUser}
                        onFormChange={onFormChange}
                        error={error}
                    />
                </div>
                <div className="auth-icon">
                    <img src={loginIcon}/>
                </div>
            </main>
        </>
    )
}

export default Login;