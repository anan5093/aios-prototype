import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './hooks/useAuth';
import { useWebSocket } from './hooks/useWebSocket';
import { ServiceHealthBar } from './components/ServiceHealthBar';
import { QueryForm } from './components/QueryForm';
import { ReasoningTrace } from './components/ReasoningTrace';
import { RAGViewer, RagChunk } from './components/RAGViewer';
import { MetricsPanel, MetricsData } from './components/MetricsPanel';
import { AuditLog } from './components/AuditLog';

// ─── Login Component ──────────────────────────────────────────────────────────

function LoginPanel() {
  const { login } = useAuth();
  
  // Tab control
  const [activeTab, setActiveTab] = useState<'login' | 'signup'>('login');
  
  // Form states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Signup states
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupRole, setSignupRole] = useState<'viewer' | 'operator' | 'admin'>('operator');
  const [signupSuccess, setSignupSuccess] = useState<string | null>(null);

  // Admin status states (PAM mode)
  const [adminExists, setAdminExists] = useState(true);
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');

  const checkAdminStatus = useCallback(async () => {
    try {
      const { data } = await axios.get<{ adminExists: boolean }>('/api/auth/admin-status');
      setAdminExists(data.adminExists);
    } catch (err) {
      console.error('Failed to query system administrator status:', err);
    }
  }, []);

  useEffect(() => {
    void checkAdminStatus();
  }, [checkAdminStatus, activeTab]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } }; message?: string };
      setError(e.response?.data?.error ?? e.message ?? 'Login failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSignupSuccess(null);
    setError(null);
    
    if (!signupEmail || !signupPassword) {
      setError('Desired Operator credentials are required.');
      return;
    }

    setLoading(true);
    try {
      if (!adminExists) {
        // No admin registered yet: 1st person becomes admin
        const response = await axios.post<{ message: string }>(
          '/api/auth/register',
          {
            email: signupEmail,
            password: signupPassword,
            role: 'admin',
          }
        );
        setSignupSuccess(response.data.message);
        setSignupEmail('');
        setSignupPassword('');
        void checkAdminStatus();
      } else {
        // Admin exists: Admin must be logged in/verify themselves via PAM check
        if (!adminEmail || !adminPassword) {
          setError('Administrator verification (PAM check) is required to register new users.');
          setLoading(false);
          return;
        }

        // 1. Authenticate the admin session
        const loginRes = await axios.post<{ token: string }>('/api/auth/login', {
          email: adminEmail,
          password: adminPassword,
        });

        // 2. Perform PAM register call with the admin's JWT
        const registerRes = await axios.post<{ message: string }>(
          '/api/auth/register',
          {
            email: signupEmail,
            password: signupPassword,
            role: signupRole,
            adminVerifyPassword: adminPassword,
          },
          {
            headers: {
              Authorization: `Bearer ${loginRes.data.token}`,
            },
          }
        );

        setSignupSuccess(registerRes.data.message);
        setSignupEmail('');
        setSignupPassword('');
        setAdminEmail('');
        setAdminPassword('');
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string; message?: string } }; message?: string };
      setError(
        e.response?.data?.message ??
          e.response?.data?.error ??
          e.message ??
          'Registration request failed.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (uEmail: string, uPass: string) => {
    setEmail(uEmail);
    setPassword(uPass);
    setActiveTab('login');
    setError(null);
  };

  return (
    <div className="login-grid-wrapper">
      {/* Left Column: Login/Signup Card */}
      <div className="animate-slide-in-left glowing-border-glow" style={{ width: '100%' }}>
        <div
          style={{
            background: 'rgba(26, 35, 50, 0.7)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            borderRadius: 16,
            padding: '32px 28px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: 3,
              background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-purple), var(--accent-teal))',
              borderTopLeftRadius: 16,
              borderTopRightRadius: 16,
            }}
          />

          {/* Logo Header */}
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <div
              style={{
                width: 48,
                height: 48,
                background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-purple))',
                borderRadius: 12,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.2rem',
                fontWeight: 800,
                color: '#fff',
                marginBottom: 10,
                boxShadow: '0 0 20px rgba(59, 130, 246, 0.4)',
              }}
            >
              AI
            </div>
            <h1 style={{ fontSize: '1.35rem', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              AIOS CONTROL PORTAL
            </h1>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
              B.Tech Capstone Project · Environment Mapped
            </p>
          </div>

          {/* Tab Selection */}
          <div className="tabs-header">
            <button
              type="button"
              className={`tab-btn ${activeTab === 'login' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('login');
                setError(null);
                setSignupSuccess(null);
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === 'signup' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('signup');
                setError(null);
                setSignupSuccess(null);
              }}
            >
              Register
            </button>
          </div>

          {error && (
            <div className="alert-error" style={{ marginBottom: 18, fontSize: '0.78rem' }}>
              <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {signupSuccess && (
            <div className="alert-info" style={{ marginBottom: 18, fontSize: '0.76rem', lineHeight: '1.4' }}>
              {signupSuccess}
            </div>
          )}

          {/* Login Form */}
          {activeTab === 'login' && (
            <form onSubmit={(e) => void handleSubmit(e)}>
              <div style={{ marginBottom: 16 }}>
                <label
                  htmlFor="email"
                  style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, letterSpacing: '0.05em' }}
                >
                  OPERATOR EMAIL
                </label>
                <input
                  id="email"
                  type="email"
                  placeholder="operator@aios"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                  style={{
                    width: '100%',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 8,
                    padding: '10px 12px',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ marginBottom: 20 }}>
                <label
                  htmlFor="password"
                  style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, letterSpacing: '0.05em' }}
                >
                  PASSWORD
                </label>
                <input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  required
                  style={{
                    width: '100%',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 8,
                    padding: '10px 12px',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    fontSize: '0.85rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
                style={{ width: '100%', padding: '11px', fontWeight: 600, fontSize: '0.85rem' }}
              >
                {loading ? 'Authenticating...' : 'Sign In'}
              </button>
            </form>
          )}

          {/* Signup Form */}
          {activeTab === 'signup' && (
            <form onSubmit={(e) => void handleSignupSubmit(e)}>
              {/* Operator info (all states) */}
              <div style={{ marginBottom: 12 }}>
                <label
                  htmlFor="signupEmail"
                  style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4, letterSpacing: '0.05em' }}
                >
                  DESIRED OPERATOR EMAIL
                </label>
                <input
                  id="signupEmail"
                  type="email"
                  placeholder="new-operator@aios"
                  value={signupEmail}
                  onChange={(e) => setSignupEmail(e.target.value)}
                  disabled={loading}
                  required
                  style={{
                    width: '100%',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 8,
                    padding: '9px 12px',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    fontSize: '0.82rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ marginBottom: 12 }}>
                <label
                  htmlFor="signupPassword"
                  style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4, letterSpacing: '0.05em' }}
                >
                  SECURE PASSWORD
                </label>
                <input
                  id="signupPassword"
                  type="password"
                  placeholder="••••••••"
                  value={signupPassword}
                  onChange={(e) => setSignupPassword(e.target.value)}
                  disabled={loading}
                  required
                  style={{
                    width: '100%',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 8,
                    padding: '9px 12px',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    fontSize: '0.82rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {adminExists ? (
                <>
                  <div style={{ marginBottom: 14 }}>
                    <label
                      htmlFor="signupRole"
                      style={{ display: 'block', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4, letterSpacing: '0.05em' }}
                    >
                      ASSIGNED ROLE
                    </label>
                    <select
                      id="signupRole"
                      value={signupRole}
                      onChange={(e) => setSignupRole(e.target.value as 'viewer' | 'operator' | 'admin')}
                      disabled={loading}
                      style={{
                        width: '100%',
                        background: 'var(--bg-input)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 8,
                        padding: '9px 12px',
                        color: 'var(--text-primary)',
                        outline: 'none',
                        fontSize: '0.82rem',
                        boxSizing: 'border-box',
                        cursor: 'pointer',
                      }}
                    >
                      <option value="viewer">Viewer (Read-only)</option>
                      <option value="operator">Operator (Standard)</option>
                      <option value="admin">Administrator (Root)</option>
                    </select>
                  </div>

                  {/* PAM admin verification check */}
                  <div
                    style={{
                      background: 'rgba(239, 68, 68, 0.05)',
                      border: '1px solid rgba(239, 68, 68, 0.15)',
                      borderRadius: 10,
                      padding: 14,
                      marginBottom: 16,
                    }}
                  >
                    <span
                      style={{
                        display: 'block',
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        color: 'var(--accent-danger)',
                        marginBottom: 10,
                        letterSpacing: '0.04em',
                        textTransform: 'uppercase',
                      }}
                    >
                      ⚠️ Administrator Verification (PAM Sudo)
                    </span>

                    <div style={{ marginBottom: 10 }}>
                      <input
                        type="email"
                        placeholder="Admin Email (e.g. admin@aios)"
                        value={adminEmail}
                        onChange={(e) => setAdminEmail(e.target.value)}
                        disabled={loading}
                        required
                        style={{
                          width: '100%',
                          background: 'rgba(10, 14, 26, 0.6)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: 6,
                          padding: '8px 10px',
                          color: 'var(--text-primary)',
                          outline: 'none',
                          fontSize: '0.78rem',
                          boxSizing: 'border-box',
                        }}
                      />
                    </div>

                    <div>
                      <input
                        type="password"
                        placeholder="Admin Password"
                        value={adminPassword}
                        onChange={(e) => setAdminPassword(e.target.value)}
                        disabled={loading}
                        required
                        style={{
                          width: '100%',
                          background: 'rgba(10, 14, 26, 0.6)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: 6,
                          padding: '8px 10px',
                          color: 'var(--text-primary)',
                          outline: 'none',
                          fontSize: '0.78rem',
                          boxSizing: 'border-box',
                        }}
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-danger"
                    disabled={loading}
                    style={{ width: '100%', padding: '11px', fontWeight: 600, fontSize: '0.85rem' }}
                  >
                    {loading ? 'Authenticating Admin...' : 'Authorize & Register Operator'}
                  </button>
                </>
              ) : (
                <>
                  <div
                    style={{
                      background: 'rgba(16, 185, 129, 0.05)',
                      border: '1px solid rgba(16, 185, 129, 0.15)',
                      borderRadius: 10,
                      padding: 12,
                      marginBottom: 16,
                      fontSize: '0.72rem',
                      lineHeight: '1.4',
                      color: 'var(--accent-success)',
                    }}
                  >
                    🚀 <strong>Root Bootstrapping Mode:</strong> No administrator account currently exists in the environment database. The first registered user will automatically be created with the <strong>Administrator (Root)</strong> role.
                  </div>

                  <button
                    type="submit"
                    className="btn btn-success"
                    disabled={loading}
                    style={{ width: '100%', padding: '11px', fontWeight: 600, fontSize: '0.85rem' }}
                  >
                    {loading ? 'Registering Admin...' : 'Initialize Root Administrator'}
                  </button>
                </>
              )}
            </form>
          )}

          {/* Quick Fill Profile Section */}
          <div
            style={{
              marginTop: 24,
              paddingTop: 18,
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            }}
          >
            <span
              style={{
                display: 'block',
                fontSize: '0.68rem',
                fontWeight: 800,
                color: 'var(--text-secondary)',
                marginBottom: 10,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Demo Operator Profiles (Click to Auto-fill)
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { label: 'System Admin', email: 'admin@aios', pass: 'admin123', badgeClass: 'badge-danger' },
                { label: 'Control Operator', email: 'operator@aios', pass: 'operator123', badgeClass: 'badge-primary' },
                { label: 'Read-only Viewer', email: 'viewer@aios', pass: 'viewer123', badgeClass: 'badge-purple' },
              ].map((prof) => (
                <button
                  key={prof.email}
                  type="button"
                  onClick={() => handleQuickFill(prof.email, prof.pass)}
                  style={{
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid rgba(255,255,255,0.04)',
                    padding: '8px 10px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all var(--transition-fast)',
                    textAlign: 'left',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                    e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.2)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.04)';
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {prof.label}
                    </span>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                      {prof.email}
                    </span>
                  </div>
                  <span className={`badge ${prof.badgeClass}`} style={{ fontSize: '0.6rem', padding: '2px 6px' }}>
                    Quick Sign In
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right Column: AIOS Project Promotion Page */}
      <div className="animate-fade-in-right" style={{ width: '100%', color: 'var(--text-primary)' }}>
        <div style={{ marginBottom: 28 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(139, 92, 246, 0.1)',
              border: '1px solid rgba(139, 92, 246, 0.2)',
              padding: '6px 12px',
              borderRadius: 99,
              fontSize: '0.72rem',
              fontWeight: 600,
              color: 'var(--accent-purple)',
              marginBottom: 14,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            <span className="pulsing-dot-green" style={{ background: 'var(--accent-purple)', boxShadow: '0 0 6px var(--accent-purple)' }} />
            Active Research Prototype
          </div>
          
          <h1
            style={{
              fontSize: '2.5rem',
              fontWeight: 850,
              lineHeight: 1.15,
              marginBottom: 12,
              letterSpacing: '-0.03em',
              color: '#ffffff',
            }}
          >
            AIOS: AI-Native Operating System
          </h1>
          
          <p style={{ fontSize: '0.95rem', color: 'var(--text-primary)', lineHeight: '1.6', margin: 0 }}>
            Integrating a localized AI agent directly into system spaces to transform static kernel structures into proactive, self-healing architectures.
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="metrics-grid">
          {[
            { label: 'System Status', value: '100% Active', sub: 'Telemetry Heartbeat', color: 'var(--accent-success)' },
            { label: 'Memory RAG Store', value: '601 Vectors', sub: 'FAISS + MongoDB Atlas', color: 'var(--accent-primary)' },
            { label: 'Remediation Conf.', value: '94.2%', sub: 'cgroups confidence', color: 'var(--accent-purple)' },
            { label: 'Evaluation Latency', value: '45 ms', sub: 'Real-time actions', color: 'var(--accent-teal)' },
            { label: 'WSL Hardening', value: 'Enforced', sub: 'Host Isolated folder', color: 'var(--accent-warning)' },
            { label: 'Test Suite Coverage', value: '56 / 56', sub: 'pytest verified (100%)', color: '#ec4899' },
          ].map((m) => (
            <div key={m.label} className="metric-card-promo">
              <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {m.label}
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 800, color: m.color, letterSpacing: '-0.02em' }}>
                {m.value}
              </span>
              <span style={{ fontSize: '0.62rem', color: 'var(--text-dim)' }}>
                {m.sub}
              </span>
            </div>
          ))}
        </div>

        {/* Info Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Card 1 */}
          <div className="info-card-promo">
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'var(--accent-primary-dim)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-primary)',
                flexShrink: 0,
              }}
            >
              <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2" />
              </svg>
            </div>
            <div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                Autonomous Telemetry Monitoring
              </h4>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                A background Python daemon continuously listens to WSL telemetry logs (CPU exhaustion, RAM usage, storage logs) and computes health metrics.
              </p>
            </div>
          </div>

          {/* Card 2 */}
          <div className="info-card-promo">
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'var(--accent-teal-dim)',
                border: '1px solid rgba(20, 184, 166, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-teal)',
                flexShrink: 0,
              }}
            >
              <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                Hybrid RAG Memory Architecture
              </h4>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                Combines high-density vector search (FAISS) for exact diagnostic logs matching with cloud MongoDB Atlas to index mitigation histories.
              </p>
            </div>
          </div>

          {/* Card 3 */}
          <div className="info-card-promo">
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'var(--accent-purple-dim)',
                border: '1px solid rgba(139, 92, 246, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-purple)',
                flexShrink: 0,
              }}
            >
              <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                cgroups Hardening & Self-Healing
              </h4>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                Enforces sandboxed Linux cgroup limits, automatically manages process niceness, and handles log rotation when directories exceed thresholds.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Dashboard Component ──────────────────────────────────────────────────────

function DashboardContent() {
  const { user, logout } = useAuth();
  const [streamingTokens, setStreamingTokens] = useState('');
  const [intent, setIntent] = useState<Record<string, unknown> | null>(null);
  const [validationStatus, setValidationStatus] = useState<string | null>(null);
  const [validationIntentId, setValidationIntentId] = useState<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [ragChunks, setRagChunks] = useState<RagChunk[]>([]);
  const [wsMetrics, setWsMetrics] = useState<MetricsData | undefined>(undefined);
  const [isStreaming, setIsStreaming] = useState(false);

  // Setup live WebSocket handlers
  const { connected } = useWebSocket('/stream', {
    token: (data) => {
      if (data.token && typeof data.token === 'string') {
        setStreamingTokens((prev) => prev + data.token);
      }
    },
    stream_done: (data) => {
      if (typeof data.latency_ms === 'number') {
        setLatencyMs(data.latency_ms);
        setIsStreaming(false);
      }
    },
    intent_parsed: (data) => {
      if (data.intent && typeof data.intent === 'object') {
        setIntent(data.intent as Record<string, unknown>);
      }
    },
    validation_result: (data) => {
      if (typeof data.result === 'string') {
        setValidationStatus(data.result);
      }
      if (typeof data.intent_id === 'number') {
        setValidationIntentId(data.intent_id);
      }
    },
    rag_retrieved: (data) => {
      if (Array.isArray(data.chunks)) {
        setRagChunks(data.chunks as RagChunk[]);
      }
    },
    metrics_update: (data) => {
      const metricsPayload = data.metrics ? data.metrics : data;
      const { type: _, ...metrics } = metricsPayload as Record<string, unknown>;
      setWsMetrics(metrics as unknown as MetricsData);
    },
  });

  const handleQueryId = (_id: string) => {
    setStreamingTokens('');
    setIntent(null);
    setValidationStatus(null);
    setValidationIntentId(null);
    setLatencyMs(null);
    setRagChunks([]);
  };

  const handleApprove = (_intentId: number) => {
    setValidationStatus('APPROVED');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--bg-primary)',
        color: 'var(--text-primary)',
        paddingTop: 68, // Account for fixed ServiceHealthBar
        paddingBottom: 40,
        boxSizing: 'border-box',
      }}
    >
      {/* Top Health Status Bar */}
      <ServiceHealthBar />

      {/* Header / Nav */}
      <header
        style={{
          maxWidth: 1400,
          margin: '0 auto 24px',
          padding: '0 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
            AI-Native Operating System Control Panel
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
            Telemetry Monitoring, Real-time RAG Context & Control Plane Decision Gate
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* WS status */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: '0.72rem',
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: connected ? 'var(--accent-success)' : 'var(--accent-danger)',
                boxShadow: connected ? '0 0 6px var(--accent-success)' : 'none',
              }}
            />
            <span style={{ color: 'var(--text-secondary)' }}>
              {connected ? 'WS CONNECTED' : 'WS DISCONNECTED'}
            </span>
          </div>

          {/* User info */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: '0.72rem',
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>OPERATOR:</span>
            <span style={{ fontWeight: 600 }}>{user?.sub}</span>
            <span className="badge badge-info" style={{ fontSize: '0.62rem', padding: '1px 6px' }}>
              {user?.role}
            </span>
          </div>

          <button
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.72rem' }}
            onClick={logout}
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <main
        style={{
          maxWidth: 1400,
          margin: '0 auto',
          padding: '0 20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(600px, 1fr))',
          gap: 24,
          boxSizing: 'border-box',
        }}
      >
        {/* Left Column: Interactivity */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <QueryForm
            onQueryId={(id) => {
              handleQueryId(id);
              setIsStreaming(true);
            }}
            onTokenReceived={(tok) => setStreamingTokens((p) => p + tok)}
            isStreaming={isStreaming}
            setIsStreaming={setIsStreaming}
          />
          <ReasoningTrace
            streamingTokens={streamingTokens}
            intent={intent}
            validationStatus={validationStatus}
            validationIntentId={validationIntentId}
            latencyMs={latencyMs}
            onApprove={handleApprove}
          />
          <RAGViewer chunks={ragChunks} />
        </div>

        {/* Right Column: Dashboards / Auditing */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <MetricsPanel wsMetrics={wsMetrics} wsConnected={connected} />
          <AuditLog />
        </div>
      </main>
    </div>
  );
}

// ─── Auth Gate wrapper ────────────────────────────────────────────────────────

function AuthGate() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <DashboardContent /> : <LoginPanel />;
}

function Footer() {
  return (
    <footer className="global-footer">
      <div className="creator-sign">
        Made with <span className="heart-pulse">❤️</span> by{' '}
        <a
          href="https://github.com/anan5093"
          target="_blank"
          rel="noopener noreferrer"
          className="creator-name"
        >
          Anand Raj
        </a>
      </div>
      
      <div className="social-links">
        <a href="mailto:anand.ar1806@gmail.com" className="social-icon-btn" title="Email Anand Raj">
          <svg width="15" height="15" fill="currentColor" viewBox="0 0 24 24">
            <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
          </svg>
        </a>
        <a href="https://github.com/anan5093" target="_blank" rel="noopener noreferrer" className="social-icon-btn" title="GitHub Profile">
          <svg width="15" height="15" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.138 20.161 22 16.416 22 12c0-5.523-4.477-10-10-10z"/>
          </svg>
        </a>
        <a href="https://www.linkedin.com/in/anand-raj-006a41217/" target="_blank" rel="noopener noreferrer" className="social-icon-btn" title="LinkedIn Profile">
          <svg width="15" height="15" fill="currentColor" viewBox="0 0 24 24">
            <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.779-1.75-1.75s.784-1.75 1.75-1.75 1.75.779 1.75 1.75-.784 1.75-1.75 1.75zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
          </svg>
        </a>
        <a href="https://medium.com/@anand.ar1806" target="_blank" rel="noopener noreferrer" className="social-icon-btn" title="Medium Blog">
          <svg width="15" height="15" fill="currentColor" viewBox="0 0 24 24">
            <path d="M13.54 12a6.8 6.8 0 01-6.77 6.82A6.8 6.8 0 010 12a6.8 6.8 0 016.77-6.82A6.8 6.8 0 0113.54 12zM20.96 12c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42zM24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z"/>
          </svg>
        </a>
        <a href="https://zenodo.org/me/uploads?q=&f=shared_with_me%3Afalse&l=list&p=1&s=10&sort=newest" target="_blank" rel="noopener noreferrer" className="social-icon-btn" title="Zenodo DOI Profile">
          <span style={{ fontSize: '0.72rem', fontWeight: 800, fontFamily: 'var(--font-sans)' }}>Z</span>
        </a>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-primary)' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <AuthGate />
        </div>
        <Footer />
      </div>
    </AuthProvider>
  );
}
