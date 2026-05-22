import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/logout-modal.css";

const LogoutButton = () => {
    const [showModal, setShowModal] = useState(false);
    const [modalPosition, setModalPosition] = useState({ top: 0, right: 0 });
    const buttonRef = useRef(null);
    const navigate = useNavigate();

    let email = "";
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
        try {
            const parsedUser = JSON.parse(storedUser);
            email = parsedUser?.email || "";
        } catch (e) {
            console.error("Ошибка парсинга user из localStorage", e);
        }
    }

    const updateModalPosition = () => {
        if (buttonRef.current) {
            const buttonRect = buttonRef.current.getBoundingClientRect();
            setModalPosition({
                top: buttonRect.bottom + window.scrollY + 50,
                right: window.innerWidth - buttonRect.right - window.scrollX + 20
            });
        }
    };

    useEffect(() => {
        if (showModal) {
            updateModalPosition();
            window.addEventListener('resize', updateModalPosition);
            window.addEventListener('scroll', updateModalPosition);

            return () => {
                window.removeEventListener('resize', updateModalPosition);
                window.removeEventListener('scroll', updateModalPosition);
            };
        }
    }, [showModal]);

    const handleLogout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        navigate('/login');
    };

    const handleButtonClick = () => {
        updateModalPosition();
        setShowModal(true);
    };

    const handleOverlayClick = () => {
        setShowModal(false);
    };

    return (
        <>
            <button
                ref={buttonRef}
                onClick={handleButtonClick}
                className="logout-btn"
            >
            </button>

            {showModal && (
                <>
                    <div
                        className="logout-modal-overlay"
                        onClick={handleOverlayClick}
                    />

                    <div
                        className="logout-modal-content"
                        style={{
                            top: `${modalPosition.top}px`,
                            right: `${modalPosition.right}px`
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="logout-modal-body">
                            <div className="user-info">
                                <p className="user-name">Имя пользователя</p>
                            </div>

                            <div className="email-info">
                                <p className="user-email">
                                    {email || "—"}
                                </p>
                            </div>

                            <div className="logout-actions">
                                <button
                                    className="logout-confirm-btn"
                                    onClick={handleLogout}
                                >
                                    Выйти из аккаунта
                                </button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </>
    );
};

export default LogoutButton;
