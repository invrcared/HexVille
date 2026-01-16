# HexVille Bot

All-in-one Discord management bot for HexVille. This bot centralizes support workflows, session operations, moderation actions, and staff tooling with a consistent HexVille theme.

## Features
- Support tickets with auto logging and transcripts
- Session operations commands (startup, reinvites, release, end)
- Vehicle registration and audit logs
- Ownership+ moderation tools (ban, kick, mute)
- AutoMod with in-server configuration panel
- Staff information embeds and control panel utilities
- Role management helpers and onboarding utilities

## Requirements
- Python 3.10+
- `discord.py` 2.3+

## Setup
1. Create a `.env` file and set `DISCORD_TOKEN`.
2. Optional: set `TEST_GUILD_ID` for fast command sync in a dev guild.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python main.py
   ```

## Configuration Notes
- Server-specific IDs live at the top of `main.py`.
- AutoMod defaults are in `get_automod_settings()`.
- Vehicle persistence writes to `vehicle_store.json` by default.

## Quick Commands
- `/panel` - support panel (staff)
- `/control-panel` - developer controls
- `/automodpanel` - AutoMod configuration (Ownership+)
- `/startup`, `/reinvites`, `/release`, `/end` - session lifecycle
- `/ban`, `/kick`, `/mute` - moderation (Ownership+)
- `/infract` - session warnings (staff)

## License
Private use for HexVille.
