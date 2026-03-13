import os
import json
import time
import aiohttp
from typing import Any
from config import (
    PLAYED_CACHE_FILE,
    PLAYED_CACHE_TTL_SECONDS,
    TOPLINE_HISTORY_FILE,
    DEFAULT_USER_ID,
    API_MODE,
    API_RX,
    MAX_SNAPSHOTS,
)
from core.api import akatsuki_get


def load_played_maps_cache() -> set[int] | None:
    if not os.path.exists(PLAYED_CACHE_FILE):
        return None

    try:
        with open(PLAYED_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        assert isinstance(payload, dict), "Cache must be dictionary"

        updated_at = float(payload.get("updated_at", 0))
        cached_user_id = int(payload.get("user_id", 0))
        ids = payload.get("played_ids", [])

        if cached_user_id != DEFAULT_USER_ID:
            return None

        age = time.time() - updated_at
        if age > PLAYED_CACHE_TTL_SECONDS:
            return None

        cached_ids = {int(x) for x in ids if x is not None}
        print(f"[CACHE] Hit: {len(cached_ids)} maps (age {age/3600:.1f}h)")

        return cached_ids
    except Exception as e:
        print(f"[CACHE] Read error: {e}")
        return None


def save_played_maps_cache(played_ids: set[int]) -> None:
    assert isinstance(played_ids, set), "Played IDs must be set"

    try:
        os.makedirs(os.path.dirname(PLAYED_CACHE_FILE), exist_ok=True)

        payload = {
            "user_id": DEFAULT_USER_ID,
            "updated_at": time.time(),
            "played_ids": sorted(list(played_ids)),
        }

        with open(PLAYED_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"[CACHE] Saved: {len(played_ids)} maps")
    except Exception as e:
        print(f"[CACHE] Write error: {e}")


async def get_user_played_map_ids(
    session: aiohttp.ClientSession,
    max_pages: int = 500,
    per_page: int = 100,
    use_cache: bool = True,
) -> set[int]:
    assert isinstance(max_pages, int), "Max pages must be integer"
    assert max_pages > 0, "Max pages must be positive"
    assert isinstance(per_page, int), "Per page must be integer"
    assert per_page > 0, "Per page must be positive"

    if use_cache:
        cached_ids = load_played_maps_cache()
        if cached_ids is not None:
            return cached_ids

    played_ids: set[int] = set()
    page = 1
    max_iterations = min(max_pages, 500)

    for _ in range(max_iterations):
        if page > max_pages:
            break

        params = {
            "id": DEFAULT_USER_ID,
            "mode": API_MODE,
            "rx": API_RX,
            "l": per_page,
            "p": page,
        }

        data = await akatsuki_get(session, "/users/scores/best", params)
        if not data:
            break

        scores = data.get("scores", [])
        if not scores:
            break

        before = len(played_ids)

        for s in scores[:per_page]:
            bmap = s.get("beatmap", {})
            bid = bmap.get("beatmap_id") or bmap.get("id")
            if bid:
                played_ids.add(bid)

        print(f"[CACHE] Page {page}: +{len(played_ids) - before} ({len(played_ids)} total)")

        if len(scores) < per_page:
            break

        page += 1

    print(f"[CACHE] Final: {len(played_ids)} unique maps")

    if played_ids:
        save_played_maps_cache(played_ids)

    return played_ids


def load_topline_history() -> dict[str, Any]:
    if not os.path.exists(TOPLINE_HISTORY_FILE):
        return {"user_id": DEFAULT_USER_ID, "snapshots": []}

    try:
        with open(TOPLINE_HISTORY_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        assert isinstance(payload, dict), "History must be dictionary"

        if int(payload.get("user_id", 0)) != DEFAULT_USER_ID:
            return {"user_id": DEFAULT_USER_ID, "snapshots": []}

        if not isinstance(payload.get("snapshots", []), list):
            return {"user_id": DEFAULT_USER_ID, "snapshots": []}

        return payload
    except Exception as e:
        print(f"[TOPLINE] Read error: {e}")
        return {"user_id": DEFAULT_USER_ID, "snapshots": []}


def save_topline_history(payload: dict[str, Any]) -> None:
    assert isinstance(payload, dict), "Payload must be dictionary"

    try:
        os.makedirs(os.path.dirname(TOPLINE_HISTORY_FILE), exist_ok=True)

        with open(TOPLINE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TOPLINE] Write error: {e}")


def append_topline_snapshot(
    metrics: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    assert isinstance(metrics, dict), "Metrics must be dictionary"

    payload = load_topline_history()
    snapshots = payload.get("snapshots", [])

    assert isinstance(snapshots, list), "Snapshots must be list"

    previous = snapshots[-1] if snapshots else None

    current = {
        "ts": int(time.time()),
        "metrics": metrics,
    }

    snapshots.append(current)

    if len(snapshots) > MAX_SNAPSHOTS:
        snapshots = snapshots[-MAX_SNAPSHOTS:]

    payload["user_id"] = DEFAULT_USER_ID
    payload["snapshots"] = snapshots

    save_topline_history(payload)

    return previous, current
