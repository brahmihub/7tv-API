from fastapi import FastAPI, Query
import requests
import difflib

app = FastAPI()


@app.get("/healthz")
def health_check():
    """Simple health check endpoint."""
    return {"ok": True}


def fetch_7tv_emotes_by_twitch_id(twitch_id: str):
    """Fetch emotes from a 7TV user by Twitch ID."""
    try:
        resp = requests.get(f"https://7tv.io/v3/users/twitch/{twitch_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        emote_set = data.get("emote_set", {}).get("emotes", [])
        return [e.get("data") for e in emote_set if e.get("data")]
    except Exception as e:
        print(f"⚠️ Failed to fetch 7TV emotes for Twitch ID {twitch_id}: {e}")
        return []


def fetch_7tv_global_emotes():
    """Fetch global 7TV emotes (for when twitch_id=0 or missing)."""
    try:
        resp = requests.get("https://7tv.io/v3/emote-sets/global", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        emotes = data.get("emotes", [])
        return [e.get("data") for e in emotes if e.get("data")]
    except Exception as e:
        print(f"⚠️ Failed to fetch global 7TV emotes: {e}")
        return []


@app.get("/7tv")
def search_7tv_emotes(
    name: str = Query(..., description="Emote name to search for"),
    twitch_id: str = Query(
        "0",
        description="Comma-separated Twitch user IDs. Use 0 or leave empty for global emotes.",
    ),
    limit: int = Query(5, ge=1, le=100, description="Number of results to return"),
):
    """Return best matching emotes from given Twitch IDs or global set."""
    all_emotes = []

    twitch_ids = [tid.strip() for tid in twitch_id.split(",") if tid.strip()]
    if not twitch_ids or twitch_ids == ["0"]:
        print("ℹ️ Using global 7TV emotes")
        all_emotes = fetch_7tv_global_emotes()
    else:
        print(f"ℹ️ Fetching emotes for Twitch IDs: {', '.join(twitch_ids)}")
        for tid in twitch_ids:
            all_emotes.extend(fetch_7tv_emotes_by_twitch_id(tid))

    if not all_emotes:
        return {"results": []}

    # Compute similarity
    def _score(candidate: str):
        return difflib.SequenceMatcher(None, candidate.lower(), name.lower()).ratio()

    sorted_emotes = sorted(
        all_emotes,
        key=lambda e: _score(e.get("name", "")),
        reverse=True,
    )

    results = []
    for emote in sorted_emotes[:limit]:
        host = emote.get("host") or {}
        files = host.get("files") or []
        if not files:
            continue

        base = host.get("url")
        # ✅ Prefer GIF if available, otherwise WEBP
        gif_files = [f["name"] for f in files if f["name"].endswith(".gif")]
        webp_files = [f["name"] for f in files if f["name"].endswith(".webp")]

        if gif_files:
            chosen_file = gif_files[-1]
        elif webp_files:
            chosen_file = webp_files[-1]
        else:
            chosen_file = files[-1]["name"]

        url = f"https:{base}/{chosen_file}"
        results.append({"name": emote.get("name"), "url": url})

    return {"results": results}
