"""
predictor.py
Rule-based "high probability" match predictor.

No pandas/numpy required (kept dependency-light on purpose).
Scores each upcoming match using:
  - Recent form (last 5 results, win/draw/loss weighted)
  - Head-to-head record between the two sides
  - Home advantage bonus
  - Goal difference trend

Outputs a confidence percentage per match and a predicted outcome
(HOME / DRAW / AWAY). Matches are only surfaced on the dashboard if
confidence clears CONFIDENCE_THRESHOLD, keeping the board to genuinely
"high probability" picks rather than every fixture on the calendar.
"""

from typing import List, Dict, Optional

CONFIDENCE_THRESHOLD = 65  # % - only picks at/above this show on the board

FORM_POINTS = {"W": 3, "D": 1, "L": 0}
HOME_ADVANTAGE_BONUS = 6  # percentage points added to home side's raw score


def _form_score(results: List[str]) -> float:
    """
    results: list like ["W", "W", "D", "L", "W"], most recent last.
    Returns a 0-100 score weighted so recent games count more.
    """
    if not results:
        return 50.0  # neutral if no data

    weights = [1, 1.2, 1.4, 1.6, 2.0][-len(results):]
    total_weight = sum(weights)
    weighted = sum(FORM_POINTS.get(r, 0) * w for r, w in zip(results, weights))
    max_possible = 3 * total_weight
    return (weighted / max_possible) * 100 if max_possible else 50.0


def _h2h_score(home_wins: int, draws: int, away_wins: int) -> Dict[str, float]:
    """Head-to-head record from the home side's perspective."""
    total = home_wins + draws + away_wins
    if total == 0:
        return {"home": 33.3, "draw": 33.3, "away": 33.3}
    return {
        "home": (home_wins / total) * 100,
        "draw": (draws / total) * 100,
        "away": (away_wins / total) * 100,
    }


def _goal_diff_score(goal_diff: int) -> float:
    """Squashes goal difference into a 0-100 bonus/penalty band."""
    clamped = max(-15, min(15, goal_diff))
    return 50 + (clamped / 15) * 20  # ranges 30-70


def predict_match(
    home_team: str,
    away_team: str,
    home_form: List[str],
    away_form: List[str],
    h2h: Dict[str, int],
    home_goal_diff: int,
    away_goal_diff: int,
) -> Dict:
    """
    Returns a prediction dict for one fixture.
    h2h expects {"home_wins": int, "draws": int, "away_wins": int}
    counted from the home team's perspective across recent meetings.
    """
    home_form_score = _form_score(home_form)
    away_form_score = _form_score(away_form)

    h2h_scores = _h2h_score(
        h2h.get("home_wins", 0), h2h.get("draws", 0), h2h.get("away_wins", 0)
    )

    home_gd_score = _goal_diff_score(home_goal_diff)
    away_gd_score = _goal_diff_score(away_goal_diff)

    # Weighted blend: form 45%, h2h 30%, goal difference 25%
    home_raw = (
        home_form_score * 0.45
        + h2h_scores["home"] * 0.30
        + home_gd_score * 0.25
        + HOME_ADVANTAGE_BONUS
    )
    away_raw = (
        away_form_score * 0.45
        + h2h_scores["away"] * 0.30
        + away_gd_score * 0.25
    )
    draw_raw = h2h_scores["draw"] * 0.6 + 20  # draws lean mostly on h2h history

    total = home_raw + away_raw + draw_raw
    home_pct = round((home_raw / total) * 100, 1)
    away_pct = round((away_raw / total) * 100, 1)
    draw_pct = round(100 - home_pct - away_pct, 1)

    outcome_probs = {"HOME": home_pct, "DRAW": draw_pct, "AWAY": away_pct}
    predicted_outcome = max(outcome_probs, key=outcome_probs.get)
    confidence = outcome_probs[predicted_outcome]

    return {
        "home_team": home_team,
        "away_team": away_team,
        "predicted_outcome": predicted_outcome,
        "confidence": confidence,
        "probabilities": outcome_probs,
        "is_high_probability": confidence >= CONFIDENCE_THRESHOLD,
    }


def rank_predictions(predictions: List[Dict]) -> List[Dict]:
    """Sort predictions by confidence, highest first."""
    return sorted(predictions, key=lambda p: p["confidence"], reverse=True)
