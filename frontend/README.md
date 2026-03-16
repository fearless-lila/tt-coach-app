# TT Coach Frontend

This is the Vite frontend for the TT Coach app.

The real backend API lives in the Python app at:

- `tt_coach_app/web.py`

The frontend talks to the backend through the Vite proxy configured in:

- `vite.config.ts`

## Run Locally

Start the Python backend from the repo root:

```bash
TT_COACH_PORT=8001 ./.venv/bin/python -m tt_coach_app.web
```

Then start the frontend from this folder:

```bash
npm install
npm run dev
```

Open the app at:

```text
http://127.0.0.1:3000
```

## API Endpoints Used

- `POST /api/recommend`
- `POST /api/feedback`
- `GET /api/history`
- `GET /api/stats`

## Notes

- This frontend replaces the older static UI that used to be served from the Python app.
- The deleted AI Studio mock server is no longer used.
