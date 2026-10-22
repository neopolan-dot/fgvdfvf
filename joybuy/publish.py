"""Publish small public deal data through the workflow's temporary token."""
import base64
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(os.environ.get("JOYBUY_OUTPUT", "results"))
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]


def request(url, payload=None):
    headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers,
        data=None if payload is None else json.dumps(payload).encode(),
        method="GET" if payload is None else "PUT")
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


for name in ("latest.json", "deals.csv", "summary.md"):
    path = ROOT / name
    if not path.exists():
        continue
    data = path.read_bytes()
    if len(data) > 1_000_000:
        raise RuntimeError("Result too large; refusing to publish")
    url = f"https://api.github.com/repos/{REPO}/contents/joybuy/results/{name}"
    payload = {"message": "Update public Joybuy scan result", "branch": "main",
               "content": base64.b64encode(data).decode()}
    try:
        current = request(url)
        payload["sha"] = current["sha"]
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    request(url, payload)
    print("Published " + name)
