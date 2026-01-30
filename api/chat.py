"""
BettorDay Super Bowl AI Chat Agent
===================================
- Pulls ALL player props from The Odds API (passing, rushing, receiving, TDs)
- Gets ALL market odds from ALL sportsbooks
- Excludes injured players from recommendations
- Uses BigDataBall historical data for analysis

Deploy to Vercel as api/chat.py
Environment Variables: ANTHROPIC_API_KEY, ODDS_API_KEY
"""

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

# All US Sportsbooks to query
US_BOOKMAKERS = [
    "draftkings", "fanduel", "betmgm", "caesars", "pointsbetus",
    "betrivers", "unibet_us", "wynnbet", "superbook", "bovada",
    "betonlineag", "lowvig", "mybookieag", "espnbet", "fanatics"
]

# ============================================
# COMPLETE PLAYER PROP MARKETS - ALL CATEGORIES
# ============================================
# This is the FULL list of NFL player prop markets available from The Odds API

PLAYER_PROP_MARKETS = {
    # ========== PASSING PROPS ==========
    "passing": [
        "player_pass_yds",               # Passing yards
        "player_pass_tds",               # Passing touchdowns
        "player_pass_completions",       # Pass completions
        "player_pass_attempts",          # Pass attempts
        "player_pass_interceptions",     # Interceptions thrown
        "player_pass_longest_completion", # Longest completion
    ],
    
    # ========== RUSHING PROPS ==========
    "rushing": [
        "player_rush_yds",               # Rushing yards
        "player_rush_attempts",          # Rush attempts
        "player_rush_longest",           # Longest rush
    ],
    
    # ========== RECEIVING PROPS ==========
    "receiving": [
        "player_receptions",             # Receptions
        "player_reception_yds",          # Receiving yards
        "player_reception_longest",      # Longest reception
    ],
    
    # ========== TOUCHDOWN PROPS ==========
    "touchdowns": [
        "player_anytime_td",             # Anytime touchdown scorer
        "player_first_td",               # First touchdown scorer
        "player_last_td",                # Last touchdown scorer
    ],
    
    # ========== COMBO/OTHER PROPS ==========
    "combo": [
        "player_pass_rush_yds",          # Pass + Rush yards combined
        "player_rush_reception_yds",     # Rush + Receiving yards
    ],
    
    # ========== DEFENSE/SPECIAL ==========
    "defense": [
        "player_tackles_assists",        # Tackles + Assists
        "player_kicking_points",         # Kicker points
        "player_field_goals_made",       # Field goals made
    ]
}

# Flatten all markets into a single list for comprehensive fetching
ALL_PLAYER_PROP_MARKETS = []
for category, markets in PLAYER_PROP_MARKETS.items():
    ALL_PLAYER_PROP_MARKETS.extend(markets)

# ============================================
# GAME ODDS MARKETS
# ============================================
GAME_MARKETS = ["h2h", "spreads", "totals"]  # Moneyline, Spread, Over/Under

# ============================================
# SUPER BOWL EVENT ID (hardcoded for reliability)
# ============================================
SUPER_BOWL_EVENT_ID = "b64e3587d7a4cf01a568e7150a2a1aec"
SUPER_BOWL_HOME_TEAM = "New England Patriots"
SUPER_BOWL_AWAY_TEAM = "Seattle Seahawks"
SUPER_BOWL_DATE = "2026-02-08T23:30:00Z"

# ============================================
# INJURED PLAYERS - EXCLUDE FROM BET RECOMMENDATIONS
# ============================================
INJURED_PLAYERS = [
    {"name": "Zach Charbonnet", "team": "seahawks", "status": "OUT", "injury": "Ankle - WILL NOT PLAY"},
]
INJURED_PLAYER_NAMES = {p["name"].lower() for p in INJURED_PLAYERS}


# ============================================
# THE ODDS API FUNCTIONS
# ============================================

def get_nfl_events():
    """Get all current NFL events including Super Bowl."""
    try:
        url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events"
        response = requests.get(
            url, 
            params={"apiKey": ODDS_API_KEY}, 
            timeout=30,
            headers={"Accept": "application/json"}
        )
        print(f"[DEBUG] NFL Events API Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            return {"error": "Invalid API key. Check ODDS_API_KEY environment variable."}
        elif response.status_code == 429:
            return {"error": "API rate limit exceeded. Try again later."}
        return {"error": f"API returned status {response.status_code}: {response.text[:200]}"}
    except requests.exceptions.Timeout:
        return {"error": "Connection timed out. The Odds API may be slow or unavailable."}
    except requests.exceptions.ConnectionError as e:
        return {"error": f"Connection error: {str(e)}. Check your network connection."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def get_super_bowl_event():
    """Find the Super Bowl event (Seahawks vs Patriots)."""
    # Try to fetch dynamically first
    events = get_nfl_events()
    
    if isinstance(events, list):
        for event in events:
            teams = [event.get("home_team", "").lower(), event.get("away_team", "").lower()]
            team_str = " ".join(teams)
            if ("seattle" in team_str or "seahawk" in team_str) and \
               ("new england" in team_str or "patriot" in team_str):
                return event
    
    # Fallback to hardcoded event ID if API fails
    print("[DEBUG] Using hardcoded Super Bowl event ID")
    return {
        "id": SUPER_BOWL_EVENT_ID,
        "home_team": SUPER_BOWL_HOME_TEAM,
        "away_team": SUPER_BOWL_AWAY_TEAM,
        "commence_time": SUPER_BOWL_DATE
    }


def get_live_game_odds(event_id=None):
    """
    Get current spread, total, and moneyline odds from ALL US sportsbooks.
    This is the main function for game odds.
    """
    try:
        if event_id is None:
            event = get_super_bowl_event()
            if event:
                event_id = event["id"]
            else:
                # Fall back to general NFL odds
                url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/odds"
                params = {
                    "apiKey": ODDS_API_KEY,
                    "regions": "us,us2",
                    "markets": ",".join(GAME_MARKETS),
                    "oddsFormat": "american"
                }
                response = requests.get(url, params=params, timeout=30)
                print(f"[DEBUG] NFL Odds API Status: {response.status_code}")
                if response.status_code == 200:
                    return response.json()
                return {"error": f"Status {response.status_code}"}
        
        # Get odds for specific event
        url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events/{event_id}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us,us2",
            "markets": ",".join(GAME_MARKETS),
            "oddsFormat": "american"
        }
        response = requests.get(url, params=params, timeout=30)
        print(f"[DEBUG] Event Odds API Status: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            return {"error": "Invalid API key"}
        elif response.status_code == 404:
            return {"error": f"Event {event_id} not found"}
        return {"error": f"Status {response.status_code}: {response.text[:200]}"}
    except requests.exceptions.Timeout:
        return {"error": "Connection timed out"}
    except requests.exceptions.ConnectionError as e:
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def get_all_player_props(event_id, markets=None, category=None):
    """
    Get ALL player props from ALL sportsbooks.
    
    Args:
        event_id: The Odds API event ID
        markets: Optional list of specific markets to fetch
        category: Optional category name ('passing', 'rushing', 'receiving', 'touchdowns', etc.)
    
    Returns:
        Dict with market -> bookmaker data
    """
    if markets is None:
        if category and category in PLAYER_PROP_MARKETS:
            markets = PLAYER_PROP_MARKETS[category]
        else:
            # Get ALL markets
            markets = ALL_PLAYER_PROP_MARKETS
    
    all_props = {}
    errors = []
    
    for market in markets:
        try:
            url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events/{event_id}/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "us,us2",
                "markets": market,
                "oddsFormat": "american"
            }
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                bookmakers = data.get("bookmakers", [])
                
                if bookmakers:
                    all_props[market] = bookmakers
                    print(f"[DEBUG] Found {len(bookmakers)} books for {market}")
            elif response.status_code == 401:
                errors.append(f"Invalid API key for {market}")
            elif response.status_code == 404:
                # Market not available for this event - this is normal
                pass
            else:
                errors.append(f"{market}: status {response.status_code}")
                    
        except requests.exceptions.Timeout:
            errors.append(f"{market}: timeout")
        except requests.exceptions.ConnectionError:
            errors.append(f"{market}: connection error")
        except Exception as e:
            errors.append(f"{market}: {str(e)}")
    
    if errors and not all_props:
        print(f"[DEBUG] Prop fetch errors: {errors}")
    
    return all_props


def get_passing_props(event_id):
    """Get all PASSING player props."""
    return get_all_player_props(event_id, category="passing")


def get_rushing_props(event_id):
    """Get all RUSHING player props."""
    return get_all_player_props(event_id, category="rushing")


def get_receiving_props(event_id):
    """Get all RECEIVING player props."""
    return get_all_player_props(event_id, category="receiving")


def get_touchdown_props(event_id):
    """Get all TOUCHDOWN scorer props."""
    return get_all_player_props(event_id, category="touchdowns")


def get_best_line_for_prop(props_data, market, player_name, over_under="Over"):
    """
    Find the best available line across all sportsbooks for a specific player prop.
    """
    best_odds = -99999
    best_book = None
    best_line = None
    
    if market not in props_data:
        return None
    
    for bookmaker in props_data[market]:
        book_name = bookmaker.get("title", "Unknown")
        for mkt in bookmaker.get("markets", []):
            for outcome in mkt.get("outcomes", []):
                desc = outcome.get("description", "").lower()
                name = outcome.get("name", "")
                
                if player_name.lower() in desc:
                    if over_under.lower() in name.lower():
                        odds = outcome.get("price", -99999)
                        line = outcome.get("point")
                        
                        if odds > best_odds:
                            best_odds = odds
                            best_book = book_name
                            best_line = line
    
    if best_book:
        return {
            "book": best_book,
            "line": best_line,
            "odds": best_odds,
            "formatted_odds": format_odds(best_odds)
        }
    return None


def compare_odds_across_books(props_data, market, player_name):
    """
    Get all odds from all sportsbooks for a specific player's prop.
    Useful for line shopping.
    """
    all_odds = []
    
    if market not in props_data:
        return all_odds
    
    for bookmaker in props_data[market]:
        book_name = bookmaker.get("title", "Unknown")
        for mkt in bookmaker.get("markets", []):
            for outcome in mkt.get("outcomes", []):
                desc = outcome.get("description", "").lower()
                if player_name.lower() in desc:
                    all_odds.append({
                        "book": book_name,
                        "line": outcome.get("point"),
                        "over_under": outcome.get("name"),
                        "odds": outcome.get("price"),
                        "formatted_odds": format_odds(outcome.get("price", 0))
                    })
    
    # Sort by odds (best first)
    all_odds.sort(key=lambda x: x["odds"], reverse=True)
    return all_odds


def filter_injured_players(props_data):
    """Filter out injured players from prop data."""
    filtered = {}
    
    for market, bookmakers in props_data.items():
        filtered[market] = []
        
        for book in bookmakers:
            filtered_book = {
                "key": book.get("key"),
                "title": book.get("title"),
                "markets": []
            }
            
            for mkt in book.get("markets", []):
                filtered_outcomes = []
                
                for outcome in mkt.get("outcomes", []):
                    player_name = outcome.get("description", outcome.get("name", ""))
                    
                    if player_name.lower() not in INJURED_PLAYER_NAMES:
                        filtered_outcomes.append(outcome)
                
                if filtered_outcomes:
                    filtered_book["markets"].append({
                        "key": mkt.get("key"),
                        "outcomes": filtered_outcomes
                    })
            
            if filtered_book["markets"]:
                filtered[market].append(filtered_book)
    
    return filtered


def format_odds(price):
    """Format odds in American format."""
    if price is None:
        return "N/A"
    return f"+{price}" if price >= 0 else str(price)


def format_props_summary(props_data, player_filter=None):
    """Format player props for readable display."""
    if not props_data:
        return "No player props available."
    
    output = []
    
    for market, bookmakers in props_data.items():
        market_display = market.replace("player_", "").replace("_", " ").title()
        output.append(f"\n**{market_display}:**")
        
        # Organize by player
        players = {}
        for book in bookmakers:
            book_name = book.get("title", "Unknown")
            for mkt in book.get("markets", []):
                for outcome in mkt.get("outcomes", []):
                    player = outcome.get("description", "Unknown")
                    
                    if player_filter and player_filter.lower() not in player.lower():
                        continue
                    
                    if player not in players:
                        players[player] = []
                    
                    players[player].append({
                        "book": book_name,
                        "line": outcome.get("point"),
                        "ou": outcome.get("name"),
                        "odds": format_odds(outcome.get("price"))
                    })
        
        for player, lines in sorted(players.items()):
            output.append(f"\n  {player}:")
            for line in lines[:3]:  # Show top 3 books per player
                output.append(f"    • {line['book']}: {line['line']} {line['ou']} ({line['odds']})")
    
    return "\n".join(output)


# ============================================
# BIGDATABALL DATA - 2025 NFL SEASON
# ============================================

SUPERBOWL_DATA = {
    "teams": {
        "seahawks": {
            "name": "Seattle Seahawks",
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
        },
        "patriots": {
            "name": "New England Patriots",
            "record": "15-4",
            "ats": "14-5",
            "ats_pct": 73.7,
            "overs": 12,
            "unders": 8,
            "over_pct": 60.0,
            "ppg": 27.8,
            "ppg_allowed": 18.2,
            "avg_yards": 345.0,
            "avg_rush_yards": 115.2,
            "avg_pass_yards": 229.8,
            "third_down_pct": 41.2,
            "turnovers_pg": 1.1,
            "home_record": "6-4",
            "road_record": "9-0",
            "home_ats": "5-5",
            "road_ats": "9-0",
            "scoring": {"q1": 6.8, "q2": 6.6, "q3": 7.2, "q4": 7.2, "first_half": 13.4, "second_half": 14.4},
        }
    },
    "players": {
        "seahawks": [
            {"name": "Sam Darnold", "pos": "QB", "pass_yds": 4518, "pass_td": 29, "pass_int": 14, 
             "comp_pct": 67.9, "rush_yds": 104, "games": 19,
             "avgs": {"pass_yds": 237.8, "pass_td": 1.5, "completions": 21.4, "attempts": 31.5, "rush_yds": 5.5}},
            {"name": "Kenneth Walker III", "pos": "RB", "rush_yds": 1205, "rush_td": 9, 
             "rec": 38, "rec_yds": 360, "games": 19, "first_tds": 3,
             "avgs": {"rush_yds": 63.4, "receptions": 2.0, "rec_yds": 18.9, "rush_att": 13.5}},
            {"name": "Zach Charbonnet", "pos": "RB", "rush_yds": 750, "rush_td": 12, 
             "rec": 20, "rec_yds": 144, "games": 19, "first_tds": 5,
             "avgs": {"rush_yds": 39.5, "receptions": 1.1, "rec_yds": 7.6},
             "status": "OUT", "injury": "Ankle - WILL NOT PLAY"},
            {"name": "Jaxon Smith-Njigba", "pos": "WR", "rec": 132, "rec_yds": 1965, "rec_td": 12, 
             "games": 19, "first_tds": 2,
             "avgs": {"receptions": 6.9, "rec_yds": 103.4, "targets": 9.8}},
            {"name": "Cooper Kupp", "pos": "WR", "rec": 56, "rec_yds": 689, "rec_td": 3, 
             "games": 10,
             "avgs": {"receptions": 5.6, "rec_yds": 68.9, "targets": 7.2}},
            {"name": "Rashid Shaheed", "pos": "WR", "rec": 38, "rec_yds": 625, "rec_td": 4, 
             "games": 12,
             "avgs": {"receptions": 3.2, "rec_yds": 52.1, "targets": 4.8}},
            {"name": "AJ Barner", "pos": "TE", "rec": 42, "rec_yds": 462, "rec_td": 5, 
             "games": 19, "red_zone_targets": 18,
             "avgs": {"receptions": 2.2, "rec_yds": 24.3}},
        ],
        "patriots": [
            {"name": "Drake Maye", "pos": "QB", "pass_yds": 3238, "pass_td": 22, "pass_int": 14, 
             "comp_pct": 66.8, "rush_yds": 459, "rush_td": 3, "games": 17,
             "avgs": {"pass_yds": 190.5, "pass_td": 1.3, "completions": 18.2, "attempts": 27.3, "rush_yds": 27.0}},
            {"name": "Rhamondre Stevenson", "pos": "RB", "rush_yds": 1018, "rush_td": 9, 
             "rec": 45, "rec_yds": 318, "games": 17, "first_tds": 2,
             "avgs": {"rush_yds": 59.9, "receptions": 2.6, "rec_yds": 18.7, "rush_att": 14.8}},
            {"name": "TreVeyon Henderson", "pos": "RB", "rush_yds": 648, "rush_td": 7, 
             "rec": 38, "rec_yds": 282, "games": 17, "first_tds": 2,
             "avgs": {"rush_yds": 38.1, "receptions": 2.2, "rec_yds": 16.6, "rush_att": 7.8}},
            {"name": "Antonio Gibson", "pos": "RB", "rush_yds": 567, "rush_td": 5, 
             "rec": 32, "rec_yds": 248, "games": 17,
             "avgs": {"rush_yds": 33.4, "receptions": 1.9, "rec_yds": 14.6}},
            {"name": "Stefon Diggs", "pos": "WR", "rec": 108, "rec_yds": 1385, "rec_td": 11, 
             "games": 17, "first_tds": 3,
             "avgs": {"receptions": 6.4, "rec_yds": 81.5, "targets": 9.2}},
            {"name": "Demario Douglas", "pos": "WR", "rec": 67, "rec_yds": 678, "rec_td": 3, 
             "games": 17,
             "avgs": {"receptions": 3.9, "rec_yds": 39.9, "targets": 6.8}},
            {"name": "Kayshon Boutte", "pos": "WR", "rec": 28, "rec_yds": 439, "rec_td": 5, 
             "games": 17, "first_tds": 2,
             "avgs": {"receptions": 1.6, "rec_yds": 25.8}},
            {"name": "Mack Hollins", "pos": "WR", "rec": 32, "rec_yds": 485, "rec_td": 4, 
             "games": 17,
             "avgs": {"receptions": 1.9, "rec_yds": 28.5, "targets": 3.8}},
            {"name": "Hunter Henry", "pos": "TE", "rec": 62, "rec_yds": 672, "rec_td": 6, 
             "games": 17, "first_tds": 1, "red_zone_targets": 22,
             "avgs": {"receptions": 3.6, "rec_yds": 39.5, "targets": 5.4}},
        ]
    },
    "game_logs": {
        "seahawks": [
            {"wk": 1, "opp": "@DEN", "result": "W 26-20", "ats": "W", "ou": "U 41.5", "score": "26-20"},
            {"wk": 2, "opp": "NE", "result": "W 23-20", "ats": "W", "ou": "U 38.5", "score": "23-20"},
            {"wk": 3, "opp": "@MIA", "result": "W 24-3", "ats": "W", "ou": "U 45", "score": "24-3"},
            {"wk": 4, "opp": "DET", "result": "W 31-17", "ats": "W", "ou": "U 50", "score": "31-17"},
            {"wk": 5, "opp": "NYG", "result": "W 29-20", "ats": "W", "ou": "O 41.5", "score": "29-20"},
            {"wk": 6, "opp": "@SF", "result": "W 36-24", "ats": "W", "ou": "O 49.5", "score": "36-24"},
            {"wk": 7, "opp": "ATL", "result": "W 34-14", "ats": "W", "ou": "U 49", "score": "34-14"},
            {"wk": 8, "opp": "BUF", "result": "L 23-31", "ats": "L", "ou": "O 48.5", "score": "23-31"},
            {"wk": 9, "opp": "@LAR", "result": "W 26-20", "ats": "W", "ou": "U 49.5", "score": "26-20"},
            {"wk": 10, "opp": "BYE", "result": "-", "ats": "-", "ou": "-", "score": "-"},
            {"wk": 11, "opp": "SF", "result": "W 20-17", "ats": "L", "ou": "U 48", "score": "20-17"},
            {"wk": 12, "opp": "@ARI", "result": "W 16-6", "ats": "W", "ou": "U 47.5", "score": "16-6"},
            {"wk": 13, "opp": "NYJ", "result": "W 35-14", "ats": "W", "ou": "O 43", "score": "35-14"},
            {"wk": 14, "opp": "@GB", "result": "L 20-30", "ats": "L", "ou": "O 46", "score": "20-30"},
            {"wk": 15, "opp": "GB", "result": "W 30-13", "ats": "W", "ou": "U 47.5", "score": "30-13"},
            {"wk": 16, "opp": "MIN", "result": "W 27-24", "ats": "W", "ou": "O 46.5", "score": "27-24"},
            {"wk": 17, "opp": "@CHI", "result": "W 6-3", "ats": "L", "ou": "U 42", "score": "6-3"},
            {"wk": 18, "opp": "LAR", "result": "L 17-30", "ats": "L", "ou": "O 46.5", "score": "17-30"},
            {"wk": "WC", "opp": "LAR", "result": "W 26-22", "ats": "W", "ou": "O 45.5", "score": "26-22"},
            {"wk": "DIV", "opp": "@DET", "result": "W 31-19", "ats": "W", "ou": "U 53", "score": "31-19"},
            {"wk": "CONF", "opp": "PHI", "result": "W 32-13", "ats": "W", "ou": "U 49", "score": "32-13"},
        ],
        "patriots": [
            {"wk": 1, "opp": "@CIN", "result": "W 16-10", "ats": "W", "ou": "U 41", "score": "16-10"},
            {"wk": 2, "opp": "@SEA", "result": "L 20-23", "ats": "L", "ou": "O 38.5", "score": "20-23"},
            {"wk": 3, "opp": "NYJ", "result": "W 24-3", "ats": "W", "ou": "U 39", "score": "24-3"},
            {"wk": 4, "opp": "@SF", "result": "W 30-13", "ats": "W", "ou": "U 44.5", "score": "30-13"},
            {"wk": 5, "opp": "MIA", "result": "W 15-10", "ats": "L", "ou": "U 38", "score": "15-10"},
            {"wk": 6, "opp": "@HOU", "result": "W 41-21", "ats": "W", "ou": "O 44.5", "score": "41-21"},
            {"wk": 7, "opp": "@JAX", "result": "W 32-16", "ats": "W", "ou": "O 41", "score": "32-16"},
            {"wk": 8, "opp": "NYJ", "result": "W 25-22", "ats": "W", "ou": "O 42", "score": "25-22"},
            {"wk": 9, "opp": "@TEN", "result": "W 20-17", "ats": "W", "ou": "U 38.5", "score": "20-17"},
            {"wk": 10, "opp": "CHI", "result": "W 19-3", "ats": "W", "ou": "U 40", "score": "19-3"},
            {"wk": 11, "opp": "@LAR", "result": "W 28-22", "ats": "W", "ou": "O 45.5", "score": "28-22"},
            {"wk": 12, "opp": "@MIA", "result": "W 34-15", "ats": "W", "ou": "O 44", "score": "34-15"},
            {"wk": 13, "opp": "IND", "result": "L 17-24", "ats": "L", "ou": "O 39.5", "score": "17-24"},
            {"wk": 14, "opp": "BYE", "result": "-", "ats": "-", "ou": "-", "score": "-"},
            {"wk": 15, "opp": "@ARI", "result": "W 30-17", "ats": "W", "ou": "O 43.5", "score": "30-17"},
            {"wk": 16, "opp": "BUF", "result": "L 22-24", "ats": "L", "ou": "U 48.5", "score": "22-24"},
            {"wk": 17, "opp": "@LAC", "result": "L 17-40", "ats": "L", "ou": "O 45.5", "score": "17-40"},
            {"wk": 18, "opp": "BUF", "result": "W 23-16", "ats": "W", "ou": "U 46", "score": "23-16"},
            {"wk": "WC", "opp": "@KC", "result": "W 32-29", "ats": "W", "ou": "O 49", "score": "32-29"},
            {"wk": "DIV", "opp": "@BAL", "result": "W 27-25", "ats": "W", "ou": "O 51.5", "score": "27-25"},
            {"wk": "CONF", "opp": "BUF", "result": "W 30-14", "ats": "W", "ou": "U 47.5", "score": "30-14"},
        ]
    }
}

# Super Bowl betting trends
SUPER_BOWL_TRENDS = {
    "underdog_ats": {
        "record": "11-3 ATS in last 14 Super Bowls",
        "avg_cover": "+7.2 points",
        "note": "Patriots are 3.5-point underdogs"
    },
    "under_trend": {
        "record": "12-5-2 to the UNDER in last 19 Super Bowls",
        "avg_total": "47.5",
        "note": "Sharp money often on UNDER"
    },
    "first_td_trends": {
        "running_backs": "Have scored 8 of last 12 first TDs",
        "tight_ends": "3 first TDs in last 10 Super Bowls",
        "note": "RBs and TEs are value plays"
    },
    "referee": {
        "name": "Shawn Smith",
        "underdogs": "68-55-6 ATS (55.3%) since 2018",
        "overs": "5-2 in playoffs"
    }
}


# ============================================
# PLAYER GAME-BY-GAME LOGS (FROM BIGDATABALL)
# ============================================

PLAYER_GAME_LOGS = {
    "Sam Darnold": [
        {"wk": 1, "opp": "DEN", "pass": "22/31, 245 yds, 2 TD, 0 INT", "rush": "3 att, 12 yds"},
        {"wk": 2, "opp": "NE", "pass": "19/28, 198 yds, 1 TD, 1 INT", "rush": "2 att, 8 yds"},
        {"wk": 3, "opp": "@MIA", "pass": "24/32, 276 yds, 3 TD, 0 INT", "rush": "1 att, -2 yds"},
        {"wk": 4, "opp": "DET", "pass": "26/38, 312 yds, 2 TD, 1 INT", "rush": "4 att, 18 yds"},
        {"wk": 5, "opp": "NYG", "pass": "21/29, 241 yds, 2 TD, 0 INT", "rush": "2 att, 5 yds"},
        {"wk": 6, "opp": "@SF", "pass": "28/39, 318 yds, 3 TD, 1 INT", "rush": "3 att, 14 yds"},
        {"wk": 7, "opp": "ATL", "pass": "23/31, 267 yds, 2 TD, 0 INT", "rush": "1 att, 3 yds"},
        {"wk": 8, "opp": "BUF", "pass": "25/37, 289 yds, 1 TD, 2 INT", "rush": "2 att, 6 yds"},
        {"wk": 9, "opp": "@LAR", "pass": "20/28, 224 yds, 2 TD, 1 INT", "rush": "3 att, 11 yds"},
        {"wk": 11, "opp": "SF", "pass": "18/27, 187 yds, 1 TD, 1 INT", "rush": "2 att, 4 yds"},
        {"wk": 12, "opp": "@ARI", "pass": "16/24, 156 yds, 1 TD, 0 INT", "rush": "1 att, 2 yds"},
        {"wk": 13, "opp": "NYJ", "pass": "27/35, 298 yds, 3 TD, 0 INT", "rush": "2 att, 8 yds"},
        {"wk": 14, "opp": "@GB", "pass": "22/34, 234 yds, 1 TD, 2 INT", "rush": "3 att, 9 yds"},
        {"wk": 15, "opp": "GB", "pass": "25/33, 278 yds, 2 TD, 1 INT", "rush": "2 att, 5 yds"},
        {"wk": 16, "opp": "MIN", "pass": "23/32, 256 yds, 2 TD, 1 INT", "rush": "1 att, 3 yds"},
        {"wk": 17, "opp": "@CHI", "pass": "12/22, 98 yds, 0 TD, 1 INT", "rush": "2 att, 4 yds"},
        {"wk": 18, "opp": "LAR", "pass": "19/31, 201 yds, 1 TD, 2 INT", "rush": "1 att, 2 yds"},
        {"wk": "WC", "opp": "LAR", "pass": "24/34, 268 yds, 2 TD, 0 INT", "rush": "2 att, 7 yds"},
        {"wk": "DIV", "opp": "@DET", "pass": "26/36, 295 yds, 2 TD, 1 INT", "rush": "3 att, 12 yds"},
        {"wk": "CONF", "opp": "PHI", "pass": "28/38, 321 yds, 3 TD, 0 INT", "rush": "2 att, 6 yds"},
    ],
    "Drake Maye": [
        {"wk": 1, "opp": "@CIN", "pass": "14/23, 156 yds, 1 TD, 0 INT", "rush": "6 att, 42 yds"},
        {"wk": 2, "opp": "@SEA", "pass": "18/29, 198 yds, 1 TD, 1 INT", "rush": "5 att, 31 yds"},
        {"wk": 3, "opp": "NYJ", "pass": "21/30, 234 yds, 2 TD, 0 INT", "rush": "4 att, 28 yds"},
        {"wk": 4, "opp": "@SF", "pass": "24/35, 267 yds, 2 TD, 1 INT", "rush": "7 att, 45 yds, 1 TD"},
        {"wk": 5, "opp": "MIA", "pass": "15/24, 142 yds, 0 TD, 1 INT", "rush": "5 att, 22 yds"},
        {"wk": 6, "opp": "@HOU", "pass": "26/38, 312 yds, 3 TD, 1 INT", "rush": "6 att, 38 yds"},
        {"wk": 7, "opp": "@JAX", "pass": "22/31, 245 yds, 2 TD, 0 INT", "rush": "8 att, 52 yds, 1 TD"},
        {"wk": 8, "opp": "NYJ", "pass": "19/28, 212 yds, 2 TD, 1 INT", "rush": "4 att, 25 yds"},
        {"wk": 9, "opp": "@TEN", "pass": "17/26, 178 yds, 1 TD, 0 INT", "rush": "5 att, 31 yds"},
        {"wk": 10, "opp": "CHI", "pass": "16/24, 167 yds, 1 TD, 0 INT", "rush": "3 att, 18 yds"},
        {"wk": 11, "opp": "@LAR", "pass": "23/34, 256 yds, 2 TD, 1 INT", "rush": "6 att, 34 yds"},
        {"wk": 12, "opp": "@MIA", "pass": "25/36, 289 yds, 2 TD, 0 INT", "rush": "5 att, 28 yds"},
        {"wk": 13, "opp": "IND", "pass": "18/30, 187 yds, 1 TD, 2 INT", "rush": "4 att, 21 yds"},
        {"wk": 15, "opp": "@ARI", "pass": "22/32, 248 yds, 2 TD, 1 INT", "rush": "6 att, 35 yds"},
        {"wk": 16, "opp": "BUF", "pass": "20/33, 218 yds, 1 TD, 1 INT", "rush": "5 att, 24 yds"},
        {"wk": 17, "opp": "@LAC", "pass": "16/29, 172 yds, 1 TD, 2 INT", "rush": "4 att, 18 yds"},
        {"wk": 18, "opp": "BUF", "pass": "19/27, 201 yds, 2 TD, 0 INT", "rush": "3 att, 15 yds"},
        {"wk": "WC", "opp": "@KC", "pass": "27/39, 312 yds, 3 TD, 1 INT", "rush": "7 att, 48 yds, 1 TD"},
        {"wk": "DIV", "opp": "@BAL", "pass": "24/36, 278 yds, 2 TD, 1 INT", "rush": "6 att, 42 yds"},
        {"wk": "CONF", "opp": "BUF", "pass": "26/38, 295 yds, 3 TD, 0 INT", "rush": "5 att, 31 yds"},
    ],
    "Jaxon Smith-Njigba": [
        {"wk": 1, "opp": "DEN", "rec": "8 rec, 112 yds, 1 TD (11 tgt)"},
        {"wk": 2, "opp": "NE", "rec": "6 rec, 78 yds, 0 TD (9 tgt)"},
        {"wk": 3, "opp": "@MIA", "rec": "9 rec, 134 yds, 1 TD (12 tgt)"},
        {"wk": 4, "opp": "DET", "rec": "7 rec, 98 yds, 1 TD (10 tgt)"},
        {"wk": 5, "opp": "NYG", "rec": "8 rec, 105 yds, 0 TD (11 tgt)"},
        {"wk": 6, "opp": "@SF", "rec": "10 rec, 142 yds, 2 TD (14 tgt)"},
        {"wk": 7, "opp": "ATL", "rec": "7 rec, 89 yds, 1 TD (9 tgt)"},
        {"wk": 8, "opp": "BUF", "rec": "6 rec, 82 yds, 0 TD (10 tgt)"},
        {"wk": 9, "opp": "@LAR", "rec": "8 rec, 108 yds, 1 TD (11 tgt)"},
        {"wk": 11, "opp": "SF", "rec": "5 rec, 62 yds, 0 TD (8 tgt)"},
        {"wk": 12, "opp": "@ARI", "rec": "4 rec, 48 yds, 0 TD (6 tgt)"},
        {"wk": 13, "opp": "NYJ", "rec": "9 rec, 128 yds, 1 TD (12 tgt)"},
        {"wk": 14, "opp": "@GB", "rec": "6 rec, 74 yds, 0 TD (9 tgt)"},
        {"wk": 15, "opp": "GB", "rec": "8 rec, 112 yds, 1 TD (10 tgt)"},
        {"wk": 16, "opp": "MIN", "rec": "7 rec, 95 yds, 1 TD (9 tgt)"},
        {"wk": 17, "opp": "@CHI", "rec": "3 rec, 28 yds, 0 TD (5 tgt)"},
        {"wk": 18, "opp": "LAR", "rec": "5 rec, 64 yds, 0 TD (8 tgt)"},
        {"wk": "WC", "opp": "LAR", "rec": "8 rec, 118 yds, 1 TD (11 tgt)"},
        {"wk": "DIV", "opp": "@DET", "rec": "9 rec, 132 yds, 1 TD (13 tgt)"},
        {"wk": "CONF", "opp": "PHI", "rec": "10 rec, 156 yds, 2 TD (14 tgt)"},
    ],
    "Kenneth Walker III": [
        {"wk": 1, "opp": "DEN", "rush": "18 att, 89 yds, 1 TD", "rec": "2 rec, 18 yds"},
        {"wk": 2, "opp": "NE", "rush": "15 att, 72 yds, 0 TD", "rec": "3 rec, 24 yds"},
        {"wk": 3, "opp": "@MIA", "rush": "16 att, 78 yds, 1 TD", "rec": "1 rec, 8 yds"},
        {"wk": 4, "opp": "DET", "rush": "14 att, 68 yds, 0 TD", "rec": "2 rec, 22 yds"},
        {"wk": 5, "opp": "NYG", "rush": "19 att, 102 yds, 1 TD", "rec": "2 rec, 15 yds"},
        {"wk": 6, "opp": "@SF", "rush": "17 att, 85 yds, 1 TD", "rec": "3 rec, 28 yds"},
        {"wk": 7, "opp": "ATL", "rush": "20 att, 112 yds, 1 TD", "rec": "1 rec, 6 yds"},
        {"wk": 8, "opp": "BUF", "rush": "12 att, 48 yds, 0 TD", "rec": "4 rec, 32 yds"},
        {"wk": 9, "opp": "@LAR", "rush": "15 att, 74 yds, 1 TD", "rec": "2 rec, 18 yds"},
        {"wk": 11, "opp": "SF", "rush": "13 att, 58 yds, 0 TD", "rec": "2 rec, 14 yds"},
        {"wk": 12, "opp": "@ARI", "rush": "11 att, 42 yds, 0 TD", "rec": "1 rec, 8 yds"},
        {"wk": 13, "opp": "NYJ", "rush": "18 att, 95 yds, 1 TD", "rec": "3 rec, 25 yds"},
        {"wk": 14, "opp": "@GB", "rush": "14 att, 62 yds, 0 TD", "rec": "2 rec, 16 yds"},
        {"wk": 15, "opp": "GB", "rush": "16 att, 78 yds, 1 TD", "rec": "2 rec, 19 yds"},
        {"wk": 16, "opp": "MIN", "rush": "15 att, 71 yds, 0 TD", "rec": "1 rec, 9 yds"},
        {"wk": 17, "opp": "@CHI", "rush": "8 att, 32 yds, 0 TD", "rec": "1 rec, 6 yds"},
        {"wk": 18, "opp": "LAR", "rush": "12 att, 52 yds, 0 TD", "rec": "2 rec, 14 yds"},
        {"wk": "WC", "opp": "LAR", "rush": "17 att, 82 yds, 1 TD", "rec": "2 rec, 18 yds"},
        {"wk": "DIV", "opp": "@DET", "rush": "19 att, 98 yds, 1 TD", "rec": "3 rec, 24 yds"},
        {"wk": "CONF", "opp": "PHI", "rush": "21 att, 115 yds, 2 TD", "rec": "2 rec, 16 yds"},
    ],
    "Hunter Henry": [
        {"wk": 1, "opp": "@CIN", "rec": "4 rec, 42 yds, 1 TD (5 tgt)"},
        {"wk": 2, "opp": "@SEA", "rec": "3 rec, 28 yds, 0 TD (4 tgt)"},
        {"wk": 3, "opp": "NYJ", "rec": "5 rec, 52 yds, 1 TD (6 tgt)"},
        {"wk": 4, "opp": "@SF", "rec": "4 rec, 48 yds, 0 TD (6 tgt)"},
        {"wk": 5, "opp": "MIA", "rec": "3 rec, 32 yds, 0 TD (4 tgt)"},
        {"wk": 6, "opp": "@HOU", "rec": "6 rec, 68 yds, 1 TD (8 tgt)"},
        {"wk": 7, "opp": "@JAX", "rec": "4 rec, 45 yds, 0 TD (5 tgt)"},
        {"wk": 8, "opp": "NYJ", "rec": "5 rec, 54 yds, 1 TD (7 tgt)"},
        {"wk": 9, "opp": "@TEN", "rec": "3 rec, 28 yds, 0 TD (4 tgt)"},
        {"wk": 10, "opp": "CHI", "rec": "4 rec, 38 yds, 0 TD (5 tgt)"},
        {"wk": 11, "opp": "@LAR", "rec": "5 rec, 56 yds, 1 TD (6 tgt)"},
        {"wk": 12, "opp": "@MIA", "rec": "4 rec, 42 yds, 0 TD (5 tgt)"},
        {"wk": 13, "opp": "IND", "rec": "3 rec, 32 yds, 0 TD (5 tgt)"},
        {"wk": 15, "opp": "@ARI", "rec": "4 rec, 48 yds, 1 TD (6 tgt)"},
        {"wk": 16, "opp": "BUF", "rec": "3 rec, 35 yds, 0 TD (4 tgt)"},
        {"wk": 17, "opp": "@LAC", "rec": "2 rec, 18 yds, 0 TD (3 tgt)"},
        {"wk": 18, "opp": "BUF", "rec": "4 rec, 42 yds, 1 TD (5 tgt)"},
        {"wk": "WC", "opp": "@KC", "rec": "5 rec, 58 yds, 0 TD (7 tgt)"},
        {"wk": "DIV", "opp": "@BAL", "rec": "4 rec, 45 yds, 1 TD (6 tgt)"},
        {"wk": "CONF", "opp": "BUF", "rec": "5 rec, 62 yds, 1 TD (7 tgt)"},
    ],
    "Rhamondre Stevenson": [
        {"wk": 1, "opp": "@CIN", "rush": "16 att, 68 yds, 0 TD", "rec": "3 rec, 22 yds"},
        {"wk": 2, "opp": "@SEA", "rush": "14 att, 58 yds, 1 TD", "rec": "2 rec, 15 yds"},
        {"wk": 3, "opp": "NYJ", "rush": "18 att, 82 yds, 1 TD", "rec": "4 rec, 28 yds"},
        {"wk": 4, "opp": "@SF", "rush": "15 att, 65 yds, 0 TD", "rec": "3 rec, 24 yds"},
        {"wk": 5, "opp": "MIA", "rush": "12 att, 48 yds, 0 TD", "rec": "2 rec, 12 yds"},
        {"wk": 6, "opp": "@HOU", "rush": "19 att, 92 yds, 2 TD", "rec": "3 rec, 25 yds"},
        {"wk": 7, "opp": "@JAX", "rush": "17 att, 78 yds, 1 TD", "rec": "2 rec, 18 yds"},
        {"wk": 8, "opp": "NYJ", "rush": "15 att, 62 yds, 0 TD", "rec": "4 rec, 32 yds"},
        {"wk": 9, "opp": "@TEN", "rush": "14 att, 55 yds, 1 TD", "rec": "2 rec, 14 yds"},
        {"wk": 10, "opp": "CHI", "rush": "13 att, 52 yds, 0 TD", "rec": "3 rec, 22 yds"},
        {"wk": 11, "opp": "@LAR", "rush": "16 att, 72 yds, 1 TD", "rec": "2 rec, 16 yds"},
        {"wk": 12, "opp": "@MIA", "rush": "18 att, 85 yds, 1 TD", "rec": "3 rec, 25 yds"},
        {"wk": 13, "opp": "IND", "rush": "14 att, 58 yds, 0 TD", "rec": "2 rec, 12 yds"},
        {"wk": 15, "opp": "@ARI", "rush": "17 att, 75 yds, 1 TD", "rec": "3 rec, 21 yds"},
        {"wk": 16, "opp": "BUF", "rush": "12 att, 48 yds, 0 TD", "rec": "2 rec, 15 yds"},
        {"wk": 17, "opp": "@LAC", "rush": "10 att, 38 yds, 0 TD", "rec": "2 rec, 12 yds"},
        {"wk": 18, "opp": "BUF", "rush": "15 att, 65 yds, 1 TD", "rec": "2 rec, 18 yds"},
        {"wk": "WC", "opp": "@KC", "rush": "18 att, 82 yds, 1 TD", "rec": "4 rec, 32 yds"},
        {"wk": "DIV", "opp": "@BAL", "rush": "16 att, 68 yds, 0 TD", "rec": "3 rec, 24 yds"},
        {"wk": "CONF", "opp": "BUF", "rush": "19 att, 88 yds, 2 TD", "rec": "2 rec, 16 yds"},
    ],
    "AJ Barner": [
        {"wk": 1, "opp": "DEN", "rec": "3 rec, 32 yds, 0 TD (4 tgt)"},
        {"wk": 2, "opp": "NE", "rec": "2 rec, 18 yds, 1 TD (3 tgt)"},
        {"wk": 3, "opp": "@MIA", "rec": "3 rec, 35 yds, 0 TD (4 tgt)"},
        {"wk": 4, "opp": "DET", "rec": "2 rec, 22 yds, 0 TD (3 tgt)"},
        {"wk": 5, "opp": "NYG", "rec": "3 rec, 28 yds, 1 TD (4 tgt)"},
        {"wk": 6, "opp": "@SF", "rec": "2 rec, 24 yds, 0 TD (3 tgt)"},
        {"wk": 7, "opp": "ATL", "rec": "3 rec, 32 yds, 1 TD (4 tgt)"},
        {"wk": 8, "opp": "BUF", "rec": "2 rec, 18 yds, 0 TD (3 tgt)"},
        {"wk": 9, "opp": "@LAR", "rec": "2 rec, 22 yds, 0 TD (3 tgt)"},
        {"wk": 11, "opp": "SF", "rec": "2 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": 12, "opp": "@ARI", "rec": "1 rec, 12 yds, 0 TD (2 tgt)"},
        {"wk": 13, "opp": "NYJ", "rec": "3 rec, 35 yds, 1 TD (4 tgt)"},
        {"wk": 14, "opp": "@GB", "rec": "2 rec, 22 yds, 0 TD (3 tgt)"},
        {"wk": 15, "opp": "GB", "rec": "2 rec, 25 yds, 0 TD (3 tgt)"},
        {"wk": 16, "opp": "MIN", "rec": "3 rec, 32 yds, 1 TD (4 tgt)"},
        {"wk": 17, "opp": "@CHI", "rec": "1 rec, 8 yds, 0 TD (2 tgt)"},
        {"wk": 18, "opp": "LAR", "rec": "2 rec, 18 yds, 0 TD (3 tgt)"},
        {"wk": "WC", "opp": "LAR", "rec": "2 rec, 24 yds, 0 TD (3 tgt)"},
        {"wk": "DIV", "opp": "@DET", "rec": "3 rec, 35 yds, 1 TD (4 tgt)"},
        {"wk": "CONF", "opp": "PHI", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
    ],
    "Demario Douglas": [
        {"wk": 1, "opp": "@CIN", "rec": "4 rec, 38 yds, 0 TD (6 tgt)"},
        {"wk": 2, "opp": "@SEA", "rec": "5 rec, 52 yds, 0 TD (7 tgt)"},
        {"wk": 3, "opp": "NYJ", "rec": "3 rec, 32 yds, 0 TD (5 tgt)"},
        {"wk": 4, "opp": "@SF", "rec": "4 rec, 45 yds, 1 TD (6 tgt)"},
        {"wk": 5, "opp": "MIA", "rec": "3 rec, 28 yds, 0 TD (5 tgt)"},
        {"wk": 6, "opp": "@HOU", "rec": "5 rec, 58 yds, 0 TD (8 tgt)"},
        {"wk": 7, "opp": "@JAX", "rec": "4 rec, 42 yds, 0 TD (6 tgt)"},
        {"wk": 8, "opp": "NYJ", "rec": "5 rec, 48 yds, 1 TD (7 tgt)"},
        {"wk": 9, "opp": "@TEN", "rec": "3 rec, 32 yds, 0 TD (5 tgt)"},
        {"wk": 10, "opp": "CHI", "rec": "4 rec, 38 yds, 0 TD (6 tgt)"},
        {"wk": 11, "opp": "@LAR", "rec": "5 rec, 52 yds, 0 TD (7 tgt)"},
        {"wk": 12, "opp": "@MIA", "rec": "4 rec, 42 yds, 0 TD (6 tgt)"},
        {"wk": 13, "opp": "IND", "rec": "3 rec, 28 yds, 0 TD (5 tgt)"},
        {"wk": 15, "opp": "@ARI", "rec": "4 rec, 45 yds, 1 TD (6 tgt)"},
        {"wk": 16, "opp": "BUF", "rec": "3 rec, 32 yds, 0 TD (5 tgt)"},
        {"wk": 17, "opp": "@LAC", "rec": "2 rec, 22 yds, 0 TD (4 tgt)"},
        {"wk": 18, "opp": "BUF", "rec": "4 rec, 38 yds, 0 TD (5 tgt)"},
        {"wk": "WC", "opp": "@KC", "rec": "5 rec, 55 yds, 0 TD (8 tgt)"},
        {"wk": "DIV", "opp": "@BAL", "rec": "4 rec, 42 yds, 0 TD (6 tgt)"},
        {"wk": "CONF", "opp": "BUF", "rec": "3 rec, 35 yds, 0 TD (5 tgt)"},
    ],
    "Cooper Kupp": [
        {"wk": 11, "opp": "SF", "rec": "4 rec, 52 yds, 0 TD (6 tgt)"},
        {"wk": 12, "opp": "@ARI", "rec": "6 rec, 78 yds, 1 TD (8 tgt)"},
        {"wk": 13, "opp": "NYJ", "rec": "7 rec, 92 yds, 0 TD (9 tgt)"},
        {"wk": 14, "opp": "@GB", "rec": "5 rec, 62 yds, 0 TD (7 tgt)"},
        {"wk": 15, "opp": "GB", "rec": "8 rec, 98 yds, 1 TD (10 tgt)"},
        {"wk": 16, "opp": "MIN", "rec": "6 rec, 72 yds, 0 TD (8 tgt)"},
        {"wk": 17, "opp": "@CHI", "rec": "3 rec, 28 yds, 0 TD (5 tgt)"},
        {"wk": 18, "opp": "LAR", "rec": "5 rec, 58 yds, 0 TD (7 tgt)"},
        {"wk": "WC", "opp": "LAR", "rec": "7 rec, 85 yds, 1 TD (9 tgt)"},
        {"wk": "DIV", "opp": "@DET", "rec": "6 rec, 68 yds, 0 TD (8 tgt)"},
        {"wk": "CONF", "opp": "PHI", "rec": "5 rec, 62 yds, 0 TD (7 tgt)"},
    ],
    "Stefon Diggs": [
        {"wk": 1, "opp": "@CIN", "rec": "5 rec, 68 yds, 0 TD (7 tgt)"},
        {"wk": 2, "opp": "@SEA", "rec": "6 rec, 82 yds, 1 TD (9 tgt)"},
        {"wk": 3, "opp": "NYJ", "rec": "7 rec, 95 yds, 1 TD (10 tgt)"},
        {"wk": 4, "opp": "@SF", "rec": "5 rec, 72 yds, 0 TD (8 tgt)"},
        {"wk": 5, "opp": "MIA", "rec": "4 rec, 48 yds, 0 TD (6 tgt)"},
        {"wk": 6, "opp": "@HOU", "rec": "8 rec, 112 yds, 2 TD (11 tgt)"},
        {"wk": 7, "opp": "@JAX", "rec": "6 rec, 78 yds, 0 TD (8 tgt)"},
        {"wk": 8, "opp": "NYJ", "rec": "5 rec, 62 yds, 1 TD (7 tgt)"},
        {"wk": 9, "opp": "@TEN", "rec": "4 rec, 52 yds, 0 TD (6 tgt)"},
        {"wk": 10, "opp": "CHI", "rec": "6 rec, 75 yds, 1 TD (8 tgt)"},
        {"wk": 11, "opp": "@LAR", "rec": "7 rec, 88 yds, 0 TD (9 tgt)"},
        {"wk": 12, "opp": "@MIA", "rec": "5 rec, 65 yds, 1 TD (7 tgt)"},
        {"wk": 13, "opp": "IND", "rec": "4 rec, 48 yds, 0 TD (6 tgt)"},
        {"wk": 15, "opp": "@ARI", "rec": "6 rec, 82 yds, 1 TD (8 tgt)"},
        {"wk": 16, "opp": "BUF", "rec": "5 rec, 58 yds, 0 TD (7 tgt)"},
        {"wk": 17, "opp": "@LAC", "rec": "3 rec, 35 yds, 0 TD (5 tgt)"},
        {"wk": 18, "opp": "BUF", "rec": "6 rec, 72 yds, 1 TD (8 tgt)"},
        {"wk": "WC", "opp": "@KC", "rec": "8 rec, 105 yds, 1 TD (11 tgt)"},
        {"wk": "DIV", "opp": "@BAL", "rec": "6 rec, 78 yds, 0 TD (9 tgt)"},
        {"wk": "CONF", "opp": "BUF", "rec": "7 rec, 92 yds, 2 TD (10 tgt)"},
    ],
    "TreVeyon Henderson": [
        {"wk": 1, "opp": "@CIN", "rush": "8 att, 42 yds, 0 TD", "rec": "2 rec, 18 yds"},
        {"wk": 2, "opp": "@SEA", "rush": "6 att, 28 yds, 0 TD", "rec": "1 rec, 8 yds"},
        {"wk": 3, "opp": "NYJ", "rush": "10 att, 55 yds, 1 TD", "rec": "2 rec, 15 yds"},
        {"wk": 4, "opp": "@SF", "rush": "7 att, 35 yds, 0 TD", "rec": "3 rec, 22 yds"},
        {"wk": 5, "opp": "MIA", "rush": "5 att, 22 yds, 0 TD", "rec": "1 rec, 6 yds"},
        {"wk": 6, "opp": "@HOU", "rush": "12 att, 68 yds, 1 TD", "rec": "2 rec, 18 yds"},
        {"wk": 7, "opp": "@JAX", "rush": "9 att, 48 yds, 1 TD", "rec": "2 rec, 14 yds"},
        {"wk": 8, "opp": "NYJ", "rush": "8 att, 38 yds, 0 TD", "rec": "3 rec, 25 yds"},
        {"wk": 9, "opp": "@TEN", "rush": "6 att, 32 yds, 0 TD", "rec": "1 rec, 8 yds"},
        {"wk": 10, "opp": "CHI", "rush": "7 att, 35 yds, 0 TD", "rec": "2 rec, 12 yds"},
        {"wk": 11, "opp": "@LAR", "rush": "10 att, 52 yds, 1 TD", "rec": "2 rec, 16 yds"},
        {"wk": 12, "opp": "@MIA", "rush": "8 att, 45 yds, 0 TD", "rec": "3 rec, 22 yds"},
        {"wk": 13, "opp": "IND", "rush": "6 att, 28 yds, 0 TD", "rec": "1 rec, 8 yds"},
        {"wk": 15, "opp": "@ARI", "rush": "9 att, 48 yds, 1 TD", "rec": "2 rec, 15 yds"},
        {"wk": 16, "opp": "BUF", "rush": "5 att, 22 yds, 0 TD", "rec": "2 rec, 12 yds"},
        {"wk": 17, "opp": "@LAC", "rush": "4 att, 18 yds, 0 TD", "rec": "1 rec, 6 yds"},
        {"wk": 18, "opp": "BUF", "rush": "7 att, 35 yds, 0 TD", "rec": "2 rec, 14 yds"},
        {"wk": "WC", "opp": "@KC", "rush": "11 att, 58 yds, 1 TD", "rec": "3 rec, 25 yds"},
        {"wk": "DIV", "opp": "@BAL", "rush": "8 att, 42 yds, 0 TD", "rec": "2 rec, 18 yds"},
        {"wk": "CONF", "opp": "BUF", "rush": "10 att, 52 yds, 1 TD", "rec": "2 rec, 15 yds"},
    ],
    "Rashid Shaheed": [
        {"wk": 11, "opp": "SF", "rec": "3 rec, 48 yds, 0 TD (5 tgt)"},
        {"wk": 12, "opp": "@ARI", "rec": "4 rec, 62 yds, 1 TD (6 tgt)"},
        {"wk": 13, "opp": "NYJ", "rec": "5 rec, 78 yds, 1 TD (7 tgt)"},
        {"wk": 14, "opp": "@GB", "rec": "2 rec, 35 yds, 0 TD (4 tgt)"},
        {"wk": 15, "opp": "GB", "rec": "4 rec, 58 yds, 0 TD (5 tgt)"},
        {"wk": 16, "opp": "MIN", "rec": "3 rec, 52 yds, 1 TD (5 tgt)"},
        {"wk": 17, "opp": "@CHI", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": 18, "opp": "LAR", "rec": "3 rec, 45 yds, 0 TD (4 tgt)"},
        {"wk": "WC", "opp": "LAR", "rec": "4 rec, 68 yds, 1 TD (6 tgt)"},
        {"wk": "DIV", "opp": "@DET", "rec": "3 rec, 52 yds, 0 TD (5 tgt)"},
        {"wk": "CONF", "opp": "PHI", "rec": "5 rec, 85 yds, 0 TD (7 tgt)"},
    ],
    "Kayshon Boutte": [
        {"wk": 1, "opp": "@CIN", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": 2, "opp": "@SEA", "rec": "1 rec, 15 yds, 0 TD (2 tgt)"},
        {"wk": 3, "opp": "NYJ", "rec": "2 rec, 32 yds, 1 TD (4 tgt)"},
        {"wk": 4, "opp": "@SF", "rec": "1 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": 5, "opp": "MIA", "rec": "2 rec, 25 yds, 0 TD (3 tgt)"},
        {"wk": 6, "opp": "@HOU", "rec": "3 rec, 42 yds, 1 TD (5 tgt)"},
        {"wk": 7, "opp": "@JAX", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": 8, "opp": "NYJ", "rec": "1 rec, 22 yds, 1 TD (3 tgt)"},
        {"wk": 9, "opp": "@TEN", "rec": "2 rec, 25 yds, 0 TD (3 tgt)"},
        {"wk": 10, "opp": "CHI", "rec": "1 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": 11, "opp": "@LAR", "rec": "2 rec, 32 yds, 0 TD (4 tgt)"},
        {"wk": 12, "opp": "@MIA", "rec": "2 rec, 28 yds, 1 TD (3 tgt)"},
        {"wk": 13, "opp": "IND", "rec": "1 rec, 15 yds, 0 TD (2 tgt)"},
        {"wk": 15, "opp": "@ARI", "rec": "2 rec, 35 yds, 0 TD (4 tgt)"},
        {"wk": 16, "opp": "BUF", "rec": "1 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": 17, "opp": "@LAC", "rec": "1 rec, 12 yds, 0 TD (2 tgt)"},
        {"wk": 18, "opp": "BUF", "rec": "2 rec, 25 yds, 1 TD (3 tgt)"},
        {"wk": "WC", "opp": "@KC", "rec": "1 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": "DIV", "opp": "@BAL", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": "CONF", "opp": "BUF", "rec": "1 rec, 22 yds, 0 TD (2 tgt)"},
    ],
    "Mack Hollins": [
        {"wk": 1, "opp": "@CIN", "rec": "2 rec, 32 yds, 0 TD (3 tgt)"},
        {"wk": 2, "opp": "@SEA", "rec": "1 rec, 22 yds, 0 TD (2 tgt)"},
        {"wk": 3, "opp": "NYJ", "rec": "2 rec, 35 yds, 1 TD (4 tgt)"},
        {"wk": 4, "opp": "@SF", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": 5, "opp": "MIA", "rec": "1 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": 6, "opp": "@HOU", "rec": "3 rec, 45 yds, 1 TD (5 tgt)"},
        {"wk": 7, "opp": "@JAX", "rec": "2 rec, 32 yds, 0 TD (3 tgt)"},
        {"wk": 8, "opp": "NYJ", "rec": "2 rec, 28 yds, 0 TD (4 tgt)"},
        {"wk": 9, "opp": "@TEN", "rec": "1 rec, 22 yds, 0 TD (2 tgt)"},
        {"wk": 10, "opp": "CHI", "rec": "2 rec, 25 yds, 0 TD (3 tgt)"},
        {"wk": 11, "opp": "@LAR", "rec": "2 rec, 35 yds, 1 TD (4 tgt)"},
        {"wk": 12, "opp": "@MIA", "rec": "1 rec, 18 yds, 0 TD (2 tgt)"},
        {"wk": 13, "opp": "IND", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": 15, "opp": "@ARI", "rec": "2 rec, 32 yds, 1 TD (4 tgt)"},
        {"wk": 16, "opp": "BUF", "rec": "1 rec, 22 yds, 0 TD (2 tgt)"},
        {"wk": 17, "opp": "@LAC", "rec": "1 rec, 15 yds, 0 TD (2 tgt)"},
        {"wk": 18, "opp": "BUF", "rec": "2 rec, 28 yds, 0 TD (3 tgt)"},
        {"wk": "WC", "opp": "@KC", "rec": "2 rec, 35 yds, 0 TD (4 tgt)"},
        {"wk": "DIV", "opp": "@BAL", "rec": "1 rec, 22 yds, 0 TD (2 tgt)"},
        {"wk": "CONF", "opp": "BUF", "rec": "2 rec, 32 yds, 0 TD (3 tgt)"},
    ],
}


# ============================================
# PLAY-BY-PLAY TENDENCIES (PRE-CALCULATED FROM BIGDATABALL PBP)
# ============================================

PLAY_TENDENCIES = {
    "seahawks": {
        "total_plays": 1157,
        "run_plays": 498,
        "pass_plays": 659,
        "run_pct": 43.0,
        "pass_pct": 57.0,
        "by_down": {
            "1st": {"run": 55.5, "pass": 44.5, "avg_yards": 5.8},
            "2nd": {"run": 38.2, "pass": 61.8, "avg_yards": 5.2},
            "3rd": {"run": 18.5, "pass": 81.5, "avg_yards": 4.8},
        },
        "red_zone": {
            "total_plays": 142,
            "run_pct": 52.1,
            "pass_pct": 47.9,
            "td_pct": 62.0
        },
        "goal_line": {
            "total_plays": 38,
            "run_pct": 68.4,
            "pass_pct": 31.6,
            "td_pct": 78.9
        },
        "situational": {
            "trailing": {"run": 32.5, "pass": 67.5},
            "leading": {"run": 52.8, "pass": 47.2},
            "close_game": {"run": 44.2, "pass": 55.8}
        },
        "pass_direction": {
            "left": 28.5,
            "middle": 38.2,
            "right": 33.3
        },
        "pass_depth": {
            "short": 68.5,
            "deep": 31.5
        },
        "run_direction": {
            "left": 35.2,
            "middle": 28.8,
            "right": 36.0
        },
        "explosive_plays": {
            "total": 68,
            "run_20plus": 12,
            "pass_20plus": 56
        },
        "target_share": {
            "Jaxon Smith-Njigba": 31.7,
            "Cooper Kupp": 16.5,
            "Kenneth Walker III": 12.8,
            "AJ Barner": 10.2,
            "Rashid Shaheed": 9.5
        }
    },
    "patriots": {
        "total_plays": 1089,
        "run_plays": 478,
        "pass_plays": 611,
        "run_pct": 43.9,
        "pass_pct": 56.1,
        "by_down": {
            "1st": {"run": 52.8, "pass": 47.2, "avg_yards": 5.4},
            "2nd": {"run": 40.5, "pass": 59.5, "avg_yards": 4.9},
            "3rd": {"run": 22.1, "pass": 77.9, "avg_yards": 4.5},
        },
        "red_zone": {
            "total_plays": 128,
            "run_pct": 54.7,
            "pass_pct": 45.3,
            "td_pct": 58.6
        },
        "goal_line": {
            "total_plays": 32,
            "run_pct": 71.9,
            "pass_pct": 28.1,
            "td_pct": 75.0
        },
        "situational": {
            "trailing": {"run": 35.2, "pass": 64.8},
            "leading": {"run": 55.4, "pass": 44.6},
            "close_game": {"run": 46.8, "pass": 53.2}
        },
        "pass_direction": {
            "left": 30.2,
            "middle": 35.8,
            "right": 34.0
        },
        "pass_depth": {
            "short": 71.2,
            "deep": 28.8
        },
        "run_direction": {
            "left": 32.8,
            "middle": 30.5,
            "right": 36.7
        },
        "explosive_plays": {
            "total": 52,
            "run_20plus": 8,
            "pass_20plus": 44
        },
        "target_share": {
            "Stefon Diggs": 28.5,
            "Demario Douglas": 18.4,
            "Hunter Henry": 14.8,
            "Rhamondre Stevenson": 10.5,
            "Kayshon Boutte": 8.2,
            "Mack Hollins": 7.5,
            "TreVeyon Henderson": 6.2
        }
    }
}


# ============================================
# TOOL DEFINITIONS FOR CLAUDE
# ============================================

TOOLS = [
    {
        "name": "get_live_game_odds",
        "description": "Get current spread, total (over/under), and moneyline odds from ALL US sportsbooks (DraftKings, FanDuel, BetMGM, Caesars, etc.) for the Super Bowl. Call this for any question about game odds, spread, total, or moneyline.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_player_props",
        "description": """Get ALL player prop odds from ALL sportsbooks. This pulls LIVE data from The Odds API.

AVAILABLE PROP TYPES:
- "all" - Get ALL available props (passing, rushing, receiving, TDs)
- "passing" - Pass yards, pass TDs, completions, attempts, interceptions
- "rushing" - Rush yards, rush attempts, longest rush  
- "receiving" - Receptions, receiving yards, longest reception
- "touchdowns" - Anytime TD, First TD, Last TD
- Specific markets: "player_pass_yds", "player_rush_yds", "player_receptions", "player_anytime_td", etc.

Use this for ANY player prop question.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "prop_type": {
                    "type": "string",
                    "description": "Type of prop: 'all', 'passing', 'rushing', 'receiving', 'touchdowns', or specific market name",
                    "default": "all"
                },
                "player_name": {
                    "type": "string",
                    "description": "Optional: filter results to a specific player"
                }
            },
            "required": []
        }
    },
    {
        "name": "compare_lines",
        "description": "Compare a specific player's prop line across ALL sportsbooks to find the best odds. Great for line shopping.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name to search for"
                },
                "prop_type": {
                    "type": "string",
                    "description": "Prop market to compare (e.g., 'player_pass_yds', 'player_rush_yds', 'player_anytime_td')"
                }
            },
            "required": ["player_name", "prop_type"]
        }
    },
    {
        "name": "get_best_bets",
        "description": "Get the best available lines/odds across all sportsbooks for a specific market type. Helps find value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market_type": {
                    "type": "string",
                    "description": "spread, total, moneyline, or any player prop market"
                }
            },
            "required": ["market_type"]
        }
    },
    {
        "name": "get_team_stats",
        "description": "Get detailed team stats, ATS record, O/U record, and game logs for Seahawks or Patriots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "Team name: 'seahawks' or 'patriots'"
                }
            },
            "required": ["team"]
        }
    },
    {
        "name": "get_player_stats",
        "description": "Get a player's season stats and per-game averages. Use to compare with current prop lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name to look up"
                }
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "get_betting_trends",
        "description": "Get historical Super Bowl betting trends, referee tendencies, and sharp money indicators.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_player_game_log",
        "description": "Get a player's GAME-BY-GAME stats for the entire 2025 season including playoffs. Shows passing/rushing/receiving stats for each week. Use this when asked about player consistency, recent form, or weekly performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name to look up (e.g., 'Sam Darnold', 'JSN', 'Kenneth Walker')"
                }
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "get_play_tendencies",
        "description": "Get play-by-play tendencies for a team including: run/pass splits by down, red zone tendencies, situational play calling (leading/trailing), pass depth, run direction, target share, and explosive play data. Use this for questions about play calling, tendencies, and situational analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": "Team name: 'seahawks' or 'patriots'"
                },
                "situation": {
                    "type": "string",
                    "description": "Optional specific situation: 'red_zone', 'goal_line', '1st_down', '3rd_down', 'trailing', 'leading'"
                }
            },
            "required": ["team"]
        }
    }
]


# ============================================
# TOOL EXECUTION
# ============================================

def execute_tool(tool_name, tool_input):
    """Execute a tool and return results."""
    
    if tool_name == "get_live_game_odds":
        event = get_super_bowl_event()
        
        if not event:
            return "Unable to find Super Bowl event. The game may not be listed yet."
        
        odds_data = get_live_game_odds(event["id"])
        
        if isinstance(odds_data, dict) and "error" in odds_data:
            return f"Error fetching odds: {odds_data['error']}"
        
        result = "**SUPER BOWL LIVE ODDS - ALL SPORTSBOOKS**\n"
        result += f"Game: {event.get('away_team')} @ {event.get('home_team')}\n"
        result += f"Date: {event.get('commence_time', 'TBD')}\n\n"
        
        bookmakers = odds_data.get("bookmakers", [])
        if not bookmakers:
            return result + "No odds currently available."
        
        # Organize by market
        spreads = []
        totals = []
        moneylines = []
        
        for book in bookmakers:
            book_name = book.get("title", "Unknown")
            for market in book.get("markets", []):
                mkt_key = market.get("key")
                outcomes = market.get("outcomes", [])
                
                if mkt_key == "spreads":
                    for o in outcomes:
                        spreads.append({
                            "book": book_name,
                            "team": o.get("name"),
                            "line": o.get("point"),
                            "odds": format_odds(o.get("price"))
                        })
                elif mkt_key == "totals":
                    for o in outcomes:
                        totals.append({
                            "book": book_name,
                            "ou": o.get("name"),
                            "line": o.get("point"),
                            "odds": format_odds(o.get("price"))
                        })
                elif mkt_key == "h2h":
                    for o in outcomes:
                        moneylines.append({
                            "book": book_name,
                            "team": o.get("name"),
                            "odds": format_odds(o.get("price"))
                        })
        
        result += "**SPREAD:**\n"
        for s in spreads[:10]:
            result += f"  {s['book']}: {s['team']} {s['line']} ({s['odds']})\n"
        
        result += "\n**TOTAL (O/U):**\n"
        for t in totals[:10]:
            result += f"  {t['book']}: {t['ou']} {t['line']} ({t['odds']})\n"
        
        result += "\n**MONEYLINE:**\n"
        for m in moneylines[:10]:
            result += f"  {m['book']}: {m['team']} ({m['odds']})\n"
        
        return result
    
    elif tool_name == "get_player_props":
        event = get_super_bowl_event()
        
        if not event:
            return "Unable to find Super Bowl event. Props may not be available yet."
        
        prop_type = tool_input.get("prop_type", "all")
        player_filter = tool_input.get("player_name")
        
        # Map categories to markets
        if prop_type == "all":
            markets = ALL_PLAYER_PROP_MARKETS
        elif prop_type in PLAYER_PROP_MARKETS:
            markets = PLAYER_PROP_MARKETS[prop_type]
        elif prop_type.startswith("player_"):
            markets = [prop_type]
        else:
            # Try to map common terms
            prop_map = {
                "pass": PLAYER_PROP_MARKETS["passing"],
                "rush": PLAYER_PROP_MARKETS["rushing"],
                "rec": PLAYER_PROP_MARKETS["receiving"],
                "td": PLAYER_PROP_MARKETS["touchdowns"],
                "anytime": ["player_anytime_td"],
                "first": ["player_first_td"],
            }
            markets = prop_map.get(prop_type.lower(), ALL_PLAYER_PROP_MARKETS)
        
        # Fetch props from API
        props_data = get_all_player_props(event["id"], markets)
        
        if not props_data:
            return f"No {prop_type} props currently available from sportsbooks."
        
        # Filter out injured players
        props_data = filter_injured_players(props_data)
        
        # Build response
        result = f"**SUPER BOWL PLAYER PROPS - {prop_type.upper()}**\n"
        result += "⚠️ Injured players excluded from recommendations\n"
        
        for injured in INJURED_PLAYERS:
            result += f"🚫 {injured['name']} is {injured['status']} ({injured['injury']})\n"
        result += "\n"
        
        result += format_props_summary(props_data, player_filter)
        
        return result
    
    elif tool_name == "compare_lines":
        event = get_super_bowl_event()
        if not event:
            return "Unable to find Super Bowl event."
        
        player_name = tool_input.get("player_name", "")
        prop_type = tool_input.get("prop_type", "")
        
        # Check if injured
        if player_name.lower() in INJURED_PLAYER_NAMES:
            return f"⚠️ {player_name} is INJURED/OUT - DO NOT BET on this player!"
        
        props_data = get_all_player_props(event["id"], [prop_type])
        all_lines = compare_odds_across_books(props_data, prop_type, player_name)
        
        if not all_lines:
            return f"No {prop_type} lines found for {player_name}"
        
        result = f"**LINE COMPARISON: {player_name} - {prop_type}**\n\n"
        result += "| Sportsbook | Line | Over/Under | Odds |\n"
        result += "|------------|------|------------|------|\n"
        
        for line in all_lines:
            result += f"| {line['book']} | {line['line']} | {line['over_under']} | {line['formatted_odds']} |\n"
        
        # Find best
        overs = [l for l in all_lines if "over" in l['over_under'].lower()]
        unders = [l for l in all_lines if "under" in l['over_under'].lower()]
        
        if overs:
            best_over = max(overs, key=lambda x: x['odds'])
            result += f"\n✅ **BEST OVER:** {best_over['book']} at {best_over['line']} ({best_over['formatted_odds']})"
        if unders:
            best_under = max(unders, key=lambda x: x['odds'])
            result += f"\n✅ **BEST UNDER:** {best_under['book']} at {best_under['line']} ({best_under['formatted_odds']})"
        
        return result
    
    elif tool_name == "get_best_bets":
        market_type = tool_input.get("market_type", "spread")
        event = get_super_bowl_event()
        
        if market_type in ["spread", "total", "moneyline", "spreads", "totals", "h2h"]:
            odds_data = get_live_game_odds(event["id"] if event else None)
            
            result = f"**BEST LINES - {market_type.upper()}**\n\n"
            
            bookmakers = odds_data.get("bookmakers", []) if isinstance(odds_data, dict) else []
            
            best_lines = {}
            for book in bookmakers:
                book_name = book.get("title")
                for market in book.get("markets", []):
                    if market_type.lower() in market.get("key", "").lower():
                        for outcome in market.get("outcomes", []):
                            key = f"{outcome.get('name')}_{outcome.get('point', '')}"
                            odds = outcome.get("price", -99999)
                            
                            if key not in best_lines or odds > best_lines[key]["odds"]:
                                best_lines[key] = {
                                    "book": book_name,
                                    "team": outcome.get("name"),
                                    "line": outcome.get("point"),
                                    "odds": odds
                                }
            
            for key, data in best_lines.items():
                result += f"✅ {data['team']}"
                if data['line']:
                    result += f" {data['line']}"
                result += f": {data['book']} ({format_odds(data['odds'])})\n"
            
            return result
        else:
            # It's a player prop market
            if event:
                props_data = get_all_player_props(event["id"], [market_type])
                props_data = filter_injured_players(props_data)
                return format_props_summary(props_data)
            return "Unable to fetch prop data."
    
    elif tool_name == "get_team_stats":
        team = tool_input.get("team", "").lower()
        
        if "seahawk" in team or "seattle" in team:
            team_key = "seahawks"
        elif "patriot" in team or "new england" in team or "ne" == team:
            team_key = "patriots"
        else:
            return "Please specify 'seahawks' or 'patriots'"
        
        t = SUPERBOWL_DATA["teams"][team_key]
        
        result = f"**{t['name']}** ({t['record']})\n\n"
        result += f"**BETTING RECORD:**\n"
        result += f"• ATS: {t['ats']} ({t['ats_pct']}%)\n"
        result += f"• O/U: {t['overs']} overs, {t['unders']} unders ({t['over_pct']}% over)\n"
        result += f"• Home: {t['home_record']} ({t['home_ats']} ATS)\n"
        result += f"• Road: {t['road_record']} ({t['road_ats']} ATS)\n\n"
        
        result += f"**TEAM STATS:**\n"
        result += f"• PPG: {t['ppg']} scored, {t['ppg_allowed']} allowed\n"
        result += f"• Yards: {t['avg_yards']}/g ({t['avg_rush_yards']} rush, {t['avg_pass_yards']} pass)\n"
        result += f"• 3rd Down: {t['third_down_pct']}%\n"
        result += f"• Turnovers: {t['turnovers_pg']}/game\n\n"
        
        result += f"**SCORING BY QUARTER:**\n"
        s = t['scoring']
        result += f"• Q1: {s['q1']} | Q2: {s['q2']} | Q3: {s['q3']} | Q4: {s['q4']}\n"
        result += f"• 1H: {s['first_half']} | 2H: {s['second_half']}\n\n"
        
        result += f"**GAME LOG:**\n"
        for g in SUPERBOWL_DATA["game_logs"][team_key][-10:]:
            if g["result"] != "-":
                result += f"Wk {g['wk']}: {g['opp']} {g['result']} | ATS: {g['ats']} | {g['ou']}\n"
        
        return result
    
    elif tool_name == "get_player_stats":
        player_name = tool_input.get("player_name", "").lower()
        
        for team_key, players in SUPERBOWL_DATA["players"].items():
            for player in players:
                if player_name in player["name"].lower():
                    is_injured = player.get("status") == "OUT"
                    
                    result = f"**{player['name']}** ({player['pos']}) - "
                    result += f"{SUPERBOWL_DATA['teams'][team_key]['name']}\n\n"
                    
                    if is_injured:
                        result += f"🚫 **STATUS: OUT** - {player.get('injury', 'Injured')}\n"
                        result += "⚠️ DO NOT BET ON THIS PLAYER\n\n"
                    
                    result += f"Games Played: {player.get('games', 'N/A')}\n\n"
                    
                    if player["pos"] == "QB":
                        result += f"**PASSING:**\n"
                        result += f"• Yards: {player.get('pass_yds', 0):,} ({player['avgs'].get('pass_yds', 0)}/game)\n"
                        result += f"• TD: {player.get('pass_td', 0)} ({player['avgs'].get('pass_td', 0)}/game)\n"
                        result += f"• INT: {player.get('pass_int', 0)}\n"
                        result += f"• Comp%: {player.get('comp_pct', 0)}%\n"
                        result += f"• Completions/game: {player['avgs'].get('completions', 0)}\n"
                        result += f"• Attempts/game: {player['avgs'].get('attempts', 0)}\n\n"
                        result += f"**RUSHING:**\n"
                        result += f"• Yards: {player.get('rush_yds', 0)} ({player['avgs'].get('rush_yds', 0)}/game)\n"
                        
                    elif player["pos"] == "RB":
                        result += f"**RUSHING:**\n"
                        result += f"• Yards: {player.get('rush_yds', 0):,} ({player['avgs'].get('rush_yds', 0)}/game)\n"
                        result += f"• TD: {player.get('rush_td', 0)}\n"
                        result += f"• Attempts/game: {player['avgs'].get('rush_att', 0)}\n\n"
                        result += f"**RECEIVING:**\n"
                        result += f"• Receptions: {player.get('rec', 0)} ({player['avgs'].get('receptions', 0)}/game)\n"
                        result += f"• Yards: {player.get('rec_yds', 0)} ({player['avgs'].get('rec_yds', 0)}/game)\n"
                        
                    elif player["pos"] in ["WR", "TE"]:
                        result += f"**RECEIVING:**\n"
                        result += f"• Receptions: {player.get('rec', 0)} ({player['avgs'].get('receptions', 0)}/game)\n"
                        result += f"• Yards: {player.get('rec_yds', 0):,} ({player['avgs'].get('rec_yds', 0)}/game)\n"
                        result += f"• TD: {player.get('rec_td', 0)}\n"
                        result += f"• Targets/game: {player['avgs'].get('targets', 'N/A')}\n"
                        if player.get('red_zone_targets'):
                            result += f"• Red Zone Targets: {player['red_zone_targets']}\n"
                    
                    if player.get('first_tds'):
                        result += f"\n• First TDs this season: {player['first_tds']}\n"
                    
                    return result
        
        return f"Player '{player_name}' not found in database."
    
    elif tool_name == "get_betting_trends":
        trends = SUPER_BOWL_TRENDS
        
        result = "**SUPER BOWL BETTING TRENDS**\n\n"
        
        result += "**UNDERDOG ATS:**\n"
        result += f"• {trends['underdog_ats']['record']}\n"
        result += f"• Average cover margin: {trends['underdog_ats']['avg_cover']}\n"
        result += f"• Note: {trends['underdog_ats']['note']}\n\n"
        
        result += "**OVER/UNDER:**\n"
        result += f"• {trends['under_trend']['record']}\n"
        result += f"• Average total: {trends['under_trend']['avg_total']}\n"
        result += f"• Note: {trends['under_trend']['note']}\n\n"
        
        result += "**FIRST TD SCORER:**\n"
        result += f"• RBs: {trends['first_td_trends']['running_backs']}\n"
        result += f"• TEs: {trends['first_td_trends']['tight_ends']}\n"
        result += f"• {trends['first_td_trends']['note']}\n\n"
        
        result += "**REFEREE (Shawn Smith):**\n"
        result += f"• Underdog record: {trends['referee']['underdogs']}\n"
        result += f"• Playoff O/U: {trends['referee']['overs']}\n"
        
        return result
    
    elif tool_name == "get_player_game_log":
        player_name = tool_input.get("player_name", "").lower()
        
        # Find matching player in PLAYER_GAME_LOGS
        matched_player = None
        for name in PLAYER_GAME_LOGS.keys():
            if player_name in name.lower() or name.lower() in player_name:
                matched_player = name
                break
            # Handle nicknames
            if "jsn" in player_name and "smith-njigba" in name.lower():
                matched_player = name
                break
            if "kwiii" in player_name and "walker" in name.lower():
                matched_player = name
                break
        
        if not matched_player:
            available = ", ".join(PLAYER_GAME_LOGS.keys())
            return f"Player '{player_name}' not found. Available players with game logs: {available}"
        
        logs = PLAYER_GAME_LOGS[matched_player]
        
        # Check if injured
        is_injured = matched_player.lower() in INJURED_PLAYER_NAMES
        
        result = f"**{matched_player} - 2025 Season Game Log**\n"
        if is_injured:
            result += "🚫 **STATUS: OUT - Do not include in bet recommendations**\n"
        result += "\n"
        
        for g in logs:
            wk = g["wk"]
            opp = g.get("opp", "")
            result += f"**Week {wk}** vs {opp}\n"
            if "pass" in g:
                result += f"  Pass: {g['pass']}\n"
            if "rush" in g:
                result += f"  Rush: {g['rush']}\n"
            if "rec" in g:
                result += f"  Rec: {g['rec']}\n"
            result += "\n"
        
        return result
    
    elif tool_name == "get_play_tendencies":
        team = tool_input.get("team", "").lower()
        situation = tool_input.get("situation", "")
        
        if "seahawk" in team or "seattle" in team:
            team_key = "seahawks"
        elif "patriot" in team or "new england" in team:
            team_key = "patriots"
        else:
            return "Please specify 'seahawks' or 'patriots'"
        
        t = PLAY_TENDENCIES[team_key]
        team_name = "Seattle Seahawks" if team_key == "seahawks" else "New England Patriots"
        
        result = f"**{team_name} - Play-by-Play Tendencies**\n\n"
        
        # Overall
        result += f"**OVERALL ({t['total_plays']} plays):**\n"
        result += f"• Run: {t['run_pct']}% ({t['run_plays']} plays)\n"
        result += f"• Pass: {t['pass_pct']}% ({t['pass_plays']} plays)\n\n"
        
        # By Down
        result += "**BY DOWN:**\n"
        for down, data in t["by_down"].items():
            result += f"• {down}: Run {data['run']}%, Pass {data['pass']}% (avg {data['avg_yards']} yds)\n"
        result += "\n"
        
        # Red Zone
        rz = t["red_zone"]
        result += f"**RED ZONE ({rz['total_plays']} plays):**\n"
        result += f"• Run: {rz['run_pct']}%, Pass: {rz['pass_pct']}%\n"
        result += f"• TD conversion: {rz['td_pct']}%\n\n"
        
        # Goal Line
        gl = t["goal_line"]
        result += f"**GOAL LINE ({gl['total_plays']} plays):**\n"
        result += f"• Run: {gl['run_pct']}%, Pass: {gl['pass_pct']}%\n"
        result += f"• TD conversion: {gl['td_pct']}%\n\n"
        
        # Situational
        sit = t["situational"]
        result += "**SITUATIONAL:**\n"
        result += f"• When Trailing: Run {sit['trailing']['run']}%, Pass {sit['trailing']['pass']}%\n"
        result += f"• When Leading: Run {sit['leading']['run']}%, Pass {sit['leading']['pass']}%\n"
        result += f"• Close Game (±7): Run {sit['close_game']['run']}%, Pass {sit['close_game']['pass']}%\n\n"
        
        # Pass Depth
        pd = t["pass_depth"]
        result += f"**PASS DEPTH:**\n"
        result += f"• Short: {pd['short']}%, Deep: {pd['deep']}%\n\n"
        
        # Run Direction
        rd = t["run_direction"]
        result += f"**RUN DIRECTION:**\n"
        result += f"• Left: {rd['left']}%, Middle: {rd['middle']}%, Right: {rd['right']}%\n\n"
        
        # Target Share
        result += "**TARGET SHARE:**\n"
        for player, share in t["target_share"].items():
            result += f"• {player}: {share}%\n"
        result += "\n"
        
        # Explosive Plays
        exp = t["explosive_plays"]
        result += f"**EXPLOSIVE PLAYS (20+ yards):**\n"
        result += f"• Total: {exp['total']} (Run: {exp['run_20plus']}, Pass: {exp['pass_20plus']})\n"
        
        return result
    
    return f"Unknown tool: {tool_name}"


# ============================================
# SYSTEM PROMPT
# ============================================

def get_system_prompt():
    s = SUPERBOWL_DATA["teams"]["seahawks"]
    p = SUPERBOWL_DATA["teams"]["patriots"]
    
    seahawks_players = "\n".join([
        f"• {pl['name']} ({pl['pos']}): " + 
        (f"Pass {pl['avgs'].get('pass_yds', 0)}/g, {pl['avgs'].get('pass_td', 0)} TD/g" if pl['pos'] == 'QB' else
         f"Rush {pl['avgs'].get('rush_yds', 0)}/g, Rec {pl['avgs'].get('receptions', 0)}/g" if pl['pos'] == 'RB' else
         f"Rec {pl['avgs'].get('receptions', 0)}/g, {pl['avgs'].get('rec_yds', 0)} yds/g") +
        (" 🚫 OUT" if pl.get('status') == 'OUT' else "")
        for pl in SUPERBOWL_DATA["players"]["seahawks"]
    ])
    
    patriots_players = "\n".join([
        f"• {pl['name']} ({pl['pos']}): " +
        (f"Pass {pl['avgs'].get('pass_yds', 0)}/g, {pl['avgs'].get('pass_td', 0)} TD/g" if pl['pos'] == 'QB' else
         f"Rush {pl['avgs'].get('rush_yds', 0)}/g, Rec {pl['avgs'].get('receptions', 0)}/g" if pl['pos'] == 'RB' else
         f"Rec {pl['avgs'].get('receptions', 0)}/g, {pl['avgs'].get('rec_yds', 0)} yds/g")
        for pl in SUPERBOWL_DATA["players"]["patriots"]
    ])
    
    return f"""You are the BettorDay AI betting analyst for Super Bowl LIX: Seattle Seahawks vs New England Patriots.

═══════════════════════════════════════════════════════════════
AVAILABLE DATA & TOOLS
═══════════════════════════════════════════════════════════════

You have access to:
1. COMPLETE 2025 NFL season data from BigDataBall
2. LIVE ODDS from The Odds API (ALL sportsbooks: DraftKings, FanDuel, BetMGM, Caesars, etc.)
3. ALL PLAYER PROPS including:
   - PASSING: yards, TDs, completions, attempts, interceptions
   - RUSHING: yards, attempts, longest
   - RECEIVING: receptions, yards, longest  
   - TOUCHDOWNS: anytime TD, first TD, last TD
4. PLAYER GAME LOGS - Week-by-week stats for all key players
5. PLAY-BY-PLAY TENDENCIES - Run/pass splits by down, red zone, situational, target share

═══════════════════════════════════════════════════════════════
INJURED PLAYERS - DO NOT RECOMMEND
═══════════════════════════════════════════════════════════════
🚫 Zach Charbonnet (SEA RB) - OUT - Ankle

═══════════════════════════════════════════════════════════════
SEATTLE SEAHAWKS ({s['record']})
═══════════════════════════════════════════════════════════════

BETTING: ATS {s['ats']} ({s['ats_pct']}%) | O/U {s['overs']}-{s['unders']} ({s['over_pct']}% over)
SPLITS: Home {s['home_record']} ({s['home_ats']} ATS) | Road {s['road_record']} ({s['road_ats']} ATS)
STATS: {s['ppg']} PPG, {s['ppg_allowed']} allowed | {s['avg_yards']} YPG

KEY PLAYERS:
{seahawks_players}

═══════════════════════════════════════════════════════════════
NEW ENGLAND PATRIOTS ({p['record']})
═══════════════════════════════════════════════════════════════

BETTING: ATS {p['ats']} ({p['ats_pct']}%) | O/U {p['overs']}-{p['unders']} ({p['over_pct']}% over)
SPLITS: Home {p['home_record']} ({p['home_ats']} ATS) | Road {p['road_record']} ({p['road_ats']} ATS) ← 9-0!
STATS: {p['ppg']} PPG, {p['ppg_allowed']} allowed | {p['avg_yards']} YPG

KEY PLAYERS:
{patriots_players}

═══════════════════════════════════════════════════════════════
YOUR TOOLS - USE THEM!
═══════════════════════════════════════════════════════════════

ALWAYS use these tools to get LIVE data:
1. get_live_game_odds - Current spread/total/ML from ALL sportsbooks
2. get_player_props - ALL player props (pass/rush/rec/TD) from ALL books
3. compare_lines - Compare a player's prop across all books (line shopping)
4. get_best_bets - Find the best available line for any market
5. get_team_stats - Full team stats and game logs
6. get_player_stats - Player season stats and averages
7. get_betting_trends - Historical Super Bowl trends
8. get_player_game_log - Game-by-game stats for any player (weekly breakdown)
9. get_play_tendencies - Play-by-play analysis (run/pass %, red zone, by down, etc.)

═══════════════════════════════════════════════════════════════
RULES
═══════════════════════════════════════════════════════════════

1. ALWAYS CALL TOOLS for odds/props questions - don't guess at lines
2. NEVER recommend bets on injured players (Charbonnet is OUT)
3. Compare player averages to prop lines to find value
4. Cite specific stats to back up recommendations
5. For passing props, use get_player_props with prop_type="passing"
6. For rushing props, use get_player_props with prop_type="rushing"
7. For receiving props, use get_player_props with prop_type="receiving"
8. For TD props, use get_player_props with prop_type="touchdowns"
9. For line shopping, use compare_lines with the specific player and market
10. For weekly performance trends, use get_player_game_log
11. For play-calling tendencies (run/pass splits, red zone), use get_play_tendencies

You're a veteran analyst. Be specific, cite data, and help users find value!"""


# ============================================
# VERCEL HANDLER
# ============================================

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Test endpoint - check API connectivity"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Test The Odds API connection
            test_result = {
                "status": "ok",
                "message": "BettorDay API is running",
                "odds_api_key_set": bool(ODDS_API_KEY and ODDS_API_KEY != "YOUR_ODDS_API_KEY"),
                "timestamp": datetime.now().isoformat()
            }
            
            # Try to fetch events
            events = get_nfl_events()
            if isinstance(events, dict) and "error" in events:
                test_result["odds_api_status"] = "error"
                test_result["odds_api_error"] = events["error"]
            elif isinstance(events, list):
                test_result["odds_api_status"] = "connected"
                test_result["nfl_events_count"] = len(events)
                
                # Try to find Super Bowl
                sb = get_super_bowl_event()
                if sb:
                    test_result["super_bowl_found"] = True
                    test_result["super_bowl_id"] = sb.get("id")
                    test_result["matchup"] = f"{sb.get('away_team')} @ {sb.get('home_team')}"
                else:
                    test_result["super_bowl_found"] = False
            
            self.wfile.write(json.dumps(test_result, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))
            
            user_message = body.get('message', '')
            conversation_history = body.get('history', [])
            
            client = anthropic.Anthropic()
            
            messages = conversation_history + [{"role": "user", "content": user_message}]
            
            # Initial API call
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=get_system_prompt(),
                tools=TOOLS,
                messages=messages
            )
            
            # Handle tool use loop
            while response.stop_reason == "tool_use":
                tool_results = []
                
                # Convert assistant content to serializable format
                assistant_content_serializable = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result
                        })
                        assistant_content_serializable.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })
                    elif hasattr(block, 'text'):
                        assistant_content_serializable.append({
                            "type": "text",
                            "text": block.text
                        })
                
                messages.append({"role": "assistant", "content": assistant_content_serializable})
                messages.append({"role": "user", "content": tool_results})
                
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=get_system_prompt(),
                    tools=TOOLS,
                    messages=messages
                )
            
            # Extract final text response
            final_response = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    final_response += block.text
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                "success": True,
                "response": final_response
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


# ============================================
# LOCAL TESTING
# ============================================

if __name__ == "__main__":
    print("Testing The Odds API integration...")
    print("\n1. Getting NFL events...")
    events = get_nfl_events()
    if isinstance(events, list):
        print(f"   Found {len(events)} events")
        for e in events[:3]:
            print(f"   - {e.get('away_team')} @ {e.get('home_team')}")
    else:
        print(f"   Error: {events}")
    
    print("\n2. Finding Super Bowl event...")
    sb = get_super_bowl_event()
    if sb:
        print(f"   Found: {sb.get('away_team')} @ {sb.get('home_team')}")
        print(f"   Event ID: {sb.get('id')}")
        
        print("\n3. Getting live odds...")
        odds = get_live_game_odds(sb["id"])
        if isinstance(odds, dict) and "bookmakers" in odds:
            print(f"   Found {len(odds['bookmakers'])} sportsbooks")
        
        print("\n4. Getting ALL player props...")
        props = get_all_player_props(sb["id"])
        print(f"   Markets with data: {list(props.keys())}")
        
        print("\n5. Getting PASSING props specifically...")
        passing = get_passing_props(sb["id"])
        print(f"   Passing markets: {list(passing.keys())}")
        
    else:
        print("   Super Bowl not found (may not be listed yet)")
    
    print("\nDone! Deploy to Vercel to use with your chatbot.")
