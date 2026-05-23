
import discord
from datetime import datetime, timezone

class EmbedBuilder:
    COLORS = {
        "primary": discord.Colour(0x5865F2),  # Discord Blurple
        "success": discord.Colour(0x57F287),  # Green
        "error": discord.Colour(0xED4245),    # Red
        "warning": discord.Colour(0xFEE75C),  # Yellow
        "info": discord.Colour(0x00B0F4),     # Light Blue
        "farming": discord.Colour(0x9B59B6),  # Purple (Languagenut)
        "sparx": discord.Colour(0x57F287),    # Green (Sparx)
        "account": discord.Colour(0xFFAA00),   # Amber
    }

    @classmethod
    def _base(cls, color: discord.Colour) -> discord.Embed:
        return discord.Embed(color=color, timestamp=datetime.now(timezone.utc))

    @classmethod
    def success(cls, title: str, description: str = "", **kwargs) -> discord.Embed:
        embed = cls._base(cls.COLORS["success"])
        embed.title = f"✅ {title}"
        embed.description = description
        return cls._add_fields(embed, kwargs)

    @classmethod
    def error(cls, title: str, description: str = "", **kwargs) -> discord.Embed:
        embed = cls._base(cls.COLORS["error"])
        embed.title = f"❌ {title}"
        embed.description = description
        return cls._add_fields(embed, kwargs)

    @classmethod
    def warning(cls, title: str, description: str = "", **kwargs) -> discord.Embed:
        embed = cls._base(cls.COLORS["warning"])
        embed.title = f"⚠️ {title}"
        embed.description = description
        return cls._add_fields(embed, kwargs)

    @classmethod
    def info(cls, title: str, description: str = "", **kwargs) -> discord.Embed:
        embed = cls._base(cls.COLORS["info"])
        embed.title = f"ℹ️ {title}"
        embed.description = description
        return cls._add_fields(embed, kwargs)

    @classmethod
    def platform_status(cls, platform_name: str, emoji: str, status_text: str, last_seen: float = None, **kwargs) -> discord.Embed:
        embed = cls._base(cls.COLORS["primary"])
        embed.title = f"{emoji} {platform_name} Status"
        description = f"Current Status: **{status_text}**\n"
        if last_seen:
            time_ago = int(datetime.now(timezone.utc).timestamp() - last_seen)
            description += f"Last Updated: {time_ago} seconds ago"
        embed.description = description
        return cls._add_fields(embed, kwargs)

    @classmethod
    def _progress_bar(cls, fraction: float, length: int = 12) -> str:
        filled = round(fraction * length)
        filled = max(0, min(length, filled))
        empty = length - filled
        bar = "█" * filled + "░" * empty
        pct = round(fraction * 100)
        return f"`{bar}` **{pct}%**"

    @classmethod
    def _add_fields(cls, embed: discord.Embed, kwargs: dict) -> discord.Embed:
        fields = kwargs.pop("fields", None)
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        thumbnail = kwargs.pop("thumbnail", None)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        image = kwargs.pop("image", None)
        if image:
            embed.set_image(url=image)
        author = kwargs.pop("author", None)
        if author:
            embed.set_author(**author)
        footer_text = kwargs.pop("footer_text", "GIOAI Bot")
        embed.set_footer(text=footer_text)
        return embed

    @classmethod
    def hub_embed(cls, title: str, description: str, color: discord.Colour, fields: list = None, footer_text: str = "GIOAI Controller") -> discord.Embed:
        embed = cls._base(color)
        embed.title = title
        embed.description = description
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text=footer_text)
        return embed

    @classmethod
    def homework_embed(cls, title: str, description: str, color: discord.Colour, fields: list = None, footer_text: str = "GIOAI Homework") -> discord.Embed:
        embed = cls._base(color)
        embed.title = title
        embed.description = description
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text=footer_text)
        return embed

    @classmethod
    def settings_embed(cls, title: str, description: str, color: discord.Colour, fields: list = None, footer_text: str = "GIOAI Settings") -> discord.Embed:
        embed = cls._base(color)
        embed.title = title
        embed.description = description
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text=footer_text)
        return embed

    @classmethod
    def xp_farm_embed(cls, title: str, description: str, color: discord.Colour, fields: list = None, footer_text: str = "LanguageNut XP Bot") -> discord.Embed:
        embed = cls._base(color)
        embed.title = title
        embed.description = description
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text=footer_text)
        return embed

