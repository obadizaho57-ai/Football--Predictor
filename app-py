"""
app.py
Flask web app that serves a football "high probability predictions"
dashboard, plus a Track Record page that logs every high-probability
pick automatically and lets you mark the real outcome so you can see
whether the model's confident calls actually hold up over time.

Run locally:
    export FOOTBALL_DATA_API_KEY=your_key_here
    python app.py

Deploy: see render.yaml / README.md
"""

import json
import os
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler

import data_fetcher
import predictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("football-predictor")

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "predictions.json")
TRACK_FILE = os.path.join(os.path.dirname(__file__), "track_record.json")
REFRESH_HOURS = int(os.environ.get("REFRESH_HOURS", "6"))


def refresh_predictions():
    """Fetch fixtures, score them, persist results, and log any new
    high-probability picks into the track record."""
    logger.info("Refreshing predictions...")

    if not data_fetcher.API_KEY:
        logger.warning("FOOTBALL_DATA_API_KEY not set — skipping refresh.")
        return

    fixtures = data_fetcher.get_upcoming_fixtures(days_ahead=7)
    fixtures = sorted(fixtures, key=lambda f: f["kickoff"])[:15]  # cap volume so rate-limited calls stay reliable
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

    log_high_probability_picks(high_prob)

    logger.info(f"Refresh complete: {len(high_prob)} high-probability picks out of {len(ranked)} fixtures.")


def _pick_id(pick):
    """Stable unique id for a pick, so the same fixture never gets logged twice."""
    return f"{pick['kickoff']}::{pick['home_team']}::{pick['away_team']}"


def load_track_record():
    if not os.path.exists(TRACK_FILE):
        return []
    with open(TRACK_FILE) as f:
        return json.load(f)


def save_track_record(entries):
    with open(TRACK_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def log_high_probability_picks(high_prob_picks):
    """Append any new high-probability picks to the track record. Skips
    picks already logged so re-running a refresh doesn't duplicate entries."""
    entries = load_track_record()
    existing_ids = {e["id"] for e in entries}
    added = 0

    for pick in high_prob_picks:
        pid = _pick_id(pick)
        if pid in existing_ids:
            continue
        entries.append({
            "id": pid,
            "competition": pick["competition"],
            "home_team": pick["home_team"],
            "away_team": pick["away_team"],
            "predicted_outcome": pick["predicted_outcome"],
            "confidence": pick["confidence"],
            "kickoff": pick["kickoff"],
            "actual_outcome": None,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        })
        added += 1

    if added:
        save_track_record(entries)
        logger.info(f"Logged {added} new pick(s) to track record.")


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


@app.route("/track")
def track_record():
    entries = load_track_record()
    entries = sorted(entries, key=lambda e: e["kickoff"], reverse=True)

    pending = [e for e in entries if e["actual_outcome"] is None]
    resolved = [e for e in entries if e["actual_outcome"] is not None]

    correct = sum(1 for e in resolved if e["actual_outcome"] == e["predicted_outcome"])
    total = len(resolved)
    accuracy = round((correct / total) * 100, 1) if total else None

    return render_template(
        "track.html",
        pending=pending,
        resolved=resolved,
        correct=correct,
        total=total,
        accuracy=accuracy,
    )


@app.route("/track/record", methods=["POST"])
def track_record_submit():
    pick_id = request.form.get("id")
    actual_outcome = request.form.get("actual_outcome")

    if pick_id and actual_outcome in ("HOME", "DRAW", "AWAY"):
        entries = load_track_record()
        for e in entries:
            if e["id"] == pick_id:
                e["actual_outcome"] = actual_outcome
                break
        save_track_record(entries)

    return redirect(url_for("track_record"))


@app.route("/api/track")
def api_track():
    return jsonify(load_track_record())


scheduler = BackgroundScheduler()
scheduler.add_job(refresh_predictions, "interval", hours=REFRESH_HOURS, next_run_time=datetime.now())
scheduler.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
