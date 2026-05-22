import { Checkbox } from "antd";
import AppButton from "../../../components/UI/Button";
import Modal from "../../../components/Modal/Modal";
import { ORGANIZER_REQUEST_STATUSES } from "../../../constants/requestProgress";
import {
  OTHER_STATUS_COLOR,
  REQUESTS_TEXT as TEXT,
  REQUEST_STATUS_COLORS,
} from "../config/requestsConfig";

type StatusSettingsModalProps = {
  isOpen: boolean;
  displayedStatuses: string[];
  statusCounts: Record<string, number>;
  onClose: () => void;
  onToggleStatus: (status: string, checked: boolean) => void;
  onSelectAll: () => void;
};

export function StatusSettingsModal({
  isOpen,
  displayedStatuses,
  statusCounts,
  onClose,
  onToggleStatus,
  onSelectAll,
}: StatusSettingsModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={TEXT.statusDisplaySettings}>
      <div className="requests-status-settings">
        <p>{TEXT.statusDisplayDescription}</p>
        <div className="requests-status-settings__list">
          {ORGANIZER_REQUEST_STATUSES.map((status) => (
            <label
              className="requests-status-settings__option"
              key={status}
              style={{ ["--status-color" as string]: REQUEST_STATUS_COLORS[status] || OTHER_STATUS_COLOR }}
            >
              <Checkbox checked={displayedStatuses.includes(status)} onChange={(event) => onToggleStatus(status, event.target.checked)}>
                {status}
              </Checkbox>
              <span>{statusCounts[status] || 0}</span>
            </label>
          ))}
        </div>
        <div className="confirm-actions">
          <AppButton className="close-btn" onClick={onSelectAll}>
            {TEXT.selectAllStatuses}
          </AppButton>
          <AppButton className="btn-send" onClick={onClose}>
            {TEXT.ready}
          </AppButton>
        </div>
      </div>
    </Modal>
  );
}
