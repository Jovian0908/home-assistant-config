#!/usr/bin/env python3
"""mesh_anomalies.py - command_line sensor helper.

Reads MESH_TOKEN from env, polls scene:5555/anomalies, reshapes into
{count, unack_count, items} for HA's command_line sensor json_attributes.
"""
import json
import os
import sys
import urllib.request

token = os.environ.get("MESH_TOKEN", "")
url = "http://scene:5555/anomalies?limit=20"
req = urllib.request.Request(url, headers={"X-Mesh-Token": token})
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
except Exception as e:
    print(json.dumps({"count": 0, "unack_count": 0, "items": [], "error": str(e)[:120]}))
    sys.exit(0)

if not isinstance(data, list):
    data = []
unack = [a for a in data if not a.get("acknowledged")]
print(json.dumps({
    "count": len(data),
    "unack_count": len(unack),
    "items": data,
}))
