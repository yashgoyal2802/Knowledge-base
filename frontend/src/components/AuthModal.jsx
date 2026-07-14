import React, { useState } from 'react';
import { X, AlertCircle, CheckCircle } from 'lucide-react';

export default function AuthModal({ isOpen, onClose, onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login';
      const body = isRegister
        ? { email, password, full_name: fullName }
        : { email, password };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed.');
      }

      if (isRegister) {
        setSuccess('Account created! You can now sign in.');
        setIsRegister(false);
      } else {
        // Store token and fetch profile
        localStorage.setItem('cyberintel_token', data.access_token);

        const meRes = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        const profile = meRes.ok ? await meRes.json() : { email };
        localStorage.setItem('cyberintel_user', JSON.stringify(profile));
        onLoginSuccess(profile, data.access_token);
        onClose();
      }
    } catch (err) {
      // Offline fallback — create mock session for preview
      if (!navigator.onLine || err.message.includes('fetch') || err.message.includes('Failed')) {
        const mockProfile = { email, full_name: fullName || email.split('@')[0] };
        localStorage.setItem('cyberintel_user', JSON.stringify(mockProfile));
        onLoginSuccess(mockProfile);
        onClose();
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button
          onClick={onClose}
          className="icon-btn"
          style={{ position: 'absolute', top: '0.75rem', right: '0.75rem' }}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h2 className="modal-title">{isRegister ? 'Create Account' : 'Sign In'}</h2>
        <p className="modal-subtitle">
          {isRegister
            ? 'Create an account to save your preferences.'
            : 'Sign in to access your saved settings.'}
        </p>

        {error && (
          <div className="alert alert-error">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            <CheckCircle size={16} /> {success}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                className="form-input"
                type="text"
                placeholder="Your name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              type="email"
              required
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              required
              minLength={8}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ marginTop: '0.5rem' }}
          >
            {loading ? 'Loading…' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          {isRegister ? 'Already have an account? ' : 'No account? '}
          <button
            onClick={() => { setIsRegister(!isRegister); setError(null); setSuccess(null); }}
            style={{ color: 'var(--accent)', fontWeight: 600 }}
          >
            {isRegister ? 'Sign In' : 'Create one'}
          </button>
        </p>
      </div>
    </div>
  );
}
