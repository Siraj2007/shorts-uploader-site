# TikTok upload MCP (tiktok-upload)

A small local MCP server that uploads videos to TikTok through the official
Login Kit and Content Posting API. It uses only the Python standard library.

## Files

- `tiktok_mcp.py` is the server.
- `.env` holds the app credentials. It lives on the PC only and is never committed. Use `.env.example` as the template.
- `tokens.json` holds per-account refresh tokens. It is created by sign-in and is also PC-only.

## Setup on the PC

1. Copy `.env.example` to `.env` next to `tiktok_mcp.py` and fill in the values.
2. Register the MCP in Claude Code with the Python script as the command.
3. In the TikTok developer portal, add `http://localhost:8080/callback` as a redirect URI for the sandbox app.

## Tools

- `tiktok_connect(account)` starts a local callback on 127.0.0.1:8080 and returns a sign-in URL. Open it in the browser signed in as that TikTok account.
- `tiktok_accounts()` lists connected account names.
- `tiktok_post(account, video_path, caption, privacy="SELF_ONLY")` uploads an MP4 in 10 MB chunks.
- `tiktok_status(account, publish_id)` checks the upload status.

## Notes

- Sandbox apps can post only private (`SELF_ONLY`) videos, so make them public by hand in TikTok until the app passes review.
- Each account needs one sign-in. Refresh tokens are saved after that.
- Keep secrets out of this folder, out of the GitHub repo, and out of memory.
