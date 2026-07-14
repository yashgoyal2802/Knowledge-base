import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import InfiniteTimeline from './components/InfiniteTimeline';
import ChatPanel from './components/ChatPanel';
import AuthModal from './components/AuthModal';

export default function App() {
  // Default to Feed (news-first experience)
  const [activeTab, setActiveTab] = useState('feed');
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('cyberintel_theme') || 'dark';
  });
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('cyberintel_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('cyberintel_theme', theme);
  }, [theme]);

  const handleLoginSuccess = (userProfile) => {
    setUser(userProfile);
  };

  const handleLogout = () => {
    localStorage.removeItem('cyberintel_token');
    localStorage.removeItem('cyberintel_user');
    setUser(null);
  };

  return (
    <>
      <Layout
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        theme={theme}
        setTheme={setTheme}
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
        onLogout={handleLogout}
      >
        {activeTab === 'feed' && <InfiniteTimeline mode="articles" />}
        {activeTab === 'vulns' && <InfiniteTimeline mode="vulns" />}
        {activeTab === 'chat' && <ChatPanel />}
      </Layout>

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onLoginSuccess={handleLoginSuccess}
      />
    </>
  );
}
