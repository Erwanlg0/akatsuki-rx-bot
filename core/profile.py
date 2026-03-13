from typing import Any
from config import STREAM_INDICATORS, JUMP_INDICATORS, STAT_RANGES
from core.utils import normalize_accuracy, pp_to_stars, mods_str


def guess_map_type(score: dict[str, Any]) -> str:
    assert isinstance(score, dict), "Score must be dictionary"

    bmap = score.get("beatmap", {})
    bpm = bmap.get("bpm", 0)
    od = bmap.get("od", 0)
    mods = score.get("mods", 0)
    name = (bmap.get("song_name") or "").lower()

    is_dt = bool(mods & 64) or bool(mods & 512)
    is_hr = bool(mods & 16)
    effective_bpm = bpm * 1.5 if is_dt else bpm

    name_lower = name
    stream_match = sum(1 for kw in STREAM_INDICATORS if kw in name_lower)
    jump_match = sum(1 for kw in JUMP_INDICATORS if kw in name_lower)

    if stream_match > jump_match:
        if effective_bpm >= 240:
            return "speed"
        return "stream"
    if jump_match > stream_match:
        return "jump"

    if bpm >= 170 and (is_hr or is_dt) and od >= 9.0:
        if effective_bpm >= 240:
            return "speed"
        return "stream"

    if effective_bpm >= 240:
        return "speed"
    if effective_bpm >= 200:
        return "stream"

    if is_hr and od >= 9.5 and bpm >= 150:
        return "stream"

    if is_dt and bpm < 160 and od < 9.0:
        return "jump"

    if is_dt and bpm >= 160:
        return "stream"
    if is_dt:
        return "jump"

    return "other"


def score_quality(score: dict[str, Any]) -> float:
    assert isinstance(score, dict), "Score must be dictionary"

    miss = score.get("count_miss", 0)
    max_combo = score.get("max_combo", 0)
    bmap = score.get("beatmap", {})
    full_combo = bmap.get("max_combo", max_combo) or max_combo

    acc = score.get("accuracy", 0)
    if acc > 1:
        acc = acc / 100.0

    combo_ratio = (max_combo / full_combo) if full_combo > 0 else 0.5
    miss_factor = max(0, 1.0 - miss * 0.08)

    quality = acc * 0.4 + combo_ratio * 0.4 + miss_factor * 0.2

    return quality


def analyze_stat_performance(
    scores: list[dict[str, Any]],
    stat_name: str,
) -> dict[str, Any]:
    assert isinstance(scores, list), "Scores must be list"
    assert isinstance(stat_name, str), "Stat name must be string"
    assert stat_name in STAT_RANGES, "Invalid stat name"

    ranges = STAT_RANGES[stat_name]
    zone_data: dict[str, list[dict[str, float]]] = {}

    for r in ranges:
        zone_key = f"{r[0]:.1f}-{r[1]:.1f}"
        zone_data[zone_key] = []

    max_scores = min(len(scores), 200)

    for i in range(max_scores):
        s = scores[i]
        bmap = s.get("beatmap", {})

        if stat_name == "difficulty_rating":
            value = bmap.get("difficulty_rating") or bmap.get("difficultyrating")
        else:
            value = bmap.get(stat_name)

        if not value or value == 0:
            continue

        max_ranges = min(len(ranges), 10)

        for j in range(max_ranges):
            r = ranges[j]
            if r[0] <= value < r[1]:
                zone_key = f"{r[0]:.1f}-{r[1]:.1f}"
                pp = s.get("pp", 0)
                acc = s.get("accuracy", 0)
                if acc > 1:
                    acc = acc / 100.0
                quality = score_quality(s)

                zone_data[zone_key].append({
                    "pp": pp,
                    "acc": acc,
                    "quality": quality,
                })
                break

    return compute_zone_metrics(zone_data, stat_name)


def compute_zone_metrics(
    zone_data: dict[str, list[dict[str, float]]],
    stat_name: str,
) -> dict[str, Any]:
    assert isinstance(zone_data, dict), "Zone data must be dictionary"
    assert isinstance(stat_name, str), "Stat name must be string"

    zone_metrics: dict[str, Any] = {}

    for zone_key, scores_in_zone in zone_data.items():
        if not scores_in_zone:
            continue

        max_scores = min(len(scores_in_zone), 100)
        zone_subset = scores_in_zone[:max_scores]

        avg_pp = sum(s["pp"] for s in zone_subset) / len(zone_subset)
        avg_acc = sum(s["acc"] for s in zone_subset) / len(zone_subset)
        avg_quality = sum(s["quality"] for s in zone_subset) / len(zone_subset)
        count = len(zone_subset)

        performance_score = (avg_pp * 0.5) + (avg_acc * 200 * 0.3) + (avg_quality * 100 * 0.2)

        zone_metrics[zone_key] = {
            "count": count,
            "avg_pp": avg_pp,
            "avg_acc": avg_acc,
            "avg_quality": avg_quality,
            "performance_score": performance_score,
        }

    best_zone = find_best_zone(zone_metrics)
    comfort_zones = find_comfort_zones(zone_metrics, best_zone)

    return {
        "best_zone": best_zone[0],
        "comfort_zones": comfort_zones,
        "zones": zone_metrics,
        "stat_name": stat_name,
    }


def find_best_zone(
    zone_metrics: dict[str, Any],
) -> tuple[str, float]:
    assert isinstance(zone_metrics, dict), "Zone metrics must be dictionary"

    best_zone = "N/A"
    best_score = 0.0

    for zone_key, metrics in zone_metrics.items():
        if metrics["count"] >= 3 and metrics["performance_score"] > best_score:
            best_score = metrics["performance_score"]
            best_zone = zone_key

    return best_zone, best_score


def find_comfort_zones(
    zone_metrics: dict[str, Any],
    best_zone_info: tuple[str, float],
) -> list[str]:
    assert isinstance(zone_metrics, dict), "Zone metrics must be dictionary"
    assert isinstance(best_zone_info, tuple), "Best zone info must be tuple"

    best_zone, best_score = best_zone_info
    threshold = best_score * 0.85

    comfort_zones: list[str] = []
    max_zones = min(len(zone_metrics), 20)
    zone_items = list(zone_metrics.items())[:max_zones]

    for zone_key, metrics in zone_items:
        if metrics["count"] >= 2 and metrics["performance_score"] >= threshold:
            comfort_zones.append(zone_key)

    return comfort_zones


def is_in_comfort_zone(
    value: float,
    performance_data: dict[str, Any],
) -> str:
    assert isinstance(value, (int, float)), "Value must be numeric"
    assert isinstance(performance_data, dict), "Performance data must be dictionary"

    if not performance_data or not performance_data.get("zones"):
        return "unfamiliar"

    best_zone = performance_data.get("best_zone", "N/A")
    comfort_zones = performance_data.get("comfort_zones", [])

    max_zones = min(len(performance_data["zones"]), 20)
    zone_items = list(performance_data["zones"].items())[:max_zones]

    for zone_key, _ in zone_items:
        try:
            parts = zone_key.split("-")
            zone_min = float(parts[0])
            zone_max = float(parts[1])

            if zone_min <= value < zone_max:
                if zone_key == best_zone:
                    return "best"
                elif zone_key in comfort_zones:
                    return "comfort"
                else:
                    return "unfamiliar"
        except (ValueError, IndexError):
            continue

    return "unfamiliar"


def compute_topline_metrics(
    scores: list[dict[str, Any]],
    buckets: list[int] | None = None,
) -> dict[str, Any]:
    assert isinstance(scores, list), "Scores must be list"

    if buckets is None:
        buckets = [1, 5, 10, 20, 50, 100]

    assert isinstance(buckets, list), "Buckets must be list"

    metrics: dict[str, Any] = {}
    sorted_scores = sorted(scores, key=lambda s: s.get("pp", 0), reverse=True)

    top100_subset = sorted_scores[:min(100, len(sorted_scores))]
    top100_total_pp = sum(s.get("pp", 0.0) for s in top100_subset)
    weighted_pp = sum(
        s.get("pp", 0.0) * (0.95 ** i)
        for i, s in enumerate(top100_subset)
    )
    # We only have the fetched score subset in-session; bonus is an estimate.
    score_count_estimate = len(sorted_scores)
    bonus_pp_estimate = 416.6667 * (1 - (0.995 ** min(score_count_estimate, 1000)))

    top100_acc_values = [
        normalize_accuracy(s.get("accuracy", 0.0))
        for s in top100_subset
        if s.get("accuracy", 0) > 0
    ]

    metrics["top100_total_pp"] = top100_total_pp
    metrics["top100_weighted_pp"] = weighted_pp
    metrics["top100_bonus_pp_estimate"] = bonus_pp_estimate
    metrics["top100_total_pp_weighted_estimate"] = weighted_pp + bonus_pp_estimate
    metrics["top100_avg_acc"] = (
        sum(top100_acc_values) / len(top100_acc_values)
        if top100_acc_values
        else 0.0
    )
    metrics["top100_count"] = len(top100_subset)

    max_buckets = min(len(buckets), 10)

    for i in range(max_buckets):
        n = buckets[i]
        if len(sorted_scores) < n:
            metrics[str(n)] = {
                "count": 0,
                "rank_pp": 0.0,
                "rank_acc": 0.0,
            }
            continue

        rank_score = sorted_scores[n - 1]
        rank_pp = rank_score.get("pp", 0.0)
        rank_acc_raw = rank_score.get("accuracy", 0.0)
        rank_acc = (
            normalize_accuracy(rank_acc_raw)
            if rank_acc_raw > 0
            else 0.0
        )

        metrics[str(n)] = {
            "count": n,
            "rank_pp": rank_pp,
            "rank_acc": rank_acc,
        }

    return metrics
