'use client';

import { useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function SubscribeForm({ variant = 'compact', darkBackground = true }) {
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [field, setField] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | success | duplicate | error
  const [errorMsg, setErrorMsg] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email) return;
    setStatus('loading');
    setErrorMsg('');

    try {
      const res = await fetch(`${API_URL}/api/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, company, title, field }),
      });

      if (res.ok) {
        setStatus('success');
      } else if (res.status === 409) {
        setStatus('duplicate');
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMsg(data.detail || 'Something went wrong. Please try again.');
        setStatus('error');
      }
    } catch {
      setErrorMsg('Network error. Please check your connection.');
      setStatus('error');
    }
  }

  // Success / duplicate — replace form with confirmation
  if (status === 'success' || status === 'duplicate') {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-4) 0' }}>
        <div style={{
          fontSize: '1.5rem',
          marginBottom: 'var(--space-2)',
          color: 'var(--color-accent)',
        }}>
          {status === 'success' ? '✓' : '✉'}
        </div>
        <p style={{
          fontSize: '0.9rem',
          fontWeight: 600,
          color: 'var(--color-accent)',
          marginBottom: 'var(--space-1)',
        }}>
          {status === 'success' ? "You're in!" : "You're already subscribed!"}
        </p>
        <p style={{
          fontSize: '0.78rem',
          color: darkBackground ? 'rgba(255,255,255,0.6)' : 'var(--color-text-secondary)',
          margin: 0,
        }}>
          {status === 'success'
            ? 'Check your inbox for a welcome email.'
            : 'Check your inbox for the latest briefing.'}
        </p>
      </div>
    );
  }

  const inputStyle = {
    width: '100%',
    padding: '10px 14px',
    fontSize: '0.85rem',
    background: darkBackground ? 'rgba(255,255,255,0.08)' : 'var(--color-surface)',
    border: `1px solid ${darkBackground ? 'rgba(255,255,255,0.15)' : 'var(--color-border)'}`,
    borderRadius: 'var(--radius)',
    color: darkBackground ? '#fff' : 'var(--color-text)',
    outline: 'none',
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Email row */}
      <div className="subscribe-row" style={{ display: 'flex', gap: 'var(--space-2)' }}>
        <input
          type="email"
          placeholder="Enter your email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="subscribe-input"
          style={{ ...inputStyle, flex: 1 }}
        />
        <button
          type="submit"
          disabled={status === 'loading'}
          className="btn-primary"
          style={{
            padding: '10px 20px',
            fontSize: '0.8rem',
            whiteSpace: 'nowrap',
            opacity: status === 'loading' ? 0.7 : 1,
            cursor: status === 'loading' ? 'wait' : 'pointer',
          }}
        >
          {status === 'loading' ? 'Subscribing...' : 'Subscribe Free'}
        </button>
      </div>

      {/* Optional professional fields (full variant only) */}
      {variant === 'full' && (
        <div style={{ marginTop: 'var(--space-4)' }}>
          <p style={{
            fontSize: '0.7rem',
            color: darkBackground ? 'rgba(255,255,255,0.4)' : 'var(--color-text-muted)',
            marginBottom: 'var(--space-3)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            fontWeight: 600,
          }}>
            Optional — Help us personalize your briefing
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
            <input
              placeholder="Company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="subscribe-input"
              style={inputStyle}
            />
            <input
              placeholder="Job Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="subscribe-input"
              style={inputStyle}
            />
          </div>
          <div style={{ marginTop: 'var(--space-2)' }}>
            <select
              value={field}
              onChange={(e) => setField(e.target.value)}
              className="subscribe-input"
              style={{
                ...inputStyle,
                color: field
                  ? inputStyle.color
                  : (darkBackground ? 'rgba(255,255,255,0.4)' : 'var(--color-text-muted)'),
                appearance: 'none',
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='${darkBackground ? 'rgba(255,255,255,0.4)' : '%23666'}' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 12px center',
                paddingRight: '32px',
              }}
            >
              <option value="">Select your field</option>
              <option value="Finance / Investment Banking">Finance / Investment Banking</option>
              <option value="Asset Management">Asset Management</option>
              <option value="Government / Policy">Government / Policy</option>
              <option value="Consulting">Consulting</option>
              <option value="Defense / Intelligence">Defense / Intelligence</option>
              <option value="Journalism / Media">Journalism / Media</option>
              <option value="Academia / Research">Academia / Research</option>
              <option value="Other">Other</option>
            </select>
          </div>
        </div>
      )}

      {/* Error message */}
      {status === 'error' && (
        <p style={{
          fontSize: '0.78rem',
          color: '#e74c3c',
          marginTop: 'var(--space-2)',
          margin: 0,
          marginTop: 'var(--space-2)',
        }}>
          {errorMsg}
        </p>
      )}

      {/* Trust line */}
      <p style={{
        fontSize: '0.7rem',
        color: darkBackground ? 'rgba(255,255,255,0.4)' : 'var(--color-text-muted)',
        margin: 0,
        marginTop: 'var(--space-2)',
      }}>
        Free forever. No spam. Unsubscribe anytime.
      </p>
    </form>
  );
}
