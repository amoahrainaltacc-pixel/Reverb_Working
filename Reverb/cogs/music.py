"""
Reverb Bot – Music Cog
All music commands: play, pause, resume, skip, stop, queue, np, volume,
loop, shuffle, leave, lyrics, search, recent, playlist, favorite.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import embeds, store as data_store
from utils.player import GuildPlayer, PlayerManager, YTDLSource
from utils.buttons import PlayerView, QueuePagesView, SearchView

log = logging.getLogger("reverb.music")

_IDLE = discord.Activity(type=discord.ActivityType.listening, name=f"music | {config.PREFIX}help")


# ─── DJ / Permission guard ─────────────────────────────────────────────────

def _has_dj(member: discord.Member) -> bool:
    """True if member has DJ role, Manage Guild, or no DJ role is set."""
    if member.guild_permissions.manage_guild:
        return True
    dj_id = data_store.get_dj_role(member.guild.id)
    if not dj_id:
        return True  # no DJ role set → everyone can use music
    return any(r.id == dj_id for r in member.roles)


def dj_required():
    async def predicate(ctx: commands.Context) -> bool:
        if not _has_dj(ctx.author):
            await ctx.send(
                embed=embeds.error(
                    "You need the **DJ role** or **Manage Server** permission to use this command.",
                    "DJ Required",
                )
            )
            return False
        return True
    return commands.check(predicate)


# ─── Music Cog ─────────────────────────────────────────────────────────────

class Music(commands.Cog, name="Music"):

    def __init__(self, bot: commands.Bot, manager: PlayerManager):
        self.bot     = bot
        self.manager = manager
        self._check_empty_vc.start()

    def cog_unload(self):
        self._check_empty_vc.cancel()

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _ensure_voice(self, ctx: commands.Context) -> Optional[discord.VoiceClient]:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=embeds.error("You must be in a voice channel first."))
            return None
        vc: discord.VoiceClient = ctx.guild.voice_client  # type: ignore
        if vc and vc.channel != ctx.author.voice.channel:
            await ctx.send(embed=embeds.error("I'm already playing in a different voice channel."))
            return None
        if not vc:
            try:
                vc = await ctx.author.voice.channel.connect()
            except Exception as exc:
                log.error("VC connect error: %s", exc)
                await ctx.send(embed=embeds.error("Could not connect to your voice channel."))
                return None
        return vc

    async def _reset_status(self):
        try:
            await self.bot.change_presence(activity=_IDLE)
        except Exception:
            pass

    # ── .play ───────────────────────────────────────────────────────────────

    @commands.command(name="play", aliases=["p"])
    @commands.guild_only()
    @dj_required()
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song or playlist from YouTube."""
        vc = await self._ensure_voice(ctx)
        if not vc:
            return

        player = self.manager.get(ctx.guild)
        player.text_channel = ctx.channel  # type: ignore
        player.bot_ref = self.bot
        player._cancel_auto_disconnect()

        async with ctx.typing():
            try:
                tracks = await YTDLSource.search_entries(query, loop=self.bot.loop, limit=1)
            except Exception as exc:
                log.error("Search error: %s", exc)
                await ctx.send(embed=embeds.error(f"Could not find anything for: `{query}`"))
                return

        if not tracks:
            await ctx.send(embed=embeds.error("No results found."))
            return

        requestor = ctx.author.display_name

        if len(tracks) > 1:
            added = 0
            for t in tracks:
                t["requestor"] = requestor
                try:
                    await player.add(t)
                    added += 1
                except OverflowError:
                    break
            await ctx.send(embed=embeds.playlist_added(tracks[0].get("title", "Playlist"), added, requestor))
        else:
            track = tracks[0]
            track["requestor"] = requestor
            try:
                pos = await player.add(track)
            except OverflowError:
                await ctx.send(embed=embeds.error("The queue is full! (max 100 tracks)"))
                return
            if vc.is_playing() or vc.is_paused():
                await ctx.send(embed=embeds.track_added(track, pos))

        await player.start()

    @app_commands.command(name="play", description="Play a song or playlist from YouTube")
    @app_commands.guild_only()
    async def slash_play(self, interaction: discord.Interaction, query: str):
        ctx = await commands.Context.from_interaction(interaction)
        await self.play(ctx, query=query)

    # ── .search ─────────────────────────────────────────────────────────────

    @commands.command(name="search")
    @commands.guild_only()
    @dj_required()
    async def search(self, ctx: commands.Context, *, query: str):
        """Search YouTube and pick a track to play."""
        vc = await self._ensure_voice(ctx)
        if not vc:
            return

        async with ctx.typing():
            try:
                results = await YTDLSource.search_entries(query, loop=self.bot.loop, limit=8)
            except Exception:
                await ctx.send(embed=embeds.error("Search failed. Try again."))
                return

        if not results:
            await ctx.send(embed=embeds.error("No results found."))
            return

        player = self.manager.get(ctx.guild)
        player.text_channel = ctx.channel  # type: ignore
        player.bot_ref = self.bot

        embed = embeds.search_results(results, query)
        view  = SearchView(results, player, ctx.author.display_name)
        await ctx.send(embed=embed, view=view)

        # Start the player loop if not running
        await player.start()

    # ── .pause ──────────────────────────────────────────────────────────────

    @commands.command(name="pause")
    @commands.guild_only()
    @dj_required()
    async def pause(self, ctx: commands.Context):
        """Pause the current song."""
        player = self.manager.get_existing(ctx.guild)
        if not player or not player.pause():
            await ctx.send(embed=embeds.warning("Nothing is currently playing.", "Warning"))
            return
        await ctx.send(embed=embeds.success(f"Paused. Use `{config.PREFIX}resume` to continue.", "Paused ⏸"))

    # ── .resume ─────────────────────────────────────────────────────────────

    @commands.command(name="resume", aliases=["r"])
    @commands.guild_only()
    @dj_required()
    async def resume(self, ctx: commands.Context):
        """Resume a paused song."""
        player = self.manager.get_existing(ctx.guild)
        if not player or not player.resume():
            await ctx.send(embed=embeds.warning("Nothing is paused.", "Warning"))
            return
        await ctx.send(embed=embeds.success("Resumed playback!", "Resumed ▶️"))

    # ── .skip ───────────────────────────────────────────────────────────────

    @commands.command(name="skip", aliases=["s"])
    @commands.guild_only()
    @dj_required()
    async def skip(self, ctx: commands.Context):
        """Skip the current song."""
        player = self.manager.get_existing(ctx.guild)
        if not player or not ctx.guild.voice_client:
            await ctx.send(embed=embeds.warning("Nothing is playing.", "Warning"))
            return
        title = player.current_meta.get("title", "the current track") if player.current_meta else "the current track"
        player.skip()
        await ctx.send(embed=embeds.success(f"Skipped **{title}**.", "Skipped ⏭"))

    # ── .stop ───────────────────────────────────────────────────────────────

    @commands.command(name="stop")
    @commands.guild_only()
    @dj_required()
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        player = self.manager.get_existing(ctx.guild)
        if player:
            player.stop()
        vc = ctx.guild.voice_client
        if vc:
            await vc.disconnect()
        self.manager.remove(ctx.guild)
        await self._reset_status()
        await ctx.send(embed=embeds.success("Stopped and cleared the queue. Goodbye! 👋", "Stopped ⏹"))

    # ── .queue ──────────────────────────────────────────────────────────────

    @commands.command(name="queue", aliases=["q"])
    @commands.guild_only()
    async def queue(self, ctx: commands.Context, page: int = 1):
        """Show the music queue with page navigation."""
        player  = self.manager.get_existing(ctx.guild)
        tracks  = player.queue_list if player else []
        current = player.current_meta if player else None
        embed   = embeds.queue_list(tracks, page=page, current=current)
        view    = QueuePagesView(tracks, current) if len(tracks) > 10 else None
        await ctx.send(embed=embed, view=view)

    # ── .nowplaying ─────────────────────────────────────────────────────────

    @commands.command(name="nowplaying", aliases=["np"])
    @commands.guild_only()
    async def nowplaying(self, ctx: commands.Context):
        """Show the current song player with controls."""
        player = self.manager.get_existing(ctx.guild)
        if not player or not player.current_meta:
            await ctx.send(embed=embeds.warning("Nothing is currently playing.", "Nothing Playing"))
            return
        pos     = player.current.position if player.current else 0.0
        vc      = ctx.guild.voice_client
        vc_name = vc.channel.name if vc else ""
        embed = embeds.now_playing(
            player.current_meta,
            position=pos,
            volume=player.volume,
            looping=player.looping,
            queue_size=player.queue_size(),
            vc_name=vc_name,
        )
        view = PlayerView(player)
        await ctx.send(embed=embed, view=view)

    # ── .volume ─────────────────────────────────────────────────────────────

    @commands.command(name="volume", aliases=["vol"])
    @commands.guild_only()
    @dj_required()
    async def volume(self, ctx: commands.Context, vol: int):
        """Set playback volume (0–100)."""
        if not 0 <= vol <= 100:
            await ctx.send(embed=embeds.error("Volume must be between **0** and **100**."))
            return
        player = self.manager.get_existing(ctx.guild)
        if not player:
            await ctx.send(embed=embeds.warning("Nothing is playing.", "Warning"))
            return
        player.set_volume(vol)
        filled = round(vol / 10)
        bar = "█" * filled + "░" * (10 - filled)
        await ctx.send(embed=embeds.success(f"Volume set to **{vol}%**\n`{bar}`", "Volume 🔊"))

    # ── .loop ───────────────────────────────────────────────────────────────

    @commands.command(name="loop", aliases=["l"])
    @commands.guild_only()
    @dj_required()
    async def loop(self, ctx: commands.Context):
        """Toggle song looping."""
        player = self.manager.get_existing(ctx.guild)
        if not player:
            await ctx.send(embed=embeds.warning("Nothing is playing.", "Warning"))
            return
        player.looping = not player.looping
        state = "enabled 🔁" if player.looping else "disabled"
        await ctx.send(embed=embeds.success(f"Loop mode **{state}**.", "Loop 🔁"))

    # ── .shuffle ────────────────────────────────────────────────────────────

    @commands.command(name="shuffle")
    @commands.guild_only()
    @dj_required()
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue."""
        player = self.manager.get_existing(ctx.guild)
        if not player or player.queue_size() < 2:
            await ctx.send(embed=embeds.warning("Need at least 2 tracks in queue to shuffle.", "Warning"))
            return
        player.shuffle()
        await ctx.send(embed=embeds.success(f"Shuffled **{player.queue_size()}** tracks! 🔀", "Shuffled"))

    # ── .leave ──────────────────────────────────────────────────────────────

    @commands.command(name="leave", aliases=["dc", "disconnect"])
    @commands.guild_only()
    @dj_required()
    async def leave(self, ctx: commands.Context):
        """Disconnect Reverb from the voice channel."""
        vc = ctx.guild.voice_client
        if not vc:
            await ctx.send(embed=embeds.warning("I'm not in a voice channel.", "Warning"))
            return
        player = self.manager.get_existing(ctx.guild)
        if player:
            player.stop()
        await vc.disconnect()
        self.manager.remove(ctx.guild)
        await self._reset_status()
        await ctx.send(embed=embeds.success("Disconnected. See you next time! 👋", "Left"))

    # ── .lyrics ─────────────────────────────────────────────────────────────

    @commands.command(name="lyrics")
    @commands.guild_only()
    async def lyrics(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Show lyrics for a song."""
        if not query:
            player = self.manager.get_existing(ctx.guild)
            if not player or not player.current_meta:
                await ctx.send(embed=embeds.error("No song is playing and no query provided. Use `.lyrics <song name>`."))
                return
            query = player.current_meta.get("title", "")

        async with ctx.typing():
            # Parse "artist - title" format or use query as title
            parts = query.split(" - ", 1)
            if len(parts) == 2:
                artist, title_q = parts[0].strip(), parts[1].strip()
            else:
                artist, title_q = "Unknown", query.strip()

            url = f"https://api.lyrics.ovh/v1/{artist}/{title_q}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            js = await resp.json()
                            lyrics_text = js.get("lyrics", "")
                        else:
                            lyrics_text = ""
            except Exception:
                lyrics_text = ""

        if not lyrics_text:
            await ctx.send(embed=embeds.warning(
                f"Could not find lyrics for **{query}**.\n"
                f"Try using the format: `.lyrics Artist - Song Title`",
                "Lyrics Not Found",
            ))
            return

        # Paginate if too long
        max_len = 4000
        chunks = [lyrics_text[i:i+max_len] for i in range(0, len(lyrics_text), max_len)]
        for i, chunk in enumerate(chunks[:3]):  # max 3 messages
            embed = discord.Embed(
                title=f"🎤  Lyrics — {query}" if i == 0 else f"🎤  Lyrics (continued)",
                description=chunk,
                color=config.BRAND_COLOR,
            )
            embed.set_footer(text=f"Reverb  •  Lyrics  •  Page {i+1}/{min(len(chunks), 3)}")
            await ctx.send(embed=embed)

    # ── .recent ─────────────────────────────────────────────────────────────

    @commands.command(name="recent", aliases=["rp"])
    @commands.guild_only()
    async def recent(self, ctx: commands.Context):
        """Show recently played tracks."""
        tracks = data_store.get_recently_played(ctx.guild.id)
        await ctx.send(embed=embeds.recently_played(tracks))

    # ── .playlist ───────────────────────────────────────────────────────────

    @commands.group(name="playlist", aliases=["pl"], invoke_without_command=True)
    @commands.guild_only()
    async def playlist(self, ctx: commands.Context):
        """Manage your playlists. Subcommands: list, save, load, delete."""
        playlists = data_store.get_playlists(ctx.author.id, ctx.guild.id)
        await ctx.send(embed=embeds.playlist_list(playlists, ctx.author.display_name))

    @playlist.command(name="list")
    @commands.guild_only()
    async def playlist_list_cmd(self, ctx: commands.Context):
        playlists = data_store.get_playlists(ctx.author.id, ctx.guild.id)
        await ctx.send(embed=embeds.playlist_list(playlists, ctx.author.display_name))

    @playlist.command(name="save")
    @commands.guild_only()
    async def playlist_save(self, ctx: commands.Context, *, name: str):
        """Save the current queue as a playlist."""
        player = self.manager.get_existing(ctx.guild)
        tracks = list(player.queue_list) if player else []
        if player and player.current_meta:
            tracks = [player.current_meta] + tracks
        if not tracks:
            await ctx.send(embed=embeds.warning("Nothing in queue to save.", "Warning"))
            return
        data_store.save_playlist(ctx.author.id, ctx.guild.id, name, tracks)
        await ctx.send(embed=embeds.success(f"Saved **{len(tracks)}** tracks as playlist **{name}**.", "Playlist Saved"))

    @playlist.command(name="load")
    @commands.guild_only()
    @dj_required()
    async def playlist_load(self, ctx: commands.Context, *, name: str):
        """Load a playlist into the queue."""
        vc = await self._ensure_voice(ctx)
        if not vc:
            return
        playlists = data_store.get_playlists(ctx.author.id, ctx.guild.id)
        if name not in playlists:
            await ctx.send(embed=embeds.error(f"Playlist **{name}** not found."))
            return
        tracks = playlists[name]
        player = self.manager.get(ctx.guild)
        player.text_channel = ctx.channel  # type: ignore
        player.bot_ref = self.bot
        added = 0
        for t in tracks:
            t["requestor"] = ctx.author.display_name
            try:
                await player.add(t)
                added += 1
            except OverflowError:
                break
        await ctx.send(embed=embeds.success(f"Loaded **{added}** tracks from playlist **{name}**.", "Playlist Loaded"))
        await player.start()

    @playlist.command(name="delete")
    @commands.guild_only()
    async def playlist_delete(self, ctx: commands.Context, *, name: str):
        """Delete one of your playlists."""
        ok = data_store.delete_playlist(ctx.author.id, ctx.guild.id, name)
        if ok:
            await ctx.send(embed=embeds.success(f"Deleted playlist **{name}**.", "Deleted"))
        else:
            await ctx.send(embed=embeds.error(f"Playlist **{name}** not found."))

    # ── .favorite ───────────────────────────────────────────────────────────

    @commands.group(name="favorite", aliases=["fav"], invoke_without_command=True)
    @commands.guild_only()
    async def favorite(self, ctx: commands.Context):
        """Manage your favorites. Subcommands: list, add, remove."""
        tracks = data_store.get_favorites(ctx.author.id, ctx.guild.id)
        await ctx.send(embed=embeds.favorites_list(tracks, ctx.author.display_name))

    @favorite.command(name="list")
    @commands.guild_only()
    async def fav_list(self, ctx: commands.Context):
        tracks = data_store.get_favorites(ctx.author.id, ctx.guild.id)
        await ctx.send(embed=embeds.favorites_list(tracks, ctx.author.display_name))

    @favorite.command(name="add")
    @commands.guild_only()
    async def fav_add(self, ctx: commands.Context):
        """Add the currently playing song to your favorites."""
        player = self.manager.get_existing(ctx.guild)
        if not player or not player.current_meta:
            await ctx.send(embed=embeds.warning("Nothing is playing.", "Warning"))
            return
        added = data_store.add_favorite(ctx.author.id, ctx.guild.id, player.current_meta)
        if added:
            await ctx.send(embed=embeds.success(
                f"Added **{player.current_meta.get('title')}** to favorites! ❤️", "Favorited"
            ))
        else:
            await ctx.send(embed=embeds.warning("This track is already in your favorites.", "Already Saved"))

    @favorite.command(name="remove")
    @commands.guild_only()
    async def fav_remove(self, ctx: commands.Context, *, query: str):
        """Remove a song from favorites by name or number."""
        favs = data_store.get_favorites(ctx.author.id, ctx.guild.id)
        # Try to find by index
        try:
            idx = int(query) - 1
            if 0 <= idx < len(favs):
                url = favs[idx]["url"]
                data_store.remove_favorite(ctx.author.id, ctx.guild.id, url)
                await ctx.send(embed=embeds.success(f"Removed **{favs[idx]['title']}** from favorites.", "Removed"))
                return
        except ValueError:
            pass
        # Find by title
        match = next((f for f in favs if query.lower() in f.get("title", "").lower()), None)
        if match:
            data_store.remove_favorite(ctx.author.id, ctx.guild.id, match["url"])
            await ctx.send(embed=embeds.success(f"Removed **{match['title']}** from favorites.", "Removed"))
        else:
            await ctx.send(embed=embeds.error(f"Could not find **{query}** in your favorites."))

    # ── Auto-disconnect loop ────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _check_empty_vc(self):
        for guild in self.bot.guilds:
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue
            members = [m for m in vc.channel.members if not m.bot]
            if members:
                continue
            player = self.manager.get_existing(guild)
            if not player or not (vc.is_playing() or vc.is_paused()):
                if player:
                    player.stop()
                await vc.disconnect()
                self.manager.remove(guild)
                await self._reset_status()
                log.info("Auto-disconnected from %s (empty VC)", guild.name)

    @_check_empty_vc.before_loop
    async def _before_check(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        vc = member.guild.voice_client
        if not vc or not before.channel or before.channel != vc.channel:
            return
        remaining = [m for m in vc.channel.members if not m.bot]
        if not remaining:
            player = self.manager.get_existing(member.guild)
            if player:
                player.schedule_auto_disconnect()
