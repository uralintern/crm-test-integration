import Modal from "./Modal";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
}

export default function InfoModal({ isOpen, onClose, title, description }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <div style={{ paddingTop: 8 }}>
        <div style={{ color: "#444", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
          {description || "Описание отсутствует"}
        </div>
      </div>
    </Modal>
  );
}

