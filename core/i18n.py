import json
import os
from typing import Any
import discord
from config import DATA_DIR, LANG_SETTINGS_FILE


DEFAULT_LANG = "fr"
SUPPORTED_LANGS = {"fr", "en"}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "fr": {
        "lang_changed": "Langue du bot definie sur FR.",
        "invalid_limit_1_50": "Le nombre doit etre entre 1 et 50.",
        "invalid_limit_ge_1": "Le nombre doit etre >= 1.",
        "recent_none": "Aucun score recent trouve.",
        "recent_title": "Scores recents - {user}",
        "recent_desc": "Scores des dernieres 24 heures",
        "recent_shown": "{count} score(s) recent(s) affiche(s).",
        "top_none": "Aucun top play trouve.",
        "top_title": "Top Plays - {user}",
        "top_desc": "{count} meilleurs scores par PP",
        "top_shown": "{count} top play(s) affiche(s).",
        "topline_title": "Topline PP/ACC - {user}",
        "topline_desc": "Top 1, 5, 10, 20, 50, 100 • snapshot enregistre",
        "topline_total_name": "Top 100 total (session)",
        "topline_history_name": "Historique gain Top 100",
        "topline_history_empty": "Pas assez de snapshots (minimum 2).",
        "topline_footer": "Snapshots: {count} • Dernier: {last}",
        "refresh_ok": "Cache mis a jour : {count} maps (valide 24h).",
        "refresh_fail": "Impossible de rafraichir le cache.",
        "clear_done": "{count} message(s) supprime(s).",
        "clear_none": "Aucun message du bot trouve.",
        "clear_perm": "Pas la permission de supprimer les messages.",
        "clear_error": "Erreur pendant la suppression des messages.",
        "recommend_invalid_min_pp": "`min_pp` doit etre > 0.",
        "recommend_invalid_max_pp": "`max_pp` doit etre > 0.",
        "recommend_invalid_pp_range": "`min_pp` doit etre <= `max_pp`.",
        "recommend_invalid_min_time": "`min_time` doit etre > 0.",
        "recommend_invalid_max_time": "`max_time` doit etre > 0.",
        "recommend_invalid_time_range": "`min_time` doit etre <= `max_time`.",
        "recommend_no_top": "Aucun top play RX trouve.",
        "recommend_profile_failed": "Impossible d'analyser le profil.",
        "recommend_analyzing": "Analyse du profil...",
        "recommend_title": "Recs pour {user}",
        "recommend_none": "Aucune map trouvee{filter_msg}",
        "recommend_try_again": "Essayez sans filtre ou reessayez plus tard",
        "profile_fetch_failed": "Impossible de recuperer les stats.",
        "profile_title": "Profil Akatsuki RX - {user}",
        "profile_rank_global": "Rank Global",
        "profile_rank_country": "Rank Pays",
        "profile_playtime": "Playtime",
        "profile_playcount": "Playcount",
        "profile_ranked_score": "Ranked Score",
        "profile_avg_level": "Niveau moyen (top plays)",
        "profile_recommend_range": "Plage de recommandation",
        "profile_preferences": "Analyse des preferences",
        "profile_comfort_zones": "Zones de confort",
        "improve_invalid_limit": "`limit` doit etre entre 1 et 10.",
        "improve_no_scores": "Aucun play trouve pour l'analyse.",
        "improve_none": "Aucun play interessant a ameliorer trouve.",
        "improve_title": "Improve - {user}",
        "improve_desc": "Plays les plus simples a ameliorer (estimation)\nAnalyse basee sur **{count} plays**",
        "improve_now": "Maintenant",
        "improve_estimate": "Estimation",
        "improve_focus": "Focus",
        "improve_footer": "Profil: {avg_pp:.0f}pp moy • {max_pp:.0f}pp max • Estimation indicative",
        "type_jump": "Jump",
        "type_stream": "Stream",
        "type_speed": "Speed",
        "type_other": "Other",
    },
    "en": {
        "lang_changed": "Bot language set to EN.",
        "invalid_limit_1_50": "Value must be between 1 and 50.",
        "invalid_limit_ge_1": "Value must be >= 1.",
        "recent_none": "No recent scores found.",
        "recent_title": "Recent Scores - {user}",
        "recent_desc": "Scores from the last 24 hours",
        "recent_shown": "Displayed {count} recent score(s).",
        "top_none": "No top play found.",
        "top_title": "Top Plays - {user}",
        "top_desc": "{count} best scores by PP",
        "top_shown": "Displayed {count} top play(s).",
        "topline_title": "Topline PP/ACC - {user}",
        "topline_desc": "Top 1, 5, 10, 20, 50, 100 • snapshot saved",
        "topline_total_name": "Top 100 total (session)",
        "topline_history_name": "Top 100 gain history",
        "topline_history_empty": "Not enough snapshots (minimum 2).",
        "topline_footer": "Snapshots: {count} • Last: {last}",
        "refresh_ok": "Cache refreshed: {count} maps (valid for 24h).",
        "refresh_fail": "Could not refresh cache.",
        "clear_done": "Deleted {count} message(s).",
        "clear_none": "No bot message found.",
        "clear_perm": "Missing permission to delete messages.",
        "clear_error": "Error while deleting messages.",
        "recommend_invalid_min_pp": "`min_pp` must be > 0.",
        "recommend_invalid_max_pp": "`max_pp` must be > 0.",
        "recommend_invalid_pp_range": "`min_pp` must be <= `max_pp`.",
        "recommend_invalid_min_time": "`min_time` must be > 0.",
        "recommend_invalid_max_time": "`max_time` must be > 0.",
        "recommend_invalid_time_range": "`min_time` must be <= `max_time`.",
        "recommend_no_top": "No RX top play found.",
        "recommend_profile_failed": "Could not analyze profile.",
        "recommend_analyzing": "Analyzing profile...",
        "recommend_title": "Recommendations for {user}",
        "recommend_none": "No map found{filter_msg}",
        "recommend_try_again": "Try without filters or try again later",
        "profile_fetch_failed": "Could not fetch stats.",
        "profile_title": "Akatsuki RX Profile - {user}",
        "profile_rank_global": "Global Rank",
        "profile_rank_country": "Country Rank",
        "profile_playtime": "Playtime",
        "profile_playcount": "Playcount",
        "profile_ranked_score": "Ranked Score",
        "profile_avg_level": "Average level (top plays)",
        "profile_recommend_range": "Recommendation range",
        "profile_preferences": "Preference analysis",
        "profile_comfort_zones": "Comfort zones",
        "improve_invalid_limit": "`limit` must be between 1 and 10.",
        "improve_no_scores": "No plays found for analysis.",
        "improve_none": "No interesting play to improve found.",
        "improve_title": "Improve - {user}",
        "improve_desc": "Easiest plays to improve (estimate)\nAnalysis based on **{count} plays**",
        "improve_now": "Now",
        "improve_estimate": "Estimate",
        "improve_focus": "Focus",
        "improve_footer": "Profile: {avg_pp:.0f}pp avg • {max_pp:.0f}pp max • Indicative estimate",
        "type_jump": "Jump",
        "type_stream": "Stream",
        "type_speed": "Speed",
        "type_other": "Other",
    },
}


def _load_lang_payload() -> dict[str, Any]:
    if not os.path.exists(LANG_SETTINGS_FILE):
        return {"guilds": {}}

    try:
        with open(LANG_SETTINGS_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return {"guilds": {}}
        guilds = payload.get("guilds", {})
        if not isinstance(guilds, dict):
            return {"guilds": {}}
        return {"guilds": guilds}
    except Exception:
        return {"guilds": {}}


def _save_lang_payload(payload: dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LANG_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def get_lang_for_interaction(interaction: discord.Interaction) -> str:
    guild = interaction.guild
    if guild is None:
        return DEFAULT_LANG

    payload = _load_lang_payload()
    guild_lang = payload.get("guilds", {}).get(str(guild.id), DEFAULT_LANG)
    if guild_lang not in SUPPORTED_LANGS:
        return DEFAULT_LANG
    return guild_lang


def set_guild_lang(guild_id: int, lang: str) -> str:
    selected = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    payload = _load_lang_payload()
    guilds = payload.setdefault("guilds", {})
    guilds[str(guild_id)] = selected
    _save_lang_payload(payload)
    return selected


def t(lang: str, key: str, **kwargs: Any) -> str:
    selected = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    template = _TRANSLATIONS.get(selected, {}).get(key)
    if template is None:
        template = _TRANSLATIONS[DEFAULT_LANG].get(key, key)

    try:
        return template.format(**kwargs)
    except Exception:
        return template


def type_label(map_type: str, lang: str) -> str:
    selected = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    key = f"type_{map_type}"
    return _TRANSLATIONS.get(selected, {}).get(key, map_type)
