import time
from typing import Any
from config import MOD_FLAGS, SPARKLINE_TICKS


def normalize_accuracy(acc: float) -> float:
    assert isinstance(acc, (int, float)), "Accuracy must be numeric"
    assert acc >= 0, "Accuracy cannot be negative"

    if acc > 1:
        return acc / 100.0
    return acc


def mods_str(mods: int) -> str:
    assert isinstance(mods, int), "Mods must be integer"
    assert mods >= 0, "Mods cannot be negative"

    normalized_mods = mods
    if normalized_mods & 512:
        normalized_mods = normalized_mods & ~64

    result: list[str] = []
    mod_items = sorted(MOD_FLAGS.items(), key=lambda x: x[1])

    for name, bit in mod_items:
        if normalized_mods & bit:
            result.append(name)

    return "".join(result) if result else "NM"


def matches_mod_filter(mods: int, filter_str: str) -> bool:
    assert isinstance(mods, int), "Mods must be integer"
    assert isinstance(filter_str, str), "Filter must be string"

    if filter_str == "all":
        return True

    has_hd = bool(mods & 8)
    has_hr = bool(mods & 16)
    has_dt_or_nc = bool(mods & 64) or bool(mods & 512)
    mod_str = mods_str(mods)

    if filter_str == "NM":
        return mod_str == "NM"

    if filter_str == "HDDT":
        return has_hd and has_dt_or_nc
    elif filter_str == "HDHR":
        return has_hd and has_hr
    elif filter_str == "DTHR":
        return has_dt_or_nc and has_hr

    if filter_str == "HD":
        return has_hd
    if filter_str == "HR":
        return has_hr
    if filter_str == "DT":
        return has_dt_or_nc

    return filter_str in mod_str


def pp_to_stars(pp: float) -> float:
    assert isinstance(pp, (int, float)), "PP must be numeric"
    assert pp >= 0, "PP cannot be negative"

    if pp < 100:
        return 2 + pp / 50
    elif pp < 200:
        return 3 + (pp - 100) / 100
    elif pp < 400:
        return 4 + (pp - 200) / 200
    elif pp < 600:
        return 5 + (pp - 400) / 200
    elif pp < 800:
        return 6 + (pp - 600) / 200
    else:
        return 7 + (pp - 800) / 300


def stars_bar(stars: float) -> str:
    assert isinstance(stars, (int, float)), "Stars must be numeric"
    assert stars >= 0, "Stars cannot be negative"

    filled = min(int(stars), 10)
    empty = 10 - filled

    return "█" * filled + "░" * empty + f" {stars:.2f}★"


def format_delta(curr: float, prev: float, suffix: str = "") -> str:
    assert isinstance(curr, (int, float)), "Current value must be numeric"
    assert isinstance(prev, (int, float)), "Previous value must be numeric"

    delta = curr - prev
    sign = "+" if delta >= 0 else ""

    return f"{sign}{delta:.2f}{suffix}"


def format_snapshot_ts(ts: int) -> str:
    assert isinstance(ts, int), "Timestamp must be integer"
    assert ts > 0, "Timestamp must be positive"

    return time.strftime('%d/%m %H:%M', time.localtime(ts))


def sparkline(values: list[float]) -> str:
    assert isinstance(values, list), "Values must be list"

    if not values:
        return "-"

    assert all(isinstance(v, (int, float)) for v in values[:10]), "All values must be numeric"

    ticks = SPARKLINE_TICKS
    vmin = min(values)
    vmax = max(values)

    if vmax - vmin < 1e-9:
        return ticks[3] * len(values)

    chars: list[str] = []
    max_len = min(len(values), 100)

    for i in range(max_len):
        v = values[i]
        idx = int((v - vmin) / (vmax - vmin) * (len(ticks) - 1))
        chars.append(ticks[idx])

    return "".join(chars)


def extract_stats(data: dict[str, Any]) -> dict[str, Any]:
    assert isinstance(data, dict), "Data must be dictionary"

    try:
        stats = data["stats"]
        assert isinstance(stats, list), "Stats must be list"
        assert len(stats) > 1, "Stats must have at least 2 elements"

        return stats[1]["std"]
    except (KeyError, IndexError, TypeError, AssertionError):
        return {}


def truncate_song_name(name: str, max_len: int = 60) -> str:
    assert isinstance(name, str), "Name must be string"
    assert isinstance(max_len, int), "Max length must be integer"
    assert max_len > 0, "Max length must be positive"

    if len(name) <= max_len:
        return name

    if "[" not in name or "]" not in name:
        return name[:max_len]

    parts = name.split(" - ")
    if len(parts) < 2:
        return name[:max_len]

    artist = parts[0][:30] if len(parts[0]) > 30 else parts[0]
    diff_part = parts[-1]

    if "[" in diff_part and "]" in diff_part:
        diff_name = diff_part.split('[')[-1].split(']')[0]
        return f"{artist} [{diff_name}]"

    return name[:max_len]
