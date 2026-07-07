import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  Reverb Bot – Configuration
# ─────────────────────────────────────────────

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
PREFIX:    str = os.getenv("PREFIX", ".")
OWNER_ID:  int = int(os.getenv("OWNER_ID", "0"))

# ── Brand colours (black / purple / neon-blue aesthetic) ───────────────────
BRAND_COLOR:   int = 0x6C3BEE   # vibrant purple       – primary
NP_COLOR:      int = 0x00D4FF   # neon cyan/blue        – now-playing card
SUCCESS_COLOR: int = 0x1DB954   # Spotify green         – queue-add / ok
ERROR_COLOR:   int = 0xED4245   # Discord red           – errors
WARNING_COLOR: int = 0xFEE75C   # Discord yellow        – warnings
INFO_COLOR:    int = 0x5865F2   # Discord blurple       – info / help
QUEUE_COLOR:   int = 0x9B59B6   # medium purple         – queue embed
STATS_COLOR:   int = 0x2ECC71   # emerald green         – stats embed
DARK_COLOR:    int = 0x23272A   # near-black            – utility embeds

# ── Custom server emojis ───────────────────────────────────────────────────
EMOJI_ERROR:   str = "<:XE:1524120772396712157>"
EMOJI_SUCCESS: str = "<:THESWE:1524120674157858826>"
EMOJI_MUSIC:   str = "<:bear_music:1524121341349990541>"
EMOJI_INFO:    str = "<:info:1523416103206916297>"

# ── Behaviour ──────────────────────────────────────────────────────────────
AUTO_DISCONNECT_DELAY: int = int(os.getenv("AUTO_DISCONNECT_DELAY", "300"))
MAX_QUEUE_SIZE:        int = int(os.getenv("MAX_QUEUE_SIZE", "100"))
DEFAULT_VOLUME:        int = int(os.getenv("DEFAULT_VOLUME", "50"))
RECENTLY_PLAYED_LIMIT: int = 10
SUPPORT_SERVER:        str = os.getenv("SUPPORT_SERVER", "https://discord.gg/reverb")

# ── yt-dlp ─────────────────────────────────────────────────────────────────
YTDL_FORMAT_OPTIONS: dict = {
    # Prefer opus/m4a (lighter, more reliable on hosted environments like
    # Replit). webm can have slow first-byte times on certain CDN edges.
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": False,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": "in_playlist",
    "socket_timeout": 30,
}

# ── FFmpeg ──────────────────────────────────────────────────────────────────
# IMPORTANT: Do NOT add -filter:a volume=X here.
# Volume is handled by discord.py's PCMVolumeTransformer (pure Python on raw
# PCM), which avoids a decode→filter→re-encode round-trip that degrades quality.
#
# -timeout: abort if no data arrives in 15s (prevents silent hangs on Replit)
# -reconnect_*: recover mid-stream if YouTube CDN rotates the URL
# -analyzeduration / -probesize: reduce stream-open latency while staying
#   well above safe demux thresholds (32k probesize, 2s analyzeduration)
FFMPEG_OPTIONS: dict = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
        "-timeout 15000000 "
        "-analyzeduration 2000000 "
        "-probesize 32768 "
    ),
    "options": "-vn",   # strip video only; no audio filters
}

# ── Data directory ──────────────────────────────────────────────────────────
DATA_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
