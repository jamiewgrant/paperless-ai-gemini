# Paperless-ngx AI Tagger (Gemini)

This script automates the tagging and titling of documents in **Paperless-ngx** using Google's **Gemini 2.5 Flash** model. 

When a document is scanned, this script:
1. reads the OCR text.
2. extracts the **Date**, **Correspondent**, and a short **Summary**.
3. selects relevant **Tags** from your existing list (or suggests new ones).
4. renames the document to: `YYYY-MM-DD - Correspondent - Summary`.

## Prerequisites
* Paperless-ngx (running in Docker/Unraid)
* A Google Gemini API Key (Free tier works fine)
* Python 3 installed inside the Paperless container

## Installation

### 1. Place the Script
Copy `ai_tagger.py` to your Paperless scripts folder (e.g., `/usr/src/paperless/scripts/`).
Make it executable:
```bash
chmod +x ai_tagger.py
```

### 2. Install Dependencies
You need to install the Python libraries **inside** the Paperless container. 
**Note:** You must do this as the `paperless` user, not root.
```bash
# Log in as paperless user
su -s /bin/bash paperless

# Install
pip install -r requirements.txt
```

### 3. Configure Docker Variables
Add the following Environment Variables to your Paperless-ngx Docker container:

| Key | Value |
| :--- | :--- |
| `PAPERLESS_POST_CONSUME_SCRIPT` | `/usr/src/paperless/scripts/ai_tagger.py` |
| `PAPERLESS_URL` | `http://192.168.X.X:8000` (Your local IP) |
| `PAPERLESS_TOKEN` | `Your_Long_API_Token` |
| `GEMINI_API_KEY` | `AIzaSy...` |

### 4. Permissions (Important!)
Ensure the script and the log file are writable/readable by the `paperless` user.
```bash
touch /tmp/ai_tagger.log
chmod 666 /tmp/ai_tagger.log
```

## Backup Script
Also included is `paperless_backup.sh`, a script designed for **Unraid User Scripts**. It performs a clean export (stripping thumbnails/archives to save space) and syncs to Google Drive via Rclone.
