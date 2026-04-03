'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getCountryName, getFlag } from '@/lib/countries';

// Client-side: use relative URL so Next.js rewrites proxy to backend
const API_URL = '';

// Continent groupings
const CONTINENTS = {
  'Middle East & North Africa': [
    'IR','IL','SA','AE','TR','EG','IQ','SY','YE','QA','JO','LB','PS','LY',
    'BH','KW','OM','TN','DZ','MA','DJ'
  ],
  'Asia-Pacific': [
    'CN','JP','IN','KR','KP','TW','PK','AU','PH','ID','VN','TH','MY','SG',
    'BD','MM','NP','LK','KH','NZ','MN','LA','BN','BT','MV','FJ','PG','WS',
    'PW','TL','HK','MO','AS','GU'
  ],
  'Europe': [
    'RU','UA','GB','FR','DE','IT','ES','PL','GR','NL','SE','NO','FI','CH',
    'AT','BE','RO','HU','CZ','DK','PT','IE','BG','HR','RS','SK','LT','LV',
    'EE','GE','AZ','AM','BY','MT','CY','LU','IS','BA','AL','VA','GL'
  ],
  'Americas': [
    'US','CA','BR','MX','AR','CO','VE','CL','PE','CU','EC','BO','PY','UY',
    'CR','PA','GT','DO','SV','NI','HT','JM','TT','BM','KY','VC'
  ],
  'Africa': [
    'NG','ZA','ET','SD','KE','LY','TZ','MZ','GH','CM','SN','ML','SO','SS',
    'UG','ZM','ZW','MG','BF','BJ','BI','TD','CG','ER','GW','GM','NE','LS',
    'TG','KM','MU','SC'
  ],
};

// Reverse lookup: code → continent
const CODE_TO_CONTINENT = {};
for (const [continent, codes] of Object.entries(CONTINENTS)) {
  for (const code of codes) {
    CODE_TO_CONTINENT[code] = continent;
  }
}

export default function CountryIndexPage() {
  const [countries, setCountries] = useState([]);
  const [openContinents, setOpenContinents] = useState(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(
          `${API_URL}/articles?status=approved&days=7&sort_by=auto_approval_score&order=desc&limit=500`,
          { cache: 'no-store' }
        );
        if (!res.ok) { setLoading(false); return; }
        const data = await res.json();
        const articles = data.articles || data;

        const countryMap = {};
        for (const art of articles) {
          for (const code of (art.country_codes || [])) {
            if (!countryMap[code]) countryMap[code] = { code, count: 0 };
            countryMap[code].count++;
          }
        }

        const list = Object.values(countryMap)
          .filter(c => c.count >= 2)
          .sort((a, b) => b.count - a.count);

        setCountries(list);

        // Auto-open top 2 continents by total article count
        const continentCounts = {};
        for (const c of list) {
          const cont = CODE_TO_CONTINENT[c.code] || 'Other';
          continentCounts[cont] = (continentCounts[cont] || 0) + c.count;
        }
        const topContinents = Object.entries(continentCounts)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 2)
          .map(([name]) => name);
        setOpenContinents(new Set(topContinents));
      } catch (e) {
        console.error('Failed to load countries:', e);
      }
      setLoading(false);
    }
    load();
  }, []);

  // Group countries by continent
  const grouped = {};
  for (const country of countries) {
    const continent = CODE_TO_CONTINENT[country.code] || 'Other';
    if (!grouped[continent]) grouped[continent] = [];
    grouped[continent].push(country);
  }

  // Sort continents by total article count
  const sortedContinents = Object.entries(grouped)
    .map(([name, countries]) => ({
      name,
      countries,
      totalArticles: countries.reduce((sum, c) => sum + c.count, 0),
    }))
    .sort((a, b) => b.totalArticles - a.totalArticles);

  const toggleContinent = (name) => {
    setOpenContinents(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 var(--space-6)' }}>
      {/* Header */}
      <div style={{
        borderBottom: '3px solid var(--color-accent)',
        paddingBottom: 'var(--space-4)',
        marginBottom: 'var(--space-8)',
        marginTop: 'var(--space-6)',
      }}>
        <h1 style={{
          fontSize: 'clamp(1.8rem, 4vw, 2.5rem)',
          fontWeight: 800,
          color: 'var(--color-text-primary)',
          letterSpacing: '-0.02em',
          margin: 0,
        }}>
          Countries
        </h1>
        <p style={{
          fontSize: '0.95rem',
          color: 'var(--color-text-secondary)',
          marginTop: 'var(--space-2)',
        }}>
          Browse geopolitical intelligence by region and country
        </p>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 'var(--space-16) 0', color: 'var(--color-text-muted)' }}>
          Loading...
        </div>
      )}

      {/* Continent accordions */}
      <div style={{ marginBottom: 'var(--space-16)' }}>
        {sortedContinents.map(({ name, countries: continentCountries, totalArticles }) => {
          const isOpen = openContinents.has(name);
          return (
            <div key={name} style={{ marginBottom: 'var(--space-4)' }}>
              {/* Continent header — clickable */}
              <button
                onClick={() => toggleContinent(name)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: 'var(--space-4) var(--space-5)',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: isOpen ? 'var(--radius) var(--radius) 0 0' : 'var(--radius)',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  <span style={{
                    fontWeight: 700,
                    fontSize: '1.05rem',
                    color: 'var(--color-text-primary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}>
                    {name}
                  </span>
                  <span style={{
                    fontSize: '0.78rem',
                    color: 'var(--color-text-muted)',
                  }}>
                    {continentCountries.length} {continentCountries.length === 1 ? 'country' : 'countries'} · {totalArticles} articles
                  </span>
                </div>
                <span style={{
                  fontSize: '1.2rem',
                  color: 'var(--color-text-muted)',
                  transition: 'transform 0.2s',
                  transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                }}>
                  ▼
                </span>
              </button>

              {/* Country grid — collapsible */}
              {isOpen && (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                  gap: 'var(--space-3)',
                  padding: 'var(--space-4)',
                  border: '1px solid var(--color-border)',
                  borderTop: 'none',
                  borderRadius: '0 0 var(--radius) var(--radius)',
                }}>
                  {continentCountries.map((country) => (
                    <Link
                      key={country.code}
                      href={`/country/${country.code}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        padding: 'var(--space-3) var(--space-4)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius)',
                        textDecoration: 'none',
                        transition: 'border-color 0.15s',
                      }}
                    >
                      <span style={{ fontSize: '1.3rem' }}>{getFlag(country.code)}</span>
                      <div>
                        <div style={{
                          fontWeight: 700,
                          fontSize: '0.88rem',
                          color: 'var(--color-text-primary)',
                        }}>
                          {getCountryName(country.code)}
                        </div>
                        <div style={{
                          fontSize: '0.72rem',
                          color: 'var(--color-text-muted)',
                        }}>
                          {country.count} {country.count === 1 ? 'article' : 'articles'}
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!loading && countries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 'var(--space-16) 0', color: 'var(--color-text-muted)' }}>
          <p>No country data available yet. Articles will appear once the scraper runs.</p>
        </div>
      )}
    </div>
  );
}
