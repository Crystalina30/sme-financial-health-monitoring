import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

// Kept in the browser, so the theme chosen on the sign-in page is the one the
// app opens in after signing in, and the one shown next time on this device.
export const THEME_STORAGE_KEY = 'fyp_theme';
export const THEMES = ['light', 'dark'];
const DEFAULT_THEME = 'light';

function readStoredTheme() {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return THEMES.includes(stored) ? stored : DEFAULT_THEME;
  } catch {
    // Storage can be unavailable (private windows, blocked site data).
    return DEFAULT_THEME;
  }
}

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readStoredTheme);

  // The stylesheets switch on this attribute; index.html sets it before the
  // first paint, and this keeps it in step afterwards.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // The choice still applies for this visit.
    }
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (THEMES.includes(next)) setThemeState(next);
  }, []);

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used inside a ThemeProvider.');
  return context;
}
