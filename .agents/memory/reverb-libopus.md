---
name: Reverb libopus loading
description: How to load the Opus audio codec library on Replit for discord.py voice.
---

## Rule
Call `discord.opus.load_opus('libopus.so.0')` explicitly at startup, before any voice client is created. `ctypes.util.find_library('opus')` returns `None` on Replit.

**Why:** Replit's NixOS environment installs libopus via `installSystemDependencies({ packages: ["libopus"] })`, which puts the .so in the Nix store. The store path is not in ld.so.cache, so `find_library` / the short name `'opus'` fails. The full versioned name `'libopus.so.0'` resolves correctly via the Nix-managed linker.

**How to apply:** In the bot's entry point (main.py), before any voice cog is loaded:
```python
def _load_opus():
    if discord.opus.is_loaded():
        return
    for lib in ("opus", "libopus.so.0", "libopus.so.1", "libopus"):
        try:
            discord.opus.load_opus(lib)
            print(f"[reverb] Loaded opus: {lib}")
            return
        except OSError:
            continue
    print("[reverb] WARNING: libopus not found — voice playback will not work.")

_load_opus()
```

System packages required: `installSystemDependencies({ packages: ["libopus", "libsodium"] })`
