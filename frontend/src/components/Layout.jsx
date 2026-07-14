import React, { useState } from 'react';
import { Shield, Menu, X, LogIn, LogOut } from 'lucide-react';
import ThemeToggle from './ThemeToggle';

export default function Layout({
  children,
  activeTab,
  setActiveTab,
  theme,
  setTheme,
  user,
  onOpenAuth,
  onLogout
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  const navItems = [
    { id: 'feed', label: 'Feed' },
    { id: 'vulns', label: 'Vulnerabilities' },
    { id: 'chat', label: 'Ask AI' },
  ];

  const handleNav = (id) => {
    setActiveTab(id);
    setDrawerOpen(false);
  };

  return (
    <>
      {/* ── Top Navbar ─────────────────────────────────────── */}
      <nav className="navbar">
        <div className="navbar-inner">
          <div className="navbar-brand">
            <Shield size={20} />
            <span>CyberIntel</span>
          </div>

          {/* Desktop nav links */}
          <div className="navbar-links">
            {navItems.map((item) => (
              <button
                key={item.id}
                className={`nav-link ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => handleNav(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Right side: theme, auth, hamburger */}
          <div className="navbar-right">
            <ThemeToggle theme={theme} setTheme={setTheme} />

            {user ? (
              <button className="icon-btn" onClick={onLogout} title="Sign out">
                <LogOut size={18} />
              </button>
            ) : (
              <button className="icon-btn" onClick={onOpenAuth} title="Sign in">
                <LogIn size={18} />
              </button>
            )}

            {/* Hamburger — visible only on mobile via CSS */}
            <button
              className="hamburger icon-btn"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>
          </div>
        </div>
      </nav>

      {/* ── Mobile Drawer ──────────────────────────────────── */}
      {drawerOpen && (
        <>
          <div className="drawer-overlay" onClick={() => setDrawerOpen(false)} />
          <div className="drawer" role="dialog" aria-modal="true">
            <div className="drawer-header">
              <div className="navbar-brand">
                <Shield size={18} />
                <span>CyberIntel</span>
              </div>
              <button className="icon-btn" onClick={() => setDrawerOpen(false)} aria-label="Close menu">
                <X size={20} />
              </button>
            </div>

            {navItems.map((item) => (
              <button
                key={item.id}
                className={`nav-link ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => handleNav(item.id)}
              >
                {item.label}
              </button>
            ))}

            <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
              {user ? (
                <button className="nav-link" onClick={() => { onLogout(); setDrawerOpen(false); }}>
                  Sign Out
                </button>
              ) : (
                <button className="nav-link" onClick={() => { onOpenAuth(); setDrawerOpen(false); }}>
                  Sign In
                </button>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Page Content ───────────────────────────────────── */}
      <main className="page">
        {children}
      </main>
    </>
  );
}
