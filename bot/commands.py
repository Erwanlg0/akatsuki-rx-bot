import time
import aiohttp
import discord
from discord import app_commands
from typing import Any
from core.api import get_user_best, get_user_recent
from core.cache import get_user_played_map_ids, load_topline_history, append_topline_snapshot
from core.profile import compute_topline_metrics
from config import EMBED_COLOR, DEFAULT_USER
from bot.client import build_embeds
from core.utils import format_delta, format_snapshot_ts
from core.i18n import get_lang_for_interaction, set_guild_lang, t


async def command_map(
    interaction: discord.Interaction,
    beatmap_id: int,
) -> None:
    embed = discord.Embed(
        title=f"Beatmap #{beatmap_id}",
        color=EMBED_COLOR,
        description=(
            f"[Voir sur osu!](https://osu.ppy.sh/b/{beatmap_id})  •  "
            f"[Voir sur Akatsuki](https://akatsuki.gg/b/{beatmap_id})"
        )
    )

    await interaction.response.send_message(embed=embed)


async def command_recent(
    interaction: discord.Interaction,
    limit: int = 5,
) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        return

    if limit < 1:
        await interaction.followup.send(t(lang, "invalid_limit_ge_1"))
        return

    async with aiohttp.ClientSession() as session:
        scores = await get_user_recent(session, limit)

        if not scores:
            await interaction.followup.send(t(lang, "recent_none"))
            return

        embeds = build_embeds(
            scores,
            t(lang, "recent_title", user=DEFAULT_USER),
            t(lang, "recent_desc")
        )

        assert interaction.channel is not None, "Channel must not be None"

        max_embeds = min(len(embeds), 10)

        for i in range(max_embeds):
            await interaction.channel.send(embed=embeds[i])

        await interaction.followup.send(
            t(lang, "recent_shown", count=len(scores)),
            ephemeral=True
        )


async def command_top(
    interaction: discord.Interaction,
    limit: int = 5,
) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        return

    if limit < 1:
        await interaction.followup.send(t(lang, "invalid_limit_ge_1"))
        return

    async with aiohttp.ClientSession() as session:
        scores = await get_user_best(session, limit)

        if not scores:
            await interaction.followup.send(t(lang, "top_none"))
            return

        embeds = build_embeds(
            scores,
            t(lang, "top_title", user=DEFAULT_USER),
            t(lang, "top_desc", count=len(scores))
        )

        assert interaction.channel is not None, "Channel must not be None"

        max_embeds = min(len(embeds), 10)

        for i in range(max_embeds):
            await interaction.channel.send(embed=embeds[i])

        await interaction.followup.send(
            t(lang, "top_shown", count=len(scores)),
            ephemeral=True
        )


async def command_topline(interaction: discord.Interaction) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        return

    async with aiohttp.ClientSession() as session:
        scores = await get_user_best(session, limit=100)

    if not scores:
        await interaction.followup.send(t(lang, "top_none"))
        return

    metrics = compute_topline_metrics(scores)
    previous, current = append_topline_snapshot(metrics)

    embed = create_topline_embed(previous, current, lang)

    await interaction.followup.send(embed=embed)


def create_topline_embed(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    lang: str,
) -> discord.Embed:
    assert isinstance(current, dict), "Current must be dictionary"

    embed = discord.Embed(
        title=t(lang, "topline_title", user=DEFAULT_USER),
        description=t(lang, "topline_desc"),
        color=EMBED_COLOR,
    )

    buckets = [1, 5, 10, 20, 50, 100]
    max_buckets = min(len(buckets), 10)

    for i in range(max_buckets):
        n = buckets[i]
        k = str(n)
        curr = current["metrics"].get(k, {})
        curr_pp = curr.get("rank_pp", curr.get("avg_pp", 0.0))
        curr_acc = curr.get("rank_acc", curr.get("avg_acc", 0.0))

        line = f"{curr_pp:.2f}pp • {curr_acc * 100:.2f}%"

        if previous:
            prev = previous.get("metrics", {}).get(k, {})
            prev_pp = prev.get("rank_pp", prev.get("avg_pp", curr_pp))
            prev_acc = prev.get("rank_acc", prev.get("avg_acc", curr_acc))
            line += (
                f"\nΔ {format_delta(curr_pp, prev_pp, 'pp')}"
                f" • {format_delta(curr_acc * 100, prev_acc * 100, '%')}"
            )

        embed.add_field(name=f"Top {n}", value=line, inline=True)

    add_topline_total_field(embed, previous, current, lang)
    add_topline_history_field(embed, lang)

    return embed


def add_topline_total_field(
    embed: discord.Embed,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    lang: str,
) -> None:
    assert isinstance(embed, discord.Embed), "Embed must be Embed"
    assert isinstance(current, dict), "Current must be dictionary"

    current_total_raw = current.get("metrics", {}).get("top100_total_pp", 0.0)
    current_total_weighted = current.get("metrics", {}).get("top100_total_pp_weighted_estimate", 0.0)
    current_weighted_base = current.get("metrics", {}).get("top100_weighted_pp", 0.0)
    current_bonus_est = current.get("metrics", {}).get("top100_bonus_pp_estimate", 0.0)
    current_avg_acc = current.get("metrics", {}).get("top100_avg_acc", 0.0)

    total_line = (
        f"Weighted (est.): {current_total_weighted:.2f}pp"
        f" = {current_weighted_base:.2f} + bonus~{current_bonus_est:.2f}\n"
        f"Raw top100 sum: {current_total_raw:.2f}pp\n"
        f"Avg acc: {current_avg_acc * 100:.2f}%"
    )

    if previous:
        prev_total = previous.get("metrics", {}).get("top100_total_pp_weighted_estimate", 0.0)
        prev_avg_acc = previous.get("metrics", {}).get("top100_avg_acc", current_avg_acc)
        total_line += (
            f"\nΔ weighted {format_delta(current_total_weighted, prev_total, 'pp')}"
            f" • {format_delta(current_avg_acc * 100, prev_avg_acc * 100, '%')}"
        )

    embed.add_field(name=t(lang, "topline_total_name"), value=total_line, inline=False)


def add_topline_history_field(embed: discord.Embed, lang: str) -> None:
    assert isinstance(embed, discord.Embed), "Embed must be Embed"

    history = load_topline_history().get("snapshots", [])
    recent = history[-8:]

    if len(recent) >= 2:
        history_lines: list[str] = []
        max_recent = min(len(recent), 8)

        for i in range(1, max_recent):
            prev_snap = recent[i - 1]
            curr_snap = recent[i]
            prev_total = prev_snap.get("metrics", {}).get("top100_total_pp", 0.0)
            curr_total = curr_snap.get("metrics", {}).get("top100_total_pp", 0.0)

            ts = curr_snap.get("ts", 0)
            ts_str = format_snapshot_ts(ts)
            delta_str = format_delta(curr_total, prev_total, 'pp')

            history_lines.append(
                f"{ts_str} : {curr_total:.2f}pp ({delta_str})"
            )

        recent_history = history_lines[-6:]

        embed.add_field(
            name=t(lang, "topline_history_name"),
            value="\n".join(recent_history),
            inline=False,
        )
    else:
        embed.add_field(
            name=t(lang, "topline_history_name"),
            value=t(lang, "topline_history_empty"),
            inline=False,
        )

    ts = history[-1].get("ts", int(time.time())) if history else int(time.time())
    embed.set_footer(
        text=t(
            lang,
            "topline_footer",
            count=len(history),
            last=time.strftime('%Y-%m-%d %H:%M', time.localtime(ts)),
        )
    )


async def command_refresh_cache(interaction: discord.Interaction) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True, ephemeral=True)
    except discord.NotFound:
        return

    async with aiohttp.ClientSession() as session:
        played_ids = await get_user_played_map_ids(session, use_cache=False)

    if played_ids:
        await interaction.followup.send(
            t(lang, "refresh_ok", count=f"{len(played_ids):,}"),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            t(lang, "refresh_fail"),
            ephemeral=True,
        )


async def command_clear(
    interaction: discord.Interaction,
    limit: int = 1,
) -> None:
    lang = get_lang_for_interaction(interaction)

    try:
        await interaction.response.defer(thinking=True, ephemeral=True)
    except discord.NotFound:
        return

    if limit < 1 or limit > 50:
        await interaction.followup.send(t(lang, "invalid_limit_1_50"), ephemeral=True)
        return

    assert interaction.channel is not None, "Channel must not be None"
    assert interaction.client.user is not None, "Client user must not be None"

    try:
        count = 0

        async for message in interaction.channel.history(limit=500):
            if message.author != interaction.client.user:
                continue

            try:
                await message.delete()
                count += 1
            except discord.HTTPException:
                continue

            if count >= limit:
                break

        if count > 0:
            await interaction.followup.send(
                t(lang, "clear_done", count=count),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                t(lang, "clear_none"),
                ephemeral=True,
            )
    except discord.errors.Forbidden:
        await interaction.followup.send(
            t(lang, "clear_perm"),
            ephemeral=True,
        )
    except Exception as e:
        print(f"[ERROR] Suppression error: {e}")
        await interaction.followup.send(
            t(lang, "clear_error"),
            ephemeral=True,
        )


async def command_set_language(
    interaction: discord.Interaction,
    language: str,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    selected = set_guild_lang(interaction.guild.id, language)
    await interaction.response.send_message(
        t(selected, "lang_changed"),
        ephemeral=True,
    )
