import React from "react";
import { motion } from "framer-motion";

export function GlassCard({ children, className = "", style, onClick, hover = true }: {
  children: React.ReactNode; className?: string; style?: React.CSSProperties; onClick?: () => void; hover?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      whileHover={hover ? { y: -2 } : undefined}
      className={`glass-card ${className}`}
      style={{ padding: 18, cursor: onClick ? "pointer" : undefined, ...style }}
      onClick={onClick}
    >
      {children}
    </motion.div>
  );
}

export function GlassPanel({ children, className = "", style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
  return <div className={`glass-panel ${className}`} style={{ padding: 20, ...style }}>{children}</div>;
}

export function GlassButton({ children, onClick, variant = "default", size = "md", disabled, type = "button", title }: {
  children: React.ReactNode; onClick?: () => void; variant?: "default" | "primary" | "danger"; size?: "md" | "sm";
  disabled?: boolean; type?: "button" | "submit"; title?: string;
}) {
  const cls = ["glass-btn", variant === "primary" ? "glass-btn-primary" : "", variant === "danger" ? "glass-btn-danger" : "",
    size === "sm" ? "glass-btn-sm" : ""].filter(Boolean).join(" ");
  return <button type={type} className={cls} onClick={onClick} disabled={disabled} title={title}>{children}</button>;
}
