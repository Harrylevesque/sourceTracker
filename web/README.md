# SourceTracker Chrome Extension

Small MV3 extension that auto-saves visited pages to a selected SourceTracker project via the FastAPI backend.

## Configure
1. Set the API base URL in `web/config.js` (defaults to `http://127.0.0.1:8000`).
2. Ensure the backend is running locally:

```bash
cd /Users/harry/PycharmProjects/SourceTracker
uvicorn local.main:app --host 127.0.0.1 --port 8000
```

## Load the extension (Chrome/Edge)
1. Open `chrome://extensions/` and enable **Developer mode**.
2. Click **Load unpacked** and select the `web/` folder.
3. Use the popup to pick/create a project and save the current tab; the background worker auto-saves new/activated pages.

## What it calls
- `GET /projects` – list projects for the dropdown.
- `POST /projects` – create a project from the popup.
- `GET /projects/{name}/visited/check?url=...` – background duplicate check.
- `POST /projects/{name}/visited` – add the page when not already visited.
