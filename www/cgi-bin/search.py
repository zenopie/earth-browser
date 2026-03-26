#!/usr/bin/env python3
"""Simple search CGI — echoes the query back as results."""
import os
import sys
from urllib.parse import parse_qs

method = os.environ.get("REQUEST_METHOD", "GET")
content_length = int(os.environ.get("CONTENT_LENGTH", 0))

body = sys.stdin.buffer.read(content_length).decode("utf-8") if content_length > 0 else ""
form = parse_qs(body)
query = form.get("q", [""])[0]

print("Content-Type: text/html; charset=utf-8")
print()
print(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Search Results — Earth Browser</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div class="container">
        <h1>Search Results</h1>
        <p class="tagline">Query: <strong>{query}</strong></p>

        <div class="info">
            <p>This is a demonstration of server-side form processing over Reticulum.</p>
            <p>Your search query "<strong>{query}</strong>" was received and processed
               entirely on the server. No JavaScript was needed.</p>
            <p>In a real deployment, this script would search a database or index
               and return matching results.</p>
        </div>

        <div class="info">
            <h2>Search Again</h2>
            <form method="POST" action="/cgi-bin/search.py">
                <input type="text" name="q" value="{query}" style="padding: 8px; width: 70%; background: #0a0e17; border: 1px solid #2a3a50; color: #c8d0df; border-radius: 4px;">
                <button type="submit" style="padding: 8px 16px; background: #1a3a28; border: 1px solid #2a5a3a; color: #48bb78; border-radius: 4px; cursor: pointer;">Search</button>
            </form>
        </div>

        <p><a href="/forms.html">&larr; Back to forms</a></p>
    </div>
</body>
</html>""")
