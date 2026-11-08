import React, { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";

function useEscapeClose(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
}

export function Modal({ open, onClose, title, children, footer }: {
  open: boolean; onClose: () => void; title?: string; children: React.ReactNode; footer?: React.ReactNode;
}) {
  useEscapeClose(open, onClose);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (open) closeRef.current?.focus(); }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="overlay-backdrop"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <motion.div
            role="dialog" aria-modal="true" aria-label={title}
            className="glass-panel-strong modal-panel"
            initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.98 }}
          >
            <div className="modal-head">
              <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
              <button ref={closeRef} className="icon-btn focus-ring" aria-label="Close dialog" onClick={onClose}>{"\u2715"}</button>
            </div>
            <div>{children}</div>
            {footer && <div className="flex items-center justify-end gap-8" style={{ marginTop: 18 }}>{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: string; children: React.ReactNode }) {
  useEscapeClose(open, onClose);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (open) closeRef.current?.focus(); }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="overlay-backdrop" style={{ padding: 0 }}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <motion.div
            role="dialog" aria-modal="true" aria-label={title}
            className="glass-panel-strong drawer-panel"
            initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }}
            transition={{ duration: 0.22 }}
          >
            <div className="modal-head">
              <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
              <button ref={closeRef} className="icon-btn focus-ring" aria-label="Close panel" onClick={onClose}>{"\u2715"}</button>
            </div>
            <div>{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
