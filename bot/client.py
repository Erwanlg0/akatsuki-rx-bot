import aiohttp
import discord
from discord import app_commands
from typing import Any
from config import (
    DEFAULT_USER,
    DEFAULT_USER_ID,
    EMBED_COLOR,
)
from core.api import get_user_best, get_user_stats, get_user_recent, enrich_scores
from core.cache import get_user_played_map_ids, load_topline_history, append_topline_snapshot
from core.profile import compute_topline_metrics, guess_map_type
from core.profile_analyzer import analyze_profile
from core.recommendation import get_recommendations
from core.utils import (
    extract_stats,
    stars_bar,
    mods_str,
    normalize_accuracy,
    truncate_song_name,
    format_delta,
    format_snapshot_ts,
)
from core.i18n import get_lang_for_interaction, t, type_label


class AkatsukiBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        print("✅ Commands synced")

    async def on_ready(self) -> None:
        assert self.user is not None, "User must not be None"
        print(f"✅ Connected: {self.user}")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name=f"osu! RX avec {DEFAULT_USER} | /recommend"
            )
        )


def create_bot() -> AkatsukiBot:
    return AkatsukiBot()


def build_embeds(
    scores: list[dict[str, Any]],
    title: str,
    desc: str = "",
) -> list[discord.Embed]:
    assert isinstance(scores, list), "Scores must be list"
    assert isinstance(title, str), "Title must be string"

    if not scores:
        embed = discord.Embed(
            title=title,
            description="Aucune map trouvée.",
            color=EMBED_COLOR,
        )
        return [embed]

    embeds: list[discord.Embed] = []
    per_page = 8
    total_pages = (len(scores) + per_page - 1) // per_page
    max_pages = min(total_pages, 20)

    for page_idx in range(max_pages):
        chunk = scores[page_idx * per_page : (page_idx + 1) * per_page]
        page_title = f"{title} ({page_idx + 1}/{max_pages})" if max_pages > 1 else title

        embed = discord.Embed(
            title=page_title,
            description=desc if page_idx == 0 else "",
            color=EMBED_COLOR,
        )

        start_num = page_idx * per_page + 1

        for i, s in enumerate(chunk, start_num):
            add_score_field(embed, s, i)

        embed.set_footer(text=f"Akatsuki Relax • /recommend • {len(scores)} scores")
        embeds.append(embed)

    return embeds


def add_score_field(
    embed: discord.Embed,
    score: dict[str, Any],
    index: int,
) -> None:
    assert isinstance(embed, discord.Embed), "Embed must be Embed"
    assert isinstance(score, dict), "Score must be dictionary"

    bmap = score.get("beatmap", {})
    bid = bmap.get("beatmap_id") or bmap.get("id", "?")
    bsid = bmap.get("beatmapset_id", bid)
    name = bmap.get("song_name") or bmap.get("full_title") or f"#{bid}"

    name = truncate_song_name(name, 60)

    pp = score.get("pp", 0)
    acc = score.get("accuracy", 0)
    misses = score.get("count_miss", 0)

    if acc > 1:
        acc_display = acc
    else:
        acc_display = acc * 100

    ar = bmap.get("ar", 0)
    od = bmap.get("od", 0)
    mods = mods_str(score.get("mods", 0))

    info_parts = [f"**{pp:.0f}pp**", f"{acc_display:.1f}%"]

    if misses > 0:
        info_parts.append(f"{misses}miss")

    if ar:
        info_parts.append(f"AR{ar:.1f}")
    if od:
        info_parts.append(f"OD{od:.1f}")

    info_parts.append(f"`RX+{mods}`")

    links = (
        f"[osu!](https://osu.ppy.sh/b/{bid}) • "
        f"[Akatsuki](https://akatsuki.gg/b/{bid}) • "
        f"[DL](https://akatsuki.gg/d/{bsid})"
    )

    embed.add_field(
        name=f"`{index}.` {name[:55]}",
        value=f"{' • '.join(info_parts)}\n{links}",
        inline=False,
    )


async def command_recommend(
    interaction: discord.Interaction,
    mods: app_commands.Choice[str] | None = None,
    min_pp: int | None = None,
    max_pp: int | None = None,
    min_time: int | None = None,
    max_time: int | None = None,
    map_type: app_commands.Choice[str] | None = None,
) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        return

    if min_pp is not None and min_pp < 1:
        await interaction.followup.send(t(lang, "recommend_invalid_min_pp"), ephemeral=True)
        return

    if max_pp is not None and max_pp < 1:
        await interaction.followup.send(t(lang, "recommend_invalid_max_pp"), ephemeral=True)
        return

    if min_pp is not None and max_pp is not None and min_pp > max_pp:
        await interaction.followup.send(t(lang, "recommend_invalid_pp_range"), ephemeral=True)
        return

    if min_time is not None and min_time < 1:
        await interaction.followup.send(t(lang, "recommend_invalid_min_time"), ephemeral=True)
        return

    if max_time is not None and max_time < 1:
        await interaction.followup.send(t(lang, "recommend_invalid_max_time"), ephemeral=True)
        return

    if min_time is not None and max_time is not None and min_time > max_time:
        await interaction.followup.send(t(lang, "recommend_invalid_time_range"), ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        best = await get_user_best(session, limit=100)

        if not best:
            await interaction.followup.send(t(lang, "recommend_no_top"))
            return

        best = await enrich_scores(session, best)

        profile = analyze_profile(best)
        played_ids = await get_user_played_map_ids(session)

        if not profile:
            await interaction.followup.send(t(lang, "recommend_profile_failed"))
            return

        if played_ids:
            profile["played_ids"] = played_ids

        await interaction.followup.send(t(lang, "recommend_analyzing"), ephemeral=True)

        mod_filter = mods.value if mods else "all"
        type_filter = map_type.value if map_type else "all"
        effective_min_pp = min_pp if min_pp is not None else int(profile["rec_min_pp"])
        effective_max_pp = max_pp if max_pp is not None else int(profile["rec_max_pp"])

        unique = await get_recommendations(
            session,
            profile,
            mod_filter,
            limit=10,
            min_pp=effective_min_pp,
            max_pp=effective_max_pp,
            min_time=min_time,
            max_time=max_time,
            map_type_filter=type_filter,
        )

        if not unique and mod_filter != "all":
            unique = await get_recommendations(
                session,
                profile,
                "all",
                limit=10,
                min_pp=effective_min_pp,
                max_pp=effective_max_pp,
                min_time=min_time,
                max_time=max_time,
                map_type_filter=type_filter,
            )
            mod_filter = "all (broadened from filtered)"

        if not unique and (min_pp is not None or max_pp is not None):
            effective_min_pp = int(profile["rec_min_pp"])
            effective_max_pp = int(profile["rec_max_pp"])
            unique = await get_recommendations(
                session,
                profile,
                "all",
                limit=10,
                min_pp=effective_min_pp,
                max_pp=effective_max_pp,
                min_time=min_time,
                max_time=max_time,
                map_type_filter=type_filter,
            )

        await send_recommendations(
            interaction,
            unique,
            profile,
            lang,
            mod_filter,
            min_pp,
            max_pp,
            effective_min_pp,
            effective_max_pp,
            min_time,
            max_time,
            type_filter,
        )


async def send_recommendations(
    interaction: discord.Interaction,
    unique: list[dict[str, Any]],
    profile: dict[str, Any],
    lang: str,
    mod_filter: str,
    min_pp: int | None,
    max_pp: int | None,
    effective_min_pp: int,
    effective_max_pp: int,
    min_time: int | None = None,
    max_time: int | None = None,
    type_filter: str = "all",
) -> None:
    assert interaction.channel is not None, "Channel must not be None"

    avg_pp = profile["avg_pp"]
    avg_stars = profile["avg_stars"]

    top_mods = profile.get("top_mods", [])
    mods_info = ", ".join([f"{mod[0]} ({mod[1]}x)" for mod in top_mods[:2]]) if top_mods else "NM"

    filter_text = f" • Filter: **{mod_filter}**" if (mod_filter != "all" and lang == "en") else ""
    if mod_filter != "all" and lang == "fr":
        filter_text = f" • Filtre : **{mod_filter}**"
    if min_pp is not None or max_pp is not None:
        custom_range_text = (
            f" • Range: **{effective_min_pp}–{effective_max_pp}pp**"
            if lang == "en"
            else f" • Plage : **{effective_min_pp}–{effective_max_pp}pp**"
        )
    else:
        custom_range_text = ""

    type_ceilings = profile.get("type_ceilings", {})
    ceilings_info = " • ".join(
        f"{type_label(t_name, lang)} ~{pp:.0f}pp"
        for t_name, pp in sorted(type_ceilings.items(), key=lambda x: x[1], reverse=True)
        if pp > 0
    )

    ar_best = profile.get("ar_performance", {}).get("best_zone", "N/A")
    od_best = profile.get("od_performance", {}).get("best_zone", "N/A")
    cs_best = profile.get("cs_performance", {}).get("best_zone", "N/A")
    rating_best = profile.get("rating_performance", {}).get("best_zone", "N/A")

    zone_parts = []
    if ar_best != "N/A":
        zone_parts.append(f"AR:{ar_best}")
    if od_best != "N/A":
        zone_parts.append(f"OD:{od_best}")
    if cs_best != "N/A":
        zone_parts.append(f"CS:{cs_best}")
    if rating_best != "N/A":
        zone_parts.append(f"★:{rating_best}")

    comfort_info = " • ".join(zone_parts) if zone_parts else "—"

    if not unique:
        filter_msg = ""
        if mod_filter != "all":
            filter_msg = f" with **{mod_filter}**" if lang == "en" else f" avec **{mod_filter}**"

        profile_label = "Profile" if lang == "en" else "Profil"
        avg_label = "Average" if lang == "en" else "Moyenne"
        range_label = "Range" if lang == "en" else "Plage"
        ceilings_label = "Ceilings" if lang == "en" else "Plafonds"
        zones_label = "Zones"
        mods_label = "Mods"
        played_label = "played beatmaps" if lang == "en" else "beatmaps jouees"

        embed = discord.Embed(
            title=t(lang, "recommend_title", user=DEFAULT_USER),
            description=(
                f"{t(lang, 'recommend_none', filter_msg=filter_msg)}\n\n"
                f"**{profile_label}:**\n"
                f"• {avg_label} : **{avg_pp:.0f}pp** (~{avg_stars:.1f}★) • Max : **{profile['max_pp']:.0f}pp**\n"
                f"• {range_label} : **{effective_min_pp}–{effective_max_pp}pp**\n"
                f"• {ceilings_label} : {ceilings_info}\n"
                f"• {zones_label} : {comfort_info}\n"
                f"• {mods_label} : **{mods_info}**\n"
                f"• {len(profile['played_ids'])} {played_label}\n\n"
                f"{t(lang, 'recommend_try_again')}"
            ),
            color=EMBED_COLOR
        )
        await interaction.channel.send(embed=embed)
    else:
        zones_label = "Zones" if lang == "fr" else "Zones"
        sort_label = "Triees par pertinence" if lang == "fr" else "Sorted by relevance"
        embeds = build_embeds(
            unique,
            t(lang, "recommend_title", user=DEFAULT_USER),
            (
                f"**{avg_pp:.0f}pp** moy (~{avg_stars:.1f}★) • Max **{profile['max_pp']:.0f}pp**{filter_text}{custom_range_text}\n"
                f"{ceilings_info}\n"
                f"{zones_label} : {comfort_info}\n"
                f"Mods : **{mods_info}** • {sort_label}"
            )
        )

        max_embeds = min(len(embeds), 10)

        for i in range(max_embeds):
            await interaction.channel.send(embed=embeds[i])


async def command_profil(interaction: discord.Interaction) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        return

    async with aiohttp.ClientSession() as session:
        data = await get_user_stats(session)
        best = await get_user_best(session, limit=100)

        best = await enrich_scores(session, best)

        profile = analyze_profile(best)

        if not data:
            await interaction.followup.send(t(lang, "profile_fetch_failed"))
            return

        stats = extract_stats(data)

        embed = create_profile_embed(stats, data, profile, best, lang)

        await interaction.followup.send(embed=embed)


def create_profile_embed(
    stats: dict[str, Any],
    data: dict[str, Any],
    profile: dict[str, Any],
    best: list[dict[str, Any]],
    lang: str,
) -> discord.Embed:
    assert isinstance(stats, dict), "Stats must be dictionary"
    assert isinstance(data, dict), "Data must be dictionary"

    rank = stats.get("global_leaderboard_rank", "?")
    country_rank = stats.get("country_leaderboard_rank", "?")
    pp = stats.get("pp", 0)
    acc = stats.get("accuracy", 0)
    playcount = stats.get("playcount", 0)
    ranked_s = stats.get("ranked_score", 0)
    level = stats.get("level", 0)
    playtime = stats.get("playtime", 0) // 3600

    grades = stats.get("grades", {})
    xh = grades.get("xh_count", 0)
    x = grades.get("x_count", 0)
    sh = grades.get("sh_count", 0)
    s = grades.get("s_count", 0)

    clan = data.get("clan", {})
    clan_name = clan.get("name", None)
    clan_tag = clan.get("tag", None)

    embed = discord.Embed(
        title=t(lang, "profile_title", user=DEFAULT_USER),
        color=EMBED_COLOR,
        url=f"https://akatsuki.gg/u/{DEFAULT_USER_ID}?mode=0&rx=1"
    )

    add_profile_fields(embed, rank, country_rank, pp, acc, level, playtime, playcount, ranked_s, lang)

    if xh or x or sh or s:
        grades_txt = f"**XH:** {xh:,} | **X:** {x:,} | **SH:** {sh:,} | **S:** {s:,}"
        embed.add_field(name="🏅 Grades SS/S", value=grades_txt, inline=False)

    if clan_name:
        clan_display = f"[{clan_tag}] {clan_name}" if clan_tag else clan_name
        embed.add_field(name="👥 Clan", value=clan_display, inline=False)

    if profile:
        add_profile_analysis_fields(embed, profile, best, lang)

    add_profile_pp_metrics_field(embed, best)

    embed.set_footer(text="akatsuki.gg • Mode Relax • /recommend")

    return embed


def add_profile_fields(
    embed: discord.Embed,
    rank: int | str,
    country_rank: int | str,
    pp: float,
    acc: float,
    level: int,
    playtime: int,
    playcount: int,
    ranked_s: int,
    lang: str,
) -> None:
    global_rank_value = _format_rank_value(rank)
    country_rank_value = _format_rank_value(country_rank)

    if global_rank_value is not None:
        embed.add_field(name=t(lang, "profile_rank_global"), value=global_rank_value, inline=True)
    if country_rank_value is not None:
        embed.add_field(name=t(lang, "profile_rank_country"), value=country_rank_value, inline=True)

    embed.add_field(name="PP", value=f"{int(pp):,}pp", inline=True)
    embed.add_field(name="Accuracy", value=f"{float(acc):.2f}%", inline=True)
    embed.add_field(name="Level", value=f"{int(level)}", inline=True)
    embed.add_field(name=t(lang, "profile_playtime"), value=f"{playtime:,}h", inline=True)
    embed.add_field(name=t(lang, "profile_playcount"), value=f"{int(playcount):,}", inline=True)
    embed.add_field(name=t(lang, "profile_ranked_score"), value=f"{int(ranked_s):,}", inline=True)


def _format_rank_value(rank: int | str) -> str | None:
    try:
        rank_int = int(rank)
    except (TypeError, ValueError):
        return None

    if rank_int <= 0:
        return None

    return f"#{rank_int:,}"


def add_profile_pp_metrics_field(
    embed: discord.Embed,
    best: list[dict[str, Any]],
) -> None:
    top_scores = sorted(best, key=lambda s: s.get("pp", 0), reverse=True)[:100]
    raw_sum = sum(s.get("pp", 0.0) for s in top_scores)
    weighted_base = sum(s.get("pp", 0.0) * (0.95 ** i) for i, s in enumerate(top_scores))
    bonus_est = 416.6667 * (1 - (0.995 ** min(len(best), 1000)))
    weighted_total_est = weighted_base + bonus_est

    embed.add_field(
        name="PP metrics",
        value=(
            f"Weighted (est.): {weighted_total_est:.2f}pp"
            f" = {weighted_base:.2f} + bonus~{bonus_est:.2f}\n"
            f"Raw top100 sum: {raw_sum:.2f}pp"
        ),
        inline=False,
    )


def add_profile_analysis_fields(
    embed: discord.Embed,
    profile: dict[str, Any],
    best: list[dict[str, Any]],
    lang: str,
) -> None:
    assert isinstance(embed, discord.Embed), "Embed must be Embed"
    assert isinstance(profile, dict), "Profile must be dictionary"

    embed.add_field(
        name=t(lang, "profile_avg_level"),
        value=stars_bar(profile["avg_stars"]),
        inline=False
    )

    embed.add_field(
        name=t(lang, "profile_recommend_range"),
        value=(
            f"{profile['rec_min_pp']:.0f}pp → {profile['rec_max_pp']:.0f}pp\n"
            f"*Le bot cherche dans cette zone*"
        ),
        inline=True
    )

    embed.add_field(
        name=t(lang, "profile_preferences"),
        value=(
            f"{len(profile['played_ids']):,} maps uniques\n"
            f"*Basé sur {len(best)} meilleurs scores*"
        ),
        inline=True
    )

    ar_perf = profile.get("ar_performance", {})
    od_perf = profile.get("od_performance", {})
    cs_perf = profile.get("cs_performance", {})
    rating_perf = profile.get("rating_performance", {})

    comfort_info: list[str] = []

    if ar_perf.get("best_zone") != "N/A":
        comfort_info.append(f"**AR:** {ar_perf['best_zone']} ⭐")
    if od_perf.get("best_zone") != "N/A":
        comfort_info.append(f"**OD:** {od_perf['best_zone']} ⭐")
    if cs_perf.get("best_zone") != "N/A":
        comfort_info.append(f"**CS:** {cs_perf['best_zone']} ⭐")
    if rating_perf.get("best_zone") != "N/A":
        comfort_info.append(f"**★:** {rating_perf['best_zone']} ⭐")

    if comfort_info:
        embed.add_field(
            name=t(lang, "profile_comfort_zones"),
            value=" • ".join(comfort_info),
            inline=False
        )


async def command_improve(
    interaction: discord.Interaction,
    limit: int = 5,
) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        return

    if limit < 1 or limit > 10:
        await interaction.followup.send(t(lang, "improve_invalid_limit"), ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        best_scores = await get_user_best(session, limit=1000)
        recent_scores = await get_user_recent(session, limit=500)

        scores = merge_unique_scores(best_scores, recent_scores)
        if not scores:
            await interaction.followup.send(t(lang, "improve_no_scores"))
            return

        scores = await enrich_scores(session, scores)
        profile = analyze_profile(scores)

        improve_candidates = compute_improve_candidates(scores, profile, limit)
        if not improve_candidates:
            await interaction.followup.send(t(lang, "improve_none"))
            return

        embed = create_improve_embed(improve_candidates, profile, len(scores), lang)
        await interaction.followup.send(embed=embed)


def merge_unique_scores(
    best_scores: list[dict[str, Any]],
    recent_scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    assert isinstance(best_scores, list), "Best scores must be list"
    assert isinstance(recent_scores, list), "Recent scores must be list"

    merged: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for score in best_scores + recent_scores:
        bmap = score.get("beatmap", {})
        bid = bmap.get("beatmap_id") or bmap.get("id")
        mods = int(score.get("mods", 0) or 0)
        if not bid:
            continue

        key = (int(bid), mods)
        if key in seen:
            continue

        seen.add(key)
        merged.append(score)

    return merged


def compute_improve_candidates(
    scores: list[dict[str, Any]],
    profile: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    assert isinstance(scores, list), "Scores must be list"
    assert isinstance(profile, dict), "Profile must be dictionary"

    avg_acc_top = profile.get("avg_acc_top", 0.97)
    target_acc = min(max(avg_acc_top, 0.97), 0.985)

    candidates: list[dict[str, Any]] = []
    max_scores = min(len(scores), 1000)

    for i in range(max_scores):
        score = scores[i]
        bmap = score.get("beatmap", {})
        pp = float(score.get("pp", 0) or 0)
        if pp <= 0:
            continue

        acc = normalize_accuracy(float(score.get("accuracy", 0) or 0))
        misses = int(score.get("count_miss", 0) or 0)
        max_combo = int(score.get("max_combo", 0) or 0)
        full_combo = int(bmap.get("max_combo", 0) or 0)
        combo_ratio = (max_combo / full_combo) if full_combo > 0 else 0.95

        acc_gap = max(0.0, target_acc - acc)
        acc_factor = min(0.08, acc_gap * 2.4)
        miss_factor = min(0.10, misses * 0.012)
        combo_factor = min(0.07, max(0.0, 0.985 - combo_ratio) * 1.4)

        total_factor = acc_factor + miss_factor + combo_factor
        if total_factor < 0.015:
            continue

        estimated_gain_pp = min(90.0, pp * total_factor)
        if estimated_gain_pp < 5:
            continue

        miss_ease = max(0.0, 1.0 - (misses / 8.0))
        acc_ease = max(0.0, 1.0 - (acc_gap / 0.03))
        combo_ease = max(0.0, min(1.0, (combo_ratio - 0.90) / 0.10))
        ease = 0.45 * miss_ease + 0.35 * acc_ease + 0.20 * combo_ease

        priority = estimated_gain_pp * (0.55 + 0.45 * ease)
        if ease < 0.25:
            continue

        candidates.append(
            {
                "score": score,
                "estimated_gain_pp": estimated_gain_pp,
                "target_acc": target_acc,
                "ease": ease,
                "priority": priority,
                "map_type": guess_map_type(score),
                "combo_ratio": combo_ratio,
            }
        )

    candidates.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return candidates[:limit]


def create_improve_embed(
    improve_candidates: list[dict[str, Any]],
    profile: dict[str, Any],
    analyzed_count: int,
    lang: str,
) -> discord.Embed:
    assert isinstance(improve_candidates, list), "Candidates must be list"

    embed = discord.Embed(
        title=t(lang, "improve_title", user=DEFAULT_USER),
        description=t(lang, "improve_desc", count=analyzed_count),
        color=EMBED_COLOR,
    )

    for idx, item in enumerate(improve_candidates, start=1):
        score = item["score"]
        bmap = score.get("beatmap", {})
        bid = bmap.get("beatmap_id") or bmap.get("id", "?")
        name = truncate_song_name(
            bmap.get("song_name") or bmap.get("full_title") or f"#{bid}",
            64,
        )

        current_pp = float(score.get("pp", 0) or 0)
        gain_pp = float(item.get("estimated_gain_pp", 0))
        projected_pp = current_pp + gain_pp
        acc = normalize_accuracy(float(score.get("accuracy", 0) or 0)) * 100
        target_acc = float(item.get("target_acc", 0.98)) * 100
        misses = int(score.get("count_miss", 0) or 0)
        map_type = item.get("map_type", "other")
        mods = mods_str(int(score.get("mods", 0) or 0))

        if misses > 0:
            plan = (
                f"reduce misses ({misses} -> {max(0, misses - 1)})"
                if lang == "en"
                else f"reduire les miss ({misses} -> {max(0, misses - 1)})"
            )
        elif acc < target_acc - 0.2:
            plan = f"target ~{target_acc:.2f}% acc" if lang == "en" else f"viser ~{target_acc:.2f}% acc"
        else:
            plan = "stabilize combo + map ending" if lang == "en" else "stabiliser combo + fin de map"

        value = (
            f"**{t(lang, 'improve_now')}:** {current_pp:.0f}pp • {acc:.2f}% • {misses}miss • `{mods}`\n"
            f"**{t(lang, 'improve_estimate')}:** +{gain_pp:.0f}pp (≈ {projected_pp:.0f}pp)\n"
            f"**{t(lang, 'improve_focus')}:** {type_label(map_type, lang)} • {plan}\n"
            f"[osu!](https://osu.ppy.sh/b/{bid}) • [Akatsuki](https://akatsuki.gg/b/{bid})"
        )

        embed.add_field(
            name=f"{idx}. {name}",
            value=value,
            inline=False,
        )

    avg_pp = profile.get("avg_pp", 0)
    max_pp = profile.get("max_pp", 0)
    embed.set_footer(
        text=t(lang, "improve_footer", avg_pp=avg_pp, max_pp=max_pp)
    )
    return embed
