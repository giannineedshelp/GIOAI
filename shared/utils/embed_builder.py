
import discord
from datetime import datetime, timezone

class EmbedBuilder:
    COLORS = {
        "primary": 0x5865F2,   # Blurple
        "sparx": 0x00AAFF,     # Bright Blue
        "languagenut": 0x9B59B6, # Purple
        "success": 0x00FF88,   # Green
        "error": 0xFF0044,     # Red
        "warning": 0xFFAA00,   # Amber
    }

    @staticmethod
    def _base(color_key="primary"):
        color = EmbedBuilder.COLORS.get(color_key, EmbedBuilder.COLORS["primary"])
        if isinstance(color_key, int): color = color_key
        return discord.Embed(color=color, timestamp=datetime.now(timezone.utc))

    @staticmethod
    def simple(title, description=None, color_key="primary", footer=None):
        e = EmbedBuilder._base(color_key)
        e.title = title
        if description:
            e.description = description
        if footer:
            e.set_footer(text=footer)
        return e

    @staticmethod
    def progress_bar(pct, length=12):
        filled = max(0, min(length, round((pct / 100) * length)))
        empty = length - filled
        return f"█" * filled + "░" * empty
