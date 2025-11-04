#!/usr/bin/env python3
import sys
import json
import base64
import urllib.request

# Fetch ngrok API data
response = urllib.request.urlopen('http://127.0.0.1:4040/api/requests/http')
data = json.loads(response.read())

ingest_requests = []

for req in data.get('requests', []):
    try:
        raw_body = req['request'].get('raw', '')
        decoded = base64.b64decode(raw_body).decode('utf-8', errors='ignore')
        if 'ingest_url' in decoded:
            # Parse the JSON body to get parameters
            body_start = decoded.find('{')
            if body_start > 0:
                body_json = json.loads(decoded[body_start:])
                args = body_json.get('params', {}).get('arguments', {})
            else:
                args = {}

            ingest_requests.append({
                'time': req['start'],
                'method': req['request']['method'],
                'uri': req['request']['uri'],
                'session_id': req['request']['uri'].split('session_id=')[1] if 'session_id=' in req['request']['uri'] else 'N/A',
                'url': args.get('url', 'N/A'),
                'collection': args.get('collection_name', 'N/A'),
                'follow_links': args.get('follow_links', 'N/A'),
                'max_pages': args.get('max_pages', 'N/A')
            })
    except:
        pass

print(f'Found {len(ingest_requests)} ingest_url requests:\n')
for i, req in enumerate(ingest_requests, 1):
    print(f'{i}. TIME: {req["time"]}')
    print(f'   Session ID: {req["session_id"]}')
    print(f'   Target URL: {req["url"]}')
    print(f'   Collection: {req["collection"]}')
    print(f'   Follow Links: {req["follow_links"]}, Max Pages: {req["max_pages"]}')
    print()
