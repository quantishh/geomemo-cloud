import SubscribeForm from '@/components/SubscribeForm';

export const metadata = {
  title: 'Subscribe — GeoMemo',
  description: 'Subscribe to the GeoMemo daily geopolitical intelligence briefing.',
};

export default function NewsletterPage() {
  return (
    <>
      {/* Hero — slim */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-8) 0 var(--space-6)',
        textAlign: 'center',
      }}>
        <div className="container" style={{ maxWidth: '640px' }}>
          <p style={{
            fontSize: '0.7rem',
            fontWeight: 600,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--color-accent)',
            marginBottom: '6px',
          }}>
            Daily Briefing
          </p>
          <h1 style={{
            fontSize: 'clamp(1.3rem, 3vw, 1.75rem)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            marginBottom: 'var(--space-3)',
          }}>
            Geopolitical intelligence,{' '}
            <span style={{ color: 'var(--color-accent)' }}>delivered daily</span>
          </h1>
          <p style={{
            fontSize: '0.9rem',
            color: 'rgba(255,255,255,0.65)',
            lineHeight: 1.6,
            marginBottom: 'var(--space-6)',
          }}>
            Join professionals who rely on GeoMemo for concise, actionable intelligence on the geopolitical events shaping markets and policy.
          </p>

          {/* Beehiiv Signup Form */}
          <div style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-5)',
            maxWidth: '440px',
            margin: '0 auto',
          }}>
            <SubscribeForm variant="full" darkBackground={true} />
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="section" style={{ paddingTop: 'var(--space-8)', paddingBottom: 'var(--space-8)' }}>
        <div className="container" style={{ maxWidth: '720px' }}>
          <h2 style={{
            fontSize: '1.25rem',
            fontWeight: 700,
            textAlign: 'center',
            marginBottom: 'var(--space-6)',
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
                <div style={{ fontSize: '1.5rem', marginBottom: 'var(--space-2)' }}>{item.icon}</div>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 'var(--space-1)' }}>
                  {item.title}
                </h3>
                <p style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', lineHeight: 1.6, margin: 0 }}>
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
