# MCard Integration Step-by-Step Guide

This guide details the complete process to set up MCard, import data from `videos.json`, and serve it via an API for the application to consume.

## 1. Installation

First, ensure you have the `mcard` package and dependencies installed.

```bash
pip install mcard fastapi uvicorn requests
```

## 2. Fix Missing Schema (Critical Step)
*Note: In the current environment, the `mcard` package was missing its database schema file. This step restores it.*

Create the file `schema/mcard_schema.sql` relative to your project root (or ensure it exists in the site-packages if you have access). We placed it in a local `schema/` directory for this setup.

**File:** `schema/mcard_schema.sql`
```sql
CREATE TABLE IF NOT EXISTS card (
    hash TEXT PRIMARY KEY,
    content BLOB NOT NULL,
    g_time TEXT NOT NULL
);
```

## 3. Import Data
We need to load the content of `data/videos.json` into the MCard SQLite database (`data/DEFAULT_DB_FILE.db`).

**Script: `import_videos.py`**
1. Reads `data/videos.json` as bytes.
2. Initializes `CardCollection` pointing to the DB.
3. Adds the content as a generic MCard.
4. Returns the **Hash** of the stored card.

**Run the import:**
```bash
python import_videos.py
```
**Expected Output:**
```
✅ Success! Saved to MCard.
🔑 Hash: ba7a27624af1511010900f501ddea0b7dacb3d3858ce2291efe45eb4245bdf02
```

## 4. Run the API Server
The default `mcard` API does not support retrieving raw content. We created a custom runner `run_api.py` that extends the API with a generic `/raw` endpoint.

**Run the server:**
```bash
python run_api.py
```
*The server will start on port `28302`.*

## 5. Verify API
Verify that you can retrieve the imported file content via the API.

**Command:**
```bash
curl http://localhost:28302/content/cards/ba7a27624af1511010900f501ddea0b7dacb3d3858ce2291efe45eb4245bdf02/raw
```
*You should see the JSON content of `videos.json`.*

## 6. Connect Application
Update your main application (`app.py`) to fetch data from this API endpoint instead of the local file.

**In `app.py`:**
1. Import `requests`.
2. Set the API URL:
   ```python
   VIDEOS_API_URL = "http://localhost:28302/content/cards/ba7a27624af1511010900f501ddea0b7dacb3d3858ce2291efe45eb4245bdf02/raw"
   ```
3. Update loading logic:
   ```python
   response = requests.get(VIDEOS_API_URL)
   if response.status_code == 200:
       return response.json()
   ```

## Summary
You now have a system where:
- Data is stored transactionally in MCard (`data/DEFAULT_DB_FILE.db`).
- Data is served via a REST API (`run_api.py`).
- The frontend (`app.py`) consumes the "Source of Truth" from the API.
