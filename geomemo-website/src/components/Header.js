'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const navLinks = [
  { href: '/', label: 'Home' },
  { href: '/about', label: 'About' },
  { href: '/events', label: 'Events' },
  { href: '/archive', label: 'Archive' },
  { href: '/advertise', label: 'Advertise' },
  { href: 'https://monitor.geomemo.news', label: 'Monitor', external: true },
];

export default function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

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
        {/* Logo */}
        <Link href="/" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          textDecoration: 'none',
        }}>
          <div style={{
            background: 'var(--color-primary)',
            color: 'var(--color-accent)',
            fontWeight: 800,
            fontSize: '1.1rem',
            letterSpacing: '-0.03em',
            padding: '6px 12px',
            borderRadius: 'var(--radius-sm)',
          }}>
            GM
          </div>
          <span style={{
            fontWeight: 700,
            fontSize: '1.25rem',
            color: 'var(--color-primary)',
            letterSpacing: '-0.02em',
          }}>
            GeoMemo
          </span>
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
                  color: isActive ? 'var(--color-primary)' : 'var(--color-text-secondary)',
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
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" strokeWidth="2">
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
                    color: isActive ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                    paddingBottom: '12px',
                    borderBottom: '1px solid var(--color-border)',
                  }}
                >
                  {link.label}
                </El>
              );
            })}
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
