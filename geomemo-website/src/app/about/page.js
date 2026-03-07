import Link from 'next/link';

export const metadata = {
  title: 'About — GeoMemo',
  description: 'About GeoMemo — Geopolitical intelligence for global decision makers.',
};

const categories = [
  { name: 'Geopolitical Conflict', icon: '⚔', description: 'Wars, civil wars, terrorism, defense pacts and military alliances.' },
  { name: 'Geopolitical Politics', icon: '🏛', description: 'National elections, diplomatic tensions, leadership changes and policy shifts.' },
  { name: 'Geopolitical Economics', icon: '📊', description: 'Trade wars, sanctions, economic pacts, BRICS, EU developments.' },
  { name: 'Global Markets', icon: '📈', description: 'Major stock, commodity, and currency moves driven by policy.' },
  { name: 'Natural Disasters', icon: '🌍', description: 'Major climate disasters with international aid or geopolitical impact.' },
  { name: 'Local with Global Impact', icon: '🔗', description: 'Local events with significant international implications.' },
];

export default function AboutPage() {
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
            About
          </p>
          <h1 style={{
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            marginBottom: 'var(--space-4)',
          }}>
            The Bloomberg of <span style={{ color: 'var(--color-accent)' }}>Geopolitics</span>
          </h1>
          <p style={{
            fontSize: '1.05rem',
            color: 'rgba(255,255,255,0.65)',
            maxWidth: '600px',
            margin: '0 auto',
            lineHeight: 1.7,
          }}>
            GeoMemo delivers daily geopolitical intelligence for investment bankers, asset managers, and policymakers who need to understand how global events impact markets and policy.
          </p>
        </div>
      </section>

      {/* Mission */}
      <section className="section">
        <div className="container" style={{ maxWidth: '720px' }}>
          <div className="accent-bar" style={{ marginBottom: 'var(--space-5)' }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-4)' }}>
            Our Mission
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--color-text-secondary)', lineHeight: 1.8 }}>
            In a world where geopolitical events move markets, shift alliances, and reshape industries overnight, professionals need a reliable, concise source of intelligence. GeoMemo curates and analyzes the most significant geopolitical developments from 250+ global sources, delivering actionable insights to your inbox every day.
          </p>
        </div>
      </section>

      {/* What We Cover */}
      <section className="section" style={{ background: 'var(--color-surface)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 'var(--space-10)' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
              What We Cover
            </h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.95rem' }}>
              Six categories of geopolitical intelligence, curated daily.
            </p>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 'var(--space-5)',
          }}>
            {categories.map((cat) => (
              <div key={cat.name} style={{
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius)',
                padding: 'var(--space-6)',
                transition: 'border-color 0.15s',
              }}>
                <div style={{ fontSize: '1.5rem', marginBottom: 'var(--space-3)' }}>{cat.icon}</div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
                  {cat.name}
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', lineHeight: 1.6, margin: 0 }}>
                  {cat.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="section">
        <div className="container" style={{ maxWidth: '720px' }}>
          <div className="accent-bar" style={{ marginBottom: 'var(--space-5)' }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-4)' }}>
            Our Methodology
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
            {[
              { step: '01', title: 'Aggregate', desc: 'We monitor 250+ RSS feeds from leading global news sources across 50+ countries, in multiple languages.' },
              { step: '02', title: 'Classify', desc: 'AI-powered classification scores each article for geopolitical relevance, filtering thousands down to the most impactful stories.' },
              { step: '03', title: 'Curate', desc: 'Our editorial team reviews, clusters related coverage, and selects the 60-80 most significant stories of the day.' },
              { step: '04', title: 'Deliver', desc: 'A structured daily briefing arrives in your inbox every evening, organized by category with concise analytical summaries.' },
            ].map((item) => (
              <div key={item.step} style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'flex-start' }}>
                <span style={{
                  fontWeight: 800,
                  fontSize: '0.85rem',
                  color: 'var(--color-accent)',
                  flexShrink: 0,
                  width: '32px',
                }}>
                  {item.step}
                </span>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '4px' }}>{item.title}</h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', lineHeight: 1.7, margin: 0 }}>
                    {item.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-12) 0',
        textAlign: 'center',
      }}>
        <div className="container">
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-3)' }}>
            Start your day with GeoMemo
          </h2>
          <p style={{ color: 'rgba(255,255,255,0.6)', marginBottom: 'var(--space-6)' }}>
            Join investment professionals and policymakers worldwide.
          </p>
          <Link href="/newsletter" className="btn-primary" style={{ padding: '14px 32px' }}>
            Subscribe Free
          </Link>
        </div>
      </section>
    </>
  );
}
