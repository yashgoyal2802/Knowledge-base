import React from 'react';
import { Shield, BookOpen, ShieldAlert, Sparkles, LogIn, LogOut, User as UserIcon, Activity, Search } from 'lucide-react';
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
  const navItems = [
    { id: 'dashboard', label: 'SOC Overview', icon: Activity },
    { id: 'timeline', label: 'Intelligence Feed', icon: BookOpen },
    { id: 'vulnerabilities', label: 'CISA KEV & CVEs', icon: ShieldAlert },
    { id: 'chat', label: 'Gemini RAG Chat', icon: Sparkles },
  ];

  return (
    <div className="app-container">
      {/* Fixed Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Shield size={22} />
          </div>
          <div>
            <div className="brand-text">CYBERINTEL</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', letterSpacing: '0.1em', fontWeight: 'bold' }}>
              GEMINI 2.0 FLASH RAG
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="nav-menu">
          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 'bold', padding: '0 0.75rem', marginBottom: '0.25rem' }}>
            ANALYST MODULES
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveTab(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar Footer: Theme Switcher & System Status */}
        <div className="sidebar-footer">
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 'bold', marginBottom: '0.4rem' }}>
              APPEARANCE
            </div>
            <ThemeToggle theme={theme} setTheme={setTheme} />
          </div>

          <div style={{
            background: 'var(--bg-search)',
            padding: '0.75rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.75rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="pulse-glow" style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00ff66', display: 'inline-block' }} />
              <span style={{ color: 'var(--text-muted)' }}>Supabase Vector DB</span>
            </div>
            <span style={{ color: '#00ff66', fontWeight: 'bold' }}>ONLINE</span>
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <main className="main-content">
        {/* Sticky Header */}
        <header className="top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <h2 style={{ fontSize: '1.25rem', color: 'var(--text-main)', textTransform: 'capitalize' }}>
              {navItems.find(i => i.id === activeTab)?.label || 'Dashboard'}
            </h2>
          </div>

          {/* User Auth Section */}
          <div className="header-actions">
            {user ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.04)', padding: '0.4rem 0.85rem', borderRadius: 'var(--radius-full)', border: '1px solid var(--border-color)' }}>
                  <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--primary)', color: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '0.75rem' }}>
                    {user.full_name ? user.full_name[0].toUpperCase() : 'U'}
                  </div>
                  <span style={{ fontSize: '0.85rem', fontWeight: '600' }}>{user.full_name || user.email}</span>
                  <span className="badge badge-source" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>ANALYST</span>
                </div>
                <button
                  type="button"
                  onClick={onLogout}
                  className="btn-outline"
                  title="Sign Out"
                  style={{ padding: '0.5rem', borderRadius: '50%' }}
                >
                  <LogOut size={16} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onOpenAuth}
                className="btn-primary"
                style={{ padding: '0.5rem 1.25rem', fontSize: '0.85rem' }}
              >
                <LogIn size={16} />
                <span>Analyst Login</span>
              </button>
            )}
          </div>
        </header>

        {/* Dynamic Page Content */}
        <div className="page-view">
          {children}
        </div>
      </main>
    </div>
  );
}
