"""
Reverb Bot – Utility Cog
Help (interactive dropdown), ping, stats, uptime, invite, support, botinfo.
Also houses the global error handler.
"""
from __future__ import annotations

import datetime
import logging
import platform
import time

import discord
from discord import app_commands
from discord.ext import commands

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import embeds, store as data_store
from utils.buttons import HelpView

log = logging.getLogger("reverb.utility")

_START_TIME = time.monotonic()


def _uptime_str() -> str:
    secs = int(time.monotonic() - _START_TIME)
    d, r  = divmod(secs, 86400)
    h, r  = divmod(r, 3600)
    m, s  = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


class Utility(commands.Cog, name="Utility"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── .help ───────────────────────────────────────────────────────────────

    @commands.command(name="help", aliases=["h"])
    async def help_cmd(self, ctx: commands.Context):
        """Show the interactive help menu."""
        prefix = data_store.get_prefix(ctx.guild.id) if ctx.guild else config.PREFIX
        avatar = str(ctx.bot.user.display_avatar) if ctx.bot.user else None
        embed  = embeds.help_home(prefix, avatar)
        view   = HelpView(prefix, avatar)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="help", description="Show the Reverb help menu")
    async def slash_help(self, interaction: discord.Interaction):
        prefix = data_store.get_prefix(interaction.guild_id) if interaction.guild_id else config.PREFIX
        avatar = str(self.bot.user.display_avatar) if self.bot.user else None
        embed  = embeds.help_home(prefix, avatar)
        view   = HelpView(prefix, avatar)
        await interaction.response.send_message(embed=embed, view=view)

    # ── .ping ───────────────────────────────────────────────────────────────

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        t  = time.perf_counter()
        msg = await ctx.send("Pinging…")
        rtt = (time.perf_counter() - t) * 1000
        embed = discord.Embed(title="🏓  Pong!", color=config.BRAND_COLOR)
        embed.add_field(name="📡  API Latency",  value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="💬  Message RTT",  value=f"`{round(rtt)}ms`",                     inline=True)
        embed.set_footer(text="Reverb  •  Network Status")
        await msg.edit(content=None, embed=embed)

    # ── .stats ──────────────────────────────────────────────────────────────

    @commands.command(name="stats")
    async def stats(self, ctx: commands.Context):
        """Show bot statistics."""
        from utils.player import PlayerManager
        # Try to get player manager from music cog
        music_cog = self.bot.get_cog("Music")
        active = music_cog.manager.active_count() if music_cog else 0

        guild_count = len(self.bot.guilds)
        user_count  = sum(g.member_count or 0 for g in self.bot.guilds)
        total_played = sum(
            data_store.get_total_songs_played(g.id) for g in self.bot.guilds
        )
        embed = embeds.bot_stats(
            bot=self.bot,
            guild_count=guild_count,
            user_count=user_count,
            uptime_str=_uptime_str(),
            songs_played=total_played,
            active_players=active,
            latency_ms=round(self.bot.latency * 1000),
            python_ver=platform.python_version(),
            dpy_ver=discord.__version__,
        )
        await ctx.send(embed=embed)

    # ── .uptime ─────────────────────────────────────────────────────────────

    @commands.command(name="uptime")
    async def uptime(self, ctx: commands.Context):
        """Show how long the bot has been running."""
        embed = embeds.info(f"Reverb has been online for **{_uptime_str()}**.", "Uptime ⏱")
        await ctx.send(embed=embed)

    # ── .invite ─────────────────────────────────────────────────────────────

    @commands.command(name="invite")
    async def invite(self, ctx: commands.Context):
        """Get the bot invite link."""
        app_id = self.bot.user.id if self.bot.user else 0
        perms = discord.Permissions(
            send_messages=True, embed_links=True, read_messages=True,
            connect=True, speak=True, use_voice_activation=True,
        )
        url   = discord.utils.oauth_url(str(app_id), permissions=perms)
        embed = discord.Embed(
            title="📨  Invite Reverb",
            description=f"[**Click here to invite Reverb**]({url}) to your server!",
            color=config.BRAND_COLOR,
        )
        embed.set_footer(text="Reverb  •  Premium Music Experience")
        await ctx.send(embed=embed)

    # ── .support ────────────────────────────────────────────────────────────

    @commands.command(name="support")
    async def support(self, ctx: commands.Context):
        """Get the support server link."""
        embed = discord.Embed(
            title="🆘  Reverb Support",
            description=(
                f"Need help? Join our support server!\n\n"
                f"[**Click here to join**]({config.SUPPORT_SERVER})"
            ),
            color=config.BRAND_COLOR,
        )
        embed.set_footer(text="Reverb  •  We're happy to help!")
        await ctx.send(embed=embed)

    # ── .botinfo ────────────────────────────────────────────────────────────

    @commands.command(name="botinfo", aliases=["about"])
    async def botinfo(self, ctx: commands.Context):
        """About Reverb."""
        embed = discord.Embed(
            title="🎧  About Reverb",
            description=(
                "Reverb is a **premium Discord music bot** with a modern player UI, "
                "interactive controls, playlists, favorites, lyrics, and much more — "
                "all powered by YouTube via yt-dlp and FFmpeg."
            ),
            color=config.BRAND_COLOR,
        )
        embed.add_field(name="🐍  Python",      value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="📦  discord.py",  value=f"`{discord.__version__}`",       inline=True)
        embed.add_field(name="🌐  Servers",     value=f"`{len(self.bot.guilds)}`",       inline=True)
        embed.add_field(name="📌  Prefix",      value=f"`{config.PREFIX}` / slash",     inline=True)
        embed.add_field(name="⏱  Uptime",      value=f"`{_uptime_str()}`",              inline=True)
        embed.add_field(name="📡  Latency",     value=f"`{round(self.bot.latency*1000)}ms`", inline=True)
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text="Reverb  •  Premium Music Experience  •  Made with ❤️")
        await ctx.send(embed=embed)

    # ── Global slash-command error handler ──────────────────────────────────

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            embed = embeds.warning(f"Slow down! Retry in `{error.retry_after:.1f}s`.", "Cooldown")
        elif isinstance(error, app_commands.MissingPermissions):
            embed = embeds.error(f"Missing permissions: `{', '.join(error.missing_permissions)}`")
        elif isinstance(error, app_commands.BotMissingPermissions):
            embed = embeds.error(f"I'm missing permissions: `{', '.join(error.missing_permissions)}`")
        else:
            log.error("Slash command error in %s: %s", interaction.command, error, exc_info=error)
            embed = embeds.error("An unexpected error occurred.", "Error")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass

    # ── Global prefix-command error handler ─────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            prefix = data_store.get_prefix(ctx.guild.id) if ctx.guild else config.PREFIX
            await ctx.send(embed=embeds.error(
                f"Missing argument: `{error.param.name}`.\nUse `{prefix}help` for usage info.",
                "Missing Argument",
            ))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=embeds.error(str(error), "Invalid Argument"))
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=embeds.error("This command cannot be used in DMs."))
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(embed=embeds.error(
                f"I need: `{', '.join(error.missing_permissions)}`"
            ))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=embeds.warning(
                f"Slow down! Retry in `{error.retry_after:.1f}s`.", "Cooldown ⏱"
            ))
        elif isinstance(error, commands.CheckFailure):
            pass  # handled in the check itself
        else:
            log.error("Unhandled error in %s: %s", ctx.command, error, exc_info=error)
            await ctx.send(embed=embeds.error(
                "An unexpected error occurred. Please try again.", "Internal Error"
            ))
