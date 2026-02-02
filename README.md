# Paperless-ngx AI Tagger & Smart Backup

This repository contains a set of scripts to supercharge [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) on Unraid (or any Docker setup).

1. **AI Tagger (`ai_tagger.py`):** Automatically analyzes scanned documents using Google Gemini to extract the creation date, correspondent, and summary, and applies relevant tags.

2. **Smart Backup (`paperless_backup.sh`):** A highly efficient backup script that performs a "Clean Export" (no thumbnails/temp files) and syncs to Google Drive via Rclone.

3. **Archive Reprocessor (`reprocess_archive.py`):** A script to retroactively apply AI tagging and naming to your existing document library.

## 🚀 Part 1: AI Tagger

Instead of manually typing metadata, this script uses the **Gemini 2.5 Flash** model to "read" your document and rename it to a standardized format:
`YYYY-MM-DD - Correspondent - Summary`

### Features

* **Intelligent Extraction:** Finds the *real* document date, not just the scan date.

* **Tag Matching:** Checks your existing Paperless tags and applies them if relevant.

* **Safe Logging:** Logs to `/tmp/` to avoid permission conflicts.

* **Crash Handler:** Captures errors and displays them directly in the Paperless web UI log.

### Installation

#### 1. Place the Script

Copy `ai_tagger.py` to your Paperless scripts folder (mapped in Docker).

```bash
cp ai_tagger.py /usr/src/paperless/scripts/
chmod +x /usr/src/paperless/scripts/ai_tagger.py
```

#### 2. Install Dependencies (Crucial Step)

You must install the Python libraries **as the paperless user**, not root. If you install them as root, the script will fail silently or crash immediately.

Run these commands in your Docker console:

```bash
# Switch to the paperless user
su -s /bin/bash paperless

# Install libraries
pip install google-genai requests typing_extensions

# Exit back to root
exit
```

#### 3. Configure Docker Environment Variables

Add these variables to your Paperless-ngx Docker container configuration.
**Note:** Ensure the variable name is exactly `PAPERLESS_POST_CONSUME_SCRIPT` (not `CONSUMPTION`).

| Variable | Value | Description |
| :--- | :--- | :--- |
| `PAPERLESS_POST_CONSUME_SCRIPT` | `/usr/src/paperless/scripts/ai_tagger.py` | Tells Paperless to run this script after scanning. |
| `PAPERLESS_URL` | `http://192.168.X.X:8000` | Your local Paperless address. |
| `PAPERLESS_TOKEN` | `your_auth_token` | Generate this in Paperless Settings > Admin > Tokens. |
| `GEMINI_API_KEY` | `AIzaSy...` | Your Google Gemini API Key. |

---

## 💾 Part 2: Smart Backup (Unraid / Rclone)

The `paperless_backup.sh` script is designed for the **Unraid User Scripts** plugin. It solves the problem of "thumbnail bloat" by filtering the export before uploading.

### Features

* **Clean Export:** Uses `-na` (No Archive) and `-nt` (No Thumbnails) to strip thousands of tiny files.

* **Self-Cleaning:** Uses `-d` to delete old files from your backup folder automatically.

* **Rclone Sync:** Efficiently uploads only changed files to the cloud.

### Usage

1. Install the **User Scripts** plugin in Unraid.

2. Create a new script and paste the contents of `paperless_backup.sh`.

3. Update the variables at the top (`LOCAL_EXPORT_PATH`, `REMOTE_NAME`, etc.).

4. Schedule it to run daily (e.g., `0 4 * * *`).

## ⏳ Part 3: Archive Reprocessor

If you have hundreds of old documents named "Scan_001.pdf", use `reprocess_archive.py` to fix them all in one go.

### Usage

1. Open the script `reprocess_archive.py` in a text editor.

2. Update the `CONFIGURATION` section at the top with your URL, Token, and API Key.

3. Copy the file to your Paperless container (e.g. into the `/consume` folder).

4. Run it manually inside the container:

   ```bash
   python3 reprocess_archive.py
   ```

5. It will iterate through every document in your library, renaming and tagging them.

## License

MIT License. See `LICENSE` for details.
