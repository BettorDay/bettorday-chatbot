from http.server import BaseHTTPRequestHandler
import json
import os
import anthropic
import requests
from datetime import datetime

# ============================================
# API CONFIGURATION
# ============================================
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "05985e695391302ae3b07e436ab47cbe")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Available sportsbooks in the US region
US_BOOKMAKERS = ["draftkings", "fanduel", "betmgm", "caesars", "pointsbet", "betrivers", "unibet", "wynnbet", "superbook"]

# Player prop markets available
PLAYER_PROP_MARKETS = [
    "player_pass_yds",
    "player_pass_tds", 
    "player_pass_completions",
    "player_pass_attempts",
    "player_pass_interceptions",
    "player_rush_yds",
    "player_rush_attempts",
    "player_receptions",
    "player_reception_yds",
    "player_anytime_td",
    "player_first_td",
    "player_pass_rush_yds",
    "player_tackles_assists"
]

# ============================================
# THE ODDS API - LIVE DATA FUNCTIONS
# ============================================

def format_odds(price):
    """Format American odds."""
    return f"+{price}" if price >= 0 else str(price)

def get_nfl_events():
    """Get all current NFL events including Super Bowl."""
    try:
        url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events"
        response = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=15)
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def get_super_bowl_event():
    """Find the Super Bowl event ID."""
    events = get_nfl_events()
    if isinstance(events, dict) and "error" in events:
        return None
    
    for event in events:
        teams = f"{event.get('home_team', '')} {event.get('away_team', '')}".lower()
        if "seahawks" in teams or "patriots" in teams:
            return event
    return None

def get_game_odds(event_id=None):
    """Get spread, total, and moneyline odds from all US sportsbooks."""
    try:
        url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american",
            "bookmakers": ",".join(US_BOOKMAKERS)
        }
        if event_id:
            params["eventIds"] = event_id
            
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_player_props(event_id, markets=None):
    """
    Get player props for a specific game from all sportsbooks.
    Returns props organized by market type and player.
    """
    if markets is None:
        markets = PLAYER_PROP_MARKETS
    
    all_props = {}
    
    for market in markets:
        try:
            url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events/{event_id}/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": market,
                "oddsFormat": "american"
            }
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                bookmakers = data.get("bookmakers", [])
                
                if bookmakers:
                    # Organize by player
                    market_data = {}
                    for book in bookmakers:
                        book_name = book["title"]
                        for mkt in book.get("markets", []):
                            for outcome in mkt.get("outcomes", []):
                                player = outcome.get("description", "Unknown")
                                line = outcome.get("point", "N/A")
                                price = outcome.get("price", 0)
                                name = outcome.get("name", "")
                                
                                if player not in market_data:
                                    market_data[player] = []
                                
                                market_data[player].append({
                                    "book": book_name,
                                    "line": line,
                                    "over_under": name,
                                    "odds": price
                                })
                    
                    if market_data:
                        all_props[market] = market_data
                        
        except Exception as e:
            continue
    
    return all_props

def get_historical_odds(event_id):
    """Get historical line movements for a game."""
    try:
        url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events/{event_id}/odds-history"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads,totals",
            "oddsFormat": "american"
        }
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def find_best_line(odds_data, market_type, team_or_side):
    """Find the best available line across all sportsbooks."""
    best_lines = []
    
    for game in odds_data if isinstance(odds_data, list) else [odds_data]:
        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] == market_type:
                    for outcome in market["outcomes"]:
                        if team_or_side.lower() in outcome["name"].lower() or team_or_side.lower() in str(outcome.get("point", "")).lower():
                            best_lines.append({
                                "book": book["title"],
                                "team": outcome["name"],
                                "line": outcome.get("point", ""),
                                "odds": outcome["price"]
                            })
    
    # Sort by best odds (highest number is best for American odds on the side you want)
    best_lines.sort(key=lambda x: x["odds"], reverse=True)
    return best_lines

def format_props_for_player(props_data, player_name):
    """Format all available props for a specific player."""
    player_lower = player_name.lower()
    result = []
    
    for market, players in props_data.items():
        for player, lines in players.items():
            if player_lower in player.lower():
                market_name = market.replace("player_", "").replace("_", " ").title()
                result.append(f"\n**{market_name}**")
                
                # Group by line value
                by_line = {}
                for l in lines:
                    key = f"{l['line']} {l['over_under']}"
                    if key not in by_line:
                        by_line[key] = []
                    by_line[key].append(f"{l['book']}: {format_odds(l['odds'])}")
                
                for line_key, books in by_line.items():
                    result.append(f"  {line_key}: {', '.join(books[:4])}")
    
    return "\n".join(result) if result else "No props currently available for this player."


# ============================================
# BIGDATABALL DATA - 2025 NFL SEASON
# ============================================

SUPERBOWL_DATA = {
    "seahawks": {
        "team": "Seattle Seahawks",
        "record": "16-3",
        "ats": "14-5",
        "ats_pct": 73.7,
        "overs": 11,
        "unders": 8,
        "over_pct": 57.9,
        "ppg": 29.2,
        "ppg_allowed": 17.1,
        "avg_yards": 350.0,
        "avg_rush_yards": 123.5,
        "avg_pass_yards": 238.6,
        "third_down_pct": 40.6,
        "turnovers_pg": 1.5,
        "home_record": "8-2",
        "road_record": "8-1",
        "home_ats": "6-4",
        "road_ats": "8-1",
        "scoring": {"q1": 7.0, "q2": 7.9, "q3": 7.6, "q4": 6.3, "first_half": 14.9, "second_half": 13.9},
        "players": [
            {"name": "Sam Darnold", "pos": "QB", "games": 19, "stats": "4,518 pass yds, 29 TD, 14 INT, 67.9% comp, 104 rush yds", 
             "avgs": {"pass_yds": 237.8, "pass_tds": 1.5, "completions": 21.4, "attempts": 31.5, "rush_yds": 5.5, "interceptions": 0.7}},
            {"name": "Kenneth Walker III", "pos": "RB", "games": 19, "stats": "1,205 rush yds, 9 TD, 4.7 YPC, 38 rec, 360 rec yds",
             "avgs": {"rush_yds": 63.4, "receptions": 2.0, "rec_yds": 18.9, "rush_attempts": 13.5}},
            {"name": "Zach Charbonnet", "pos": "RB", "games": 19, "stats": "750 rush yds, 12 TD, 4.0 YPC, 20 rec, 144 rec yds",
             "avgs": {"rush_yds": 39.5, "receptions": 1.1, "rec_yds": 7.6}},
            {"name": "Jaxon Smith-Njigba", "pos": "WR", "games": 19, "stats": "132 rec, 1,965 yds, 12 TD, 14.9 YPR",
             "avgs": {"receptions": 6.9, "rec_yds": 103.4, "targets": 9.8}},
            {"name": "Cooper Kupp", "pos": "WR", "games": 10, "stats": "56 rec, 689 yds, 3 TD, 12.3 YPR",
             "avgs": {"receptions": 5.6, "rec_yds": 68.9, "targets": 7.2}},
            {"name": "Rashid Shaheed", "pos": "WR", "games": 5, "stats": "16 rec, 239 yds, 0 TD, 14.9 YPR",
             "avgs": {"receptions": 3.2, "rec_yds": 47.8}},
            {"name": "Tory Horton", "pos": "WR", "games": 15, "stats": "13 rec, 161 yds, 5 TD, 12.4 YPR", "avgs": {}},
            {"name": "AJ Barner", "pos": "TE", "games": 19, "stats": "54 rec, 532 yds, 6 TD",
             "avgs": {"receptions": 2.8, "rec_yds": 28.0}},
            {"name": "Ernest Jones", "pos": "LB", "games": 19, "stats": "177 tackles, 0.5 sacks, 6 INT", "avgs": {"tackles": 9.3}},
            {"name": "Drake Thomas", "pos": "LB", "games": 19, "stats": "143 tackles, 3.5 sacks, 1 INT", "avgs": {"tackles": 7.5}},
            {"name": "Devon Witherspoon", "pos": "CB", "games": 17, "stats": "109 tackles, 0.5 sacks, 1 INT", "avgs": {"tackles": 6.4}},
            {"name": "Coby Bryant", "pos": "SAF", "games": 19, "stats": "100 tackles, 4 INT", "avgs": {"tackles": 5.3}},
        ],
        "game_log": [
            {"week": 1, "opp": "San Francisco 49ers", "venue": "Home", "result": "L 13-17", "spread": "+2.5", "ats": "✗", "total": 43.5, "pts": 30, "ou": "UNDER"},
            {"week": 2, "opp": "Pittsburgh Steelers", "venue": "Road", "result": "W 31-17", "spread": "+3.5", "ats": "✓", "total": 40.5, "pts": 48, "ou": "OVER"},
            {"week": 3, "opp": "New Orleans Saints", "venue": "Home", "result": "W 44-13", "spread": "-7.5", "ats": "✓", "total": 41.5, "pts": 57, "ou": "OVER"},
            {"week": 4, "opp": "Arizona Cardinals", "venue": "Road", "result": "W 23-20", "spread": "-1.5", "ats": "✓", "total": 43.5, "pts": 43, "ou": "UNDER"},
            {"week": 5, "opp": "Tampa Bay Buccaneers", "venue": "Home", "result": "L 35-38", "spread": "-3.5", "ats": "✗", "total": 44.5, "pts": 73, "ou": "OVER"},
            {"week": 6, "opp": "Jacksonville Jaguars", "venue": "Road", "result": "W 20-12", "spread": "-1.5", "ats": "✓", "total": 47.5, "pts": 32, "ou": "UNDER"},
            {"week": 7, "opp": "Houston Texans", "venue": "Home", "result": "W 27-19", "spread": "-3.0", "ats": "✓", "total": 41.5, "pts": 46, "ou": "OVER"},
            {"week": 9, "opp": "Washington Commanders", "venue": "Road", "result": "W 38-14", "spread": "-2.5", "ats": "✓", "total": 47.5, "pts": 52, "ou": "OVER"},
            {"week": 10, "opp": "Arizona Cardinals", "venue": "Home", "result": "W 44-22", "spread": "-7.5", "ats": "✓", "total": 44.5, "pts": 66, "ou": "OVER"},
            {"week": 11, "opp": "Los Angeles Rams", "venue": "Road", "result": "L 19-21", "spread": "+3.0", "ats": "✓", "total": 49.5, "pts": 40, "ou": "UNDER"},
            {"week": 12, "opp": "Tennessee Titans", "venue": "Road", "result": "W 30-24", "spread": "-12.5", "ats": "✗", "total": 41.5, "pts": 54, "ou": "OVER"},
            {"week": 13, "opp": "Minnesota Vikings", "venue": "Home", "result": "W 26-0", "spread": "-12.5", "ats": "✓", "total": 42.5, "pts": 26, "ou": "UNDER"},
            {"week": 14, "opp": "Atlanta Falcons", "venue": "Road", "result": "W 37-9", "spread": "-7.0", "ats": "✓", "total": 44.5, "pts": 46, "ou": "OVER"},
            {"week": 15, "opp": "Indianapolis Colts", "venue": "Home", "result": "W 18-16", "spread": "-12.5", "ats": "✗", "total": 41.5, "pts": 34, "ou": "UNDER"},
            {"week": 16, "opp": "Los Angeles Rams", "venue": "Home", "result": "W 38-37", "spread": "-1.5", "ats": "✗", "total": 42.5, "pts": 75, "ou": "OVER"},
            {"week": 17, "opp": "Carolina Panthers", "venue": "Road", "result": "W 27-10", "spread": "-6.5", "ats": "✓", "total": 42.5, "pts": 37, "ou": "UNDER"},
            {"week": 18, "opp": "San Francisco 49ers", "venue": "Road", "result": "W 13-3", "spread": "-2.5", "ats": "✓", "total": 48.5, "pts": 16, "ou": "UNDER"},
            {"week": "WC", "opp": "San Francisco 49ers", "venue": "Home", "result": "W 41-6", "spread": "-7.0", "ats": "✓", "total": 44.5, "pts": 47, "ou": "OVER"},
            {"week": "DIV", "opp": "Los Angeles Rams", "venue": "Home", "result": "W 31-27", "spread": "-2.5", "ats": "✓", "total": 45.5, "pts": 58, "ou": "OVER"},
        ]
    },
    "patriots": {
        "team": "New England Patriots",
        "record": "17-3",
        "ats": "14-6",
        "ats_pct": 70.0,
        "overs": 12,
        "unders": 8,
        "over_pct": 60.0,
        "ppg": 27.2,
        "ppg_allowed": 17.3,
        "avg_yards": 361.8,
        "avg_rush_yards": 140.9,
        "avg_pass_yards": 224.9,
        "third_down_pct": 40.7,
        "turnovers_pg": 1.1,
        "home_record": "8-3",
        "road_record": "9-0",
        "home_ats": "7-4",
        "road_ats": "7-2",
        "scoring": {"q1": 6.4, "q2": 10.0, "q3": 5.5, "q4": 5.2, "first_half": 16.4, "second_half": 10.7},
        "players": [
            {"name": "Drake Maye", "pos": "QB", "games": 20, "stats": "4,927 pass yds, 35 TD, 10 INT, 69.8% comp, 591 rush yds, 5 rush TD",
             "avgs": {"pass_yds": 246.4, "pass_tds": 1.75, "completions": 22.1, "attempts": 31.7, "rush_yds": 29.6, "interceptions": 0.5}},
            {"name": "TreVeyon Henderson", "pos": "RB", "games": 19, "stats": "968 rush yds, 9 TD, 4.7 YPC, 37 rec, 228 rec yds",
             "avgs": {"rush_yds": 50.9, "receptions": 1.9, "rec_yds": 12.0, "rush_attempts": 10.8}},
            {"name": "Rhamondre Stevenson", "pos": "RB", "games": 18, "stats": "797 rush yds, 7 TD, 4.4 YPC, 39 rec, 431 rec yds",
             "avgs": {"rush_yds": 44.3, "receptions": 2.2, "rec_yds": 23.9, "rush_attempts": 10.1}},
            {"name": "Antonio Gibson", "pos": "RB", "games": 18, "stats": "106 rush yds, 1 TD, 4.2 YPC", "avgs": {}},
            {"name": "Stefon Diggs", "pos": "WR", "games": 18, "stats": "96 rec, 1,086 yds, 5 TD, 11.3 YPR",
             "avgs": {"receptions": 5.3, "rec_yds": 60.3, "targets": 8.1}},
            {"name": "Kayshon Boutte", "pos": "WR", "games": 18, "stats": "41 rec, 698 yds, 7 TD, 17.0 YPR",
             "avgs": {"receptions": 2.3, "rec_yds": 38.8}},
            {"name": "Mack Hollins", "pos": "WR", "games": 17, "stats": "48 rec, 601 yds, 2 TD, 12.5 YPR",
             "avgs": {"receptions": 2.8, "rec_yds": 35.4}},
            {"name": "DeMario Douglas", "pos": "WR", "games": 19, "stats": "34 rec, 486 yds, 4 TD, 14.3 YPR",
             "avgs": {"receptions": 1.8, "rec_yds": 25.6}},
            {"name": "Hunter Henry", "pos": "TE", "games": 19, "stats": "66 rec, 849 yds, 8 TD, 12.9 YPR",
             "avgs": {"receptions": 3.5, "rec_yds": 44.7}},
            {"name": "Austin Hooper", "pos": "TE", "games": 17, "stats": "22 rec, 277 yds, 2 TD",
             "avgs": {"receptions": 1.3, "rec_yds": 16.3}},
            {"name": "Robert Spillane", "pos": "LB", "games": 17, "stats": "146 tackles, 1.0 sacks, 2 INT", "avgs": {"tackles": 8.6}},
            {"name": "Christian Elliss", "pos": "LB", "games": 20, "stats": "145 tackles, 1.0 sacks", "avgs": {"tackles": 7.3}},
            {"name": "Christian Gonzalez", "pos": "CB", "games": 19, "stats": "108 tackles, 1.0 sacks, 1 INT", "avgs": {"tackles": 5.7}},
        ],
        "game_log": [
            {"week": 1, "opp": "Las Vegas Raiders", "venue": "Home", "result": "L 13-20", "spread": "-2.5", "ats": "✗", "total": 44.5, "pts": 33, "ou": "UNDER"},
            {"week": 2, "opp": "Miami Dolphins", "venue": "Road", "result": "W 33-27", "spread": "+1.5", "ats": "✓", "total": 42.5, "pts": 60, "ou": "OVER"},
            {"week": 3, "opp": "Pittsburgh Steelers", "venue": "Home", "result": "L 14-21", "spread": "+1.5", "ats": "✗", "total": 44.5, "pts": 35, "ou": "UNDER"},
            {"week": 4, "opp": "Carolina Panthers", "venue": "Home", "result": "W 42-13", "spread": "-5.5", "ats": "✓", "total": 42.5, "pts": 55, "ou": "OVER"},
            {"week": 5, "opp": "Buffalo Bills", "venue": "Road", "result": "W 23-20", "spread": "+7.5", "ats": "✓", "total": 49.5, "pts": 43, "ou": "UNDER"},
            {"week": 6, "opp": "New Orleans Saints", "venue": "Road", "result": "W 25-19", "spread": "-3.5", "ats": "✓", "total": 45.5, "pts": 44, "ou": "UNDER"},
            {"week": 7, "opp": "Tennessee Titans", "venue": "Road", "result": "W 31-13", "spread": "-6.5", "ats": "✓", "total": 40.5, "pts": 44, "ou": "OVER"},
            {"week": 8, "opp": "Cleveland Browns", "venue": "Home", "result": "W 32-13", "spread": "-6.5", "ats": "✓", "total": 40.5, "pts": 45, "ou": "OVER"},
            {"week": 9, "opp": "Atlanta Falcons", "venue": "Home", "result": "W 24-23", "spread": "-5.5", "ats": "✗", "total": 45.5, "pts": 47, "ou": "OVER"},
            {"week": 10, "opp": "Tampa Bay Buccaneers", "venue": "Road", "result": "W 28-23", "spread": "+2.5", "ats": "✓", "total": 48.5, "pts": 51, "ou": "OVER"},
            {"week": 11, "opp": "New York Jets", "venue": "Home", "result": "W 27-14", "spread": "-12.5", "ats": "✓", "total": 43.5, "pts": 41, "ou": "UNDER"},
            {"week": 12, "opp": "Cincinnati Bengals", "venue": "Road", "result": "W 26-20", "spread": "-7.5", "ats": "✗", "total": 50.5, "pts": 46, "ou": "UNDER"},
            {"week": 13, "opp": "New York Giants", "venue": "Home", "result": "W 33-15", "spread": "-7.0", "ats": "✓", "total": 46.5, "pts": 48, "ou": "OVER"},
            {"week": 15, "opp": "Buffalo Bills", "venue": "Home", "result": "L 31-35", "spread": "+2.5", "ats": "✗", "total": 49.5, "pts": 66, "ou": "OVER"},
            {"week": 16, "opp": "Baltimore Ravens", "venue": "Road", "result": "W 28-24", "spread": "+3.5", "ats": "✓", "total": 47.5, "pts": 52, "ou": "OVER"},
            {"week": 17, "opp": "New York Jets", "venue": "Road", "result": "W 42-10", "spread": "-12.5", "ats": "✓", "total": 42.5, "pts": 52, "ou": "OVER"},
            {"week": 18, "opp": "Miami Dolphins", "venue": "Home", "result": "W 38-10", "spread": "-14.5", "ats": "✓", "total": 44.5, "pts": 48, "ou": "OVER"},
            {"week": "WC", "opp": "Los Angeles Chargers", "venue": "Home", "result": "W 16-3", "spread": "-3.5", "ats": "✓", "total": 45.5, "pts": 19, "ou": "UNDER"},
            {"week": "DIV", "opp": "Houston Texans", "venue": "Home", "result": "W 28-16", "spread": "-3.0", "ats": "✓", "total": 40.5, "pts": 44, "ou": "OVER"},
            {"week": "CONF", "opp": "Denver Broncos", "venue": "Road", "result": "W 10-7", "spread": "-3.5", "ats": "✗", "total": 43.5, "pts": 17, "ou": "UNDER"},
        ]
    }
}


# ============================================
# CLAUDE TOOLS - LIVE ODDS API INTEGRATION
# ============================================

TOOLS = [
    {
        "name": "get_live_game_odds",
        "description": "Fetch current Super Bowl betting odds (spread, total, moneyline) from ALL US sportsbooks including DraftKings, FanDuel, BetMGM, Caesars, PointsBet, BetRivers. Returns live lines from each book.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_player_prop_odds",
        "description": "Fetch player prop betting lines from all sportsbooks for a specific player. Shows over/under lines and odds for passing yards, rushing yards, receptions, receiving yards, touchdowns, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string", 
                    "description": "Player name (e.g., 'Drake Maye', 'Jaxon Smith-Njigba', 'Kenneth Walker')"
                },
                "prop_type": {
                    "type": "string",
                    "description": "Optional: specific prop type ('pass_yds', 'rush_yds', 'receptions', 'rec_yds', 'anytime_td'). If not specified, returns all available props."
                }
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "compare_odds_across_books",
        "description": "Compare betting odds across all sportsbooks to find the best available line for a specific bet. Helps identify line shopping opportunities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bet_type": {
                    "type": "string",
                    "description": "'spread', 'total', 'moneyline', or 'player_prop'"
                },
                "selection": {
                    "type": "string",
                    "description": "Team name, Over/Under, or player name"
                }
            },
            "required": ["bet_type"]
        }
    },
    {
        "name": "get_line_history",
        "description": "Get historical line movement for the Super Bowl showing how spreads and totals have moved since opening.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    }
]

def execute_tool(tool_name, tool_input):
    """Execute an odds API tool and return formatted results."""
    
    if tool_name == "get_live_game_odds":
        # Get Super Bowl event
        event = get_super_bowl_event()
        
        if event:
            odds = get_game_odds(event["id"])
            if isinstance(odds, list) and len(odds) > 0:
                result = f"📊 **LIVE SUPER BOWL ODDS**\n"
                result += f"**{odds[0].get('away_team', 'Away')} @ {odds[0].get('home_team', 'Home')}**\n"
                result += f"Kickoff: {odds[0].get('commence_time', 'TBD')}\n\n"
                
                for book in odds[0].get("bookmakers", []):
                    result += f"📚 **{book['title']}**\n"
                    for market in book.get("markets", []):
                        if market["key"] == "spreads":
                            for o in market["outcomes"]:
                                result += f"  Spread: {o['name']} {o.get('point', '')} ({format_odds(o['price'])})\n"
                        elif market["key"] == "totals":
                            for o in market["outcomes"]:
                                result += f"  Total: {o['name']} {o.get('point', '')} ({format_odds(o['price'])})\n"
                        elif market["key"] == "h2h":
                            for o in market["outcomes"]:
                                result += f"  Moneyline: {o['name']} ({format_odds(o['price'])})\n"
                    result += "\n"
                return result
        
        # Fallback if API unavailable
        return """📊 **SUPER BOWL ODDS** (Live odds temporarily unavailable)

Based on season performance, here are projected lines:
• Both teams covered 70%+ ATS this season
• Combined games averaged ~46 total points  
• Patriots 9-0 on the road (historic!)
• Seahawks 8-1 road ATS

Check DraftKings, FanDuel, BetMGM, or Caesars for current live lines."""

    elif tool_name == "get_player_prop_odds":
        player_name = tool_input.get("player_name", "").lower()
        prop_type = tool_input.get("prop_type", None)
        
        # Find player in our data first
        player_data = None
        team_key = None
        for t in ["seahawks", "patriots"]:
            for p in SUPERBOWL_DATA[t]["players"]:
                if player_name in p["name"].lower() or \
                   (player_name == "jsn" and "smith-njigba" in p["name"].lower()):
                    player_data = p
                    team_key = t
                    break
        
        if not player_data:
            return f"Player '{player_name}' not found in Super Bowl rosters."
        
        result = f"**{player_data['name']}** ({player_data['pos']}) - {SUPERBOWL_DATA[team_key]['team']}\n\n"
        result += f"**Season Stats ({player_data['games']} games):**\n{player_data['stats']}\n\n"
        
        # Show per-game averages
        if player_data.get("avgs"):
            result += "**Season Averages (prop baselines):**\n"
            for key, val in player_data["avgs"].items():
                label = key.replace("_", " ").title()
                result += f"• {label}: {val}/game\n"
        
        # Try to get live props from API
        event = get_super_bowl_event()
        if event:
            markets = [f"player_{prop_type}"] if prop_type else PLAYER_PROP_MARKETS
            props = get_player_props(event["id"], markets)
            
            if props:
                formatted = format_props_for_player(props, player_data["name"])
                if "No props" not in formatted:
                    result += f"\n**LIVE PROPS FROM SPORTSBOOKS:**\n{formatted}"
                    return result
        
        # Provide analysis based on averages
        result += "\n**Prop Analysis:**\n"
        if player_data.get("avgs"):
            avgs = player_data["avgs"]
            if "pass_yds" in avgs:
                result += f"• Pass Yds: Season avg {avgs['pass_yds']}/g - look for lines around {int(avgs['pass_yds'] - 10)}-{int(avgs['pass_yds'] + 10)}\n"
            if "rush_yds" in avgs:
                result += f"• Rush Yds: Season avg {avgs['rush_yds']}/g - look for lines around {int(avgs['rush_yds'] - 5)}-{int(avgs['rush_yds'] + 5)}\n"
            if "rec_yds" in avgs:
                result += f"• Rec Yds: Season avg {avgs['rec_yds']}/g - look for lines around {int(avgs['rec_yds'] - 10)}-{int(avgs['rec_yds'] + 10)}\n"
            if "receptions" in avgs:
                result += f"• Receptions: Season avg {avgs['receptions']}/g - look for lines around {avgs['receptions'] - 0.5}-{avgs['receptions'] + 0.5}\n"
        
        return result

    elif tool_name == "compare_odds_across_books":
        bet_type = tool_input.get("bet_type", "spread")
        selection = tool_input.get("selection", "")
        
        event = get_super_bowl_event()
        if event:
            odds = get_game_odds(event["id"])
            if isinstance(odds, list) and len(odds) > 0:
                market_key = "spreads" if bet_type == "spread" else "totals" if bet_type == "total" else "h2h"
                best = find_best_line(odds, market_key, selection if selection else "over")
                
                if best:
                    result = f"**BEST {bet_type.upper()} ODDS - {selection.upper() if selection else 'ALL'}**\n\n"
                    for i, line in enumerate(best[:8], 1):
                        result += f"{i}. **{line['book']}**: {line['team']} {line['line']} ({format_odds(line['odds'])})\n"
                    
                    if len(best) > 1:
                        diff = best[0]['odds'] - best[-1]['odds']
                        result += f"\n💡 **Line shopping value:** {diff} cents between best and worst\n"
                    return result
        
        return f"""**Line Shopping Tips for {bet_type.upper()}:**

Always compare across books! Typical differences:
• Spreads: 0.5-1 point variation
• Totals: 0.5-1 point variation  
• Moneylines: 5-15 cent variation on favorites

Check: DraftKings, FanDuel, BetMGM, Caesars, PointsBet, BetRivers"""

    elif tool_name == "get_line_history":
        event = get_super_bowl_event()
        if event:
            history = get_historical_odds(event["id"])
            if not isinstance(history, dict) or "error" not in history:
                result = "**SUPER BOWL LINE MOVEMENT**\n\n"
                # Would parse historical data here
                return result
        
        return """**Line Movement Analysis:**

Based on typical Super Bowl patterns:
• Lines often move 1-3 points from open to close
• Sharp money typically comes in early
• Public money pushes favorites closer to kickoff
• Totals often climb as casual bettors take overs

Monitor for steam moves and reverse line movement for best value."""

    return "Tool not recognized."


# ============================================
# SYSTEM PROMPT
# ============================================

def build_system_prompt():
    s = SUPERBOWL_DATA["seahawks"]
    p = SUPERBOWL_DATA["patriots"]
    
    def fmt_player(pl):
        line = f"• {pl['name']} ({pl['pos']}, {pl['games']}g): {pl['stats']}"
        if pl.get("avgs"):
            avgs_str = ", ".join([f"{k.replace('_',' ')}: {v}/g" for k, v in list(pl["avgs"].items())[:4]])
            line += f"\n    ↳ Avgs: {avgs_str}"
        return line
    
    sea_players = "\n".join([fmt_player(p) for p in s["players"]])
    ne_players = "\n".join([fmt_player(p) for p in p["players"]])
    
    sea_games = "\n".join([f"  Wk{g['week']}: {g['result']} vs {g['opp']} | {g['spread']} {g['ats']} | {g['total']} ({g['pts']}) {g['ou']}" for g in s["game_log"]])
    ne_games = "\n".join([f"  Wk{g['week']}: {g['result']} vs {g['opp']} | {g['spread']} {g['ats']} | {g['total']} ({g['pts']}) {g['ou']}" for g in p["game_log"]])

    return f"""You are the BettorDay AI, a veteran sports betting analyst helping subscribers with Super Bowl analysis.

═══════════════════════════════════════════════════════════════
DATA SOURCES AVAILABLE
═══════════════════════════════════════════════════════════════

1. **BigDataBall 2025 Season Data** - Complete game logs, ATS/O/U results, player stats
2. **The Odds API (LIVE)** - Real-time odds from DraftKings, FanDuel, BetMGM, Caesars, PointsBet, BetRivers

**TOOLS YOU CAN USE:**
• get_live_game_odds - Fetch current spread/total/ML from all sportsbooks
• get_player_prop_odds - Get player prop lines from all books
• compare_odds_across_books - Find best available lines
• get_line_history - See how lines have moved

═══════════════════════════════════════════════════════════════
SEATTLE SEAHAWKS ({s['record']})
═══════════════════════════════════════════════════════════════

**BETTING:** ATS {s['ats']} ({s['ats_pct']}%) | O/U {s['overs']}-{s['unders']} ({s['over_pct']}% over)
**SPLITS:** Home {s['home_record']} ({s['home_ats']} ATS) | Road {s['road_record']} ({s['road_ats']} ATS)
**SCORING:** {s['ppg']} PPG / {s['ppg_allowed']} allowed | 1H: {s['scoring']['first_half']} | 2H: {s['scoring']['second_half']}
**OFFENSE:** {s['avg_yards']} yds/g ({s['avg_rush_yards']} rush, {s['avg_pass_yards']} pass) | 3rd Down: {s['third_down_pct']}%

**KEY PLAYERS:**
{sea_players}

**GAME LOG:**
{sea_games}

═══════════════════════════════════════════════════════════════
NEW ENGLAND PATRIOTS ({p['record']})
═══════════════════════════════════════════════════════════════

**BETTING:** ATS {p['ats']} ({p['ats_pct']}%) | O/U {p['overs']}-{p['unders']} ({p['over_pct']}% over)
**SPLITS:** Home {p['home_record']} ({p['home_ats']} ATS) | Road {p['road_record']} ({p['road_ats']} ATS) ← **9-0 ROAD RECORD!**
**SCORING:** {p['ppg']} PPG / {p['ppg_allowed']} allowed | 1H: {p['scoring']['first_half']} | 2H: {p['scoring']['second_half']}
**OFFENSE:** {p['avg_yards']} yds/g ({p['avg_rush_yards']} rush, {p['avg_pass_yards']} pass) | 3rd Down: {p['third_down_pct']}%

**KEY PLAYERS:**
{ne_players}

**GAME LOG:**
{ne_games}

═══════════════════════════════════════════════════════════════
YOUR APPROACH
═══════════════════════════════════════════════════════════════

You're like Scott and Mac from BettorDay - data-driven, direct, actionable insights.

1. **USE TOOLS** when asked about current odds or props - fetch live data first
2. **CITE SPECIFIC STATS** - always back up analysis with numbers
3. **COMPARE TO AVERAGES** - player props should be compared to season baselines
4. **FIND VALUE** - identify when lines don't match historical performance
5. **LINE SHOP** - remind users to compare across books
6. **NO GUARANTEES** - acknowledge variance in betting

**KEY SUPER BOWL ANGLES:**
• Both teams 70%+ ATS - sharps have been on them all year
• Patriots historic 9-0 road record
• JSN: 103.4 rec yds/game - elite WR1 usage
• Drake Maye dual-threat: 246 pass + 30 rush yds/game
• NE trends OVER (60%), SEA balanced (58%)
• Combined games avg ~46 total points this season"""


# ============================================
# HTTP HANDLER
# ============================================

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
                self.wfile.write(json.dumps({"error": "ANTHROPIC_API_KEY not configured"}).encode())
                return
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # Build conversation
            messages = [{"role": h["role"], "content": h["content"]} for h in history[-10:]]
            messages.append({"role": "user", "content": user_message})
            
            # Call Claude with tools
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=build_system_prompt(),
                tools=TOOLS,
                messages=messages
            )
            
            # Handle tool calls iteratively
            final_text = ""
            while response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                    elif block.type == "text":
                        final_text += block.text
                
                # Continue conversation with tool results
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=build_system_prompt(),
                    tools=TOOLS,
                    messages=messages
                )
            
            # Extract final text response
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
            
            self.wfile.write(json.dumps({
                "response": final_text,
                "success": True
            }).encode())
            
        except Exception as e:
            self.wfile.write(json.dumps({
                "error": str(e),
                "success": False
            }).encode())
