import { useContext, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Badge, Dropdown } from "antd";
import type { MenuProps } from "antd";
import {
  BarsOutlined,
  BellOutlined,
  ContainerOutlined,
  ExportOutlined,
  LoginOutlined,
  LogoutOutlined,
  MenuOutlined,
  SaveOutlined,
  TeamOutlined,
  UserOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import "../../styles/header.scss";
import { AuthContext } from "../../context/AuthContext";
import { useNotifications } from "../../context/NotificationsContext";
import client from "../../api/client";
import { createTestingSSOLink } from "../../api/testing";
import { isGlobalOrganizer } from "../../utils/access";
import { useToast } from "../Toast/ToastProvider";
import Modal from "../Modal/Modal";
import AppButton from "../UI/Button";
import logoIcon from "../../assets/LogoIcon.png";

const HEADER_TEXT = {
  automation: "Архив мероприятий",
  closeMenu: "Закрыть меню",
  delete: "Удалить",
  deleteAllNotifications: "Удалить все",
  guest: "Гость",
  internships: "Стажировки",
  internshipsAdmin: "Админ. стажировки",
  login: "Войти",
  logout: "Выйти",
  myRequests: "Мои заявки",
  noNotifications: "Пока нет уведомлений",
  notificationCenter: "Центр уведомлений",
  notifications: "Уведомления",
  openLink: "Открыть ссылку",
  openMenu: "Открыть меню",
  organizer: "Организатор",
  planner: "Планировщик",
  profile: "Профиль",
  projectant: "Проектант",
  requests: "Заявки",
  testing: "Модуль тестирования",
} as const;

interface HeaderImportMetaEnv {
  VITE_TESTING_URL?: string;
}

const TESTING_MODULE_URL =
  ((import.meta as ImportMeta & { env?: HeaderImportMetaEnv }).env?.VITE_TESTING_URL || "").trim() || "https://example.com/testing";

function isProjectantRole(role?: string) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "student" || normalized.includes("project");
}

function isOrganizerRole(role?: string) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "organizer" || normalized.includes("admin") || normalized.includes("curator");
}

export default function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useContext(AuthContext);
  const { notifications, unreadCount, markAllAsRead, markAsRead, removeNotification, clearNotifications } =
    useNotifications();
  const { showToast } = useToast();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const unreadNoticeKeyRef = useRef("");
  const isProjectant = isProjectantRole(user?.role);
  const isOrganizer = isOrganizerRole(user?.role);
  const canManageAutomation = Boolean(user && isGlobalOrganizer(user));

  useEffect(() => {
    if (!notificationsOpen) return;
    markAllAsRead();
  }, [notificationsOpen, markAllAsRead]);

  useEffect(() => {
    if (!user || unreadCount <= 0) {
      unreadNoticeKeyRef.current = "";
      return;
    }

    const latestUnread = notifications.find((notification) => !notification.read);
    const noticeKey = `${user.id}:${unreadCount}:${latestUnread?.id ?? "none"}`;
    if (unreadNoticeKeyRef.current === noticeKey) return;

    unreadNoticeKeyRef.current = noticeKey;
    showToast(
      "info",
      unreadCount === 1
        ? "У вас есть непрочитанное уведомление в центре уведомлений"
        : `У вас ${unreadCount} непрочитанных уведомлений в центре уведомлений`
    );
  }, [notifications, showToast, unreadCount, user]);

  const goTo = (path: string) => {
    setMobileMenuOpen(false);
    navigate(path);
  };

  const openTestingModule = async () => {
    if (!TESTING_MODULE_URL) return;
    setMobileMenuOpen(false);

    if (client.USE_MOCK) {
      window.open(TESTING_MODULE_URL, "_blank", "noopener,noreferrer");
      return;
    }

    try {
      const response = await createTestingSSOLink();
      window.open(response.url, "_blank", "noopener,noreferrer");
    } catch {
      showToast("error", "Не удалось открыть модуль тестирования");
    }
  };

  const mobileMenuItems: MenuProps["items"] = user
    ? [
      {
        key: "/requests",
        label: (
          <span className="mobile-menu-entry">
            <span className="mobile-menu-entry__icon">
              <BarsOutlined />
            </span>
            <span>{isProjectant ? HEADER_TEXT.myRequests : HEADER_TEXT.requests}</span>
          </span>
        ),
      },
      {
        key: "/internships",
        label: (
          <span className="mobile-menu-entry">
            <span className="mobile-menu-entry__icon">
              <RocketOutlined />
            </span>
            <span>{HEADER_TEXT.internships}</span>
          </span>
        ),
      },

      {
        key: "/internships/admin",
        label: (
          <span className="mobile-menu-entry">
            <span className="mobile-menu-entry__icon">
              <TeamOutlined />
            </span>
            <span>{HEADER_TEXT.internshipsAdmin}</span>
          </span>
        ),
      },

      ...(canManageAutomation
        ? [
          {
            key: "/automation",
            label: (
              <span className="mobile-menu-entry">
                <span className="mobile-menu-entry__icon">
                  <SaveOutlined />
                </span>
                <span>{HEADER_TEXT.automation}</span>
              </span>
            ),
          },
        ]
        : []),
      {
        key: "/planner",
        label: (
          <span className="mobile-menu-entry">
            <span className="mobile-menu-entry__icon">
              <TeamOutlined />
            </span>
            <span>{HEADER_TEXT.planner}</span>
          </span>
        ),
      },
      ...(TESTING_MODULE_URL
        ? [
          {
            key: "__testing",
            label: (
              <span className="mobile-menu-entry">
                <span className="mobile-menu-entry__icon">
                  <ContainerOutlined />
                </span>
                <span>{HEADER_TEXT.testing}</span>
              </span>
            ),
          },
        ]
        : []),
      {
        key: "/profile",
        label: (
          <span className="mobile-menu-entry">
            <span className="mobile-menu-entry__icon">
              <UserOutlined />
            </span>
            <span>{HEADER_TEXT.profile}</span>
          </span>
        ),
      },
    ]
    : [];

  const onMobileMenuClick: MenuProps["onClick"] = ({ key }) => {
    if (key === "__testing") {
      void openTestingModule();
      return;
    }

    goTo(String(key));
  };

  const activeMobileMenuKey =
    ["/planner", "/automation", "/requests", "/internships/admin", "/internships", "/profile"].find((path) =>
      location.pathname.startsWith(path)
    ) ?? "";

  const openNotifications = () => {
    setMobileMenuOpen(false);
    setNotificationsOpen(true);
  };

  const openNotificationLink = async (id: string, link?: string) => {
    markAsRead(id);
    if (!link) return;

    try {
      const url = new URL(link, window.location.origin);
      if (url.origin === window.location.origin && url.pathname === "/testing") {
        const applicationId = Number(url.searchParams.get("applicationId"));
        const response = await createTestingSSOLink(Number.isFinite(applicationId) && applicationId > 0 ? applicationId : undefined);
        setNotificationsOpen(false);
        window.open(response.url, "_blank", "noopener,noreferrer");
        return;
      }

      if (url.origin === window.location.origin) {
        setNotificationsOpen(false);
        navigate(`${url.pathname}${url.search}${url.hash}`);
        return;
      }
    } catch {
      showToast("error", "Не удалось открыть ссылку из уведомления");
      return;
    }

    window.open(link, "_blank", "noopener,noreferrer");
  };

  const formatDateTime = (iso: string) => {
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return "";
    return dt.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const isActivePath = (path: string) => location.pathname.startsWith(path);
  const isInternshipsListActive = location.pathname === "/internships";
  const isInternshipsAdminActive = location.pathname.startsWith("/internships/admin");

  const mobileBottomItems = user
    ? [
      {
        key: "requests",
        label: isProjectant ? HEADER_TEXT.myRequests : HEADER_TEXT.requests,
        icon: <BarsOutlined />,
        active: isActivePath("/requests"),
        onClick: () => goTo("/requests"),
      },
      {
        key: "internships",
        label: HEADER_TEXT.internships,
        icon: <RocketOutlined />,
        active: isInternshipsListActive,
        onClick: () => goTo("/internships"),
      },
      ...(canManageAutomation
        ? [
          {
            key: "internships-admin",
            label: HEADER_TEXT.internshipsAdmin,
            icon: <TeamOutlined />,
            active: isInternshipsAdminActive,
            onClick: () => goTo("/internships/admin"),
          },
        ]
        : []),
      ...(canManageAutomation
        ? [
          {
            key: "automation",
            label: HEADER_TEXT.automation,
            icon: <SaveOutlined />,
            active: isActivePath("/automation"),
            onClick: () => goTo("/automation"),
          },
        ]
        : []),
      {
        key: "planner",
        label: HEADER_TEXT.planner,
        icon: <TeamOutlined />,
        active: isActivePath("/planner"),
        onClick: () => goTo("/planner"),
      },
      ...(TESTING_MODULE_URL
        ? [
          {
            key: "testing",
            label: HEADER_TEXT.testing,
            icon: <ContainerOutlined />,
            active: false,
            onClick: () => void openTestingModule(),
          },
        ]
        : []),
      {
        key: "profile",
        label: HEADER_TEXT.profile,
        icon: <UserOutlined />,
        active: isActivePath("/profile"),
        onClick: () => goTo("/profile"),
      },
    ]
    : [];

  return (
    <>
      <header className={`app-header ${user ? "app-header--auth" : "app-header--guest"}`}>
        {user ? (
          <div className={`mobile-menu ${mobileMenuOpen ? "open" : ""}`}>
            <Dropdown
              open={mobileMenuOpen}
              onOpenChange={setMobileMenuOpen}
              trigger={["click"]}
              placement="bottomLeft"
              classNames={{ root: "mobile-menu-dropdown" }}
              menu={{
                items: mobileMenuItems,
                selectedKeys: activeMobileMenuKey ? [activeMobileMenuKey] : [],
                onClick: onMobileMenuClick,
              }}
            >
              <AppButton className="mobile-menu-btn" aria-label={mobileMenuOpen ? HEADER_TEXT.closeMenu : HEADER_TEXT.openMenu}>
                <MenuOutlined />
              </AppButton>
            </Dropdown>
          </div>
        ) : (
          <div className="mobile-menu-spacer" aria-hidden />
        )}

        <div className="header-left">
          {user && (
            <>
              <AppButton className={`head-btn head-btn--muted${isActivePath("/requests") ? " is-active" : ""}`} onClick={() => navigate("/requests")}>
                <BarsOutlined />
                <span>{isProjectant ? HEADER_TEXT.myRequests : HEADER_TEXT.requests}</span>
              </AppButton>

              {canManageAutomation && (
                <AppButton className={`head-btn head-btn--automation${isActivePath("/automation") ? " is-active" : ""}`} onClick={() => navigate("/automation")}>
                  <SaveOutlined />
                  <span>{HEADER_TEXT.automation}</span>
                </AppButton>
              )}

              <AppButton className={`head-btn head-btn--planner${isActivePath("/planner") ? " is-active" : ""}`} onClick={() => navigate("/planner")}>
                <TeamOutlined />
                <span>{HEADER_TEXT.planner}</span>
              </AppButton>

              {TESTING_MODULE_URL && (
                <AppButton className="head-btn head-btn--testing" onClick={() => void openTestingModule()}>
                  <ContainerOutlined />
                  <span>{HEADER_TEXT.testing}</span>
                  <ExportOutlined className="head-btn__external-icon" />
                </AppButton>
              )}

              <AppButton className={`head-btn head-btn--muted${isInternshipsListActive ? " is-active" : ""}`} onClick={() => navigate("/internships")}>
                <RocketOutlined />
                <span>{HEADER_TEXT.internships}</span>
              </AppButton>


              <AppButton className={`head-btn head-btn--muted${isInternshipsAdminActive ? " is-active" : ""}`} onClick={() => navigate("/internships/admin")}>
                <TeamOutlined />
                <span>{HEADER_TEXT.internshipsAdmin}</span>
              </AppButton>

            </>
          )}
        </div>

        <div className="header-center">
          <AppButton className="header-logo" onClick={() => goTo("/")}>
            <img src={logoIcon} alt="logo" className="header-logo-img" />
          </AppButton>
        </div>

        <div className="header-right">
          {user ? (
            <>
              <div className="profile-box" onClick={() => navigate("/profile")}>
                <UserOutlined className="profile-icon" />
                <div className="profile-text">
                  <div className="role">{isOrganizer ? HEADER_TEXT.organizer : HEADER_TEXT.projectant}</div>
                  <div className="name">{user.name ? `${user.name} ${user.surname || ""}` : HEADER_TEXT.guest}</div>
                </div>
              </div>

              <AppButton className="head-btn head-btn--notify" onClick={openNotifications} aria-label={HEADER_TEXT.notificationCenter}>
                <Badge dot={unreadCount > 0} className="notification-badge">
                  <BellOutlined />
                </Badge>
                <span>{HEADER_TEXT.notifications}</span>
              </AppButton>

              <AppButton
                className="head-btn head-btn--danger"
                onClick={() => {
                  setMobileMenuOpen(false);
                  void logout?.();
                  navigate("/login");
                }}
              >
                <LogoutOutlined />
                <span>{HEADER_TEXT.logout}</span>
              </AppButton>
            </>
          ) : (
            <AppButton className="head-btn head-btn--login" onClick={() => navigate("/login")}>
              <LoginOutlined />
              <span>{HEADER_TEXT.login}</span>
            </AppButton>
          )}
        </div>

        <Modal isOpen={notificationsOpen} onClose={() => setNotificationsOpen(false)} title={HEADER_TEXT.notificationCenter}>
          <div className="notification-center">
            {notifications.length === 0 ? (
              <div className="notification-empty">{HEADER_TEXT.noNotifications}</div>
            ) : (
              <>
                <div className="notification-center__toolbar">
                  <AppButton className="notification-clear-btn" onClick={clearNotifications}>
                    {HEADER_TEXT.deleteAllNotifications}
                  </AppButton>
                </div>
                {notifications.map((notification) => (
                  <div key={notification.id} className={`notification-item ${notification.read ? "is-read" : "is-unread"}`}>
                    <div className="notification-item__head">
                      <div className="notification-item__title">{notification.title}</div>
                      <div className="notification-item__date">{formatDateTime(notification.createdAt)}</div>
                    </div>
                    {notification.message && <div className="notification-item__message">{notification.message}</div>}
                    <div className="notification-item__actions">
                      {notification.link && !isOrganizer && (
                        <AppButton
                          className="notification-link-btn"
                          onClick={() => void openNotificationLink(notification.id, notification.link)}
                        >
                          {HEADER_TEXT.openLink}
                        </AppButton>
                      )}
                      <AppButton className="notification-remove-btn" onClick={() => removeNotification(notification.id)}>
                        {HEADER_TEXT.delete}
                      </AppButton>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </Modal>
      </header>

      {user && (
        <nav className="mobile-bottom-nav" aria-label="Основная мобильная навигация">
          {mobileBottomItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`mobile-bottom-nav__item ${item.active ? "is-active" : ""}`}
              onClick={item.onClick}
              title={item.label}
            >
              <span className="mobile-bottom-nav__icon">{item.icon}</span>
              <span className="mobile-bottom-nav__label">{item.label}</span>
            </button>
          ))}
        </nav>
      )}
    </>
  );
}