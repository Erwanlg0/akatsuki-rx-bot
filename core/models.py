from typing import TypedDict, NotRequired


class Beatmap(TypedDict):
    beatmap_id: NotRequired[int]
    id: NotRequired[int]
    beatmapset_id: NotRequired[int]
    song_name: NotRequired[str]
    full_title: NotRequired[str]
    ar: NotRequired[float]
    od: NotRequired[float]
    cs: NotRequired[float]
    bpm: NotRequired[float]
    difficulty_rating: NotRequired[float]
    difficultyrating: NotRequired[float]
    max_combo: NotRequired[int]
    ranked: NotRequired[int]
    total_length: NotRequired[int]
    hit_length: NotRequired[int]


class Score(TypedDict):
    beatmap: NotRequired[Beatmap]
    pp: NotRequired[float]
    accuracy: NotRequired[float]
    mods: NotRequired[int]
    count_miss: NotRequired[int]
    max_combo: NotRequired[int]


class Grades(TypedDict):
    xh_count: NotRequired[int]
    x_count: NotRequired[int]
    sh_count: NotRequired[int]
    s_count: NotRequired[int]


class Stats(TypedDict):
    global_leaderboard_rank: NotRequired[int]
    country_leaderboard_rank: NotRequired[int]
    pp: NotRequired[float]
    accuracy: NotRequired[float]
    playcount: NotRequired[int]
    ranked_score: NotRequired[int]
    level: NotRequired[int]
    playtime: NotRequired[int]
    grades: NotRequired[Grades]


class Clan(TypedDict):
    name: NotRequired[str]
    tag: NotRequired[str]


class UserData(TypedDict):
    stats: NotRequired[list[dict[str, Stats]]]
    clan: NotRequired[Clan]


class ZoneMetrics(TypedDict):
    count: int
    avg_pp: float
    avg_acc: float
    avg_quality: float
    performance_score: float


class StatPerformance(TypedDict):
    best_zone: str
    comfort_zones: list[str]
    zones: dict[str, ZoneMetrics]
    stat_name: str


class Profile(TypedDict):
    avg_pp: float
    max_pp: float
    min_pp: float
    avg_acc: float
    avg_acc_top: float
    avg_stars: float
    avg_ar: float
    avg_od: float
    avg_cs: float
    avg_rating: float
    rec_min_pp: float
    rec_max_pp: float
    type_ceilings: dict[str, float]
    type_affinity: dict[str, float]
    dominant_type: str
    mod_affinity: dict[str, float]
    ar_performance: StatPerformance
    od_performance: StatPerformance
    cs_performance: StatPerformance
    rating_performance: StatPerformance
    played_ids: set[int]
    top_mods: list[tuple[str, int]]


class Snapshot(TypedDict):
    ts: int
    metrics: dict[str, dict[str, float]]


class ToplineHistory(TypedDict):
    user_id: int
    snapshots: list[Snapshot]


class CacheData(TypedDict):
    user_id: int
    updated_at: float
    played_ids: list[int]
