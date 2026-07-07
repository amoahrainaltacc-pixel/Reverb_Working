"""
Reverb Bot – UI Views & Buttons
PlayerView, HelpView, QueuePagesView, SearchView
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

import discord

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import embeds
from utils import store as data_store

if TYPE_CHECKING:
    from utils.player import GuildPlayer

log = logging.getLogger("reverb.buttons")

_IDLE_ACTIVITY = discord.Activity(
    type=discord.ActivityType.listening,
    name=f"music | {config.PREFIX}help",
)

# Simple per-user interaction cooldown (seconds)
BUTTON_COOLDOWN = 1.5
_cooldowns: dict[int, float] = {}


def _check_cooldown(user_id: int) -> float:
    """Returns remaining cooldown seconds (0.0 if clear)."""
    now  = time.monotonic()
    last = _cooldowns.get(user_id, 0)
    rem  = BUTTON_COOLDOWN - (now - last)
    if rem > 0:
        return rem
    _cooldowns[user_id] = now
    return 0.0


def _fmt_dur(seconds: float) -> str:
    if not seconds:
        return "∞"
    s  = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ─── Player View (8 buttons, 2 rows) ───────────────────────────────────────

class PlayerView(discord.ui.View):
    """Full interactive player — attaches to the now-playing card."""

    def __init__(self, player: "GuildPlayer"):
        super().__init__(timeout=None)
        self.player = player
        self._refresh_states()

    def _refresh_states(self) -> None:
        vc         = self.player.guild.voice_client
        is_playing = bool(vc and vc.is_playing())
        is_paused  = bool(vc and vc.is_paused())
        active     = is_playing or is_paused

        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            cid = child.custom_id
            if cid == "reverb:resume":
                child.disabled = is_playing or not active
            elif cid == "reverb:pause":
                child.disabled = not is_playing
            elif cid == "reverb:skip":
                child.disabled = not active
            elif cid == "reverb:shuffle":
                child.disabled = self.player.queue_size() < 2
            elif cid == "reverb:voldown":
                child.disabled = self.player.volume <= 0
            elif cid == "reverb:volup":
                child.disabled = self.player.volume >= 100

    async def _guard(self, interaction: discord.Interaction) -> bool:
        """
        Three-way guard:
          1. Cooldown
          2. Same voice channel
          3. DJ role (if set)
        """
        # 1. Cooldown
        cd = _check_cooldown(interaction.user.id)
        if cd > 0:
            await interaction.response.send_message(
                embed=embeds.warning(f"Slow down! Try again in `{cd:.1f}s`.", "Cooldown"),
                ephemeral=True,
            )
            return False

        # 2. Same voice channel
        vc        = interaction.guild.voice_client if interaction.guild else None
        member_vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc or not member_vc or vc.channel != member_vc:
            await interaction.response.send_message(
                embed=embeds.error("You must be in the same voice channel as Reverb."),
                ephemeral=True,
            )
            return False

        # 3. DJ role
        if not data_store.has_dj(interaction.user):
            await interaction.response.send_message(
                embed=embeds.error(
                    "You need the **DJ role** or **Manage Server** permission to use music controls.",
                    "DJ Required",
                ),
                ephemeral=True,
            )
            return False

        return True

    async def _update_card(self, interaction: discord.Interaction) -> None:
        """Refresh the now-playing embed and button states in place."""
        try:
            self._refresh_states()
            if self.player.current_meta:
                pos     = self.player.current.position if self.player.current else 0.0
                vc      = self.player.guild.voice_client
                vc_name = vc.channel.name if vc else ""
                embed   = embeds.now_playing(
                    self.player.current_meta,
                    position=pos,
                    volume=self.player.volume,
                    looping=self.player.looping,
                    queue_size=self.player.queue_size(),
                    vc_name=vc_name,
                )
                await interaction.message.edit(embed=embed, view=self)
            else:
                await interaction.message.edit(view=self)
        except Exception as exc:
            log.debug("Could not update player card: %s", exc)

    # ── Row 0 ───────────────────────────────────────────────────────────────

    @discord.ui.button(emoji="▶️", label="Resume", style=discord.ButtonStyle.success,
                       custom_id="reverb:resume", row=0)
    async def btn_resume(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        ok    = self.player.resume()
        msg   = "Resumed playback." if ok else "Nothing is paused."
        embed = embeds.success(msg, "Resumed ▶️") if ok else embeds.warning(msg, "Warning")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._update_card(interaction)

    @discord.ui.button(emoji="⏸", label="Pause", style=discord.ButtonStyle.secondary,
                       custom_id="reverb:pause", row=0)
    async def btn_pause(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        ok    = self.player.pause()
        msg   = "Paused playback." if ok else "Nothing is playing."
        embed = embeds.success(msg, "Paused ⏸") if ok else embeds.warning(msg, "Warning")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._update_card(interaction)

    @discord.ui.button(emoji="⏭", label="Skip", style=discord.ButtonStyle.primary,
                       custom_id="reverb:skip", row=0)
    async def btn_skip(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        title = (
            self.player.current_meta.get("title", "track")
            if self.player.current_meta else "track"
        )
        self.player.skip()
        await interaction.response.send_message(
            embed=embeds.success(f"Skipped **{title[:200]}**.", "Skipped ⏭"),
            ephemeral=True,
        )
        await self._update_card(interaction)

    @discord.ui.button(emoji="⏹", label="Stop", style=discord.ButtonStyle.danger,
                       custom_id="reverb:stop", row=0)
    async def btn_stop(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        self.player.stop()
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        try:
            await interaction.client.change_presence(activity=_IDLE_ACTIVITY)
        except Exception:
            pass
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Stopped playback and cleared the queue.", "Stopped ⏹"),
            view=self,
        )

    @discord.ui.button(emoji="🔁", label="Loop", style=discord.ButtonStyle.secondary,
                       custom_id="reverb:loop", row=0)
    async def btn_loop(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        self.player.looping = not self.player.looping
        state = "enabled 🔁" if self.player.looping else "disabled"
        await interaction.response.send_message(
            embed=embeds.success(f"Loop **{state}**.", "Loop 🔁"),
            ephemeral=True,
        )
        await self._update_card(interaction)

    # ── Row 1 ───────────────────────────────────────────────────────────────

    @discord.ui.button(emoji="🔀", label="Shuffle", style=discord.ButtonStyle.secondary,
                       custom_id="reverb:shuffle", row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        n = self.player.queue_size()
        if n < 2:
            await interaction.response.send_message(
                embed=embeds.warning("Need at least 2 queued tracks to shuffle.", "Warning"),
                ephemeral=True,
            )
            return
        self.player.shuffle()
        await interaction.response.send_message(
            embed=embeds.success(f"Shuffled **{n}** tracks! 🔀", "Shuffled"),
            ephemeral=True,
        )
        await self._update_card(interaction)

    @discord.ui.button(emoji="📜", label="Queue", style=discord.ButtonStyle.secondary,
                       custom_id="reverb:queue", row=1)
    async def btn_queue(self, interaction: discord.Interaction, _: discord.ui.Button):
        tracks  = self.player.queue_list
        current = self.player.current_meta
        embed   = embeds.queue_list(tracks, current=current)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="🔉", label="Vol -", style=discord.ButtonStyle.secondary,
                       custom_id="reverb:voldown", row=1)
    async def btn_voldown(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        new_vol = max(0, self.player.volume - 10)
        self.player.set_volume(new_vol)
        bar = "█" * (new_vol // 10) + "░" * (10 - new_vol // 10)
        await interaction.response.send_message(
            embed=embeds.success(f"Volume: **{new_vol}%**\n`{bar}`", "Volume 🔉"),
            ephemeral=True,
        )
        await self._update_card(interaction)

    @discord.ui.button(emoji="🔊", label="Vol +", style=discord.ButtonStyle.secondary,
                       custom_id="reverb:volup", row=1)
    async def btn_volup(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard(interaction):
            return
        new_vol = min(100, self.player.volume + 10)
        self.player.set_volume(new_vol)
        bar = "█" * (new_vol // 10) + "░" * (10 - new_vol // 10)
        await interaction.response.send_message(
            embed=embeds.success(f"Volume: **{new_vol}%**\n`{bar}`", "Volume 🔊"),
            ephemeral=True,
        )
        await self._update_card(interaction)


# ─── Help View (category dropdown) ─────────────────────────────────────────

class HelpView(discord.ui.View):
    def __init__(self, prefix: str, bot_avatar: Optional[str] = None):
        super().__init__(timeout=120)
        self.prefix     = prefix
        self.bot_avatar = bot_avatar
        self.add_item(HelpSelect(prefix))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class HelpSelect(discord.ui.Select):
    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(
            placeholder="📂  Select a category…",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Home",     value="home",     emoji="🏠", description="Back to the main menu"),
                discord.SelectOption(label="Music",    value="music",    emoji="🎵", description="All music commands"),
                discord.SelectOption(label="Utility",  value="utility",  emoji="🛠", description="General utility commands"),
                discord.SelectOption(label="Settings", value="settings", emoji="⚙️", description="Bot settings"),
                discord.SelectOption(label="Admin",    value="admin",    emoji="👑", description="Admin-only commands"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        avatar = (
            str(interaction.client.user.display_avatar)
            if interaction.client.user else None
        )
        v = self.values[0]
        embed_map = {
            "home":     embeds.help_home(self.prefix, avatar),
            "music":    embeds.help_music(self.prefix),
            "utility":  embeds.help_utility(self.prefix),
            "settings": embeds.help_settings(self.prefix),
            "admin":    embeds.help_admin(self.prefix),
        }
        await interaction.response.edit_message(embed=embed_map[v], view=self.view)


# ─── Queue Pages View ───────────────────────────────────────────────────────

class QueuePagesView(discord.ui.View):
    def __init__(self, tracks: list[dict], current: Optional[dict], per_page: int = 10):
        super().__init__(timeout=60)
        self.tracks   = tracks
        self.current  = current
        self.per_page = per_page
        self.page     = 1
        self.total    = max(1, (len(tracks) + per_page - 1) // per_page)
        self._update_buttons()

    def _update_buttons(self):
        self.btn_prev.disabled = self.page <= 1
        self.btn_next.disabled = self.page >= self.total

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, custom_id="q:prev")
    async def btn_prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = max(1, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(
            embed=embeds.queue_list(self.tracks, self.page, self.per_page, self.current),
            view=self,
        )

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="q:next")
    async def btn_next(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = min(self.total, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(
            embed=embeds.queue_list(self.tracks, self.page, self.per_page, self.current),
            view=self,
        )


# ─── Search Select View ─────────────────────────────────────────────────────

class SearchView(discord.ui.View):
    """Dropdown to select a track from search results."""

    def __init__(self, results: list[dict], player: "GuildPlayer", requestor: str):
        super().__init__(timeout=30)
        self.results   = results
        self.player    = player
        self.requestor = requestor
        self.chosen: Optional[dict] = None
        self.add_item(SearchSelect(results))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class SearchSelect(discord.ui.Select):
    def __init__(self, results: list[dict]):
        options = []
        for i, t in enumerate(results[:10]):
            dur   = _fmt_dur(t.get("duration", 0))
            label = t["title"][:98]
            desc  = f"{t.get('uploader', '')} — {dur}"[:100]
            options.append(discord.SelectOption(label=label, value=str(i), description=desc, emoji="🎵"))
        super().__init__(placeholder="🎵  Choose a track to play…", options=options)

    async def callback(self, interaction: discord.Interaction):
        # DJ check
        if not data_store.has_dj(interaction.user):
            await interaction.response.send_message(
                embed=embeds.error(
                    "You need the **DJ role** or **Manage Server** permission to queue tracks.",
                    "DJ Required",
                ),
                ephemeral=True,
            )
            return

        idx   = int(self.values[0])
        track = self.view.results[idx]
        track["requestor"] = self.view.requestor
        try:
            pos = await self.view.player.add(track)
        except OverflowError:
            await interaction.response.edit_message(
                embed=embeds.error("The queue is full!"), view=None
            )
            return

        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            embed = embeds.track_added(track, pos)
        else:
            embed = embeds.success(f"Now playing **{track['title'][:200]}**.", "Playing")

        self.view.chosen = track
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self.view)
        await self.view.player.start()
