import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/logout-modal.css";

const AVATAR_COLORS = [
    "#f44336", "#e91e63", "#9c27b0", "#673ab7", "#3f51b5", "#2196f3",
    "#03a9f4", "#00bcd4", "#009688", "#4caf50", "#8bc34a", "#cddc39",
    "#ffeb3b", "#ffc107", "#ff9800", "#ff5722", "#795548", "#607d8b",
];

function getStoredUser() {
    try {
        const storedUser = localStorage.getItem("user");
        return storedUser ? JSON.parse(storedUser) : null;
    } catch (e) {
        console.error("Ошибка парсинга user из localStorage", e);
        return null;
    }
}

function getInitials(user) {
    const surname = String(user?.surname || "").trim();
    const name = String(user?.name || "").trim();
    const email = String(user?.email || "").trim();
    const fromName = `${surname[0] || ""}${name[0] || ""}`.toUpperCase();
    return fromName || email.slice(0, 2).toUpperCase() || "--";
}

function getAvatarColor(user) {
    const source = String(user?.id ?? user?.email ?? user?.name ?? "default");
    let hash = 0;
    for (let i = 0; i < source.length; i += 1) hash = (hash * 31 + source.charCodeAt(i)) | 0;
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

const LogoutButton = () => {
    const [showModal, setShowModal] = useState(false);
    const [modalPosition, setModalPosition] = useState({ top: 0, right: 0 });
    const buttonRef = useRef(null);
    const navigate = useNavigate();

    const currentUser = getStoredUser();
    const email = currentUser?.email || "";
    const fullName = [currentUser?.surname, currentUser?.name]
        .filter(Boolean)
        .join(" ") || currentUser?.full_name || currentUser?.username || "Пользователь";
    const initials = getInitials(currentUser);
    const avatarColor = getAvatarColor(currentUser);

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
                style={{ backgroundColor: avatarColor }}
            >
                {initials}
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
                                <p className="user-name">{fullName}</p>
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