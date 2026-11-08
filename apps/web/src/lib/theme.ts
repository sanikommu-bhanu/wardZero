export type ThemePref = "auto" | "light" | "dark";
const KEY = "wz-theme";

export function getTheme(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "auto";
  } catch { return "auto"; }
}

export function applyTheme(pref: ThemePref): void {
  const el = document.documentElement;
  if (pref === "auto") el.removeAttribute("data-theme"); else el.setAttribute("data-theme", pref);
  try { if (pref === "auto") localStorage.removeItem(KEY); else localStorage.setItem(KEY, pref); } catch { /* storage may be blocked */ }
}
