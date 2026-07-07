"""
Reverb Bot – Music Player & Queue Manager
"""
from __future__ import annotations

import asyncio
import copy
import logging
import random
import shlex
import time
from typing import Optional

import discord
import yt_dlp

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import store as data_store

log = logging.getLogger("reverb.player")


# ─── YTDLSource ────────────────────────────────────────────────────────────

class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume=volume)
        self.data      = data
        self.title:    str           = data.get("title", "Unknown")
        self.url:      str           = data.get("webpage_url", data.get("url", ""))
        self.thumbnail: Optional[str]= data.get("thumbnail")
        self.duration: float         = float(data.get("duration") or 0)
        self.uploader: str           = data.get("uploader") or data.get("channel", "Unknown")
        self.start_time: float       = time.time()

    @property
    def position(self) -> float:
        return time.time() - self.start_time

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        loop: asyncio.AbstractEventLoop,
        volume: float = 0.5,
        stream: bool = True,
    ) -> "YTDLSource":
        ydl_opts = copy.deepcopy(config.YTDL_FORMAT_OPTIONS)
        ydl_opts["noplaylist"]    = True
        ydl_opts["extract_flat"]  = False

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=not stream)
            )

        if "entries" in data:
            data = data["entries"][0]

        if stream:
            # Track the exact format object we're using so we can pick up
            # its headers later (format-level headers take priority over the
            # top-level info dict when formats differ in CDN requirements).
            chosen_fmt: dict = data
            if data.get("url"):
                stream_url = data["url"]
            else:
                chosen_fmt = next(
                    (f for f in data.get("requested_formats", []) if f.get("url")),
                    data,
                )
                stream_url = chosen_fmt.get("url") or data.get("webpage_url", "")
        else:
            chosen_fmt = data
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                stream_url = ydl.prepare_filename(data)

        ffmpeg_opts = copy.deepcopy(config.FFMPEG_OPTIONS)
        ffmpeg_opts["options"] = f"-vn -filter:a volume={volume}"

        # Forward yt-dlp's required HTTP headers to FFmpeg so the CDN
        # doesn't 403. yt-dlp stores the exact headers it used (User-Agent,
        # etc.) in data["http_headers"]; without them FFmpeg's bare request
        # gets rejected by YouTube's edge servers.
        # Prefer format-level headers; fall back to top-level info dict.
        http_headers: dict = chosen_fmt.get("http_headers") or data.get("http_headers") or {}
        if http_headers:
            # Sanitise each value: strip CR/LF and quote chars to prevent
            # argument-injection into FFmpeg's option string.
            def _safe(v: str) -> str:
                return str(v).replace("\r", "").replace("\n", "").replace("'", "").replace('"', "")

            header_str = "".join(
                f"{k}: {_safe(v)}\r\n" for k, v in http_headers.items()
            )
            # shlex.quote produces a safely-quoted token that discord.py's
            # shlex.split will parse back as a single -headers argument.
            ffmpeg_opts["before_options"] = (
                f"-headers {shlex.quote(header_str)} "
                + ffmpeg_opts.get("before_options", "")
            )

        return cls(discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts), data=data, volume=volume)

    @classmethod
    async def search_entries(
        cls,
        query: str,
        *,
        loop: asyncio.AbstractEventLoop,
        limit: int = 1,
    ) -> list[dict]:
        """Return track metadata dicts. limit=1 for play, limit=5+ for search."""
        ydl_opts = copy.deepcopy(config.YTDL_FORMAT_OPTIONS)
        ydl_opts["noplaylist"]   = False
        ydl_opts["extract_flat"] = True

        # Always prefix non-URL queries with ytsearch so yt-dlp uses the
        # YouTube search extractor. Without this, limit=1 queries hit the
        # generic extractor which returns nothing.
        # Clamp limit to at least 1 — callers passing 0 or negative get 1 result.
        effective_limit = max(limit, 1)
        if not query.startswith("http"):
            query = f"ytsearch{effective_limit}:{query}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = await loop.run_in_executor(
                None, lambda: ydl.extract_info(query, download=False)
            )

        if "entries" in data:
            base_url  = data.get("webpage_url", "")
            extractor = data.get("extractor_key", "")
            results   = []
            for e in (data["entries"] or []):
                if not e:
                    continue
                url = e.get("webpage_url") or e.get("url", "")
                if url and not url.startswith("http") and "youtu" in (base_url + extractor).lower():
                    url = f"https://www.youtube.com/watch?v={url}"
                results.append({
                    "title":    e.get("title", "Unknown"),
                    "url":      url,
                    "thumbnail": e.get("thumbnail"),
                    "duration": float(e.get("duration") or 0),
                    "uploader": e.get("uploader") or e.get("channel", "Unknown"),
                })
            return results[:limit] if limit > 0 else results

        return [{
            "title":    data.get("title", "Unknown"),
            "url":      data.get("webpage_url", data.get("url", "")),
            "thumbnail": data.get("thumbnail"),
            "duration": float(data.get("duration") or 0),
            "uploader": data.get("uploader") or data.get("channel", "Unknown"),
        }]


# ─── GuildPlayer ───────────────────────────────────────────────────────────

class GuildPlayer:

    def __init__(self, guild: discord.Guild, bot: discord.Client, manager: "PlayerManager"):
        self.guild    = guild
        self.bot      = bot
        self._manager = manager

        self._queue:   asyncio.Queue[dict] = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)
        self._pending: list[dict]          = []

        self.current:      Optional[YTDLSource] = None
        self.current_meta: Optional[dict]       = None

        self.volume:   int  = config.DEFAULT_VOLUME
        self.looping:  bool = False

        self._play_next_event = asyncio.Event()
        self._auto_dc_task:   Optional[asyncio.Task] = None
        self._player_task:    Optional[asyncio.Task] = None

        self.text_channel: Optional[discord.TextChannel] = None
        self.np_message:   Optional[discord.Message]     = None
        self.bot_ref:      Optional[discord.Client]      = None

    # ── Queue helpers ───────────────────────────────────────────────────────

    @property
    def queue_list(self) -> list[dict]:
        return list(self._pending)

    def queue_size(self) -> int:
        return len(self._pending)

    async def add(self, track: dict) -> int:
        if self._queue.full():
            raise OverflowError("Queue is full.")
        await self._queue.put(track)
        self._pending.append(track)
        return len(self._pending)

    def shuffle(self) -> None:
        random.shuffle(self._pending)
        new_q: asyncio.Queue[dict] = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)
        for t in self._pending:
            new_q.put_nowait(t)
        self._queue = new_q

    def clear(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._pending.clear()

    # ── Playback ────────────────────────────────────────────────────────────

    def _after_play(self, error: Optional[Exception]) -> None:
        if error:
            log.error("Playback error: %s", error)
        self.bot.loop.call_soon_threadsafe(self._play_next_event.set)

    async def _player_loop(self) -> None:
        await self.bot.wait_until_ready()
        self._play_next_event.clear()

        while True:
            self._play_next_event.clear()

            if self.looping and self.current_meta:
                track = self.current_meta
            else:
                try:
                    track = await asyncio.wait_for(self._queue.get(), timeout=180)
                    if track in self._pending:
                        self._pending.remove(track)
                except asyncio.TimeoutError:
                    await self._idle_disconnect()
                    return

            self.current_meta = track

            try:
                source = await YTDLSource.from_url(
                    track["url"], loop=self.bot.loop, volume=self.volume / 100
                )
            except Exception as exc:
                log.error("Failed to load %s: %s", track.get("title"), exc)
                if self.text_channel:
                    from utils.embeds import error as err_embed
                    await self.text_channel.send(
                        embed=err_embed(f"Could not load **{track.get('title', 'Unknown')}**. Skipping.", "Playback Error"),
                        delete_after=10,
                    )
                continue

            self.current = source
            vc = self.guild.voice_client
            if not vc or not vc.is_connected():
                log.warning("Voice client gone before playback in %s — stopping player.", self.guild.name)
                self.current = None
                self.current_meta = None
                # Explicit teardown so stale player isn't left in the manager
                # if the voice-state event was missed or delayed.
                self._manager._players.pop(self.guild.id, None)
                await self._reset_presence()
                return

            try:
                vc.play(source, after=self._after_play)
            except discord.ClientException as exc:
                log.error("vc.play() failed (%s) — skipping track.", exc)
                self._play_next_event.set()
                continue

            # Record to recently played & increment counter
            data_store.add_recently_played(self.guild.id, track)
            data_store.increment_songs_played(self.guild.id)

            await self._update_presence(track.get("title", "music"))
            if self.text_channel:
                await self._send_np_card()

            await self._play_next_event.wait()
            self.current = None

            if self.np_message:
                try:
                    await self.np_message.delete()
                except Exception:
                    pass
                self.np_message = None

        await self._reset_presence()

    async def _update_presence(self, song_title: str) -> None:
        bot = self.bot_ref or self.bot
        try:
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=song_title[:128],
                ),
                status=discord.Status.online,
            )
        except Exception:
            pass

    async def _reset_presence(self) -> None:
        bot = self.bot_ref or self.bot
        try:
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"music | {config.PREFIX}help",
                ),
                status=discord.Status.online,
            )
        except Exception:
            pass

    async def start(self) -> None:
        if self._player_task and not self._player_task.done():
            return
        self._player_task = self.bot.loop.create_task(self._player_loop())

    def stop(self) -> None:
        self._cancel_auto_disconnect()
        if self._player_task:
            self._player_task.cancel()
            self._player_task = None
        self.clear()
        self.current      = None
        self.current_meta = None
        vc = self.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()

    def skip(self) -> None:
        vc = self.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()

    def pause(self) -> bool:
        vc = self.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            return True
        return False

    def resume(self) -> bool:
        vc = self.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            return True
        return False

    def set_volume(self, vol: int) -> None:
        self.volume = vol
        if self.current:
            self.current.volume = vol / 100

    # ── Now-playing card ────────────────────────────────────────────────────

    async def _send_np_card(self) -> None:
        if not self.text_channel or not self.current_meta:
            return
        from utils.embeds import now_playing as np_embed
        from utils.buttons import PlayerView
        vc      = self.guild.voice_client
        vc_name = vc.channel.name if vc else ""
        embed = np_embed(
            self.current_meta,
            position=0,
            volume=self.volume,
            looping=self.looping,
            queue_size=self.queue_size(),
            vc_name=vc_name,
        )
        view = PlayerView(self)
        try:
            self.np_message = await self.text_channel.send(embed=embed, view=view)
        except Exception as exc:
            log.warning("Could not send NP card: %s", exc)

    # ── Auto-disconnect ─────────────────────────────────────────────────────

    async def _idle_disconnect(self) -> None:
        vc = self.guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()
        await self._reset_presence()
        if self.text_channel:
            from utils.embeds import warning as warn_embed
            await self.text_channel.send(
                embed=warn_embed("Left the voice channel due to inactivity.", "Idle"),
                delete_after=15,
            )
        self._manager._players.pop(self.guild.id, None)

    def schedule_auto_disconnect(self, delay: int = config.AUTO_DISCONNECT_DELAY) -> None:
        self._cancel_auto_disconnect()
        self._auto_dc_task = self.bot.loop.create_task(self._auto_disconnect_after(delay))

    def _cancel_auto_disconnect(self) -> None:
        if self._auto_dc_task and not self._auto_dc_task.done():
            self._auto_dc_task.cancel()
        self._auto_dc_task = None

    async def _auto_disconnect_after(self, delay: int) -> None:
        await asyncio.sleep(delay)
        vc = self.guild.voice_client
        if vc and vc.is_connected():
            members = [m for m in vc.channel.members if not m.bot]
            if not members:
                self.stop()
                await vc.disconnect()
                await self._reset_presence()
                self._manager._players.pop(self.guild.id, None)
                if self.text_channel:
                    from utils.embeds import warning as warn_embed
                    await self.text_channel.send(
                        embed=warn_embed("Everyone left. Disconnected.", "Auto-Disconnect"),
                        delete_after=15,
                    )


# ─── PlayerManager ─────────────────────────────────────────────────────────

class PlayerManager:

    def __init__(self, bot: discord.Client):
        self.bot      = bot
        self._players: dict[int, GuildPlayer] = {}

    def get(self, guild: discord.Guild) -> GuildPlayer:
        if guild.id not in self._players:
            self._players[guild.id] = GuildPlayer(guild, self.bot, self)
        return self._players[guild.id]

    def get_existing(self, guild: discord.Guild) -> Optional[GuildPlayer]:
        return self._players.get(guild.id)

    def remove(self, guild: discord.Guild) -> None:
        player = self._players.pop(guild.id, None)
        if player:
            player.stop()

    def active_count(self) -> int:
        return sum(
            1 for p in self._players.values()
            if (vc := p.guild.voice_client) and vc.is_playing()
        )
