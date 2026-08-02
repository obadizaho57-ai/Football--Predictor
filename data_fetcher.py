"""
data_fetcher.py
Pulls upcoming fixtures and recent team form from football-data.org's
free tier (https://www.football-data.org). Free tier covers 12 top
competitions and allows 10 requests/minute, which is comfortable for a
scheduled job that runs every few hours.

Get a free API key: https://www.football-data.org/client/register
Set it as the FOOTBALL_DATA_API_KEY environment variable.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict

BASE_URL = "https://api.football-data.org/v4"
API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

# Free-tier competitions worth tracking. Trim this list if you want
# fewer requests per refresh cycle.
COMPETITIONS = [
    "PL",   # Premier League
    "PD",   # La Liga
    "SA",   # Serie A
    "BL1",  # Bundesliga
    "FL1",  # Ligue 1
    "CL",   # Champions League
    "BSA",  # Campeonato Brasileiro Série A (mid-season, active now)
    "DED",  # Eredivisie
    "ELC",  # Championship (England 2nd tier)
    "PPL",  # Primeira Liga
]

HEADERS = {"X-Auth-Token": API_KEY}


def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_upcoming_fixtures(days_ahead: int = 3) -> List[Dict]:
    """Fetch fixtures across tracked competitions in the next N days."""
    date_from = datetime.utcnow().strftime("%Y-%m-%d")
    date_to = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    fixtures = []
    for comp in COMPETITIONS:
        try:
            data = _get(
                f"/competitions/{comp}/matches",
                params={"dateFrom": date_from, "dateTo": date_to, "status": "SCHEDULED"},
            )
            for m in data.get("matches", []):
                fixtures.append({
                    "competition": comp,
                    "match_id": m["id"],
                    "home_team": m["homeTeam"]["name"],
                    "home_team_id": m["homeTeam"]["id"],
                    "away_team": m["awayTeam"]["name"],
                    "away_team_id": m["awayTeam"]["id"],
                    "kickoff": m["utcDate"],
                })
        except requests.RequestException:
            # Skip a competition on failure rather than killing the whole refresh
            continue
    return fixtures


def get_team_form(team_id: int, last_n: int = 5) -> List[str]:
    """Returns last N results for a team as ['W','D','L',...], most recent last."""
    try:
        data = _get(f"/teams/{team_id}/matches", params={"status": "FINISHED", "limit": last_n})
    except requests.RequestException:
        return []

    results = []
    matches = sorted(data.get("matches", []), key=lambda m: m["utcDate"])
    for m in matches[-last_n:]:
        home_id = m["homeTeam"]["id"]
        home_score = m["score"]["fullTime"]["home"]
        away_score = m["score"]["fullTime"]["away"]
        if home_score is None or away_score is None:
            continue
        team_is_home = home_id == team_id
        if home_score == away_score:
            results.append("D")
        elif (home_score > away_score) == team_is_home:
            results.append("W")
        else:
            results.append("L")
    return results


def get_head_to_head(match_id: int, limit: int = 5) -> Dict[str, int]:
    """Returns home/draw/away counts from the last N meetings between two sides."""
    try:
        data = _get(f"/matches/{match_id}/head2head", params={"limit": limit})
    except requests.RequestException:
        return {"home_wins": 0, "draws": 0, "away_wins": 0}

    home_wins = draws = away_wins = 0
    for m in data.get("matches", []):
        home_score = m["score"]["fullTime"]["home"]
        away_score = m["score"]["fullTime"]["away"]
        if home_score is None or away_score is None:
            continue
        if home_score > away_score:
            home_wins += 1
        elif home_score < away_score:
            away_wins += 1
        else:
            draws += 1
    return {"home_wins": home_wins, "draws": draws, "away_wins": away_wins}


def get_goal_difference(team_id: int) -> int:
    """Season goal difference from the competition standings, if available."""
    try:
        data = _get(f"/teams/{team_id}")
        running = data.get("runningCompetitions", [])
        if not running:
            return 0
        comp_id = running[0]["id"]
        standings = _get(f"/competitions/{comp_id}/standings")
        for table_group in standings.get("standings", []):
            for row in table_group.get("table", []):
                if row["team"]["id"] == team_id:
                    return row.get("goalDifference", 0)
    except requests.RequestException:
        pass
    return 0
