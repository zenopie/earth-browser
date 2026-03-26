#!/usr/bin/env python3
"""Simple guestbook CGI — stores and displays messages."""
import os
import sys
import json
import html
from urllib.parse import parse_qs
from datetime import datetime

GUESTBOOK_FILE = os.path.join(os.environ.get("DOCUMENT_ROOT", "."), ".guestbook.json")

def load_entries():
    if os.path.exists(GUESTBOOK_FILE):
        with open(GUESTBOOK_FILE, "r") as f:
            return json.load(f)
    return []

def save_entries(entries):
    with open(GUESTBOOK_FILE, "w") as f:
        json.dump(entries[-100:], f)  # Keep last 100 entries

method = os.environ.get("REQUEST_METHOD", "GET")
content_length = int(os.environ.get("CONTENT_LENGTH", 0))

entries = load_entries()

if method == "POST" and content_length > 0:
    body = sys.stdin.buffer.read(content_length).decode("utf-8")
    form = parse_qs(body)
    name = form.get("name", ["Anonymous"])[0].strip() or "Anonymous"
    message = form.get("message", [""])[0].strip()
    if message:
        entries.append({
            "name": name[:50],
            "message": message[:500],
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save_entries(entries)

entries_html = ""
for entry in reversed(entries):
    safe_name = html.escape(entry["name"])
    safe_msg = html.escape(entry["message"])
    entries_html += (
        f'<div style="padding: 10px; margin-bottom: 6px; background: #0a0e17; border-radius: 4px;">'
        f'<strong style="color: #6a9fd8;">{safe_name}</strong> '
        f'<span style="color: #4a5568; font-size: 11px;">{entry["time"]}</span>'
        f'<p style="margin: 4px 0 0; color: #c8d0df;">{safe_msg}</p></div>'
    )

if not entries_html:
    entries_html = '<p style="color: #4a5568; font-style: italic;">No messages yet. Be the first!</p>'

print("Content-Type: text/html; charset=utf-8")
print()
print(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Guestbook — Earth Browser</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div class="container">
        <h1>Guestbook</h1>
        <p class="tagline">{len(entries)} messages</p>

        <div class="info">
            <h2>Leave a Message</h2>
            <form method="POST" action="/cgi-bin/guestbook.py">
                <div style="margin-bottom: 8px;">
                    <input type="text" name="name" placeholder="Your name" style="padding: 8px; width: 100%; background: #0a0e17; border: 1px solid #2a3a50; color: #c8d0df; border-radius: 4px;">
                </div>
                <div style="margin-bottom: 8px;">
                    <textarea name="message" placeholder="Your message..." rows="3" style="padding: 8px; width: 100%; background: #0a0e17; border: 1px solid #2a3a50; color: #c8d0df; border-radius: 4px; resize: vertical;"></textarea>
                </div>
                <button type="submit" style="padding: 8px 16px; background: #1a3a28; border: 1px solid #2a5a3a; color: #48bb78; border-radius: 4px; cursor: pointer;">Post</button>
            </form>
        </div>

        <div class="info">
            <h2>Messages</h2>
            {entries_html}
        </div>

        <p><a href="/forms.html">&larr; Back to forms</a></p>
    </div>
</body>
</html>""")
