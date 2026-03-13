import random
import aiohttp
from typing import Any
from config import API_MODE, API_RX, DEFAULT_USER_ID, AKATSUKI_API
from core.api import akatsuki_get, enrich_scores
from core.profile import guess_map_type, score_quality, is_in_comfort_zone
from core.utils import matches_mod_filter


async def get_recommendations(
    session: aiohttp.ClientSession,
    profile: dict[str, Any],
    mod_filter: str = "all",
    limit: int = 10,
    min_pp: float | None = None,
    max_pp: float | None = None,
    min_time: int | None = None,
    max_time: int | None = None,
    map_type_filter: str = "all",
) -> list[dict[str, Any]]:
    assert isinstance(profile, dict), "Profile must be dictionary"
    assert isinstance(mod_filter, str), "Mod filter must be string"
    assert isinstance(limit, int), "Limit must be integer"
    assert limit > 0, "Limit must be positive"

    played = profile["played_ids"]
    rec_min_pp = float(min_pp) if min_pp is not None else profile["rec_min_pp"]
    rec_max_pp = float(max_pp) if max_pp is not None else profile["rec_max_pp"]
    type_ceilings = profile.get("type_ceilings", {})
    type_affinity = profile.get("type_affinity", {})

    print(f"[RECO] Range: {rec_min_pp:.0f}-{rec_max_pp:.0f}pp")
    print(f"[RECO] Time: {min_time}s-{max_time}s" if min_time or max_time else "")
    print(f"[RECO] Map type filter: {map_type_filter}")
    print(f"[RECO] Ceilings: {type_ceilings}")
    print(f"[RECO] Filter: {mod_filter}")
    print(f"[RECO] Played: {len(played)} maps to exclude")
    print(f"[RECO] Limit: {limit}")

    candidates: list[dict[str, Any]] = []
    scores_checked = 0
    reject_counts: dict[str, int] = {
        "no_bid_pp": 0, "played": 0, "pp_range": 0,
        "mod_filter": 0, "accuracy": 0, "mod_affinity": 0,
        "duration_range": 0, "type_filter": 0, "type_affinity": 0,
    }
    pp_samples: list[str] = []

    avg_pp = profile.get("avg_pp", 300)
    if avg_pp >= 700:
        base_pages = list(range(3, 15))
    elif avg_pp >= 500:
        base_pages = list(range(8, 25))
    elif avg_pp >= 350:
        base_pages = list(range(15, 40))
    elif avg_pp >= 200:
        base_pages = list(range(25, 55))
    else:
        base_pages = list(range(40, 70))

    pages = random.sample(base_pages, min(12, len(base_pages)))

    for page in pages:
        users = await get_leaderboard_users(session, page)
        if not users:
            continue

        selected_users = random.sample(users[:40], min(15, len(users[:40])))
        print(f"[RECO] Page {page}: {len(selected_users)} players")

        max_users = min(len(selected_users), 20)

        for i in range(max_users):
            user = selected_users[i]
            uid = user.get("id")

            if not uid or uid == DEFAULT_USER_ID:
                continue

            user_scores = await get_user_scores(session, uid)
            user_scores = await enrich_scores(session, user_scores)

            max_scores = min(len(user_scores), 25)

            for j in range(max_scores):
                s = user_scores[j]
                scores_checked += 1

                if should_add_candidate(
                    s,
                    played,
                    rec_min_pp,
                    rec_max_pp,
                    type_ceilings,
                    type_affinity,
                    profile,
                    mod_filter,
                    min_time,
                    max_time,
                    map_type_filter,
                    reject_counts=reject_counts,
                    pp_samples=pp_samples,
                ):
                    candidates.append(s)

        if len(candidates) >= 120:
            print(f"[RECO] Enough candidates ({len(candidates)}), stopping")
            break

    print(f"[RECO] Checked {scores_checked}, found {len(candidates)} candidates")
    print(f"[RECO] Rejections: {reject_counts}")
    if pp_samples:
        print(f"[RECO] PP range samples (first rejected): {', '.join(pp_samples[:15])}")

    unique = deduplicate_candidates(candidates)

    print(f"[RECO] {len(unique)} unique maps")

    return unique[:limit]


async def get_leaderboard_users(
    session: aiohttp.ClientSession,
    page: int,
) -> list[dict[str, Any]]:
    data = await akatsuki_get(
        session,
        "/leaderboard",
        {"mode": API_MODE, "rx": API_RX, "p": page, "l": 50},
    )

    return data.get("users", []) if data else []


async def get_user_scores(
    session: aiohttp.ClientSession,
    user_id: int,
) -> list[dict[str, Any]]:
    data = await akatsuki_get(
        session,
        "/users/scores/best",
        {"id": user_id, "mode": API_MODE, "rx": API_RX, "l": 25, "p": 1},
    )

    return data.get("scores", []) if data else []


def should_add_candidate(
    score: dict[str, Any],
    played: set[int],
    rec_min_pp: float,
    rec_max_pp: float,
    type_ceilings: dict[str, float],
    type_affinity: dict[str, float],
    profile: dict[str, Any],
    mod_filter: str,
    min_time: int | None = None,
    max_time: int | None = None,
    map_type_filter: str = "all",
    debug: bool = False,
    reject_counts: dict[str, int] | None = None,
    pp_samples: list[str] | None = None,
) -> bool:
    assert isinstance(score, dict), "Score must be dictionary"
    assert isinstance(played, set), "Played must be set"

    bmap = score.get("beatmap", {})
    bid = bmap.get("beatmap_id") or bmap.get("id")
    pp = score.get("pp", 0)

    if not (bid and pp > 0):
        if reject_counts is not None:
            reject_counts["no_bid_pp"] = reject_counts.get("no_bid_pp", 0) + 1
        if debug:
            print(f"[DEBUG] REJECT bid/pp: bid={bid} pp={pp}")
        return False

    if bid in played:
        if reject_counts is not None:
            reject_counts["played"] = reject_counts.get("played", 0) + 1
        if debug:
            print(f"[DEBUG] REJECT played: bid={bid}")
        return False

    map_type = guess_map_type(score)
    ceiling = type_ceilings.get(map_type, rec_max_pp)
    effective_max = min(rec_max_pp, ceiling * 1.12)

    if not (rec_min_pp <= pp <= effective_max):
        if reject_counts is not None:
            reject_counts["pp_range"] = reject_counts.get("pp_range", 0) + 1
        if pp_samples is not None and len(pp_samples) < 15:
            pp_samples.append(f"{pp:.0f}pp({map_type},max={effective_max:.0f})")
        if debug:
            print(f"[DEBUG] REJECT pp_range: pp={pp:.0f} type={map_type} (need {rec_min_pp:.0f}-{effective_max:.0f})")
        return False

    if min_time is not None or max_time is not None:
        duration = bmap.get("total_length") or bmap.get("hit_length", 0)
        if duration:
            if min_time is not None and duration < min_time:
                if reject_counts is not None:
                    reject_counts["duration_range"] = reject_counts.get("duration_range", 0) + 1
                if debug:
                    print(f"[DEBUG] REJECT duration too short: {duration}s < {min_time}s")
                return False
            if max_time is not None and duration > max_time:
                if reject_counts is not None:
                    reject_counts["duration_range"] = reject_counts.get("duration_range", 0) + 1
                if debug:
                    print(f"[DEBUG] REJECT duration too long: {duration}s > {max_time}s")
                return False

    if mod_filter != "all" and not matches_mod_filter(score.get("mods", 0), mod_filter):
        if reject_counts is not None:
            reject_counts["mod_filter"] = reject_counts.get("mod_filter", 0) + 1
        if debug:
            print(f"[DEBUG] REJECT mod_filter")
        return False

    if map_type_filter != "all" and map_type != map_type_filter:
        if reject_counts is not None:
            reject_counts["type_filter"] = reject_counts.get("type_filter", 0) + 1
        if debug:
            print(f"[DEBUG] REJECT type_filter: {map_type} != {map_type_filter}")
        return False

    if map_type_filter == "all" and not check_type_affinity(map_type, type_affinity):
        if reject_counts is not None:
            reject_counts["type_affinity"] = reject_counts.get("type_affinity", 0) + 1
        if debug:
            print(f"[DEBUG] REJECT type_affinity: {map_type}")
        return False

    score["_map_type"] = map_type
    score["relevance"] = calculate_relevance(score, profile, mod_filter)

    if mod_filter == "all":
        if not check_mod_affinity(score, profile):
            if reject_counts is not None:
                reject_counts["mod_affinity"] = reject_counts.get("mod_affinity", 0) + 1
            if debug:
                print(f"[DEBUG] REJECT mod_affinity")
            return False

    return True


def check_mod_affinity(score: dict[str, Any], profile: dict[str, Any]) -> bool:
    assert isinstance(score, dict), "Score must be dictionary"
    assert isinstance(profile, dict), "Profile must be dictionary"

    mods = score.get("mods", 0)
    mod_affinity = profile.get("mod_affinity", {})

    has_hd = bool(mods & 8)
    has_hr = bool(mods & 16)
    has_dt = bool(mods & 64) or bool(mods & 512)

    if has_hd and mod_affinity.get("HD", 0.0) < 0.01:
        return False
    if has_hr and mod_affinity.get("HR", 0.0) < 0.01:
        return False
    if has_dt and mod_affinity.get("DT", 0.0) < 0.01:
        return False

    return True


def check_type_affinity(map_type: str, type_affinity: dict[str, float]) -> bool:
    assert isinstance(map_type, str), "Map type must be string"
    assert isinstance(type_affinity, dict), "Type affinity must be dictionary"

    affinity = type_affinity.get(map_type, 0.0)

    if affinity < 0.02:
        return False

    return True


def deduplicate_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    assert isinstance(candidates, list), "Candidates must be list"

    sorted_candidates = sorted(
        candidates,
        key=lambda x: x.get("relevance", 0),
        reverse=True,
    )

    seen: set[int] = set()
    max_candidates = min(len(sorted_candidates), 500)

    by_type: dict[str, list[dict[str, Any]]] = {
        "jump": [],
        "stream": [],
        "speed": [],
        "other": [],
    }

    for i in range(max_candidates):
        s = sorted_candidates[i]
        bid = s.get("beatmap", {}).get("beatmap_id") or s.get("beatmap", {}).get("id")
        if not bid or bid in seen:
            continue
        seen.add(bid)
        map_type = s.get("_map_type", "other")
        if map_type not in by_type:
            map_type = "other"
        by_type[map_type].append(s)

    unique: list[dict[str, Any]] = []
    type_order = ["jump", "stream", "speed", "other"]
    exhausted = False

    while not exhausted and len(unique) < 500:
        exhausted = True
        for map_type in type_order:
            bucket = by_type[map_type]
            if bucket:
                unique.append(bucket.pop(0))
                exhausted = False

    return unique


def calculate_relevance(
    score: dict[str, Any],
    profile: dict[str, Any],
    mod_filter: str = "all",
) -> float:
    assert isinstance(score, dict), "Score must be dictionary"
    assert isinstance(profile, dict), "Profile must be dictionary"

    relevance = 0.0
    bmap = score.get("beatmap", {})
    pp = score.get("pp", 0)
    map_type = score.get("_map_type", "other")
    type_ceilings = profile.get("type_ceilings", {})

    ceiling = type_ceilings.get(map_type, profile.get("avg_pp", 200))

    sweet_min = ceiling * 0.60
    sweet_max = ceiling * 0.85

    relevance += calculate_pp_relevance(pp, sweet_min, sweet_max)
    relevance += calculate_type_relevance(map_type, profile.get("dominant_type", "other"))
    relevance += calculate_stat_relevance(bmap, profile)
    relevance += calculate_rank_bonus(bmap)
    relevance += calculate_quality_bonus(score)
    relevance += calculate_accuracy_penalty(score, profile)
    relevance += calculate_mod_penalty(score, profile, mod_filter)

    return relevance


def calculate_pp_relevance(pp: float, sweet_min: float, sweet_max: float) -> float:
    assert isinstance(pp, (int, float)), "PP must be numeric"

    if sweet_min <= pp <= sweet_max:
        range_size = max(1, sweet_max - sweet_min)
        return 12 + (pp - sweet_min) / range_size * 8
    elif pp < sweet_min:
        return max(0, 8 - (sweet_min - pp) / 30)
    else:
        return -(pp - sweet_max) / 15


def calculate_type_relevance(map_type: str, dominant_type: str) -> float:
    assert isinstance(map_type, str), "Map type must be string"
    assert isinstance(dominant_type, str), "Dominant type must be string"

    if map_type == dominant_type:
        return 3.0
    else:
        return 1.0


def calculate_stat_relevance(
    bmap: dict[str, Any],
    profile: dict[str, Any],
) -> float:
    assert isinstance(bmap, dict), "Beatmap must be dictionary"
    assert isinstance(profile, dict), "Profile must be dictionary"

    relevance = 0.0

    ar = bmap.get("ar", 0)
    od = bmap.get("od", 0)
    cs = bmap.get("cs", 0)
    rating = bmap.get("difficulty_rating") or bmap.get("difficultyrating", 0)

    ar_perf = profile.get("ar_performance", {})
    od_perf = profile.get("od_performance", {})
    cs_perf = profile.get("cs_performance", {})
    rating_perf = profile.get("rating_performance", {})

    if ar and ar_perf:
        relevance += get_stat_bonus(ar, ar_perf, 5, 3, -2)

    if od and od_perf:
        relevance += get_stat_bonus(od, od_perf, 5, 3, -2)

    if cs and cs_perf:
        relevance += get_stat_bonus(cs, cs_perf, 4, 2, -1)

    if rating and rating_perf:
        relevance += get_stat_bonus(rating, rating_perf, 6, 4, -3)

    return relevance


def get_stat_bonus(
    value: float,
    perf_data: dict[str, Any],
    best_bonus: float,
    comfort_bonus: float,
    unfamiliar_penalty: float,
) -> float:
    assert isinstance(value, (int, float)), "Value must be numeric"
    assert isinstance(perf_data, dict), "Performance data must be dictionary"

    in_comfort = is_in_comfort_zone(value, perf_data)

    if in_comfort == "best":
        return best_bonus
    elif in_comfort == "comfort":
        return comfort_bonus
    else:
        return unfamiliar_penalty


def calculate_rank_bonus(bmap: dict[str, Any]) -> float:
    assert isinstance(bmap, dict), "Beatmap must be dictionary"

    if bmap.get("ranked", 0) >= 2:
        return 2.0

    return 0.0


def calculate_quality_bonus(score: dict[str, Any]) -> float:
    assert isinstance(score, dict), "Score must be dictionary"

    quality = score_quality(score)
    return quality * 3


def calculate_accuracy_penalty(score: dict[str, Any], profile: dict[str, Any]) -> float:
    assert isinstance(score, dict), "Score must be dictionary"
    assert isinstance(profile, dict), "Profile must be dictionary"

    acc = score.get("accuracy", 0)
    if acc > 1:
        acc = acc / 100.0

    avg_acc = profile.get("avg_acc", 0.96)

    if acc < avg_acc - 0.05:
        return -3.0

    return 0.0


def calculate_mod_penalty(
    score: dict[str, Any],
    profile: dict[str, Any],
    mod_filter: str,
) -> float:
    assert isinstance(score, dict), "Score must be dictionary"
    assert isinstance(profile, dict), "Profile must be dictionary"

    if mod_filter != "all":
        return 0.0

    mods = score.get("mods", 0)
    mod_affinity = profile.get("mod_affinity", {})

    has_hd = bool(mods & 8)
    has_hr = bool(mods & 16)
    has_dt = bool(mods & 64) or bool(mods & 512)

    penalty = 0.0

    if has_hd and mod_affinity.get("HD", 0) > 0.5:
        penalty += 1.0
    if has_hr and mod_affinity.get("HR", 0) > 0.3:
        penalty += 1.0
    if has_dt and mod_affinity.get("DT", 0) > 0.3:
        penalty += 1.0

    return penalty
