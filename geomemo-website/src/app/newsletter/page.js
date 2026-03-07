export const metadata = {
  title: 'Subscribe — GeoMemo',
  description: 'Subscribe to the GeoMemo daily geopolitical intelligence briefing.',
};

export default function NewsletterPage() {
  return (
    <>
      {/* Hero */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-16) 0 var(--space-12)',
        textAlign: 'center',
      }}>
        <div className="container" style={{ maxWidth: '640px' }}>
          <p style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--color-accent)',
            marginBottom: 'var(--space-3)',
          }}>
            Daily Briefing
          </p>
          <h1 style={{
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            marginBottom: 'var(--space-4)',
          }}>
            Geopolitical intelligence,<br />
            <span style={{ color: 'var(--color-accent)' }}>delivered daily</span>
          </h1>
          <p style={{
            fontSize: '1rem',
            color: 'rgba(255,255,255,0.65)',
            lineHeight: 1.7,
            marginBottom: 'var(--space-8)',
          }}>
            Join professionals who rely on GeoMemo for concise, actionable intelligence on the geopolitical events shaping markets and policy.
          </p>

          {/* Beehiiv Signup Form */}
          <div style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-8)',
            maxWidth: '440px',
            margin: '0 auto',
          }}>
            <iframe
              src="https://embeds.beehiiv.com/f5b23597-6d09-4708-a9af-2b21e5e58e32?slim=true"
              data-test-id="beehiiv-embed"
              height="52"
              frameBorder="0"
              scrolling="no"
              style={{
                width: '100%',
                border: 'none',
                borderRadius: 'var(--radius)',
                marginBottom: 'var(--space-3)',
              }}
            />
            <p style={{
              fontSize: '0.75rem',
              color: 'rgba(255,255,255,0.4)',
              margin: 0,
            }}>
              Free forever. No spam. Unsubscribe anytime.
            </p>
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="section">
        <div className="container" style={{ maxWidth: '720px' }}>
          <h2 style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            textAlign: 'center',
            marginBottom: 'var(--space-8)',
          }}>
            What you get
          </h2>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--space-6)',
          }}>
            {[
              { icon: '📰', title: 'Daily Briefing', desc: '60-80 curated stories organized by category, delivered every evening.' },
              { icon: '🔍', title: 'Analytical Summaries', desc: 'Concise, wire-style summaries written for investment professionals.' },
              { icon: '🌍', title: 'Global Coverage', desc: '250+ sources across 50+ countries, covering all major regions.' },
              { icon: '📊', title: 'Market Context', desc: 'Every story framed through its impact on markets and policy.' },
            ].map((item) => (
              <div key={item.title} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>{item.icon}</div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
                  {item.title}
                </h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', lineHeight: 1.6, margin: 0 }}>
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
