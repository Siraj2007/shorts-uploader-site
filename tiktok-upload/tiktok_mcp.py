#!/usr/bin/env python3
"""Minimal TikTok upload MCP server (stdio, stdlib only).

Uses the official TikTok Login Kit + Content Posting API. Posts go to
accounts that have authorized the app (sandbox target users are allowed
while the app is unaudited; posts are private until the app is audited).

Config is read from a .env file next to this script or from the environment:
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI
Secrets never belong in this folder; keep the .env on the PC only.
"""
import base64
import hashlib
import http.server
import json
import os
import pathlib
import secrets
import sys
import threading
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ENV_FILE = pathlib.Path(os.environ.get("TIKTOK_ENV_FILE", HERE / ".env"))
TOKEN_FILE = pathlib.Path(os.environ.get("TIKTOK_TOKEN_FILE", HERE / "tokens.json"))
API = "https://open.tiktokapis.com"
CHUNK = 10 * 1024 * 1024  # 10 MB chunks; TikTok allows up to 64 MB per chunk


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()
CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:8080/callback")
SCOPES = "user.info.basic,video.upload,video.publish"


def _post_json(url, body, token=None, form=False):
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json; charset=UTF-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def load_tokens():
    return json.loads(TOKEN_FILE.read_text()) if TOKEN_FILE.exists() else {}


def save_tokens(tokens):
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def access_token(account):
    tokens = load_tokens()
    acct = tokens.get(account)
    if not acct:
        raise RuntimeError(f"account '{account}' is not connected; run tiktok_connect first")
    resp = _post_json(
        f"{API}/v2/oauth/token/",
        {"client_key": CLIENT_KEY, "client_secret": CLIENT_SECRET,
         "grant_type": "refresh_token", "refresh_token": acct["refresh_token"]},
        form=True,
    )
    if "access_token" not in resp:
        raise RuntimeError(f"token refresh failed: {resp}")
    acct["access_token"] = resp["access_token"]
    acct["refresh_token"] = resp.get("refresh_token", acct["refresh_token"])
    tokens[account] = acct
    save_tokens(tokens)
    return acct["access_token"]


def connect(account):
    """Starts a local OAuth callback server and returns the TikTok sign-in URL."""
    state = secrets.token_urlsafe(16)
    # PKCE: TikTok requires a code_challenge; the verifier is sent back at token exchange.
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": CLIENT_KEY, "scope": SCOPES, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "state": f"{account}|{state}",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    port = urllib.parse.urlparse(REDIRECT_URI).port or 8080

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got_state = q.get("state", [""])[0]
            if not got_state.endswith(state):
                self.send_response(400); self.end_headers(); return
            resp = _post_json(f"{API}/v2/oauth/token/", {
                "client_key": CLIENT_KEY, "client_secret": CLIENT_SECRET,
                "code": q.get("code", [""])[0], "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI, "code_verifier": verifier}, form=True)
            if "access_token" in resp:
                tokens = load_tokens()
                tokens[account] = {"open_id": resp.get("open_id"), "refresh_token": resp["refresh_token"]}
                save_tokens(tokens)
                msg = f"Connected {account}. You can close this tab."
            else:
                msg = f"Sign-in failed: {resp}"
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(msg.encode())
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return {"sign_in_url": url, "note": "Open this URL in the browser signed in as the target account."}


def post_video(account, video_path, caption, privacy="SELF_ONLY"):
    token = access_token(account)
    size = os.path.getsize(video_path)
    total = max(1, -(-size // CHUNK))
    chunk_size = size if total == 1 else CHUNK
    init = _post_json(f"{API}/v2/post/publish/video/init/", {
        "post_info": {"title": caption[:2200], "privacy_level": privacy,
                      "disable_comment": False, "disable_duet": False, "disable_stitch": False},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                        "chunk_size": chunk_size, "total_chunk_count": total},
    }, token=token)
    if init.get("error", {}).get("code", "ok") != "ok":
        raise RuntimeError(f"init failed: {init}")
    upload_url = init["data"]["upload_url"]
    with open(video_path, "rb") as f:
        for i in range(total):
            data = f.read(chunk_size)
            start, end = i * chunk_size, i * chunk_size + len(data) - 1
            req = urllib.request.Request(upload_url, data=data, method="PUT", headers={
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Content-Length": str(len(data))})
            urllib.request.urlopen(req, timeout=300).read()
    return {"publish_id": init["data"]["publish_id"], "privacy": privacy}


def publish_status(account, publish_id):
    token = access_token(account)
    return _post_json(f"{API}/v2/post/publish/status/fetch/", {"publish_id": publish_id}, token=token)


TOOLS = {
    "tiktok_connect": {
        "description": "Start sign-in for an account and return the TikTok sign-in URL.",
        "inputSchema": {"type": "object", "properties": {"account": {"type": "string"}}, "required": ["account"]},
        "fn": lambda a: connect(a["account"]),
    },
    "tiktok_accounts": {
        "description": "List connected accounts (names only).",
        "inputSchema": {"type": "object", "properties": {}},
        "fn": lambda a: sorted(load_tokens().keys()),
    },
    "tiktok_post": {
        "description": "Upload a local MP4 to a connected account. Defaults to SELF_ONLY (private).",
        "inputSchema": {"type": "object", "properties": {
            "account": {"type": "string"}, "video_path": {"type": "string"},
            "caption": {"type": "string"}, "privacy": {"type": "string", "default": "SELF_ONLY"}},
            "required": ["account", "video_path", "caption"]},
        "fn": lambda a: post_video(a["account"], a["video_path"], a["caption"], a.get("privacy", "SELF_ONLY")),
    },
    "tiktok_status": {
        "description": "Check the status of an upload by publish_id.",
        "inputSchema": {"type": "object", "properties": {
            "account": {"type": "string"}, "publish_id": {"type": "string"}},
            "required": ["account", "publish_id"]},
        "fn": lambda a: publish_status(a["account"], a["publish_id"]),
    },
}


def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error:
        out["error"] = {"code": -32000, "message": str(error)}
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            reply(mid, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                        "serverInfo": {"name": "tiktok-upload", "version": "0.1.0"}})
        elif method == "tools/list":
            reply(mid, {"tools": [{"name": k, "description": v["description"], "inputSchema": v["inputSchema"]}
                                   for k, v in TOOLS.items()]})
        elif method == "tools/call":
            p = msg["params"]
            try:
                result = TOOLS[p["name"]]["fn"](p.get("arguments", {}))
                reply(mid, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
            except Exception as e:  # report tool errors back to the client
                reply(mid, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        elif mid is not None:
            reply(mid, {})


if __name__ == "__main__":
    main()
