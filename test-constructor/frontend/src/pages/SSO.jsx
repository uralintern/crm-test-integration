import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { authAPI } from "../services/api.js";

const exchangeRequests = new Map();

function exchangeTicketOnce(ticket) {
    if (!exchangeRequests.has(ticket)) {
        const request = authAPI.ssoExchange(ticket).finally(() => {
            setTimeout(() => exchangeRequests.delete(ticket), 30000);
        });
        exchangeRequests.set(ticket, request);
    }
    return exchangeRequests.get(ticket);
}

function getErrorMessage(error) {
    const data = error?.response?.data;
    if (typeof data === "string" && data.trim()) {
        return data.trim();
    }
    if (data?.detail) {
        return data.detail;
    }
    return "Не удалось выполнить вход через CRM.";
}

export default function SSO() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const [message, setMessage] = useState("Выполняется вход...");

    useEffect(() => {
        let cancelled = false;

        const run = async () => {
            const ticket = params.get("ticket");
            if (!ticket) {
                setMessage("SSO ticket не найден.");
                return;
            }

            try {
                const response = await exchangeTicketOnce(ticket);
                const data = response.data;

                localStorage.setItem("token", data.token);
                localStorage.setItem(
                    "user",
                    JSON.stringify({
                        id: data.user_id,
                        email: data.email,
                        name: data.name,
                        surname: data.surname,
                        role: data.role,
                    })
                );

                if (data.application) {
                    localStorage.setItem("testingApplication", JSON.stringify(data.application));
                }

                if (cancelled) return;

                if ((data.role === "manager" || data.role === "admin") && data.next) {
                    navigate(data.next, { replace: true });
                    return;
                }

                const applicationId = data.application?.application?.id;
                const eventId = data.application?.event?.id;
                const specializationId = data.application?.specialization?.id;
                if (data.role === "intern" && eventId) {
                    const query = new URLSearchParams({ event_id: String(eventId) });
                    if (applicationId) query.set("application_id", String(applicationId));
                    if (specializationId) query.set("specialization_id", String(specializationId));
                    navigate(`/myTestStudent?${query.toString()}`, { replace: true });
                    return;
                }
                if (data.role === "intern" && data.test_link) {
                    const query = applicationId ? `?application_id=${applicationId}` : "";
                    navigate(`/test/${data.test_link}${query}`, { replace: true });
                    return;
                }

                navigate(data.role === "intern" ? "/StudentHome" : "/tests", { replace: true });
            } catch (error) {
                console.error("SSO exchange failed", error);
                setMessage(getErrorMessage(error));
            }
        };

        run();
        return () => {
            cancelled = true;
        };
    }, [navigate, params]);

    return <div style={{ padding: 32 }}>{message}</div>;
}
