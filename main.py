from typing import Any
import logging
import discord
from discord import app_commands
from config import DISCORD_TOKEN
from bot.client import create_bot, command_recommend, command_profil, command_improve
from bot.commands import (
    command_map,
    command_recent,
    command_top,
    command_topline,
    command_refresh_cache,
    command_clear,
    command_set_language,
)


bot = create_bot()


@bot.tree.command(name="recommend", description="Recommandations de maps RX pour Charlouuw")
@app_commands.describe(
    mods="Filtrer par mods spécifiques (optionnel)",
    min_pp="PP minimum (optionnel, défaut: profil)",
    max_pp="PP maximum (optionnel, défaut: profil)",
    min_time="Durée minimum en secondes (optionnel)",
    max_time="Durée maximum en secondes (optionnel)",
    map_type="Filtrer par type de map (optionnel)",
)
@app_commands.choices(mods=[
    app_commands.Choice(name="Tous les mods", value="all"),
    app_commands.Choice(name="NM (No Mod)", value="NM"),
    app_commands.Choice(name="HD (Hidden)", value="HD"),
    app_commands.Choice(name="HR (Hard Rock)", value="HR"),
    app_commands.Choice(name="DT (Double Time)", value="DT"),
    app_commands.Choice(name="HDDT", value="HDDT"),
    app_commands.Choice(name="HDHR", value="HDHR"),
    app_commands.Choice(name="DTHR", value="DTHR"),
], map_type=[
    app_commands.Choice(name="Tous les types", value="all"),
    app_commands.Choice(name="Jump", value="jump"),
    app_commands.Choice(name="Stream", value="stream"),
    app_commands.Choice(name="Speed", value="speed"),
    app_commands.Choice(name="Other", value="other"),
])
async def recommend(
    interaction: discord.Interaction,
    mods: app_commands.Choice[str] | None = None,
    min_pp: int | None = None,
    max_pp: int | None = None,
    min_time: int | None = None,
    max_time: int | None = None,
    map_type: app_commands.Choice[str] | None = None,
) -> None:
    await command_recommend(interaction, mods, min_pp, max_pp, min_time, max_time, map_type)


@bot.tree.command(name="profil", description="Stats RX complètes de Charlouuw sur Akatsuki")
async def profil(interaction: discord.Interaction) -> None:
    await command_profil(interaction)


@bot.tree.command(name="improve", description="Trouve les plays les plus faciles à améliorer")
@app_commands.describe(limit="Nombre de plays à proposer (1-10, défaut: 5)")
async def improve(interaction: discord.Interaction, limit: int = 5) -> None:
    await command_improve(interaction, limit)


@bot.tree.command(name="map", description="Liens vers une beatmap osu!")
@app_commands.describe(beatmap_id="L'ID de la beatmap (ex: 129891)")
async def map_info(interaction: discord.Interaction, beatmap_id: int) -> None:
    await command_map(interaction, beatmap_id)


@bot.tree.command(name="recent", description="Scores récents de Charlouuw sur Akatsuki RX")
@app_commands.describe(limit="Nombre de scores à afficher (défaut: 5)")
async def recent(interaction: discord.Interaction, limit: int = 5) -> None:
    await command_recent(interaction, limit)


@bot.tree.command(name="top", description="Top plays RX de Charlouuw")
@app_commands.describe(limit="Nombre de scores à afficher (défaut: 5)")
async def top(interaction: discord.Interaction, limit: int = 5) -> None:
    await command_top(interaction, limit)


@bot.tree.command(name="topline", description="Suivi Top 1/5/10/20/50/100 (PP + ACC) dans le temps")
async def topline(interaction: discord.Interaction) -> None:
    await command_topline(interaction)


@bot.tree.command(name="refresh_cache", description="Force la mise à jour du cache des maps jouées")
async def refresh_cache(interaction: discord.Interaction) -> None:
    await command_refresh_cache(interaction)


@bot.tree.command(name="clear", description="Supprime les messages récents du bot")
@app_commands.describe(limit="Nombre de messages à supprimer (1-50, défaut: 1)")
async def clear(interaction: discord.Interaction, limit: int = 1) -> None:
    await command_clear(interaction, limit)


@bot.tree.command(name="lang", description="Changer la langue du bot / Change bot language")
@app_commands.describe(language="fr ou en")
@app_commands.choices(language=[
    app_commands.Choice(name="Francais", value="fr"),
    app_commands.Choice(name="English", value="en"),
])
async def lang(interaction: discord.Interaction, language: app_commands.Choice[str]) -> None:
    await command_set_language(interaction, language.value)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    original = getattr(error, "original", error)
    if isinstance(original, discord.NotFound) and original.code == 10062:
        logging.warning("Interaction expired before response — user may need to retry.")
        return
    logging.error("Unhandled command error: %s", error, exc_info=error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send("Une erreur est survenue.", ephemeral=True)
        else:
            await interaction.response.send_message("Une erreur est survenue.", ephemeral=True)
    except discord.NotFound:
        pass


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("DISCORD_TOKEN manquant dans .env !")
    else:
        bot.run(DISCORD_TOKEN)
