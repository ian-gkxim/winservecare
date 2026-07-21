import { useEffect, useState } from 'react';

interface ConfirmationToastProps {
  message: string;
  onClose: () => void;
  duration?: number;
}

export default function ConfirmationToast({
  message,
  onClose,
  duration = 3000,
}: ConfirmationToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onClose();
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 flex items-center gap-2 px-4 py-3 bg-green-50 border border-green-200 rounded-md text-green-800 shadow-lg"
    >
      <span aria-hidden="true">✓</span>
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
