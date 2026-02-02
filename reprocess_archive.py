#!/usr/bin/env python3
import requests
import json
import time
from google import genai
from google.genai import types
import typing_extensions as typing

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# Update these with your details before running
PAPERLESS_URL = "http://192.168.X.X:8000"
PAPERLESS_TOKEN = "your_paperless_token_here"
GEMINI_API_KEY = "your_gemini_api_key_here"

# Model Selection
# Use 'gemini-2.0-flash' if you have billing enabled (recommended).
# Use 'gemini-2.0-flash-lite' if you are on the free tier to avoid rate limits.
MODEL_NAME = "gemini-2.5-flash"

# Safety Delay (Seconds)
# Set to 0 if you have billing enabled. Set to 10-15 if using free tier.
DELAY_SECONDS = 0

# ==============================================================================
# SETUP
# ==============================================================================
class DocumentMetadata(typing.TypedDict):
    summary: str
    created_date: str
    correspondent: str
    tags: list[str]
    suggested_new_tag: str

def get_headers():
    return {"Authorization": f"Token {PAPERLESS_TOKEN}", "Content-Type": "application/json"}

def get_current_tags():
    try:
        url = f"{PAPERLESS_URL}/api/tags/?page_size=1000"
        resp = requests.get(url, headers=get_headers(), timeout=10)
        tag_map = {t['name'].lower(): t['id'] for t in resp.json().get('results', [])}
        return tag_map, list(tag_map.keys())
    except Exception as e:
        print(f"Error fetching tags: {e}")
        return {}, []

def create_tag(tag_name):
    print(f"   --> Creating tag: {tag_name}")
    try:
        resp = requests.post(f"{PAPERLESS_URL}/api/tags/", 
                             json={"name": tag_name, "color": "#a6a6a6", "matching_algorithm": 0}, 
                             headers=get_headers(), timeout=10)
        if resp.status_code == 201: return resp.json().get('id')
    except: pass
    return None

def get_or_create_correspondent(name):
    if not name or name.lower() in ["none", "unknown", ""]: return None
    try:
        search_url = f"{PAPERLESS_URL}/api/correspondents/?name__iexact={name}"
        resp = requests.get(search_url, headers=get_headers(), timeout=10)
        if resp.status_code == 200 and resp.json()['count'] > 0:
            return resp.json()['results'][0]['id']
    except: pass

    print(f"   --> Creating Correspondent: {name}")
    try:
        resp = requests.post(f"{PAPERLESS_URL}/api/correspondents/", 
                             json={"name": name, "matching_algorithm": 0}, 
                             headers=get_headers(), timeout=10)
        if resp.status_code == 201: return resp.json()['id']
    except: pass
    return None

def analyze_and_update(doc_id, tag_map, current_tag_list):
    print(f"--> [Doc {doc_id}] Fetching...", end="\r")
    
    # 1. Get Text
    try:
        resp = requests.get(f"{PAPERLESS_URL}/api/documents/{doc_id}/", headers=get_headers(), timeout=10)
        if resp.status_code != 200: return
        text = resp.json().get('content', '')
    except: return

    if not text: 
        print(f"⚠️ [Doc {doc_id}] Skipped: No text.")
        return

    # 2. Gemini Analysis
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Analyze this document.
    1. EXTRACT 'created_date' (YYYY-MM-DD). If unclear, use today.
    2. EXTRACT 'correspondent' (The sender, e.g. 'Thames Water', 'NHS').
    3. EXTRACT 'summary' (Short content description, e.g. 'Monthly Bill', 'Referral Letter').
       * Do NOT include the date or correspondent in the summary.
       * Keep it under 6 words.
    4. SELECT tags from: {json.dumps(current_tag_list)}.
    5. SUGGEST new tags in 'suggested_new_tag' if needed.
    
    TEXT: {text[:100000]}
    """

    try:
        print(f"--> [Doc {doc_id}] analyzing...", end="\r")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentMetadata,
                temperature=0.1,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                ]
            )
        )
        data = json.loads(response.text)
    except Exception as e:
        print(f"❌ [Doc {doc_id}] Error: {e}")
        return

    # 3. Process Metadata
    final_tag_ids = []
    
    # Tags
    for t_name in data.get('tags', []):
        tid = tag_map.get(t_name.lower())
        if not tid: 
            tid = create_tag(t_name)
            if tid: 
                tag_map[t_name.lower()] = tid
                current_tag_list.append(t_name)
        if tid: final_tag_ids.append(tid)

    # Suggestions
    sugg = data.get('suggested_new_tag')
    if sugg and sugg.lower() not in ["none", ""]:
        tid = tag_map.get(sugg.lower())
        if not tid: 
            tid = create_tag(sugg)
            if tid:
                tag_map[sugg.lower()] = tid
                current_tag_list.append(sugg)
        if tid: final_tag_ids.append(tid)
        try:
            requests.post(f"{PAPERLESS_URL}/api/documents/{doc_id}/notes/", 
                          json={"note": f"AI SUGGESTION: {sugg}"}, headers=get_headers(), timeout=10)
        except: pass

    # Correspondent
    corr_name = data.get('correspondent', 'Unknown')
    corr_id = get_or_create_correspondent(corr_name)

    # 4. Construct Standard Title
    date_str = data.get('created_date', '2026-01-01')
    summary = data.get('summary', 'Document')
    standard_title = f"{date_str} - {corr_name} - {summary}"

    # 5. Patch
    payload = {
        "title": standard_title,
        "created": date_str,
        "correspondent": corr_id,
        "tags": final_tag_ids
    }
    
    try:
        r = requests.patch(f"{PAPERLESS_URL}/api/documents/{doc_id}/", 
                           json=payload, headers=get_headers(), timeout=10)
        if r.status_code == 200:
            print(f"✅ [Doc {doc_id}] Fixed: {standard_title}")
        else:
            print(f"❌ [Doc {doc_id}] Failed: {r.text}")
    except Exception as e:
        print(f"❌ [Doc {doc_id}] Patch Error: {e}")

if __name__ == "__main__":
    print("--- Starting Archive Reprocess ---")
    tag_map, current_tag_list = get_current_tags()
    
    try:
        # Fetch all documents
        r = requests.get(f"{PAPERLESS_URL}/api/documents/?page_size=10000", headers=get_headers(), timeout=30)
        all_ids = [d['id'] for d in r.json().get('results', [])]
        print(f"Found {len(all_ids)} documents.")
        
        for doc_id in all_ids:
            analyze_and_update(doc_id, tag_map, current_tag_list)
            time.sleep(DELAY_SECONDS)
            
    except Exception as e:
        print(f"Critical Error: {e}")
