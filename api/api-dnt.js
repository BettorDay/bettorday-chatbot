// ══════════════════════════════════════════════════════════════
// Dunks & Threes proxy: RETIRED (410 Gone)
//
// Nothing of ours calls this since the NBA Game Center takedown
// (bettorday-app d8156e8, OTA confirmed 2026-09-29). It was open to
// any origin (CORS fallback "*"), so anyone could pull D&T API data
// through our key. It now answers 410 for every request and never
// contacts dunksandthrees.com or reads DNT_API_KEY.
//
// Do not restore a browser-facing proxy. If a D&T agreement ever
// lands, pull server-side in the NBA-HQ pipeline instead.
// ══════════════════════════════════════════════════════════════

export default function handler(req, res) {
    res.setHeader('Cache-Control', 'public, s-maxage=86400');
    return res.status(410).json({ error: 'Gone' });
}
