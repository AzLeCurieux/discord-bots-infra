"""
Discord Moderation Bot
Fonctionnalités : suppression automatique de mots bannis, commandes !ban et !kick,
endpoint HTTP /health sur le port 8080 pour le monitoring.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
GUILD_ID: int = int(os.environ["GUILD_ID"])
LOG_CHANNEL_ID: int = int(os.environ.get("LOG_CHANNEL_ID", "0"))
HEALTH_PORT: int = int(os.environ.get("HEALTH_PORT", "8080"))

BANNED_WORDS: list[str] = [
    word.strip().lower()
    for word in os.environ.get(
        "BANNED_WORDS",
        "spam,insulte,publicite,arnaque",
    ).split(",")
    if word.strip()
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("bot-moderation")

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Track bot start time for uptime calculation
_start_time: datetime = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@bot.event
async def on_ready() -> None:
    log.info("Bot connecté : %s (ID %s)", bot.user, bot.user.id)
    guild = bot.get_guild(GUILD_ID)
    if guild:
        log.info("Serveur cible : %s", guild.name)
    else:
        log.warning("Serveur avec l'ID %s introuvable.", GUILD_ID)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="les messages | !help",
        )
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    # Ignorer les messages du bot lui-même
    if message.author.bot:
        return

    # Vérifier les mots bannis
    content_lower = message.content.lower()
    for word in BANNED_WORDS:
        if word in content_lower:
            await _handle_banned_word(message, word)
            return  # On ne traite pas les commandes sur un message supprimé

    # Laisser les commandes s'exécuter normalement
    await bot.process_commands(message)


async def _handle_banned_word(message: discord.Message, word: str) -> None:
    """Supprime le message contenant un mot banni et notifie dans le salon de log."""
    try:
        await message.delete()
        log.info(
            "Message supprimé de %s dans #%s (mot banni : '%s')",
            message.author,
            message.channel,
            word,
        )

        # Avertir l'utilisateur en DM (best-effort)
        try:
            await message.author.send(
                f"⚠️ Ton message dans **{message.guild.name}** a été supprimé "
                f"car il contient un terme interdit."
            )
        except discord.Forbidden:
            pass  # DMs désactivés

        # Log dans le salon de modération
        await _send_log(
            guild=message.guild,
            embed=discord.Embed(
                title="🚫 Message supprimé",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            .add_field(name="Auteur", value=message.author.mention)
            .add_field(name="Salon", value=message.channel.mention)
            .add_field(name="Mot détecté", value=f"`{word}`")
            .add_field(
                name="Contenu (tronqué)",
                value=message.content[:200] or "*(vide)*",
                inline=False,
            ),
        )
    except discord.NotFound:
        pass  # Déjà supprimé
    except discord.Forbidden:
        log.warning("Permissions insuffisantes pour supprimer le message.")


async def _send_log(guild: discord.Guild, embed: discord.Embed) -> None:
    """Envoie un embed dans le salon de log si configuré."""
    if not LOG_CHANNEL_ID:
        return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel and isinstance(channel, discord.TextChannel):
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning("Impossible d'envoyer dans le salon de log (ID %s).", LOG_CHANNEL_ID)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_member(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "Aucune raison spécifiée",
) -> None:
    """Bannit un membre du serveur. Usage : !ban @membre [raison]"""
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ Tu ne peux pas bannir quelqu'un avec un rôle supérieur ou égal au tien.")
        return

    try:
        await member.send(
            f"🔨 Tu as été banni de **{ctx.guild.name}**.\n**Raison :** {reason}"
        )
    except discord.Forbidden:
        pass

    await member.ban(reason=f"{ctx.author} : {reason}", delete_message_days=1)

    embed = discord.Embed(
        title="🔨 Membre banni",
        color=discord.Color.dark_red(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Membre", value=f"{member} ({member.id})")
    embed.add_field(name="Modérateur", value=ctx.author.mention)
    embed.add_field(name="Raison", value=reason, inline=False)
    embed.set_footer(text=f"ID action : ban-{member.id}")

    await ctx.send(embed=embed)
    await _send_log(guild=ctx.guild, embed=embed)
    log.info("Ban : %s banni par %s. Raison : %s", member, ctx.author, reason)


@ban_member.error
async def ban_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission de bannir des membres.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable. Utilise une mention ou un ID.")
    else:
        log.error("Erreur ban : %s", error)
        await ctx.send("❌ Une erreur inattendue s'est produite.")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_member(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "Aucune raison spécifiée",
) -> None:
    """Expulse un membre du serveur. Usage : !kick @membre [raison]"""
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ Tu ne peux pas expulser quelqu'un avec un rôle supérieur ou égal au tien.")
        return

    try:
        await member.send(
            f"👢 Tu as été expulsé de **{ctx.guild.name}**.\n**Raison :** {reason}"
        )
    except discord.Forbidden:
        pass

    await member.kick(reason=f"{ctx.author} : {reason}")

    embed = discord.Embed(
        title="👢 Membre expulsé",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Membre", value=f"{member} ({member.id})")
    embed.add_field(name="Modérateur", value=ctx.author.mention)
    embed.add_field(name="Raison", value=reason, inline=False)
    embed.set_footer(text=f"ID action : kick-{member.id}")

    await ctx.send(embed=embed)
    await _send_log(guild=ctx.guild, embed=embed)
    log.info("Kick : %s expulsé par %s. Raison : %s", member, ctx.author, reason)


@kick_member.error
async def kick_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission d'expulser des membres.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable. Utilise une mention ou un ID.")
    else:
        log.error("Erreur kick : %s", error)
        await ctx.send("❌ Une erreur inattendue s'est produite.")


@bot.command(name="minfo")
@commands.has_permissions(moderate_members=True)
async def member_info(ctx: commands.Context, member: discord.Member | None = None) -> None:
    """Affiche les informations d'un membre. Usage : !minfo [@membre]"""
    target = member or ctx.author
    embed = discord.Embed(
        title=f"ℹ️ Informations — {target}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=target.id)
    embed.add_field(name="Rejoint le serveur", value=discord.utils.format_dt(target.joined_at, "R"))
    embed.add_field(name="Compte créé", value=discord.utils.format_dt(target.created_at, "R"))
    roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]
    embed.add_field(
        name=f"Rôles ({len(roles)})",
        value=", ".join(roles[:10]) or "Aucun",
        inline=False,
    )
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# Health HTTP endpoint
# ---------------------------------------------------------------------------


async def health_handler(request: web.Request) -> web.Response:
    """Endpoint /health — retourne l'état du bot au format JSON."""
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _start_time).total_seconds()
    guild = bot.get_guild(GUILD_ID)

    payload = {
        "status": "ok",
        "bot": str(bot.user) if bot.user else "disconnected",
        "latency_ms": round(bot.latency * 1000, 2),
        "uptime_seconds": round(uptime_seconds, 0),
        "guild": guild.name if guild else None,
        "guild_member_count": guild.member_count if guild else None,
        "timestamp": now.isoformat(),
    }

    status_code = 200 if bot.is_ready() else 503
    return web.json_response(payload, status=status_code)


async def start_health_server() -> None:
    """Lance le serveur HTTP de health check en arrière-plan."""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)  # Alias racine pour la sonde Docker

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    log.info("Serveur health démarré sur http://0.0.0.0:%s/health", HEALTH_PORT)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    async with bot:
        await start_health_server()
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
