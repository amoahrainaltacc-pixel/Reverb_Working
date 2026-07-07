"""
Reverb Bot – Data Store
Persists per-guild settings, recently played, playlists, and favorites.
Uses atomic file writes (write-temp → fsync → os.replace) and a
threading.Lock to prevent lost-updates and corruption on concurrent tasks.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger("reverb.store")

_PATH       = os.path.join(config.DATA_DIR, "guild_data.json")
_WRITE_LOCK = threading.Lock()  # serialises all load/save calls


# ─── Internal I/O ──────────────────────────────────────────────────────────

def _load() -> dict:
    with _WRITE_LOCK:
        if not os.path.exists(_PATH):
            return {}
        try:
            with open(_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Try the backup written on every successful save
            backup = _PATH + ".bak"
            if os.path.exists(backup):
                try:
                    with open(backup, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    log.warning("data store was corrupt — restored from backup")
                    return data
                except Exception:
                    pass
            log.warning("data store unreadable and no backup available; starting fresh")
            return {}


def _save(data: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    tmp    = _PATH + ".tmp"
    backup = _PATH + ".bak"
    with _WRITE_LOCK:
        try:
            # Atomic write: temp → fsync → replace
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # Keep previous version as backup before replacing
            if os.path.exists(_PATH):
                try:
                    os.replace(_PATH, backup)
                except OSError:
                    pass
            os.replace(tmp, _PATH)
        except Exception as exc:
            log.warning("Could not write data store: %s", exc)
            try:
                os.remove(tmp)
            except OSError:
                pass


def _guild(data: dict, guild_id: int) -> dict:
    key = str(guild_id)
    if key not in data:
        data[key] = {
            "prefix":          config.PREFIX,
            "dj_role":         None,
            "recently_played": [],
            "playlists":       {},
            "favorites":       {},
            "total_played":    0,
        }
    return data[key]


# ─── Prefix ────────────────────────────────────────────────────────────────

def get_prefix(guild_id: int) -> str:
    data = _load()
    return _guild(data, guild_id).get("prefix", config.PREFIX)


def set_prefix(guild_id: int, prefix: str) -> None:
    data = _load()
    _guild(data, guild_id)["prefix"] = prefix
    _save(data)


# ─── DJ Role ───────────────────────────────────────────────────────────────

def get_dj_role(guild_id: int) -> Optional[int]:
    data = _load()
    return _guild(data, guild_id).get("dj_role")


def set_dj_role(guild_id: int, role_id: Optional[int]) -> None:
    data = _load()
    _guild(data, guild_id)["dj_role"] = role_id
    _save(data)


def has_dj(member: "discord.Member") -> bool:
    """True if member has DJ role, Manage Guild perm, or no DJ role is set."""
    import discord
    if member.guild_permissions.manage_guild:
        return True
    dj_id = get_dj_role(member.guild.id)
    if not dj_id:
        return True  # no restriction
    return any(r.id == dj_id for r in member.roles)


# ─── Recently Played ───────────────────────────────────────────────────────

def add_recently_played(guild_id: int, track: dict) -> None:
    data = _load()
    g    = _guild(data, guild_id)
    rp: list = g.setdefault("recently_played", [])
    rp = [t for t in rp if t.get("url") != track.get("url")]
    rp.insert(0, {
        "title":     track.get("title", "Unknown"),
        "url":       track.get("url", ""),
        "duration":  track.get("duration", 0),
        "uploader":  track.get("uploader", "Unknown"),
        "thumbnail": track.get("thumbnail"),
    })
    g["recently_played"] = rp[: config.RECENTLY_PLAYED_LIMIT]
    _save(data)


def get_recently_played(guild_id: int) -> list[dict]:
    data = _load()
    return _guild(data, guild_id).get("recently_played", [])


# ─── Playlists ─────────────────────────────────────────────────────────────

def get_playlists(user_id: int, guild_id: int) -> dict[str, list[dict]]:
    data = _load()
    g = _guild(data, guild_id)
    return g.setdefault("playlists", {}).get(str(user_id), {})


def save_playlist(user_id: int, guild_id: int, name: str, tracks: list[dict]) -> None:
    data = _load()
    g = _guild(data, guild_id)
    g.setdefault("playlists", {}).setdefault(str(user_id), {})[name] = tracks
    _save(data)


def delete_playlist(user_id: int, guild_id: int, name: str) -> bool:
    data = _load()
    g = _guild(data, guild_id)
    playlists = g.setdefault("playlists", {}).get(str(user_id), {})
    if name in playlists:
        del playlists[name]
        _save(data)
        return True
    return False


# ─── Favorites ─────────────────────────────────────────────────────────────

def get_favorites(user_id: int, guild_id: int) -> list[dict]:
    data = _load()
    g = _guild(data, guild_id)
    return g.setdefault("favorites", {}).get(str(user_id), [])


def add_favorite(user_id: int, guild_id: int, track: dict) -> bool:
    data = _load()
    g    = _guild(data, guild_id)
    favs: list = g.setdefault("favorites", {}).setdefault(str(user_id), [])
    if any(f.get("url") == track.get("url") for f in favs):
        return False
    favs.append({
        "title":     track.get("title", "Unknown"),
        "url":       track.get("url", ""),
        "duration":  track.get("duration", 0),
        "uploader":  track.get("uploader", "Unknown"),
        "thumbnail": track.get("thumbnail"),
    })
    _save(data)
    return True


def remove_favorite(user_id: int, guild_id: int, url: str) -> bool:
    data = _load()
    g    = _guild(data, guild_id)
    favs = g.setdefault("favorites", {}).get(str(user_id), [])
    before = len(favs)
    g["favorites"][str(user_id)] = [f for f in favs if f.get("url") != url]
    _save(data)
    return len(g["favorites"][str(user_id)]) < before


# ─── Guild stats ───────────────────────────────────────────────────────────

def get_total_songs_played(guild_id: int) -> int:
    data = _load()
    return _guild(data, guild_id).get("total_played", 0)


def increment_songs_played(guild_id: int) -> None:
    data = _load()
    g    = _guild(data, guild_id)
    g["total_played"] = g.get("total_played", 0) + 1
    _save(data)
