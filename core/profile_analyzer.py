from typing import Any
from core.utils import normalize_accuracy, pp_to_stars, mods_str
from core.profile import (
    guess_map_type,
    score_quality,
    analyze_stat_performance,
)


def analyze_profile(scores: list[dict[str, Any]]) -> dict[str, Any]:
    assert isinstance(scores, list), "Scores must be list"

    if not scores:
        return {}

    pp_list = [s.get("pp", 0) for s in scores if s.get("pp", 0) > 0]

    if not pp_list:
        return {}

    ar_performance = analyze_stat_performance(scores, "ar")
    od_performance = analyze_stat_performance(scores, "od")
    cs_performance = analyze_stat_performance(scores, "cs")
    rating_performance = analyze_stat_performance(scores, "difficulty_rating")

    type_scores = compute_type_scores(scores)
    type_ceilings = compute_type_ceilings(type_scores)
    type_affinity = compute_type_affinity(type_scores)

    avg_pp = sum(pp_list) / len(pp_list)
    max_pp = max(pp_list)
    min_pp = min(pp_list)

    avg_acc_values = compute_avg_acc_values(scores)
    avg_acc = sum(avg_acc_values) / len(avg_acc_values) if avg_acc_values else 0.96
    avg_acc_top = compute_avg_acc_top(scores, pp_list)

    sorted_pp = sorted(pp_list)
    q25_idx = max(0, int(len(sorted_pp) * 0.25) - 1)
    q90_idx = max(0, int(len(sorted_pp) * 0.90) - 1)
    p25 = sorted_pp[q25_idx]
    p90 = sorted_pp[q90_idx]

    rec_min_pp = max(50, p25 * 0.90)
    rec_max_pp = max(rec_min_pp + 20, min(max_pp * 1.08, p90 * 1.15))

    estimated_stars = pp_to_stars(avg_pp)

    played_ids = extract_played_ids(scores)

    type_counts = {mt: len(entries) for mt, entries in type_scores.items() if entries}
    dominant_type = max(type_counts, key=type_counts.get) if type_counts else "other"

    mod_affinity = compute_mod_affinity(scores)
    top_mods = compute_top_mods(scores)

    ar_list, od_list, cs_list, rating_list = extract_stat_lists(scores)

    print_profile_summary(
        type_ceilings,
        dominant_type,
        max_pp,
        avg_pp,
        avg_acc,
        avg_acc_top,
        rec_min_pp,
        rec_max_pp,
        type_affinity,
        mod_affinity,
        ar_performance,
        od_performance,
        cs_performance,
        rating_performance,
    )

    return {
        "avg_pp": avg_pp,
        "max_pp": max_pp,
        "min_pp": min_pp,
        "avg_acc": avg_acc,
        "avg_acc_top": avg_acc_top,
        "avg_stars": estimated_stars,
        "avg_ar": sum(ar_list) / len(ar_list) if ar_list else 9.5,
        "avg_od": sum(od_list) / len(od_list) if od_list else 9,
        "avg_cs": sum(cs_list) / len(cs_list) if cs_list else 4,
        "avg_rating": sum(rating_list) / len(rating_list) if rating_list else 5.5,
        "rec_min_pp": rec_min_pp,
        "rec_max_pp": rec_max_pp,
        "type_ceilings": type_ceilings,
        "type_affinity": type_affinity,
        "dominant_type": dominant_type,
        "mod_affinity": mod_affinity,
        "ar_performance": ar_performance,
        "od_performance": od_performance,
        "cs_performance": cs_performance,
        "rating_performance": rating_performance,
        "played_ids": played_ids,
        "top_mods": top_mods,
    }


def compute_type_scores(
    scores: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    assert isinstance(scores, list), "Scores must be list"

    type_scores: dict[str, list[dict[str, Any]]] = {
        "jump": [],
        "stream": [],
        "speed": [],
        "other": [],
    }

    max_scores = min(len(scores), 200)

    for i in range(max_scores):
        s = scores[i]
        pp = s.get("pp", 0)
        if pp <= 0:
            continue

        mt = guess_map_type(s)
        quality = score_quality(s)

        type_scores[mt].append({
            "pp": pp,
            "quality": quality,
            "score": s,
        })

    return type_scores


def compute_type_ceilings(
    type_scores: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    assert isinstance(type_scores, dict), "Type scores must be dictionary"

    type_ceilings: dict[str, float] = {}

    for mt, entries in type_scores.items():
        if not entries:
            continue

        top = sorted(entries, key=lambda e: e["pp"], reverse=True)[:5]
        pp_values = [e["pp"] for e in top]

        if not pp_values:
            continue

        sorted_pp = sorted(pp_values)
        median_pp = sorted_pp[len(sorted_pp) // 2]
        type_ceilings[mt] = median_pp * 0.92

    return type_ceilings


def compute_avg_acc_values(
    scores: list[dict[str, Any]],
) -> list[float]:
    assert isinstance(scores, list), "Scores must be list"

    acc_list = [s.get("accuracy", 0) for s in scores if s.get("accuracy", 0) > 0]
    normalized_acc: list[float] = []

    max_acc = min(len(acc_list), 200)

    for i in range(max_acc):
        acc = acc_list[i]
        if acc > 1:
            normalized_acc.append(acc / 100.0)
        else:
            normalized_acc.append(acc)

    return normalized_acc


def compute_avg_acc_top(
    scores: list[dict[str, Any]],
    pp_list: list[float],
) -> float:
    assert isinstance(scores, list), "Scores must be list"
    assert isinstance(pp_list, list), "PP list must be list"

    top_50_count = max(10, len(pp_list) // 2)
    mid_scores = sorted(scores, key=lambda x: x.get("pp", 0), reverse=True)[:top_50_count]

    mid_acc_list: list[float] = []
    max_scores = min(len(mid_scores), 100)

    for i in range(max_scores):
        s = mid_scores[i]
        acc = s.get("accuracy", 0)
        if acc > 1:
            mid_acc_list.append(acc / 100.0)
        elif acc > 0:
            mid_acc_list.append(acc)

    avg_acc_top = sum(mid_acc_list) / len(mid_acc_list) if mid_acc_list else 0.96
    avg_acc_top = max(0.90, avg_acc_top - 0.005)

    return avg_acc_top


def extract_played_ids(scores: list[dict[str, Any]]) -> set[int]:
    assert isinstance(scores, list), "Scores must be list"

    played_ids = {
        s.get("beatmap", {}).get("beatmap_id") or s.get("beatmap", {}).get("id")
        for s in scores
        if s.get("beatmap")
    }
    played_ids.discard(None)

    return played_ids


def compute_mod_affinity(scores: list[dict[str, Any]]) -> dict[str, float]:
    assert isinstance(scores, list), "Scores must be list"

    mod_presence_counts = {"HD": 0, "HR": 0, "DT": 0}
    total_scores = len(scores)
    max_scores = min(total_scores, 200)

    for i in range(max_scores):
        s = scores[i]
        mods = s.get("mods", 0)

        if mods & 8:
            mod_presence_counts["HD"] += 1
        if mods & 16:
            mod_presence_counts["HR"] += 1
        if mods & 64 or mods & 512:
            mod_presence_counts["DT"] += 1

    mod_affinity = {
        mod: (count / max_scores if max_scores > 0 else 0.0)
        for mod, count in mod_presence_counts.items()
    }

    return mod_affinity


def compute_type_affinity(
    type_scores: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    assert isinstance(type_scores, dict), "Type scores must be dictionary"

    total_scores = sum(len(entries) for entries in type_scores.values())

    if total_scores == 0:
        return {"jump": 0.0, "stream": 0.0, "speed": 0.0, "other": 0.0}

    type_affinity = {}
    for map_type, entries in type_scores.items():
        count = len(entries)
        type_affinity[map_type] = count / total_scores if total_scores > 0 else 0.0

    return type_affinity


def compute_top_mods(scores: list[dict[str, Any]]) -> list[tuple[str, int]]:
    assert isinstance(scores, list), "Scores must be list"

    mods_count: dict[str, int] = {}
    max_scores = min(len(scores), 200)

    for i in range(max_scores):
        s = scores[i]
        mods = s.get("mods", 0)
        mod = mods_str(mods)
        mods_count[mod] = mods_count.get(mod, 0) + 1

    sorted_mods = sorted(mods_count.items(), key=lambda x: x[1], reverse=True)

    return sorted_mods[:3]


def extract_stat_lists(
    scores: list[dict[str, Any]],
) -> tuple[list[float], list[float], list[float], list[float]]:
    assert isinstance(scores, list), "Scores must be list"

    ar_list: list[float] = []
    od_list: list[float] = []
    cs_list: list[float] = []
    rating_list: list[float] = []

    max_scores = min(len(scores), 200)

    for i in range(max_scores):
        s = scores[i]
        bmap = s.get("beatmap", {})

        ar = bmap.get("ar")
        if ar:
            ar_list.append(ar)

        od = bmap.get("od")
        if od:
            od_list.append(od)

        cs = bmap.get("cs")
        if cs:
            cs_list.append(cs)

        rating = bmap.get("difficulty_rating") or bmap.get("difficultyrating", 0)
        if rating:
            rating_list.append(rating)

    return ar_list, od_list, cs_list, rating_list


def print_profile_summary(
    type_ceilings: dict[str, float],
    dominant_type: str,
    max_pp: float,
    avg_pp: float,
    avg_acc: float,
    avg_acc_top: float,
    rec_min_pp: float,
    rec_max_pp: float,
    type_affinity: dict[str, float],
    mod_affinity: dict[str, float],
    ar_performance: dict[str, Any],
    od_performance: dict[str, Any],
    cs_performance: dict[str, Any],
    rating_performance: dict[str, Any],
) -> None:
    ceilings_str = ", ".join(f"{k}={v:.0f}pp" for k, v in type_ceilings.items())
    print(f"[PROFILE] Type ceilings: {ceilings_str}")
    print(f"[PROFILE] Dominant: {dominant_type} | Max: {max_pp:.0f} | Avg: {avg_pp:.0f}")
    print(f"[PROFILE] Acc: {avg_acc:.1%} | Top avg: {avg_acc_top:.1%}")
    print(f"[PROFILE] Range: {rec_min_pp:.0f}-{rec_max_pp:.0f}pp")

    affinity_str = ", ".join(f"{k}={v:.1%}" for k, v in type_affinity.items())
    print(f"[PROFILE] Type affinity: {affinity_str}")

    hd = mod_affinity['HD']
    hr = mod_affinity['HR']
    dt = mod_affinity['DT']
    print(f"[PROFILE] Mods: HD={hd:.1%}, HR={hr:.1%}, DT={dt:.1%}")

    ar_best = ar_performance['best_zone']
    od_best = od_performance['best_zone']
    cs_best = cs_performance['best_zone']
    rating_best = rating_performance['best_zone']
    print(f"[PROFILE] Best zones: AR={ar_best} OD={od_best} CS={cs_best} ★={rating_best}")
