from http.server import BaseHTTPRequestHandler
import json
import os
import anthropic

# Super Bowl Data - Seahawks vs Patriots 2025 Season
DATA = {
    "seahawks": {
        "record": "16-3", "ats": "14-5 (73.7%)", "ou_record": "11-8 (57.9% over)",
        "ppg": 29.2, "ppg_allowed": 17.1,
        "scoring": {"q1": 7.0, "q2": 7.9, "q3": 7.6, "q4": 6.3, "h1": 14.9, "h2": 13.9},
        "yards": {"total": 350.0, "rush": 123.5, "pass": 238.6},
        "third_down_pct": 43.0, "turnovers_pg": 1.5, "takeaways_pg": 1.5,
        "home": "8-2 (6-4 ATS)", "road": "8-1 (8-1 ATS)",
        "players": [
            {"name": "Geno Smith", "pos": "QB", "stats": "4,282 pass yds, 33 TD, 15 INT, 70.2% comp, 266 rush yds"},
            {"name": "Kenneth Walker III", "pos": "RB", "stats": "1,108 rush yds, 13 TD, 4.5 YPC, 42 rec, 287 rec yds"},
            {"name": "Zach Charbonnet", "pos": "RB", "stats": "607 rush yds, 8 TD, 38 rec, 281 rec yds"},
            {"name": "DK Metcalf", "pos": "WR", "stats": "70 rec, 1,194 yds, 10 TD, 17.1 YPR"},
            {"name": "Jaxon Smith-Njigba", "pos": "WR", "stats": "108 rec, 1,177 yds, 6 TD, 10.9 YPR"},
            {"name": "Tyler Lockett", "pos": "WR", "stats": "51 rec, 650 yds, 4 TD"},
            {"name": "Noah Fant", "pos": "TE", "stats": "36 rec, 414 yds, 2 TD"},
            {"name": "Boye Mafe", "pos": "EDGE", "stats": "41 tackles, 9.5 sacks"},
            {"name": "Leonard Williams", "pos": "DL", "stats": "57 tackles, 7.5 sacks"},
        ]
    },
    "patriots": {
        "record": "17-3", "ats": "14-6 (70%)", "ou_record": "12-8 (60% over)",
        "ppg": 26.4, "ppg_allowed": 15.2,
        "scoring": {"q1": 6.9, "q2": 6.5, "q3": 6.9, "q4": 6.6, "h1": 13.4, "h2": 13.5},
        "yards": {"total": 361.8, "rush": 140.9, "pass": 224.9},
        "third_down_pct": 42.5, "turnovers_pg": 1.1, "takeaways_pg": 1.5,
        "home": "9-1 (7-3 ATS)", "road": "8-2 (7-3 ATS)",
        "players": [
            {"name": "Drake Maye", "pos": "QB", "stats": "3,238 pass yds, 22 TD, 14 INT, 66.8% comp, 459 rush yds, 3 rush TD"},
            {"name": "Rhamondre Stevenson", "pos": "RB", "stats": "1,018 rush yds, 9 TD, 4.0 YPC, 39 rec, 318 rec yds"},
            {"name": "Antonio Gibson", "pos": "RB", "stats": "106 rush yds, 1 TD"},
            {"name": "Ja'Lynn Polk", "pos": "WR", "stats": "43 rec, 698 yds, 4 TD"},
            {"name": "Demario Douglas", "pos": "WR", "stats": "67 rec, 678 yds, 3 TD"},
            {"name": "Kayshon Boutte", "pos": "WR", "stats": "28 rec, 439 yds, 5 TD"},
            {"name": "Hunter Henry", "pos": "TE", "stats": "62 rec, 672 yds, 6 TD"},
            {"name": "Austin Hooper", "pos": "TE", "stats": "23 rec, 277 yds, 2 TD"},
            {"name": "Keion White", "pos": "EDGE", "stats": "54 tackles, 7.0 sacks"},
            {"name": "Christian Barmore", "pos": "DL", "stats": "28 tackles, 4.5 sacks"},
        ]
    }
}

def build_system_prompt():
    s = DATA["seahawks"]
    p = DATA["patriots"]
    
    seahawks_players = "\n".join([f"  - {pl['name']} ({pl['pos']}): {pl['stats']}" for pl in s["players"]])
    patriots_players = "\n".join([f"  - {pl['name']} ({pl['pos']}): {pl['stats']}" for pl in p["players"]])
    
    return f"""You are the BettorDay AI Assistant, a sports betting analyst helping subscribers analyze the Super Bowl matchup between the Seattle Seahawks and New England Patriots.

## YOUR DATA - 2025 NFL SEASON

### SEATTLE SEAHAWKS ({s['record']})
- ATS Record: {s['ats']}
- Over/Under: {s['ou_record']}
- Points Per Game: {s['ppg']} scored, {s['ppg_allowed']} allowed
- Scoring by Quarter: Q1 {s['scoring']['q1']}, Q2 {s['scoring']['q2']}, Q3 {s['scoring']['q3']}, Q4 {s['scoring']['q4']}
- First Half: {s['scoring']['h1']} PPG | Second Half: {s['scoring']['h2']} PPG
- Total Yards: {s['yards']['total']}/game ({s['yards']['rush']} rush, {s['yards']['pass']} pass)
- Third Down: {s['third_down_pct']}%
- Turnovers: {s['turnovers_pg']}/game | Takeaways: {s['takeaways_pg']}/game
- Home: {s['home']} | Road: {s['road']}
- Key Players:
{seahawks_players}

### NEW ENGLAND PATRIOTS ({p['record']})
- ATS Record: {p['ats']}
- Over/Under: {p['ou_record']}
- Points Per Game: {p['ppg']} scored, {p['ppg_allowed']} allowed
- Scoring by Quarter: Q1 {p['scoring']['q1']}, Q2 {p['scoring']['q2']}, Q3 {p['scoring']['q3']}, Q4 {p['scoring']['q4']}
- First Half: {p['scoring']['h1']} PPG | Second Half: {p['scoring']['h2']} PPG
- Total Yards: {p['yards']['total']}/game ({p['yards']['rush']} rush, {p['yards']['pass']} pass)
- Third Down: {p['third_down_pct']}%
- Turnovers: {p['turnovers_pg']}/game | Takeaways: {p['takeaways_pg']}/game
- Home: {p['home']} | Road: {p['road']}
- Key Players:
{patriots_players}

## YOUR PERSONALITY
You speak like a seasoned sports betting analyst with 20+ years of experience - like Scott and Mac from the BettorDay podcast. Be data-driven but conversational. Lead with insights, cite specific numbers, and help subscribers make informed betting decisions.

## RULES
1. ALWAYS cite specific stats from the data above
2. Be direct and actionable - these are bettors looking for edges
3. Acknowledge uncertainty - never guarantee outcomes
4. Compare and contrast the teams when relevant
5. For player props, reference their season averages
6. Keep responses focused and valuable"""


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            user_message = data.get('message', '')
            history = data.get('history', [])
            
            if not user_message:
                self.wfile.write(json.dumps({"error": "No message provided"}).encode())
                return
            
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                self.wfile.write(json.dumps({"error": "API key not configured. Add ANTHROPIC_API_KEY to Vercel environment variables."}).encode())
                return
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # Build conversation history
            messages = []
            for h in history[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": user_message})
            
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=build_system_prompt(),
                messages=messages
            )
            
            self.wfile.write(json.dumps({
                "response": response.content[0].text,
                "success": True
            }).encode())
            
        except Exception as e:
            self.wfile.write(json.dumps({
                "error": str(e),
                "success": False
            }).encode())
