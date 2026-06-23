import React, { useState, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff, FiLock, FiLogIn, FiPhone, FiMail, FiUser, FiShield } from 'react-icons/fi';

function detectType(value) {
  const v = value.trim();
  if (!v) return null;
  if (/^\+?\d{7,15}$/.test(v))                     return 'phone';
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v))        return 'email';
  if (/^[a-z0-9_-]{2,}$/i.test(v))                 return 'handle';
  return null;
}

export default function Login() {
  const { login } = useAuth();
  const navigate  = useNavigate();

  const [identifier,    setIdentifier]    = useState('');
  const [password,      setPassword]      = useState('');
  const [showPassword,  setShowPassword]  = useState(false);
  const [error,         setError]         = useState('');
  const [loading,       setLoading]       = useState(false);

  const idType = useMemo(() => detectType(identifier), [identifier]);

  const IdIcon = idType === 'phone' ? FiPhone
               : idType === 'email' ? FiMail
               : FiUser;

  const placeholder = 'Phone, email, or @handle';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!identifier.trim()) { setError('Please enter your phone, email, or handle.'); return; }
    if (!password)           { setError('Please enter your password.'); return; }
    setLoading(true);
    try {
      await login(identifier.trim(), password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lu-login-page">
      {/* Background pattern */}
      <div className="lu-login-bg" aria-hidden="true" />

      <div className="lu-login-card">

        {/* Header */}
        <div className="lu-login-header">
          <div className="lu-login-brand">
            <div className="lu-logo-mark">LU</div>
            <div>
              <h1 className="lu-login-title">LinkUp</h1>
              <p className="lu-login-subtitle">Admin Console</p>
            </div>
          </div>

          <div className="lu-login-badge">
            <FiShield size={11} />
            <span>Secure · Admin only</span>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="lu-alert lu-alert-error" role="alert">
            <span>⚠</span> {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="lu-login-form" noValidate>

          {/* Identifier */}
          <div className="lu-form-group">
            <label htmlFor="identifier">Sign in with</label>
            <div className="lu-input-wrap">
              <span className="lu-input-icon">
                <IdIcon size={15} />
              </span>
              <input
                id="identifier"
                type="text"
                inputMode="text"
                autoComplete="username"
                placeholder={placeholder}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoFocus
                spellCheck={false}
                autoCapitalize="none"
              />
              {idType && (
                <span className={`lu-id-badge lu-id-badge--${idType}`}>
                  {idType}
                </span>
              )}
            </div>
            <p className="lu-field-hint">Accepts phone (+256…), email, or @handle</p>
          </div>

          {/* Password */}
          <div className="lu-form-group">
            <label htmlFor="password">Password</label>
            <div className="lu-input-wrap lu-input-wrap--action">
              <span className="lu-input-icon">
                <FiLock size={15} />
              </span>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="lu-input-toggle"
                onClick={() => setShowPassword(v => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <FiEyeOff size={15} /> : <FiEye size={15} />}
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="lu-btn-primary"
            disabled={loading}
          >
            {loading
              ? <span className="lu-spinner" />
              : <FiLogIn size={16} />
            }
            {loading ? 'Signing in…' : 'Sign In to Admin'}
          </button>
        </form>

        {/* Footer hint */}
        <div className="lu-login-footer">
          <span>samuel-ocen</span>
          <span className="lu-dot" />
          <span>+256700000001</span>
          <span className="lu-dot" />
          <span>111111</span>
        </div>
      </div>
    </div>
  );
}
