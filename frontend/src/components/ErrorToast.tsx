"use client";

import { useEffect } from "react";

interface ErrorToastProps {
  message: string;
  visible: boolean;
  onClose: () => void;
}

export function ErrorToast({ message, visible, onClose }: ErrorToastProps) {
  useEffect(() => {
    if (!visible) {
      return;
    }

    const id = window.setTimeout(onClose, 4500);
    return () => window.clearTimeout(id);
  }, [visible, onClose]);

  if (!visible) {
    return null;
  }

  return (
    <div className="fixed right-4 top-4 z-50 max-w-sm rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 shadow-lg" role="alert" aria-live="assertive">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-rose-800">{message}</p>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-rose-300 bg-white px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"
        >
          Close
        </button>
      </div>
    </div>
  );
}
