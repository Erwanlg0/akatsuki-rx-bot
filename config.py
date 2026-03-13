import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: Final[str | None] = os.getenv("DISCORD_TOKEN")
AKATSUKI_API: Final[str] = "https://akatsuki.gg/api/v1"
OSU_API_V2: Final[str] = "https://osu.ppy.sh/api/v2"

DEFAULT_USER: Final[str] = os.getenv("DEFAULT_USER", "Charlouuw")
DEFAULT_USER_ID: Final[int] = int(os.getenv("DEFAULT_USER_ID", "158897"))

API_MODE: Final[int] = 0
API_RX: Final[int] = 1

EMBED_COLOR: Final[int] = 0xFF4F7B

DATA_DIR: Final[str] = "data"
PLAYED_CACHE_FILE: Final[str] = "data/played_maps_cache.json"
PLAYED_CACHE_TTL_SECONDS: Final[int] = 86400
TOPLINE_HISTORY_FILE: Final[str] = "data/topline_history.json"
LANG_SETTINGS_FILE: Final[str] = "data/lang_settings.json"

API_TIMEOUT_SECONDS: Final[int] = 10
MAX_PAGES: Final[int] = 500
PER_PAGE: Final[int] = 100
LEADERBOARD_PER_PAGE: Final[int] = 50

MAX_SNAPSHOTS: Final[int] = 500
MAX_RETRIES: Final[int] = 3

MOD_FLAGS: Final[dict[str, int]] = {
    "NF": 1,
    "EZ": 2,
    "HD": 8,
    "HR": 16,
    "SD": 32,
    "DT": 64,
    "HT": 256,
    "NC": 512,
    "FL": 1024,
    "SO": 4096,
}

SPARKLINE_TICKS: Final[str] = "▁▂▃▄▅▆▇█"

TYPE_LABELS: Final[dict[str, str]] = {
    "jump": "🎯 Jump",
    "stream": "🌊 Stream",
    "speed": "⚡ Speed",
    "other": "🎵 Other",
}

STREAM_INDICATORS: Final[tuple[str, ...]] = (
    "xi -", "xi-", "vinxis", "dragonforce", "galneryus", "gyze",
    "fleshgod", "undead corporation", "manticora", "babymetal",
    "rivers of nihil", "kardashev", "ryu5150", "imperial circus",
    "road of resistance", "sidetracked day", "raise my sword",
    "ascension to heaven", "blue zenith", "over the top",
    "aragami", "honesty", "rog-unlimitation", "freedom dive",
    "image material", "snow goose", "louder than steel",
    "euphoria", "inferno", "symphony of the night",
    "mythologia's end", "ice angel", "xevel", "happppy song",
    "defenders", "through the fire and flames", "valley of the damned",
    "snow-sleep", "hollow", "humiliation supreme",
    "a thousand", "makiba", "matzcor", "bass slut",
    "parabellum", "mou ii kai", "pure ruby", "slider",
    "fool moon", "lama", "kegare naki",
)

JUMP_INDICATORS: Final[tuple[str, ...]] = (
    "jump", "aim", "sotarks", "browiec", "monstrata",
    "harumachi", "haitai", "cbcc", "padoru", "stay with me",
    "hitorigoto", "renai circulation", "kani do-luck",
    "horrible kids", "bbydoll", "r u 4 me", "glory days",
    "dt jump pack", "one by one", "juvenile",
)

STAT_RANGES: Final[dict[str, tuple[tuple[float, float], ...]]] = {
    "ar": ((0.0, 8.5), (8.5, 9.3), (9.3, 9.7), (9.7, 10.0), (10.0, 11.0)),
    "od": ((0.0, 8.0), (8.0, 9.0), (9.0, 9.5), (9.5, 10.0), (10.0, 11.0)),
    "cs": ((0.0, 3.5), (3.5, 4.0), (4.0, 4.5), (4.5, 5.0), (5.0, 7.0)),
    "difficulty_rating": ((0.0, 5.0), (5.0, 5.5), (5.5, 6.0), (6.0, 6.5), (6.5, 7.0), (7.0, 10.0)),
}
