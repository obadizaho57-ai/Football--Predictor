"""
app.py
Flask web app that serves a football "high probability predictions"
dashboard. A background scheduler refreshes predictions automatically
so the page stays current without any manual trigger or phone-side
process.

Run locally:
    export FOOTBALL_DATA_API_KEY=your_key_here
    python app.py

Deploy: see render.yaml / README.md
"""

import json
import os
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template
from apscheduler.schedulers.background import BackgroundScheduler

import data_fetcher
import predictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("football-predictor")

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "predictions.json")
REFRESH_HOURS = int(os.environ.get("REFRESH_HOURS", "6"))


def refresh_predictions():
    """Fetch fixtures, score them, and persist results to disk."""
    logger.info("Refreshing predictions...")

    if not data_fetcher.API_KEY:
        logger.warning("FOOTBALL_DATA_API_KEY not set — skipping refresh.")
        return

    fixtures = data_fetcher.get_upcoming_fixtures(days_ahead=7)
    predictions = []

    for fx in fixtures:
        try:
            home_form = data_fetcher.get_team_form(fx["home_team_id"])
            away_form = data_fetcher.get_team_form(fx["away_team_id"])
            h2h = data_fetcher.get_head_to_head(fx["match_id"])
            home_gd = data_fetcher.get_goal_difference(fx["home_team_id"])
            away_gd = data_fetcher.get_goal_difference(fx["away_team_id"])

            result = predictor.predict_match(
                home_team=fx["home_team"],
                away_team=fx["away_team"],
                home_form=home_form,
                away_form=away_form,
                h2h=h2h,
                home_goal_diff=home_gd,
                away_goal_diff=away_gd,
            )
            result["competition"] = fx["competition"]
            result["kickoff"] = fx["kickoff"]
            predictions.append(result)
        except Exception as e:
            logger.warning(f"Skipping fixture {fx.get('home_team')} vs {fx.get('away_team')}: {e}")
            continue

    ranked = predictor.rank_predictions(predictions)
    high_prob = [p for p in ranked if p["is_high_probability"]]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "high_probability_picks": high_prob,
        "all_predictions": ranked,
    }

    with open(DATA_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"Refresh complete: {len(high_prob)} high-probability picks out of {len(ranked)} fixtures.")


def load_predictions():
    if not os.path.exists(DATA_FILE):
        return {"generated_at": None, "high_probability_picks": [], "all_predictions": []}
    with open(DATA_FILE) as f:
        return json.load(f)


@app.route("/")
def dashboard():
    data = load_predictions()
    return render_template("index.html", data=data)


@app.route("/api/predictions")
def api_predictions():
    return jsonify(load_predictions())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Manual trigger, useful for testing without waiting on the scheduler."""
    refresh_predictions()
    return jsonify({"status": "ok"})


scheduler = BackgroundScheduler()
scheduler.add_job(refresh_predictions, "interval", hours=REFRESH_HOURS, next_run_time=datetime.now())
scheduler.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
