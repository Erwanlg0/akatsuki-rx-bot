import aiohttp
import asyncio
from typing import Any
from config import (
    AKATSUKI_API,
    API_MODE,
    API_RX,
    API_TIMEOUT_SECONDS,
    DEFAULT_USER_ID,
)


async def akatsuki_get(
    session: aiohttp.ClientSession,
    endpoint: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    assert isinstance(endpoint, str), "Endpoint must be string"
    assert isinstance(params, dict), "Params must be dictionary"

    url = f"{AKATSUKI_API}{endpoint}"

    try:
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)
        async with session.get(url, params=params, timeout=timeout) as response:
            if response.status == 200:
                data = await response.json(content_type=None)
                assert isinstance(data, dict), "Response must be dictionary"
                return data
            else:
                print(f"[API] {endpoint} → {response.status}")
    except Exception as e:
        print(f"[API] Error {endpoint}: {e}")

    return None


async def get_beatmap_details(
    session: aiohttp.ClientSession,
    beatmap_id: int,
) -> dict[str, Any] | None:
    assert isinstance(beatmap_id, int), "Beatmap ID must be integer"

    try:
        url = f"https://catboy.best/api/v2/b/{beatmap_id}"
        timeout = aiohttp.ClientTimeout(total=3)
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                data = await response.json(content_type=None)
                assert isinstance(data, dict), "Response must be dictionary"
                return {
                    "cs": data.get("cs"),
                    "difficulty_rating": data.get("difficulty_rating"),
                }
            else:
                return None
    except Exception:
        return None


async def enrich_beatmap_data(
    session: aiohttp.ClientSession,
    beatmap: dict[str, Any],
) -> dict[str, Any]:
    assert isinstance(beatmap, dict), "Beatmap must be dictionary"

    if beatmap.get("cs") and beatmap.get("difficulty_rating"):
        return beatmap

    beatmap_id = beatmap.get("beatmap_id") or beatmap.get("id")
    if not beatmap_id:
        return beatmap

    details = await get_beatmap_details(session, beatmap_id)
    if details:
        if not beatmap.get("cs") and details.get("cs"):
            beatmap["cs"] = details["cs"]
        if not beatmap.get("difficulty_rating") and details.get("difficulty_rating"):
            beatmap["difficulty_rating"] = details["difficulty_rating"]

    return beatmap


async def enrich_scores(
    session: aiohttp.ClientSession,
    scores: list[dict[str, Any]],
    max_concurrent: int = 5,
) -> list[dict[str, Any]]:
    assert isinstance(scores, list), "Scores must be list"
    assert isinstance(max_concurrent, int), "Max concurrent must be integer"
    assert max_concurrent > 0, "Max concurrent must be positive"

    semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_with_semaphore(score: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            if score.get("beatmap"):
                score["beatmap"] = await enrich_beatmap_data(session, score["beatmap"])
            return score

    try:
        enriched = await asyncio.gather(
            *[enrich_with_semaphore(s) for s in scores],
            return_exceptions=False,
        )
        return enriched
    except Exception as e:
        print(f"[API] Error enriching scores: {e}")
        return scores


async def get_user_best(
    session: aiohttp.ClientSession,
    limit: int = 100,
) -> list[dict[str, Any]]:
    assert isinstance(limit, int), "Limit must be integer"
    assert limit > 0, "Limit must be positive"
    assert limit <= 1000, "Limit cannot exceed 1000"

    all_scores: list[dict[str, Any]] = []
    page = 1
    per_page = min(limit, 100)
    max_pages = 20

    for _ in range(max_pages):
        if len(all_scores) >= limit:
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

        all_scores.extend(scores)

        if len(scores) < per_page:
            break

        page += 1

    return all_scores[:limit]


async def get_leaderboard(
    session: aiohttp.ClientSession,
    page: int = 1,
) -> list[dict[str, Any]]:
    assert isinstance(page, int), "Page must be integer"
    assert page > 0, "Page must be positive"

    params = {
        "mode": API_MODE,
        "rx": API_RX,
        "p": page,
        "l": 50,
    }

    data = await akatsuki_get(session, "/leaderboard", params)

    return data.get("users", []) if data else []


async def get_user_stats(
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    params = {
        "id": DEFAULT_USER_ID,
        "mode": API_MODE,
        "rx": API_RX,
    }

    data = await akatsuki_get(session, "/users/full", params)

    return data if data else {}


async def get_user_recent(
    session: aiohttp.ClientSession,
    limit: int = 5,
) -> list[dict[str, Any]]:
    assert isinstance(limit, int), "Limit must be integer"
    assert limit > 0, "Limit must be positive"
    assert limit <= 1000, "Limit cannot exceed 1000"

    all_scores: list[dict[str, Any]] = []
    page = 1
    per_page = min(limit, 100)
    max_pages = 10

    for _ in range(max_pages):
        if len(all_scores) >= limit:
            break

        params = {
            "id": DEFAULT_USER_ID,
            "mode": API_MODE,
            "rx": API_RX,
            "l": per_page,
            "p": page,
        }

        data = await akatsuki_get(session, "/users/scores/recent", params)
        if not data:
            break

        scores = data.get("scores", [])
        if not scores:
            break

        all_scores.extend(scores)

        if len(scores) < per_page:
            break

        page += 1

    return all_scores[:limit]
