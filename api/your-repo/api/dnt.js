// ══════════════════════════════════════════════════════════════
// Dunks & Threes API Proxy for BettorDay
// Deploy as: /api/dnt.js in your Vercel project
//
// This proxy:
// 1. Keeps your D&T API key server-side (never exposed to browsers)
// 2. All requests come from Vercel's single server IP
// 3. Adds caching headers to reduce API calls
// 4. Restricts access to your BettorDay domain
// ══════════════════════════════════════════════════════════════

// ⚠️ SET YOUR API KEY HERE (or better: use Vercel Environment Variables)
// In Vercel dashboard: Settings > Environment Variables > Add DNT_API_KEY
const DNT_API_KEY = process.env.DNT_API_KEY || 'YOUR_DUNKS_AND_THREES_API_KEY_HERE';

const DNT_BASE = 'https://dunksandthrees.com/api/v1';

// Allowed endpoints to prevent abuse
const ALLOWED_ENDPOINTS = {
    'epm':                  '/epm',
    'epm-all':              '/epm-all',
    'season-epm':           '/season-epm',
    'team-epm':             '/team-epm',
    'game-predictions':     '/game-predictions',
    'game-predictions-box': '/game-predictions-box',
};

// Allowed origins (update with your actual domains)
const ALLOWED_ORIGINS = [
    'https://www.bettorday.com',
    'https://bettorday.com',
    'http://localhost:3000',     // For local development
    'http://127.0.0.1:5500',    // VS Code Live Server
];

export default async function handler(req, res) {
    // ─── CORS ───
    const origin = req.headers.origin || '';
    if (ALLOWED_ORIGINS.includes(origin)) {
        res.setHeader('Access-Control-Allow-Origin', origin);
    } else {
        // Allow any origin in development; tighten for production
        res.setHeader('Access-Control-Allow-Origin', '*');
    }
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    // ─── Parse request ───
    const { endpoint, ...params } = req.query;

    if (!endpoint || !ALLOWED_ENDPOINTS[endpoint]) {
        return res.status(400).json({
            error: 'Invalid endpoint',
            allowed: Object.keys(ALLOWED_ENDPOINTS),
        });
    }

    // ─── Build D&T API URL ───
    const dntPath = ALLOWED_ENDPOINTS[endpoint];
    const queryParams = new URLSearchParams();

    // Forward allowed parameters
    const SAFE_PARAMS = ['date', 'game_id', 'season', 'seasontype', 'game_optimized', 'days'];
    SAFE_PARAMS.forEach(p => {
        if (params[p] !== undefined) queryParams.set(p, params[p]);
    });

    const dntUrl = `${DNT_BASE}${dntPath}${queryParams.toString() ? '?' + queryParams.toString() : ''}`;

    try {
        const response = await fetch(dntUrl, {
            method: 'GET',
            headers: {
                'Authorization': DNT_API_KEY,
                'Accept': 'application/json',
            },
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`D&T API error [${response.status}]:`, errorText);
            return res.status(response.status).json({
                error: `D&T API returned ${response.status}`,
                detail: errorText.substring(0, 200),
            });
        }

        const data = await response.json();

        // ─── Cache control ───
        // Game predictions update overnight + 20 min before tip
        // Team EPM updates overnight
        // Cache for 5 minutes to balance freshness vs API limits
        res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');

        return res.status(200).json(data);

    } catch (error) {
        console.error('Proxy error:', error);
        return res.status(500).json({ error: 'Internal proxy error' });
    }
}
