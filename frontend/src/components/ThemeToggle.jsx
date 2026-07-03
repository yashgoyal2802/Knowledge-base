import React from 'react';
import { Sun, Moon, Zap, Shield, Terminal } from 'lucide-react';

export default function ThemeToggle({ theme, setTheme }) {
  const themes = [
    { id: 'orange', label: 'Cyber Orange', icon: Zap },
    { id: 'green', label: 'Hacker Green', icon: Terminal },
    { id: 'cyan', label: 'Neon Cyan', icon: Shield },
  ];

  return (
    <div className="theme-selector" title="Switch Theme Palette">
      {themes.map((t) => {
        const Icon = t.icon;
        const isActive = theme === t.id;
        return (
          <button
            key={t.id}
            type="button"
            className={`theme-btn ${isActive ? 'active' : ''}`}
            onClick={() => setTheme(t.id)}
          >
            <Icon size={14} />
            <span>{t.label.split(' ')[1]}</span>
          </button>
        );
      })}
    </div>
  );
}
