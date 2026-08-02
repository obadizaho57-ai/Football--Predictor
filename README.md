# Matchday Board — Football Prediction Dashboard

A self-contained web app that scores upcoming football fixtures on recent
form, head-to-head history, and goal difference, then displays the
high-probability picks on a dashboard. No Telegram, no phone process to
keep alive — it runs on a host and refreshes itself on a schedule.

## How it works

- `data_fetcher.py` — pulls fixtures and team stats from [football-data.org](https://www.football-data.org)'s free API
- `predictor.py` — scores each fixture (form 45%, head-to-head 30%, goal difference 25%, plus a home advantage bonus) and flags anything ≥65% confidence as "high probability"
- `app.py` — Flask app that serves the dashboard and runs a background scheduler to refresh predictions automatically
- `templates/index.html` — the dashboard itself

## 1. Get a free API key

Sign up at https://www.football-data.org/client/register — free tier covers
the Premier League, La Liga, Serie A, Bundesliga, Ligue 1, and Champions
League, with 10 requests/minute. That's enough for a refresh every few hours.

## 2. Run it locally (optional, to test first)

```bash
cd football-predictor
pip install -r requirements.txt
export FOOTBALL_DATA_API_KEY=your_key_here
python app.py
```

Visit `http://localhost:5000` — it fetches predictions immediately on
startup, then every `REFRESH_HOURS` (default 6) after that.

## 3. Deploy to Render (free tier)

1. Push this folder to a GitHub repo
2. In Render, choose **New → Blueprint**, point it at your repo — it will read `render.yaml` automatically
3. When prompted, paste in your `FOOTBALL_DATA_API_KEY`
4. Deploy. Render gives you a public URL for the dashboard.

You can update the site afterward straight from your phone using GitHub's
mobile web editor (edit a file → commit) — Render redeploys automatically
on push.

## Important caveat: free tier sleep

Render's free web service tier spins down after ~15 minutes of no traffic,
which pauses the background scheduler too. Two ways to handle this:

- **Simplest:** don't worry about it — the page still refreshes the moment
  someone visits after a spin-down (the scheduler's `next_run_time` fires
  on startup), so picks are never more than one visit stale.
- **Always-fresh:** use a free uptime pinger (e.g. UptimeRobot) to hit your
  URL every 10 minutes, which keeps the service awake and the scheduler
  running continuously.

## Changing the confidence threshold

Edit `CONFIDENCE_THRESHOLD` in `predictor.py` (default 65). Lower it to
surface more picks, raise it to be stricter.

## Disclaimer

This tool produces statistical estimates for entertainment and informational
purposes. It is not betting or financial advice.
