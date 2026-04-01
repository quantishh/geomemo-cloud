'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

const navLinks = [
  { href: '/', label: 'Home' },
  { href: '/country', label: 'Countries' },
  { href: '/about', label: 'About' },
  { href: '/events', label: 'Events' },
  { href: '/archive', label: 'Archive' },
  { href: '/advertise', label: 'Advertise' },
  { href: 'https://monitor.geomemo.news', label: 'Monitor', external: true },
];

export default function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    const saved = document.documentElement.getAttribute('data-theme');
    if (saved === 'dark') setTheme('dark');
  }, []);

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  };

  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      background: 'var(--color-bg)',
      borderBottom: '1px solid var(--color-border)',
      height: 'var(--header-height)',
    }}>
      <div className="container" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '100%',
      }}>
        {/* Logo — theme-aware SVG */}
        <Link href="/" style={{ display: 'flex', alignItems: 'center', textDecoration: 'none' }}>
          {theme === 'dark' ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="160" height="45">
              <rect x="120" y="5" width="190" height="80" rx="6" fill="transparent" stroke="#E2C26D" strokeWidth="6"/>
              <line x1="120" y1="22" x2="310" y2="22" stroke="#E2C26D" strokeWidth="3"/>
              <line x1="120" y1="68" x2="310" y2="68" stroke="#E2C26D" strokeWidth="3"/>
              <text x="220" y="61" textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight="800" fontSize="52" fill="#FFFFFF" letterSpacing="-2">memo</text>
              <rect x="5" y="5" width="130" height="80" rx="6" fill="#E2C26D"/>
              <line x1="5" y1="22" x2="135" y2="22" stroke="#161625" strokeWidth="3"/>
              <line x1="5" y1="68" x2="135" y2="68" stroke="#161625" strokeWidth="3"/>
              <text x="70" y="61" textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight="800" fontSize="52" fill="#161625" letterSpacing="-2">Geo</text>
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 90" width="160" height="45">
              <rect x="120" y="5" width="190" height="80" rx="6" fill="#FFFFFF" stroke="#161625" strokeWidth="6"/>
              <line x1="120" y1="22" x2="310" y2="22" stroke="#161625" strokeWidth="3"/>
              <line x1="120" y1="68" x2="310" y2="68" stroke="#161625" strokeWidth="3"/>
              <text x="220" y="61" textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight="800" fontSize="52" fill="#161625" letterSpacing="-2">memo</text>
              <rect x="5" y="5" width="130" height="80" rx="6" fill="#161625"/>
              <line x1="5" y1="22" x2="135" y2="22" stroke="#E2C26D" strokeWidth="3"/>
              <line x1="5" y1="68" x2="135" y2="68" stroke="#E2C26D" strokeWidth="3"/>
              <text x="70" y="61" textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight="800" fontSize="52" fill="#FFFFFF" letterSpacing="-2">Geo</text>
            </svg>
          )}
        </Link>

        {/* Desktop Nav */}
        <nav style={{
          display: 'flex',
          alignItems: 'center',
          gap: '28px',
        }} className="desktop-nav">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return link.external ? (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  color: 'var(--color-text-secondary)',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={(e) => e.target.style.color = 'var(--color-accent)'}
                onMouseLeave={(e) => e.target.style.color = 'var(--color-text-secondary)'}
              >
                {link.label}
              </a>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                style={{
                  fontSize: '0.875rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--color-text)' : 'var(--color-text-secondary)',
                  borderBottom: isActive ? '2px solid var(--color-accent)' : '2px solid transparent',
                  paddingBottom: '4px',
                  transition: 'color 0.15s, border-color 0.15s',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.target.style.color = 'var(--color-accent)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.target.style.color = 'var(--color-text-secondary)';
                }}
              >
                {link.label}
              </Link>
            );
          })}
          <button
            onClick={toggleTheme}
            className="theme-toggle"
            aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
            title={theme === 'light' ? 'Dark mode' : 'Light mode'}
          >
            {theme === 'light' ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            )}
          </button>
          <Link href="/newsletter" className="btn-primary" style={{
            padding: '8px 20px',
            fontSize: '0.8rem',
          }}>
            Subscribe
          </Link>
        </nav>

        {/* Mobile Hamburger */}
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
          style={{
            display: 'none',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '8px',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-text)" strokeWidth="2">
            {mobileOpen ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="mobile-drawer" style={{
          position: 'fixed',
          top: 'var(--header-height)',
          left: 0,
          right: 0,
          bottom: 0,
          background: 'var(--color-bg)',
          zIndex: 99,
          padding: 'var(--space-6)',
          borderTop: '1px solid var(--color-border)',
        }}>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              const El = link.external ? 'a' : Link;
              const extraProps = link.external ? { target: '_blank', rel: 'noopener noreferrer' } : {};
              return (
                <El
                  key={link.href}
                  href={link.href}
                  {...extraProps}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: isActive ? 700 : 500,
                    color: isActive ? 'var(--color-text)' : 'var(--color-text-secondary)',
                    paddingBottom: '12px',
                    borderBottom: '1px solid var(--color-border)',
                  }}
                >
                  {link.label}
                </El>
              );
            })}
            <button
              onClick={toggleTheme}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 0',
                background: 'none',
                border: 'none',
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                fontSize: '1.1rem',
                fontWeight: 500,
                color: 'var(--color-text-secondary)',
              }}
            >
              {theme === 'light' ? (
                <>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                  </svg>
                  Dark Mode
                </>
              ) : (
                <>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="5"/>
                    <line x1="12" y1="1" x2="12" y2="3"/>
                    <line x1="12" y1="21" x2="12" y2="23"/>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                    <line x1="1" y1="12" x2="3" y2="12"/>
                    <line x1="21" y1="12" x2="23" y2="12"/>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                  </svg>
                  Light Mode
                </>
              )}
            </button>
            <Link
              href="/newsletter"
              className="btn-primary"
              onClick={() => setMobileOpen(false)}
              style={{ textAlign: 'center', marginTop: '8px' }}
            >
              Subscribe to Newsletter
            </Link>
          </nav>
        </div>
      )}

      <style jsx global>{`
        @media (max-width: 768px) {
          .desktop-nav { display: none !important; }
          .mobile-menu-btn { display: block !important; }
        }
      `}</style>
    </header>
  );
}
