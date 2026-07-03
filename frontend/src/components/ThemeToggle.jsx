import React from 'react';
import { Sun, Moon } from 'lucide-react';

export default function ThemeToggle({ theme, setTheme }) {
  const isDark = theme === 'dark' || theme !== 'light';

  const toggleTheme = () => {
    setTheme(isDark ? 'light' : 'dark');
  };

  return (
    <button
      type="button"
      className="theme-toggle-btn"
      onClick={toggleTheme}
      title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      aria-label="Toggle Dark/Light Mode"
    >
      {isDark ? (
        <>
          <Sun size={16} className="theme-icon sun" />
          <span>Light Mode</span>
        </>
      ) : (
        <>
          <Moon size={16} className="theme-icon moon" />
          <span>Dark Mode</span>
        </>
      )}
    </button>
  );
}
