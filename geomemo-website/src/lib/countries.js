// ISO 3166-1 alpha-2 → country name mapping (comprehensive)
export const COUNTRY_NAMES = {
  AF: 'Afghanistan', AL: 'Albania', DZ: 'Algeria', AS: 'American Samoa',
  AM: 'Armenia', AR: 'Argentina', AU: 'Australia', AT: 'Austria',
  AZ: 'Azerbaijan', BH: 'Bahrain', BD: 'Bangladesh', BY: 'Belarus',
  BE: 'Belgium', BJ: 'Benin', BM: 'Bermuda', BT: 'Bhutan',
  BO: 'Bolivia', BA: 'Bosnia', BR: 'Brazil', BN: 'Brunei',
  BG: 'Bulgaria', BF: 'Burkina Faso', BI: 'Burundi', KH: 'Cambodia',
  CM: 'Cameroon', CA: 'Canada', CG: 'Congo', TD: 'Chad',
  CL: 'Chile', CN: 'China', CO: 'Colombia', KM: 'Comoros',
  CR: 'Costa Rica', HR: 'Croatia', CU: 'Cuba', CY: 'Cyprus',
  CZ: 'Czech Republic', DK: 'Denmark', DJ: 'Djibouti', DO: 'Dominican Republic',
  EC: 'Ecuador', EG: 'Egypt', SV: 'El Salvador', ER: 'Eritrea',
  EE: 'Estonia', ET: 'Ethiopia', FJ: 'Fiji', FI: 'Finland',
  FR: 'France', GE: 'Georgia', DE: 'Germany', GH: 'Ghana',
  GR: 'Greece', GL: 'Greenland', GT: 'Guatemala', GU: 'Guam',
  GW: 'Guinea-Bissau', GM: 'Gambia', HT: 'Haiti', HK: 'Hong Kong',
  HU: 'Hungary', IS: 'Iceland', IN: 'India', ID: 'Indonesia',
  IR: 'Iran', IQ: 'Iraq', IE: 'Ireland', IL: 'Israel',
  IT: 'Italy', JM: 'Jamaica', JP: 'Japan', JO: 'Jordan',
  KZ: 'Kazakhstan', KE: 'Kenya', KP: 'North Korea', KR: 'South Korea',
  KW: 'Kuwait', KY: 'Cayman Islands', LA: 'Laos', LV: 'Latvia',
  LB: 'Lebanon', LS: 'Lesotho', LR: 'Liberia', LY: 'Libya',
  LT: 'Lithuania', LU: 'Luxembourg', MO: 'Macau', MG: 'Madagascar',
  MW: 'Malawi', MY: 'Malaysia', MV: 'Maldives', ML: 'Mali',
  MT: 'Malta', MU: 'Mauritius', MX: 'Mexico', MN: 'Mongolia',
  MA: 'Morocco', MZ: 'Mozambique', MM: 'Myanmar', NP: 'Nepal',
  NL: 'Netherlands', NZ: 'New Zealand', NI: 'Nicaragua', NE: 'Niger',
  NG: 'Nigeria', NO: 'Norway', OM: 'Oman', PK: 'Pakistan',
  PA: 'Panama', PG: 'Papua New Guinea', PY: 'Paraguay', PE: 'Peru',
  PH: 'Philippines', PL: 'Poland', PT: 'Portugal', PS: 'Palestine',
  PW: 'Palau', QA: 'Qatar', RO: 'Romania', RU: 'Russia',
  SA: 'Saudi Arabia', SN: 'Senegal', RS: 'Serbia', SC: 'Seychelles',
  SG: 'Singapore', SK: 'Slovakia', SO: 'Somalia', ZA: 'South Africa',
  SS: 'South Sudan', ES: 'Spain', LK: 'Sri Lanka', SD: 'Sudan',
  SE: 'Sweden', CH: 'Switzerland', SY: 'Syria', TW: 'Taiwan',
  TZ: 'Tanzania', TH: 'Thailand', TG: 'Togo', TL: 'Timor-Leste',
  TN: 'Tunisia', TR: 'Turkey', TT: 'Trinidad and Tobago',
  UA: 'Ukraine', AE: 'UAE', GB: 'United Kingdom', US: 'United States',
  UG: 'Uganda', UY: 'Uruguay', UZ: 'Uzbekistan', VA: 'Vatican City',
  VC: 'St Vincent', VE: 'Venezuela', VN: 'Vietnam', WS: 'Samoa',
  YE: 'Yemen', ZM: 'Zambia', ZW: 'Zimbabwe',
};

// Generate flag emoji from ISO country code
// Each letter maps to a regional indicator symbol: A=🇦, B=🇧, etc.
export function getFlag(code) {
  if (!code || code.length !== 2) return '🌐';
  const upper = code.toUpperCase();
  const cp1 = 0x1F1E6 + (upper.charCodeAt(0) - 65);
  const cp2 = 0x1F1E6 + (upper.charCodeAt(1) - 65);
  return String.fromCodePoint(cp1, cp2);
}

export function getCountryName(code) {
  return COUNTRY_NAMES[code?.toUpperCase()] || code?.toUpperCase() || 'Unknown';
}
