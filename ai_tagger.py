#!/usr/bin/env python3
import os
import sys
import traceback

# GLOBAL CRASH HANDLER
try:
    import requests
    import json
    import logging
    from google import genai
    from google.genai import types
    import typing_extensions as typing

    # ==============================================================================
    # CONFIGURATION
    # ==============================================================================
    # These are pulled from Environment Variables in Unraid/Docker
    PAPERLESS_URL = os.environ.get('PAPERLESS_URL', 'http://localhost:8000')
    PAPERLESS_TOKEN = os.environ.get('PAPERLESS_TOKEN')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    MODEL_NAME = "gemini-2.5-flash"
    TIMEOUT_SECONDS = 30

    # Logging
    logging.basicConfig(
        filename='/tmp/ai_tagger.log',
        level=logging.INFO,
        format='%(asctime)s - %(message)s'
    )

    # Get Document ID (Passed by Paperless or Environment)
    DOCUMENT_ID = os.environ.get('DOCUMENT_ID')
    if not DOCUMENT_ID and len(sys.argv) > 1:
        DOCUMENT_ID = sys.argv[1]

    # ==============================================================================
    # LOGIC
    # ==============================================================================
    class DocumentMetadata(typing.TypedDict):
        summary: str
        created_date: str
        correspondent: str
        tags: list[str]
        suggested_new_tag: str

    def get_headers():
        if not PAPERLESS_TOKEN:
            raise ValueError("PAPERLESS_TOKEN environment variable is missing.")
        return {"Authorization": f"Token {PAPERLESS_TOKEN}", "Content-Type": "application/json"}

    def get_current_tags():
        try:
            url = f"{PAPERLESS_URL}/api/tags/?page_size=1000"
            resp = requests.get(url, headers=get_headers(), timeout=TIMEOUT_SECONDS)
            tag_map = {t['name'].lower(): t['id'] for t in resp.json().get('results', [])}
            return tag_map, list(tag_map.keys())
        except Exception as e:
            logging.error(f"Failed to fetch tags: {e}")
            return {}, []

    def create_tag(tag_name):
        try:
            resp = requests.post(f"{PAPERLESS_URL}/api/tags/", 
                                 json={"name": tag_name, "color": "#a6a6a6", "matching_algorithm": 0}, 
                                 headers=get_headers(), timeout=TIMEOUT_SECONDS)
            if resp.status_code == 201: return resp.json().get('id')
        except: pass
        return None

    def get_or_create_correspondent(name):
        if not name or name.lower() in ["none", "unknown", ""]: return None
        try:
            search_url = f"{PAPERLESS_URL}/api/correspondents/?name__iexact={name}"
            resp = requests.get(search_url, headers=get_headers(), timeout=TIMEOUT_SECONDS)
            if resp.status_code == 200 and resp.json()['count'] > 0:
                return resp.json()['results'][0]['id']
        except: pass

        logging.info(f"Creating new correspondent: {name}")
        try:
            resp = requests.post(f"{PAPERLESS_URL}/api/correspondents/", 
                                 json={"name": name, "matching_algorithm": 0}, 
                                 headers=get_headers(), timeout=TIMEOUT_SECONDS)
            if resp.status_code == 201: return resp.json()['id']
        except: pass
        return None

    def analyze_and_update(doc_id):
        logging.info(f"--- Processing Scan ID: {doc_id} ---")
        
        # Get Text
        try:
            resp = requests.get(f"{PAPERLESS_URL}/api/documents/{doc_id}/", headers=get_headers(), timeout=TIMEOUT_SECONDS)
            text = resp.json().get('content', '')
        except Exception as e:
            logging.error(f"Failed to get text: {e}")
            return

        if not text:
            logging.warning("No text found.")
            return

        if not GEMINI_API_KEY:
            logging.error("GEMINI_API_KEY is missing.")
            return

        # Gemini
        tag_map, current_tag_list = get_current_tags()
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        Analyze this scanned document.
        1. EXTRACT 'created_date' (YYYY-MM-DD). If unclear, use today.
        2. EXTRACT 'correspondent' (The sender, e.g. 'Thames Water').
        3. EXTRACT 'summary' (Short content description).
           * Do NOT include the date or correspondent in the summary.
           * Keep it under 6 words.
        4. SELECT tags from: {json.dumps(current_tag_list)}.
        5. SUGGEST new tags in 'suggested_new_tag' if strictly necessary.
        
        TEXT: {text[:100000]} 
        """

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentMetadata,
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
        except Exception as e:
            logging.error(f"Gemini API Error: {e}")
            return

        # Process Tags
        final_ids = []
        for t_name in data.get('tags', []):
            tid = tag_map.get(t_name.lower())
            if not tid: tid = create_tag(t_name)
            if tid: final_ids.append(tid)

        sugg = data.get('suggested_new_tag')
        if sugg and sugg.lower() not in ["none", ""]:
            tid = tag_map.get(sugg.lower())
            if not tid: tid = create_tag(sugg)
            if tid: final_ids.append(tid)
            requests.post(f"{PAPERLESS_URL}/api/documents/{doc_id}/notes/", 
                          json={"note": f"AI SUGGESTION: {sugg}"}, headers=get_headers())
            
            # Auto-tag Inbox if specific tags are missing (Optional logic)
            inbox_id = tag_map.get('inbox')
            if not inbox_id: inbox_id = create_tag("Inbox")
            if inbox_id and inbox_id not in final_ids:
                final_ids.append(inbox_id)

        corr_id = get_or_create_correspondent(data.get('correspondent', 'Unknown'))
        
        date_str = data.get('created_date', '2026-01-01')
        summary = data.get('summary', 'Document')
        standard_title = f"{date_str} - {data.get('correspondent', 'Unknown')} - {summary}"

        payload = {
            "title": standard_title,
            "created": date_str,
            "correspondent": corr_id,
            "tags": final_ids
        }
        
        logging.info(f"Applying Update: {standard_title}")
        requests.patch(f"{PAPERLESS_URL}/api/documents/{doc_id}/", json=payload, headers=get_headers())
        logging.info("Success.")

    if __name__ == "__main__":
        if DOCUMENT_ID:
            analyze_and_update(DOCUMENT_ID)
        else:
            logging.error("No ID provided")

except Exception as e:
    error_msg = f"CRITICAL SCRIPT ERROR: {str(e)}\n{traceback.format_exc()}"
    print(error_msg, file=sys.stderr)
    try:
        logging.error(error_msg)
    except: pass
    sys.exit(1)
