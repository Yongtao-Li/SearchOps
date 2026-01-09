# SearchOps

A lightweight job-search tracking dashboard that implements:

- **70/20/10** time allocation (Networking / Planning / Applying)
- **4 channels** (Network, Online Postings, New Connections, Search Firms)
- **5×5×7** execution structure (5 days/week, 5 SMART actions/day, 7 active targets)
- Weekly KPI scoreboard (hours, outreach, meetings, screens, interviews, etc.)

## Quickstart

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run job_search_tracker.py
```

## Data storage

SearchOps stores data in a local SQLite file:

- `job_search_tracker.db`

> Tip: If you want backups, periodically copy this file or export CSV from the app.

## Publish to GitHub (commands)

```bash
git init
git add .
git commit -m "Initial commit: SearchOps tracker"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/searchops.git
git push -u origin main
```

## License

MIT
