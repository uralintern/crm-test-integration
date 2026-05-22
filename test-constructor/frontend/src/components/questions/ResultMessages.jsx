import { useState } from "react";

export default function ResultMessages({ messages, updateMessages }) {
    const handleSuccessChange = (e) => {
        updateMessages({ ...messages, success: e.target.value });
    };

    const handleFailureChange = (e) => {
        updateMessages({ ...messages, failure: e.target.value });
    };

    return (
        <div className="">

            <div className="section-header-result">
                <h3>Окончание</h3>
            </div>
            <div className="result-messages question-block">
            <div className="messages-container">
                <div className="message-group">
                    <h4>Сообщение при успешном прохождении</h4>
                    <textarea
                        className="message-textarea"
                        placeholder="Введите текст сообщения об успехе..."
                        value={messages.success || ""}
                        onChange={handleSuccessChange}
                        rows={3}
                    />
                </div>

                <div className="message-group">
                    <h4>Сообщение при провальном прохождении</h4>
                    <textarea
                        className="message-textarea"
                        placeholder="Введите текст сообщения об ошибке..."
                        value={messages.failure || ""}
                        onChange={handleFailureChange}
                        rows={3}
                    />
                </div>
            </div>
            </div>
        </div>
    );
}