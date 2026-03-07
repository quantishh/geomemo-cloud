import Link from 'next/link';

export default function Footer() {
  return (
    <footer style={{
      background: 'var(--color-primary)',
      color: 'var(--color-text-inverse)',
      paddingTop: 'var(--space-12)',
      paddingBottom: 'var(--space-8)',
    }}>
      <div className="container">
        {/* Main footer grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 'var(--space-10)',
          paddingBottom: 'var(--space-10)',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          {/* Brand column */}
          <div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              marginBottom: 'var(--space-4)',
            }}>
              <div style={{
                background: 'var(--color-accent)',
                color: 'var(--color-primary)',
                fontWeight: 800,
                fontSize: '1rem',
                padding: '5px 10px',
                borderRadius: 'var(--radius-sm)',
              }}>
                GM
              </div>
              <span style={{ fontWeight: 700, fontSize: '1.15rem' }}>GeoMemo</span>
            </div>
            <p style={{
              fontSize: '0.85rem',
              color: 'rgba(255,255,255,0.6)',
              lineHeight: 1.7,
              maxWidth: '300px',
            }}>
              Geopolitical intelligence for global decision makers. Daily briefings on conflicts, trade, markets, and policy.
            </p>
            {/* Social icons */}
            <div style={{
              display: 'flex',
              gap: 'var(--space-4)',
              marginTop: 'var(--space-5)',
            }}>
              {[
                { label: 'X', href: 'https://x.com/geomemonews' },
                { label: 'TG', href: 'https://t.me/geomemonews' },
                { label: 'LI', href: 'https://linkedin.com/company/geomemo' },
              ].map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="footer-social"
                >
                  {social.label}
                </a>
              ))}
            </div>
          </div>

          {/* Navigation column */}
          <div>
            <h4 style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--color-accent)',
              marginBottom: 'var(--space-4)',
            }}>
              Navigation
            </h4>
            <nav style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-3)',
            }}>
              {[
                { href: '/', label: 'Home' },
                { href: '/about', label: 'About' },
                { href: '/events', label: 'Events' },
                { href: '/archive', label: 'Archive' },
                { href: '/newsletter', label: 'Newsletter' },
                { href: '/advertise', label: 'Advertise' },
              ].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="footer-link"
                  style={{ fontSize: '0.875rem' }}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>

          {/* Newsletter column */}
          <div>
            <h4 style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--color-accent)',
              marginBottom: 'var(--space-4)',
            }}>
              Daily Briefing
            </h4>
            <p style={{
              fontSize: '0.85rem',
              color: 'rgba(255,255,255,0.6)',
              lineHeight: 1.7,
              marginBottom: 'var(--space-4)',
            }}>
              Get the top geopolitical stories delivered to your inbox every evening.
            </p>
            <Link
              href="/newsletter"
              className="footer-cta"
            >
              Subscribe Free
            </Link>
          </div>
        </div>

        {/* Bottom bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: 'var(--space-6)',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}>
          <p style={{
            fontSize: '0.75rem',
            color: 'rgba(255,255,255,0.4)',
          }}>
            &copy; {new Date().getFullYear()} GeoMemo. All rights reserved.
          </p>
          <div style={{
            display: 'flex',
            gap: 'var(--space-6)',
          }}>
            <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>
              Privacy
            </span>
            <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>
              Terms
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
