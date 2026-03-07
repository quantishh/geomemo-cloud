import Link from 'next/link';

export const metadata = {
  title: 'Advertise — GeoMemo',
  description: 'Reach investment bankers, asset managers, and policymakers through GeoMemo advertising.',
};

const products = [
  {
    name: 'Sponsor Posts',
    description: 'Branded content placed directly in the GeoMemo news feed alongside editorial articles. Your message reaches professionals as they scan the day\'s intelligence.',
    placement: 'Homepage news feed',
    audience: 'All site visitors',
    icon: '📰',
  },
  {
    name: 'Newsletter Sponsorship',
    description: 'A premium banner position in the daily GeoMemo newsletter, delivered to subscriber inboxes every evening. High open rates from an engaged professional audience.',
    placement: 'Daily email newsletter',
    audience: 'All subscribers',
    icon: '✉',
  },
  {
    name: 'Featured Podcast',
    description: 'Your podcast featured on the GeoMemo homepage with a dedicated player card. Reach an audience actively seeking geopolitical analysis and commentary.',
    placement: 'Homepage podcast section',
    audience: 'All site visitors',
    icon: '🎙',
  },
  {
    name: 'Event Listing',
    description: 'Promote your conference, summit, or event on the GeoMemo Events calendar. Reach professionals planning their geopolitical engagement calendar.',
    placement: 'Events page',
    audience: 'Event-interested professionals',
    icon: '📅',
  },
];

const audienceStats = [
  { label: 'Global Sources', value: '250+', note: 'RSS feeds monitored daily' },
  { label: 'Categories', value: '6', note: 'Areas of geopolitical coverage' },
  { label: 'Countries', value: '50+', note: 'Worldwide source coverage' },
  { label: 'Daily Briefings', value: '7 days', note: 'Consistent daily delivery' },
];

export default function AdvertisePage() {
  return (
    <>
      {/* Hero */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-16) 0 var(--space-12)',
        textAlign: 'center',
      }}>
        <div className="container">
          <p style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--color-accent)',
            marginBottom: 'var(--space-3)',
          }}>
            Partnerships
          </p>
          <h1 style={{
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            marginBottom: 'var(--space-4)',
          }}>
            Advertise with <span style={{ color: 'var(--color-accent)' }}>GeoMemo</span>
          </h1>
          <p style={{
            fontSize: '1.05rem',
            color: 'rgba(255,255,255,0.65)',
            maxWidth: '580px',
            margin: '0 auto',
            lineHeight: 1.7,
          }}>
            Reach investment bankers, asset managers, and policymakers who rely on GeoMemo for daily geopolitical intelligence.
          </p>
        </div>
      </section>

      {/* Audience stats */}
      <section className="section" style={{ background: 'var(--color-surface)' }}>
        <div className="container">
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--space-5)',
            maxWidth: '900px',
            margin: '0 auto',
          }}>
            {audienceStats.map((stat) => (
              <div key={stat.label} style={{
                textAlign: 'center',
                padding: 'var(--space-5)',
              }}>
                <div style={{
                  fontSize: '2rem',
                  fontWeight: 800,
                  color: 'var(--color-accent)',
                  lineHeight: 1,
                  marginBottom: 'var(--space-2)',
                }}>
                  {stat.value}
                </div>
                <div style={{
                  fontSize: '0.9rem',
                  fontWeight: 700,
                  color: 'var(--color-text)',
                  marginBottom: '2px',
                }}>
                  {stat.label}
                </div>
                <div style={{
                  fontSize: '0.75rem',
                  color: 'var(--color-text-muted)',
                }}>
                  {stat.note}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Our audience */}
      <section className="section">
        <div className="container" style={{ maxWidth: '720px' }}>
          <div className="accent-bar" style={{ marginBottom: 'var(--space-5)' }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-4)' }}>
            Our Audience
          </h2>
          <p style={{
            fontSize: '1rem',
            color: 'var(--color-text-secondary)',
            lineHeight: 1.8,
            marginBottom: 'var(--space-5)',
          }}>
            GeoMemo readers are professionals who need geopolitical awareness to make better decisions. They include:
          </p>
          <ul style={{
            listStyle: 'none',
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
          }}>
            {[
              'Investment bankers and portfolio managers',
              'Hedge fund analysts and traders',
              'Government affairs and policy advisors',
              'Corporate strategy teams at multinationals',
              'Risk and compliance professionals',
              'Defense and intelligence analysts',
            ].map((item) => (
              <li key={item} style={{
                fontSize: '0.95rem',
                color: 'var(--color-text)',
                paddingLeft: 'var(--space-5)',
                position: 'relative',
                lineHeight: 1.6,
              }}>
                <span style={{
                  position: 'absolute',
                  left: 0,
                  color: 'var(--color-accent)',
                  fontWeight: 700,
                }}>
                  —
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Ad products */}
      <section className="section" style={{ background: 'var(--color-surface)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
              Advertising Products
            </h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.95rem' }}>
              Multiple touchpoints to reach geopolitical professionals.
            </p>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--space-5)',
            maxWidth: '1000px',
            margin: '0 auto',
          }}>
            {products.map((product) => (
              <div key={product.name} style={{
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius)',
                padding: 'var(--space-6)',
                display: 'flex',
                flexDirection: 'column',
                transition: 'border-color 0.15s',
              }}>
                <div style={{ fontSize: '1.5rem', marginBottom: 'var(--space-3)' }}>
                  {product.icon}
                </div>
                <h3 style={{
                  fontSize: '1.1rem',
                  fontWeight: 700,
                  marginBottom: 'var(--space-3)',
                }}>
                  {product.name}
                </h3>
                <p style={{
                  fontSize: '0.85rem',
                  color: 'var(--color-text-secondary)',
                  lineHeight: 1.7,
                  marginBottom: 'var(--space-4)',
                  flex: 1,
                }}>
                  {product.description}
                </p>
                <div style={{
                  fontSize: '0.75rem',
                  color: 'var(--color-text-muted)',
                  borderTop: '1px solid var(--color-border)',
                  paddingTop: 'var(--space-3)',
                }}>
                  <div style={{ marginBottom: '4px' }}>
                    <strong style={{ color: 'var(--color-text-secondary)' }}>Placement:</strong> {product.placement}
                  </div>
                  <div>
                    <strong style={{ color: 'var(--color-text-secondary)' }}>Reach:</strong> {product.audience}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact CTA */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-16) 0',
        textAlign: 'center',
      }}>
        <div className="container" style={{ maxWidth: '600px' }}>
          <h2 style={{
            fontSize: 'clamp(1.25rem, 3vw, 1.75rem)',
            fontWeight: 700,
            marginBottom: 'var(--space-4)',
          }}>
            Ready to reach global decision makers?
          </h2>
          <p style={{
            fontSize: '0.95rem',
            color: 'rgba(255,255,255,0.6)',
            marginBottom: 'var(--space-6)',
            lineHeight: 1.7,
          }}>
            Get in touch to discuss advertising opportunities, sponsorship packages, and custom partnerships.
          </p>
          <a
            href="mailto:advertise@geomemo.news"
            className="btn-primary"
            style={{
              padding: '14px 36px',
              fontSize: '0.95rem',
            }}
          >
            Contact Us
          </a>
          <p style={{
            marginTop: 'var(--space-4)',
            fontSize: '0.8rem',
            color: 'rgba(255,255,255,0.4)',
          }}>
            advertise@geomemo.news
          </p>
        </div>
      </section>
    </>
  );
}
