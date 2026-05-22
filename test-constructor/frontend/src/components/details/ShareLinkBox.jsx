import React from 'react';
import PodelitsiIcon from "../../assets/Podelitsi.svg";
import CopySubIcon from "../../assets/copy_sub.svg";

export default function ShareLinkBox({ link }) {
    const handleCopy = () => {
        navigator.clipboard.writeText(link);
    };
    return (
        <div className="share-link-box">
            <div className="share-link-box-inner">
                <img src={PodelitsiIcon} alt="время" />
                <p>Поделиться ссылкой</p>
            </div>
            <div className="share-link-box-inner1">
            <div className="share-link-input-box">
                <input type="text" value={link} readOnly />
                <button onClick={handleCopy}>
                    <img src={CopySubIcon} alt="Копировать" className="copy-sub-icon" />
                </button>

            </div>
            </div>
        </div>
    );
}
