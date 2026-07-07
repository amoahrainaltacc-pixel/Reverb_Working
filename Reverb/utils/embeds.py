"""
Reverb Bot – Embed Builders
Premium dark / purple / neon aesthetic.
All user-supplied strings are truncated to stay within Discord's limits.
"""
from __future__ import annotations

import datetime
from typing import Optional

import discord

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ─── Helpers ───────────────────────────────────────────────────────────────

def _trunc(text: str, limit: int = 1024, suffix: str = "…") -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)] + suffix

def _trunc_desc(text: str) -> str:
    return _trunc(text, 4096)

def _trunc_field(text: str) -> str:
    return _trunc(text, 1024)

def _base(color: int = config.BRAND_COLOR) -> discord.Embed:
    embed = discord.Embed(color=color)
    embed.timestamp = datetime.datetime.utcnow()
    return embed

def _fmt(seconds: float) -> str:
    if not seconds:
        return "0:00"
    s = int(seconds)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _fmt_long(seconds: float) -> str:
    if not seconds:
        return "0s"
    s = int(seconds)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"

def _bar(current: float, total: float, length: int = 19) -> str:
    """Render a sleek ─⬤─ progress slider."""
    if total <= 0:
        return "─" * length
    filled = min(int((current / total) * length), length - 1)
    return "─" * filled + "⬤" + "─" * max(0, length - filled - 1)

def _vol_bar(volume: int, length: int = 8) -> str:
    filled = round(volume / 100 * length)
    return "▰" * filled + "▱" * (length - filled)


# ─── Now Playing ───────────────────────────────────────────────────────────

def now_playing(
    track: dict,
    position: float = 0.0,
    volume: int = 50,
    looping: bool = False,
    queue_size: int = 0,
    vc_name: str = "",
    bot_icon: Optional[str] = None,
) -> discord.Embed:
    title    = _trunc(track.get("title", "Unknown"), 256)
    url      = track.get("url", "")
    uploader = _trunc(track.get("uploader", "Unknown"), 100)
    dur      = float(track.get("duration") or 0)
    req      = _trunc(track.get("requestor", "Unknown"), 80)
    thumb    = track.get("thumbnail")

    # Build embed — author = status line, title = song name w/ link
    embed = discord.Embed(color=config.NP_COLOR, title=title, url=url or None)
    embed.set_author(
        name="▶  NOW PLAYING",
        icon_url=bot_icon or discord.Embed.Empty,
    )
    embed.timestamp = datetime.datetime.utcnow()

    # Progress bar + timestamps
    bar      = _bar(position, dur)
    pos_str  = _fmt(position)
    dur_str  = _fmt(dur)
    embed.description = (
        f"by **{uploader}**\n\n"
        f"`{pos_str}` {bar} `{dur_str}`"
    )

    # Stats row — 3 inline
    loop_val = "`🟢 ON`" if looping else "`⭘  OFF`"
    embed.add_field(name="🔊  Volume",  value=f"`{volume}%`\n`{_vol_bar(volume)}`", inline=True)
    embed.add_field(name="🔁  Loop",    value=loop_val,                              inline=True)
    embed.add_field(
        name="📋  Up Next",
        value=f"`{queue_size} track{'s' if queue_size != 1 else ''}`",
        inline=True,
    )

    # Requested by + channel
    embed.add_field(name="👤  Requested by", value=f"`{req}`",                   inline=True)
    if vc_name:
        embed.add_field(name="🎧  Channel", value=f"`{_trunc(vc_name, 50)}`",   inline=True)

    # Big artwork at bottom — much more visually impactful than a thumbnail
    if thumb:
        embed.set_image(url=thumb)

    embed.set_footer(text=f"Reverb  •  {vc_name or 'Premium Music'}")
    return embed


# ─── Enqueued ──────────────────────────────────────────────────────────────

def track_added(track: dict, position: int) -> discord.Embed:
    title = _trunc(track.get("title", "Unknown"), 256)
    url   = track.get("url", "")
    dur   = _fmt_long(track.get("duration", 0))
    req   = _trunc(track.get("requestor", "Unknown"), 80)
    thumb = track.get("thumbnail")

    embed = discord.Embed(color=config.SUCCESS_COLOR, title=title, url=url or None)
    embed.set_author(name="✅  Added to Queue")
    embed.timestamp = datetime.datetime.utcnow()

    embed.add_field(name="⏱  Duration",    value=f"`{dur}`",        inline=True)
    embed.add_field(name="🔢  Position",    value=f"`#{position}`",  inline=True)
    embed.add_field(name="👤  Requested by", value=f"`{req}`",       inline=True)

    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.set_footer(text="Reverb  •  Queue")
    return embed


def playlist_added(title: str, count: int, requestor: str = "Unknown") -> discord.Embed:
    embed = _base(config.SUCCESS_COLOR)
    embed.set_author(name="✅  Playlist Enqueued")
    embed.title = _trunc(title, 256)
    embed.timestamp = datetime.datetime.utcnow()
    embed.add_field(name="🎵  Tracks Added", value=f"`{count}`",                  inline=True)
    embed.add_field(name="👤  Requested by", value=f"`{_trunc(requestor, 80)}`", inline=True)
    embed.set_footer(text="Reverb  •  Queue")
    return embed


# ─── Queue ─────────────────────────────────────────────────────────────────

def queue_list(
    tracks: list[dict],
    page: int = 1,
    per_page: int = 10,
    current: Optional[dict] = None,
) -> discord.Embed:
    embed = _base(config.QUEUE_COLOR)
    embed.timestamp = datetime.datetime.utcnow()

    total_tracks = len(tracks)
    total_pages  = max(1, (total_tracks + per_page - 1) // per_page)
    page         = min(max(1, page), total_pages)

    embed.title = f"📋  Queue  —  {total_tracks} track{'s' if total_tracks != 1 else ''}"

    # Now playing
    if current:
        dur  = _fmt(current.get("duration", 0))
        req  = _trunc(current.get("requestor", ""), 50)
        line = f"**[{_trunc(current['title'], 80)}]({current['url']})** — `{dur}`"
        if req:
            line += f"  ·  👤 {req}"
        embed.add_field(name="▶  Now Playing", value=_trunc_field(line), inline=False)

    if not tracks:
        embed.add_field(
            name="📭  Up Next",
            value="The queue is empty. Use `.play <song>` to add something!",
            inline=False,
        )
        embed.set_footer(text="Reverb  •  Queue is empty")
        return embed

    start = (page - 1) * per_page
    lines = []
    for i, t in enumerate(tracks[start : start + per_page], start=start + 1):
        dur     = _fmt(t.get("duration", 0))
        req     = _trunc(t.get("requestor", ""), 30)
        req_str = f" ·  👤 {req}" if req else ""
        title   = _trunc(t.get("title", "Unknown"), 60)
        lines.append(f"`{i:02d}.`  [{title}]({t['url']})  —  `{dur}`{req_str}")

    embed.add_field(
        name=f"🎵  Up Next  (page {page} / {total_pages})",
        value=_trunc_field("\n".join(lines)),
        inline=False,
    )

    total_dur = sum(t.get("duration", 0) for t in tracks)
    embed.set_footer(
        text=f"Reverb  •  {total_tracks} tracks  •  {_fmt_long(total_dur)} total  •  Page {page}/{total_pages}"
    )
    return embed


# ─── Search Results ────────────────────────────────────────────────────────

def search_results(results: list[dict], query: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = f"🔍  Search Results"
    embed.description = _trunc_desc(f"Showing results for **{_trunc(query, 100)}**")
    embed.timestamp = datetime.datetime.utcnow()

    lines = []
    for i, t in enumerate(results, 1):
        dur   = _fmt(t.get("duration", 0))
        title = _trunc(t.get("title", "Unknown"), 70)
        upl   = _trunc(t.get("uploader", "Unknown"), 30)
        lines.append(f"`{i}.`  **{title}**\n      `{dur}`  ·  {upl}")

    embed.add_field(name="\u200b", value=_trunc_field("\n".join(lines)), inline=False)
    embed.set_footer(text="Reverb  •  Select a track from the menu below")
    return embed


# ─── Recently Played ───────────────────────────────────────────────────────

def recently_played(tracks: list[dict]) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = "🕐  Recently Played"
    embed.timestamp = datetime.datetime.utcnow()
    if not tracks:
        embed.description = "No recently played tracks yet."
        return embed
    lines = []
    for i, t in enumerate(tracks, 1):
        dur   = _fmt(t.get("duration", 0))
        title = _trunc(t.get("title", "Unknown"), 70)
        lines.append(f"`{i:02d}.`  [{title}]({t['url']})  —  `{dur}`")
    embed.description = _trunc_desc("\n".join(lines))
    embed.set_footer(text=f"Reverb  •  Last {len(tracks)} played")
    return embed


# ─── Playlists ─────────────────────────────────────────────────────────────

def playlist_list(playlists: dict, user: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = f"📚  {_trunc(user, 40)}'s Playlists"
    embed.timestamp = datetime.datetime.utcnow()
    if not playlists:
        embed.description = (
            "You have no saved playlists.\n"
            "Use `.playlist save <name>` to save the current queue."
        )
        return embed
    lines = []
    for i, (name, tracks) in enumerate(playlists.items(), 1):
        n = len(tracks)
        lines.append(f"`{i}.`  **{_trunc(name, 50)}**  —  `{n} track{'s' if n != 1 else ''}`")
    embed.description = _trunc_desc("\n".join(lines))
    embed.set_footer(text="Reverb  •  .playlist load <name> to play")
    return embed


# ─── Favorites ─────────────────────────────────────────────────────────────

def favorites_list(tracks: list[dict], user: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = f"❤️  {_trunc(user, 40)}'s Favorites"
    embed.timestamp = datetime.datetime.utcnow()
    if not tracks:
        embed.description = (
            "No favorites yet.\n"
            "Use `.favorite add` while a song is playing to save it."
        )
        return embed
    lines = []
    for i, t in enumerate(tracks, 1):
        dur   = _fmt(t.get("duration", 0))
        title = _trunc(t.get("title", "Unknown"), 70)
        lines.append(f"`{i:02d}.`  [{title}]({t['url']})  —  `{dur}`")
    embed.description = _trunc_desc("\n".join(lines))
    embed.set_footer(text=f"Reverb  •  {len(tracks)} saved  •  ❤️")
    return embed


# ─── Stats ─────────────────────────────────────────────────────────────────

def bot_stats(
    bot,
    guild_count: int,
    user_count: int,
    uptime_str: str,
    songs_played: int,
    active_players: int,
    latency_ms: int,
    python_ver: str,
    dpy_ver: str,
) -> discord.Embed:
    embed = _base(config.STATS_COLOR)
    embed.title = "📊  Reverb — Statistics"
    embed.timestamp = datetime.datetime.utcnow()

    embed.add_field(name="🌐  Servers",        value=f"`{guild_count:,}`",    inline=True)
    embed.add_field(name="👥  Users",           value=f"`{user_count:,}`",    inline=True)
    embed.add_field(name="🎵  Active Players",  value=f"`{active_players}`",  inline=True)
    embed.add_field(name="🎶  Songs Played",    value=f"`{songs_played:,}`",  inline=True)
    embed.add_field(name="📡  Latency",         value=f"`{latency_ms}ms`",    inline=True)
    embed.add_field(name="⏱  Uptime",          value=f"`{uptime_str}`",       inline=True)
    embed.add_field(name="🐍  Python",          value=f"`{python_ver}`",       inline=True)
    embed.add_field(name="📦  discord.py",      value=f"`{dpy_ver}`",          inline=True)
    embed.add_field(name="⚙️  Prefix",         value=f"`{config.PREFIX}`",    inline=True)

    if bot.user and bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="Reverb  •  Premium Music Experience")
    return embed


# ─── Help ──────────────────────────────────────────────────────────────────

def help_home(prefix: str, bot_avatar: Optional[str] = None) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = "🎧  Reverb — Help"
    embed.timestamp = datetime.datetime.utcnow()
    embed.description = _trunc_desc(
        f"**Premium Discord music bot** — YouTube powered, interactive controls, "
        f"playlists, lyrics, and more.\n\n"
        f"Use the dropdown below to browse commands.\n\n"
        f"**Prefix:** `{prefix}`  ·  **Slash commands** also supported"
    )
    embed.add_field(
        name="🚀  Quick Start",
        value=f"`{prefix}play <song name or URL>`",
        inline=True,
    )
    embed.add_field(
        name="🎮  Controls",
        value="Interactive buttons on every player card",
        inline=True,
    )
    if bot_avatar:
        embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text="Reverb  •  Select a category below")
    return embed


def _cmd_table(cmds: list[tuple[str, str]]) -> str:
    return "\n".join(f"`{c}`\n╰ {d}" for c, d in cmds)


def help_music(prefix: str) -> discord.Embed:
    embed = _base(config.NP_COLOR)
    embed.title = "🎵  Music Commands"
    embed.timestamp = datetime.datetime.utcnow()
    cmds = [
        (f"{prefix}play <song/url>",  "Search YouTube and play"),
        (f"{prefix}search <song>",    "Pick from top 8 results"),
        (f"{prefix}pause",            "Pause playback"),
        (f"{prefix}resume",           "Resume playback"),
        (f"{prefix}skip",             "Skip current track"),
        (f"{prefix}stop",             "Stop & clear the queue"),
        (f"{prefix}queue",            "View the queue"),
        (f"{prefix}nowplaying",       "Show the player card"),
        (f"{prefix}volume <0–100>",   "Set volume"),
        (f"{prefix}loop",             "Toggle loop mode"),
        (f"{prefix}shuffle",          "Shuffle the queue"),
        (f"{prefix}leave",            "Disconnect from voice"),
        (f"{prefix}lyrics [song]",    "Show lyrics"),
        (f"{prefix}recent",           "Recently played"),
        (f"{prefix}playlist",         "Manage playlists"),
        (f"{prefix}favorite",         "Manage favorites"),
    ]
    half = len(cmds) // 2
    embed.add_field(name="\u200b", value=_cmd_table(cmds[:half]),  inline=True)
    embed.add_field(name="\u200b", value=_cmd_table(cmds[half:]),  inline=True)
    embed.set_footer(text="Reverb  •  🎵 Music")
    return embed


def help_utility(prefix: str) -> discord.Embed:
    embed = _base(config.INFO_COLOR)
    embed.title = "🛠  Utility Commands"
    embed.timestamp = datetime.datetime.utcnow()
    cmds = [
        (f"{prefix}help",    "Interactive help menu"),
        (f"{prefix}ping",    "Check bot latency"),
        (f"{prefix}stats",   "Bot statistics"),
        (f"{prefix}uptime",  "How long bot has been online"),
        (f"{prefix}invite",  "Get the invite link"),
        (f"{prefix}support", "Support server link"),
        (f"{prefix}botinfo", "About Reverb"),
    ]
    embed.description = _trunc_desc(_cmd_table(cmds))
    embed.set_footer(text="Reverb  •  🛠 Utility")
    return embed


def help_settings(prefix: str) -> discord.Embed:
    embed = _base(config.QUEUE_COLOR)
    embed.title = "⚙️  Settings Commands"
    embed.timestamp = datetime.datetime.utcnow()
    cmds = [
        (f"{prefix}setprefix <prefix>", "Change command prefix  (Admin)"),
        (f"{prefix}setdj <@role>",      "Assign a DJ role  (Admin)"),
        (f"{prefix}removedj",           "Remove the DJ role  (Admin)"),
        (f"{prefix}djrole",             "Show current DJ role"),
        (f"{prefix}settings",           "View all server settings  (Admin)"),
    ]
    embed.description = _trunc_desc(_cmd_table(cmds))
    embed.set_footer(text="Reverb  •  ⚙️ Settings  •  Requires Manage Server")
    return embed


def help_admin(prefix: str) -> discord.Embed:
    embed = _base(config.ERROR_COLOR)
    embed.title = "👑  Admin Commands"
    embed.timestamp = datetime.datetime.utcnow()
    cmds = [
        (f"{prefix}setprefix <prefix>", "Change command prefix"),
        (f"{prefix}setdj <@role>",      "Set DJ role"),
        (f"{prefix}removedj",           "Remove DJ role"),
        (f"{prefix}settings",           "View server config"),
    ]
    embed.description = _trunc_desc(_cmd_table(cmds))
    embed.set_footer(text="Reverb  •  👑 Admin  •  Requires Manage Server")
    return embed


# ─── Generic builders ──────────────────────────────────────────────────────

def error(message: str, title: str = "Error") -> discord.Embed:
    embed = _base(config.ERROR_COLOR)
    embed.title = f"❌  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def success(message: str, title: str = "Success") -> discord.Embed:
    embed = _base(config.SUCCESS_COLOR)
    embed.title = f"✅  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def warning(message: str, title: str = "Warning") -> discord.Embed:
    embed = _base(config.WARNING_COLOR)
    embed.title = f"⚠️  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def info(message: str, title: str = "Info") -> discord.Embed:
    embed = _base(config.INFO_COLOR)
    embed.title = f"ℹ️  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def welcome(guild_name: str, prefix: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = "🎧  Hey! I'm Reverb."
    embed.timestamp = datetime.datetime.utcnow()
    embed.description = _trunc_desc(
        f"Thanks for adding me to **{_trunc(guild_name, 100)}**!\n\n"
        f"I'm a premium music bot — YouTube search, interactive player controls, "
        f"playlists, favorites, lyrics, and more.\n\n"
        f"**Get started:** `{prefix}play <song>` or `{prefix}help`"
    )
    embed.add_field(
        name="🚀  Quick Start",
        value=f"`{prefix}play Never Gonna Give You Up`",
        inline=True,
    )
    embed.add_field(
        name="🎮  Player Controls",
        value="▶️ ⏸ ⏭ ⏹ 🔁 🔀 ❤️ 🔉 🔊\nAll buttons on the player card",
        inline=True,
    )
    embed.set_footer(text="Reverb  •  Premium Music Experience")
    return embed
