"""
Reverb Bot – Embed Builders
Black / purple / neon-blue premium aesthetic.
All user-supplied strings are truncated before insertion to stay within
Discord's field (1 024 chars) and description (4 096 chars) limits.
"""
from __future__ import annotations

import datetime
from typing import Optional

import discord

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SEP = "━━━━━━━━━━━━━━━━━━━━━━━"


# ─── Safety helpers ────────────────────────────────────────────────────────

def _trunc(text: str, limit: int = 1024, suffix: str = "…") -> str:
    """Hard-truncate a string to `limit` characters."""
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)] + suffix


def _trunc_desc(text: str) -> str:
    return _trunc(text, 4096)


def _trunc_field(text: str) -> str:
    return _trunc(text, 1024)


# ─── Internals ─────────────────────────────────────────────────────────────

def _base(color: int = config.BRAND_COLOR) -> discord.Embed:
    embed = discord.Embed(color=color)
    embed.timestamp = datetime.datetime.utcnow()
    return embed


def _fmt(seconds: float) -> str:
    if not seconds:
        return "∞"
    s = int(seconds)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _fmt_long(seconds: float) -> str:
    if not seconds:
        return "∞"
    s = int(seconds)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m:02d}m {s:02d}s"


def _bar(current: float, total: float, length: int = 18) -> str:
    if total <= 0:
        return "━" * length
    filled = min(int((current / total) * length), length - 1)
    return "━" * filled + "🔘" + "━" * (length - filled - 1)


# ─── Now Playing ───────────────────────────────────────────────────────────

def now_playing(
    track: dict,
    position: float = 0.0,
    volume: int = 50,
    looping: bool = False,
    queue_size: int = 0,
    vc_name: str = "",
) -> discord.Embed:
    embed = _base(config.NP_COLOR)
    embed.title = "🎧  Reverb Music Player"

    title    = _trunc(track.get("title", "Unknown"), 200)
    url      = track.get("url", "")
    uploader = _trunc(track.get("uploader", "Unknown"), 100)
    dur      = track.get("duration", 0)
    req      = _trunc(track.get("requestor", "Unknown"), 100)

    bar      = _bar(position, dur)
    time_str = f"`{_fmt(position)}` {bar} `{_fmt(dur)}`"

    embed.description = _trunc_desc(
        f"{SEP}\n"
        f"**🎵  Playing:**\n[{title}]({url})\n\n"
        f"**👤  Artist:**\n{uploader}\n"
        f"{SEP}"
    )

    embed.add_field(name="⏱  Duration", value=f"`{_fmt(dur)}`",       inline=True)
    embed.add_field(name="🔊  Volume",   value=f"`{volume}%`",         inline=True)
    embed.add_field(name="🔄  Loop",     value="On 🔁" if looping else "Off", inline=True)
    embed.add_field(name="🙋  Requested By", value=f"`{req}`",         inline=True)
    embed.add_field(
        name="📜  Queue",
        value=f"`{queue_size} track{'s' if queue_size != 1 else ''}`",
        inline=True,
    )
    if vc_name:
        embed.add_field(name="🎧  Channel", value=f"`{_trunc(vc_name, 50)}`", inline=True)

    embed.add_field(name="\u200b", value=time_str, inline=False)

    thumb = track.get("thumbnail")
    if thumb:
        embed.set_thumbnail(url=thumb)

    embed.set_footer(text=f"Reverb  •  Premium Music Experience  •  {SEP[:8]}")
    return embed


# ─── Enqueued Track ────────────────────────────────────────────────────────

def track_added(track: dict, position: int) -> discord.Embed:
    embed = _base(config.SUCCESS_COLOR)
    embed.title = "Enqueued Track"
    title = _trunc(track.get("title", "Unknown"), 200)
    url   = track.get("url", "")
    embed.description = _trunc_desc(
        f"{config.EMOJI_SUCCESS} Added **[{title}]({url})** to the queue."
    )
    thumb = track.get("thumbnail")
    if thumb:
        embed.set_thumbnail(url=thumb)
    dur = _fmt_long(track.get("duration", 0))
    req = _trunc(track.get("requestor", "Unknown"), 80)
    embed.set_footer(text=f"Duration : {dur}  •  Requestor : {req}  •  Position : {position}")
    return embed


def playlist_added(title: str, count: int, requestor: str = "Unknown") -> discord.Embed:
    embed = _base(config.SUCCESS_COLOR)
    embed.title = "Playlist Enqueued"
    embed.description = _trunc_desc(
        f"{config.EMOJI_SUCCESS} Added **{count}** tracks from **{_trunc(title, 200)}** to the queue."
    )
    embed.set_footer(text=f"Requestor : {_trunc(requestor, 80)}  •  {count} tracks")
    return embed


# ─── Queue ─────────────────────────────────────────────────────────────────

def queue_list(
    tracks: list[dict],
    page: int = 1,
    per_page: int = 10,
    current: Optional[dict] = None,
) -> discord.Embed:
    embed = _base(config.QUEUE_COLOR)
    embed.title = "📜  Music Queue"

    if current:
        dur = _fmt(current.get("duration", 0))
        req = _trunc(current.get("requestor", ""), 60)
        np_val = _trunc_field(
            f"**[{_trunc(current['title'], 100)}]({current['url']})** — `{dur}`"
            + (f" — 👤 `{req}`" if req else "")
        )
        embed.add_field(name="▶️  Now Playing", value=np_val, inline=False)

    if not tracks:
        embed.add_field(name="📭  Up Next", value="The queue is empty.", inline=False)
        embed.set_footer(text="Reverb  •  Use .play to add songs")
        return embed

    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page        = min(max(1, page), total_pages)
    start       = (page - 1) * per_page

    lines = []
    for i, t in enumerate(tracks[start : start + per_page], start=start + 1):
        dur     = _fmt(t.get("duration", 0))
        req     = _trunc(t.get("requestor", ""), 40)
        req_str = f" · 👤 `{req}`" if req else ""
        title   = _trunc(t.get("title", "Unknown"), 80)
        lines.append(f"`{i}.` **[{title}]({t['url']})** — `{dur}`{req_str}")

    embed.add_field(
        name=f"📋  Up Next  (page {page}/{total_pages})",
        value=_trunc_field("\n".join(lines)),
        inline=False,
    )
    total_dur = sum(t.get("duration", 0) for t in tracks)
    embed.set_footer(
        text=(
            f"Reverb  •  {len(tracks)} tracks  •  {_fmt_long(total_dur)} total"
            f"  •  Page {page}/{total_pages}"
        )
    )
    return embed


# ─── Search Results ────────────────────────────────────────────────────────

def search_results(results: list[dict], query: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = "🔍  Search Results"
    embed.description = _trunc_desc(
        f"Results for: **{_trunc(query, 200)}**\nSelect a track from the dropdown below."
    )
    lines = []
    for i, t in enumerate(results, 1):
        dur   = _fmt(t.get("duration", 0))
        title = _trunc(t.get("title", "Unknown"), 80)
        upl   = _trunc(t.get("uploader", "Unknown"), 40)
        lines.append(f"`{i}.` **{title}** — `{dur}` — {upl}")
    embed.add_field(name="\u200b", value=_trunc_field("\n".join(lines)), inline=False)
    embed.set_footer(text="Reverb  •  Select a track or dismiss to cancel")
    return embed


# ─── Recently Played ───────────────────────────────────────────────────────

def recently_played(tracks: list[dict]) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = "🕐  Recently Played"
    if not tracks:
        embed.description = "No recently played tracks."
        return embed
    lines = []
    for i, t in enumerate(tracks, 1):
        dur   = _fmt(t.get("duration", 0))
        title = _trunc(t.get("title", "Unknown"), 80)
        lines.append(f"`{i}.` **[{title}]({t['url']})** — `{dur}`")
    embed.description = _trunc_desc("\n".join(lines))
    embed.set_footer(text=f"Reverb  •  Last {len(tracks)} played")
    return embed


# ─── Playlists ─────────────────────────────────────────────────────────────

def playlist_list(playlists: dict, user: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = f"📚  {_trunc(user, 50)}'s Playlists"
    if not playlists:
        embed.description = "You have no saved playlists. Use `.playlist save <name>` to create one."
        return embed
    lines = [
        f"`{i}.` **{_trunc(name, 50)}** — {len(tracks)} track{'s' if len(tracks) != 1 else ''}"
        for i, (name, tracks) in enumerate(playlists.items(), 1)
    ]
    embed.description = _trunc_desc("\n".join(lines))
    embed.set_footer(text="Reverb  •  .playlist load <name> to play")
    return embed


# ─── Favorites ─────────────────────────────────────────────────────────────

def favorites_list(tracks: list[dict], user: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = f"❤️  {_trunc(user, 50)}'s Favorites"
    if not tracks:
        embed.description = "No favorites yet. Use `.favorite add` while a song is playing."
        return embed
    lines = []
    for i, t in enumerate(tracks, 1):
        dur   = _fmt(t.get("duration", 0))
        title = _trunc(t.get("title", "Unknown"), 80)
        lines.append(f"`{i}.` **[{title}]({t['url']})** — `{dur}`")
    embed.description = _trunc_desc("\n".join(lines))
    embed.set_footer(text=f"Reverb  •  {len(tracks)} saved")
    return embed


# ─── Stats ─────────────────────────────────────────────────────────────────

def bot_stats(
    bot: "discord.Client",
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
    embed.title = "📊  Reverb Statistics"
    embed.add_field(name="🌐  Servers",        value=f"`{guild_count}`",      inline=True)
    embed.add_field(name="👥  Users",           value=f"`{user_count}`",       inline=True)
    embed.add_field(name="🎵  Active Players",  value=f"`{active_players}`",   inline=True)
    embed.add_field(name="⏱  Uptime",          value=f"`{uptime_str}`",        inline=True)
    embed.add_field(name="📡  Latency",         value=f"`{latency_ms}ms`",      inline=True)
    embed.add_field(name="🎶  Songs Played",    value=f"`{songs_played}`",      inline=True)
    embed.add_field(name="🐍  Python",          value=f"`{python_ver}`",        inline=True)
    embed.add_field(name="📦  discord.py",      value=f"`{dpy_ver}`",           inline=True)
    embed.add_field(name="⚙️  Prefix",         value=f"`{config.PREFIX}`",     inline=True)
    if bot.user and bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="Reverb  •  Premium Music Experience")
    return embed


# ─── Help ──────────────────────────────────────────────────────────────────

def help_home(prefix: str, bot_avatar: Optional[str] = None) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = "🎧  Reverb Help Menu"
    embed.description = _trunc_desc(
        f"{SEP}\n"
        f"**Select a category below** to see all commands.\n\n"
        f"🎵 Music  ·  ⚙️ Settings  ·  🛠 Utility  ·  👑 Admin\n"
        f"{SEP}\n"
        f"**Prefix:** `{prefix}`  ·  Also supports `/slash` commands"
    )
    if bot_avatar:
        embed.set_thumbnail(url=bot_avatar)
    embed.set_footer(text=f"Reverb Music Bot  •  {SEP[:8]}")
    return embed


def help_music(prefix: str) -> discord.Embed:
    embed = _base(config.NP_COLOR)
    embed.title = "🎵  Music Commands"
    cmds = [
        (f"`{prefix}play <song/url>`", "Search and play music"),
        (f"`{prefix}pause`",           "Pause playback"),
        (f"`{prefix}resume`",          "Resume playback"),
        (f"`{prefix}skip`",            "Skip current song"),
        (f"`{prefix}stop`",            "Stop & clear queue"),
        (f"`{prefix}queue`",           "Show music queue"),
        (f"`{prefix}nowplaying`",      "Show current song player"),
        (f"`{prefix}volume <0-100>`",  "Change volume"),
        (f"`{prefix}loop`",            "Toggle loop mode"),
        (f"`{prefix}shuffle`",         "Shuffle queue"),
        (f"`{prefix}leave`",           "Disconnect bot"),
        (f"`{prefix}search <song>`",   "Search and pick a track"),
        (f"`{prefix}lyrics [song]`",   "Show song lyrics"),
        (f"`{prefix}recent`",          "Recently played songs"),
        (f"`{prefix}playlist`",        "Manage playlists"),
        (f"`{prefix}favorite`",        "Manage favorites"),
    ]
    embed.description = _trunc_desc("\n".join(f"{c}  —  {d}" for c, d in cmds))
    embed.set_footer(text="Reverb  •  🎵 Music")
    return embed


def help_utility(prefix: str) -> discord.Embed:
    embed = _base(config.INFO_COLOR)
    embed.title = "🛠  Utility Commands"
    cmds = [
        (f"`{prefix}help`",    "Show this help menu"),
        (f"`{prefix}ping`",    "Bot latency"),
        (f"`{prefix}stats`",   "Bot statistics"),
        (f"`{prefix}uptime`",  "Bot uptime"),
        (f"`{prefix}invite`",  "Invite Reverb"),
        (f"`{prefix}support`", "Support server"),
        (f"`{prefix}botinfo`", "About Reverb"),
    ]
    embed.description = _trunc_desc("\n".join(f"{c}  —  {d}" for c, d in cmds))
    embed.set_footer(text="Reverb  •  🛠 Utility")
    return embed


def help_settings(prefix: str) -> discord.Embed:
    embed = _base(config.QUEUE_COLOR)
    embed.title = "⚙️  Settings Commands"
    cmds = [
        (f"`{prefix}setprefix <prefix>`", "Change bot prefix (Admin)"),
        (f"`{prefix}setdj <@role>`",      "Set DJ role (Admin)"),
        (f"`{prefix}removedj`",           "Remove DJ role (Admin)"),
        (f"`{prefix}djrole`",             "Show current DJ role"),
        (f"`{prefix}settings`",           "View server settings (Admin)"),
    ]
    embed.description = _trunc_desc("\n".join(f"{c}  —  {d}" for c, d in cmds))
    embed.set_footer(text="Reverb  •  ⚙️ Settings  •  Requires Manage Server")
    return embed


def help_admin(prefix: str) -> discord.Embed:
    embed = _base(config.ERROR_COLOR)
    embed.title = "👑  Admin Commands"
    cmds = [
        (f"`{prefix}setprefix <prefix>`", "Change bot prefix"),
        (f"`{prefix}setdj <@role>`",      "Set DJ role"),
        (f"`{prefix}removedj`",           "Remove DJ role"),
        (f"`{prefix}settings`",           "View server config"),
    ]
    embed.description = _trunc_desc("\n".join(f"{c}  —  {d}" for c, d in cmds))
    embed.set_footer(text="Reverb  •  👑 Admin  •  Requires Manage Server")
    return embed


# ─── Generic builders ──────────────────────────────────────────────────────

def error(message: str, title: str = "Error") -> discord.Embed:
    embed = _base(config.ERROR_COLOR)
    embed.title = f"{config.EMOJI_ERROR}  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def success(message: str, title: str = "Success") -> discord.Embed:
    embed = _base(config.SUCCESS_COLOR)
    embed.title = f"{config.EMOJI_SUCCESS}  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def warning(message: str, title: str = "Warning") -> discord.Embed:
    embed = _base(config.WARNING_COLOR)
    embed.title = f"⚠️  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def info(message: str, title: str = "Info") -> discord.Embed:
    embed = _base(config.INFO_COLOR)
    embed.title = f"{config.EMOJI_INFO}  {_trunc(title, 200)}"
    embed.description = _trunc_desc(message)
    return embed


def welcome(guild_name: str, prefix: str) -> discord.Embed:
    embed = _base(config.BRAND_COLOR)
    embed.title = f"{config.EMOJI_MUSIC}  Hey there! I'm Reverb."
    embed.description = _trunc_desc(
        f"{SEP}\n"
        f"Thanks for inviting me to **{_trunc(guild_name, 100)}**!\n"
        f"I'm a **premium Discord music bot** with a modern player UI, "
        f"interactive controls, playlists, and much more.\n\n"
        f"Get started with `{prefix}play <song>` or `{prefix}help`.\n"
        f"{SEP}"
    )
    embed.add_field(name="🚀  Quick Start", value=(
        f"`{prefix}play Never Gonna Give You Up`\n"
        f"`{prefix}help` — full command list"
    ), inline=True)
    embed.add_field(name="🎮  Controls", value=(
        "▶️ ⏸ ⏭ ⏹ 🔁 🔀 📜 🔊\n"
        "Interactive buttons on every player card"
    ), inline=True)
    embed.set_footer(text="Reverb  •  Premium Music Experience")
    return embed
