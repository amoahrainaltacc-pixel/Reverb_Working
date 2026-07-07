"""
Reverb Bot – Settings Cog
Per-guild prefix, DJ role management. Admin-only commands.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import embeds, store as data_store

log = logging.getLogger("reverb.settings")


class Settings(commands.Cog, name="Settings"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── .setprefix ──────────────────────────────────────────────────────────

    @commands.command(name="setprefix")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setprefix(self, ctx: commands.Context, prefix: str):
        """Change the bot prefix for this server (Admin only)."""
        if len(prefix) > 5:
            await ctx.send(embed=embeds.error("Prefix must be 5 characters or fewer."))
            return
        data_store.set_prefix(ctx.guild.id, prefix)
        # Update the bot's command_prefix dynamically
        embed = embeds.success(
            f"Server prefix changed to `{prefix}`.\n"
            f"Commands will now use `{prefix}help`, `{prefix}play`, etc.",
            "Prefix Updated ⚙️",
        )
        await ctx.send(embed=embed)
        log.info("Guild %s prefix changed to %r", ctx.guild.name, prefix)

    @setprefix.error
    async def setprefix_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=embeds.error("You need **Manage Server** to change the prefix."))
        elif isinstance(error, commands.MissingRequiredArgument):
            prefix = data_store.get_prefix(ctx.guild.id)
            await ctx.send(embed=embeds.error(f"Usage: `{prefix}setprefix <new_prefix>`"))

    # ── .setdj ──────────────────────────────────────────────────────────────

    @commands.command(name="setdj")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setdj(self, ctx: commands.Context, role: discord.Role):
        """Set the DJ role for this server (Admin only)."""
        data_store.set_dj_role(ctx.guild.id, role.id)
        await ctx.send(embed=embeds.success(
            f"DJ role set to {role.mention}.\n"
            f"Only members with this role (or Manage Server) can control music.",
            "DJ Role Set 🎧",
        ))

    @setdj.error
    async def setdj_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=embeds.error("You need **Manage Server** to set the DJ role."))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=embeds.error("Role not found. Mention a role or use its name."))
        elif isinstance(error, commands.MissingRequiredArgument):
            prefix = data_store.get_prefix(ctx.guild.id)
            await ctx.send(embed=embeds.error(f"Usage: `{prefix}setdj @Role`"))

    # ── .removedj ───────────────────────────────────────────────────────────

    @commands.command(name="removedj")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def removedj(self, ctx: commands.Context):
        """Remove the DJ role restriction (everyone can use music)."""
        data_store.set_dj_role(ctx.guild.id, None)
        await ctx.send(embed=embeds.success(
            "DJ role removed. Everyone can now use music commands.",
            "DJ Role Removed",
        ))

    # ── .djrole ─────────────────────────────────────────────────────────────

    @commands.command(name="djrole")
    @commands.guild_only()
    async def djrole(self, ctx: commands.Context):
        """Show the current DJ role."""
        dj_id = data_store.get_dj_role(ctx.guild.id)
        if not dj_id:
            await ctx.send(embed=embeds.info(
                "No DJ role is set. Everyone can use music commands.", "DJ Role"
            ))
            return
        role = ctx.guild.get_role(dj_id)
        if role:
            await ctx.send(embed=embeds.info(
                f"Current DJ role: {role.mention}", "DJ Role 🎧"
            ))
        else:
            data_store.set_dj_role(ctx.guild.id, None)
            await ctx.send(embed=embeds.warning(
                "The previously set DJ role no longer exists. Cleared.", "DJ Role"
            ))

    # ── .settings ───────────────────────────────────────────────────────────

    @commands.command(name="settings", aliases=["config"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def settings_cmd(self, ctx: commands.Context):
        """Show current server settings."""
        prefix = data_store.get_prefix(ctx.guild.id)
        dj_id  = data_store.get_dj_role(ctx.guild.id)
        dj_str = ctx.guild.get_role(dj_id).mention if dj_id and ctx.guild.get_role(dj_id) else "None (open to all)"

        embed = discord.Embed(title="⚙️  Server Settings", color=config.BRAND_COLOR)
        embed.add_field(name="📌  Prefix",  value=f"`{prefix}`", inline=True)
        embed.add_field(name="🎧  DJ Role", value=dj_str,        inline=True)
        embed.set_footer(text=f"Reverb  •  {ctx.guild.name}")
        await ctx.send(embed=embed)
