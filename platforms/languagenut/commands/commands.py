"""
commands.py — Hub, Login, Settings, Health, Homeworks, Leaderboard, Farm XP,
              Saved Accounts, DM Progress, Pin Hub, Admin/Owner Commands

Uses async LNApiClient from automation.api_direct (FIXED: token as query param).
FIXED: All API calls use call_lnut() with token as query parameter, not Bearer header.
"""

import asyncio
import json
import logging
import os
import random
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import discord
from discord import Interaction, app_commands, ui
from discord.ext import commands

from automation.api_direct import LNApiClient
from automation.stealth import StealthManager

logger = logging.getLogger("lnut-bot")

GREEN = discord.Colour(0x00FF88)
RED = discord.Colour(0xFF0044)
BLUE = discord.Colour(0x0088FF)
AMBER = discord.Colour(0xFFAA00)
PURPLE = discord.Colour(0x8833FF)

OWNER_ID = 1453752725324955656

# ─── Language flag helpers ────────────────────────────────────────────────

FLAG_MAP = {
    "spanish": "🇪🇸", "french": "🇫🇷", "german": "🇩🇪", "italian": "🇮🇹",
    "mandarin": "🇨🇳", "arabic": "🇸🇦", "polish": "🇵🇱", "irish": "🇮🇪",
    "welsh": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "latin": "🏛️", "japanese": "🇯🇵",
    "portuguese": "🇵🇹", "russian": "🇷🇺", "dutch": "🇳🇱", "turkish": "🇹🇷",
}

CURRICULUM_UIDS = {
    "spanish": 54, "french": 55, "german": 56, "italian": 57,
    "mandarin": 58, "arabic": 59, "polish": 60, "irish": 61,
    "welsh": 62, "latin": 63, "japanese": 64,
}

def _flag(lang_name: str) -> str:
    return FLAG_MAP.get(lang_name.lower(), "🌐")

# ─── Account file helpers (file-based, matches repo pattern) ──────────────

def get_accounts_dir(guild_id: Optional[int]) -> Path:
    d = Path("accounts") / str(guild_id or 0)
    d.mkdir(parents=True, exist_ok=True)
    return d

def load_account(guild_id: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    d = get_accounts_dir(guild_id)
    files = sorted(d.glob("*.txt"))
    if not files:
        return None, None
    try:
        content = files[0].read_text().strip()
        if ":" in content:
            u, p = content.split(":", 1)
            return u.strip(), p.strip()
        return content.strip(), None
    except Exception:
        return None, None

def save_account(guild_id: Optional[int], username: str, password: str):
    d = get_accounts_dir(guild_id)
    safe = username.replace("/", "_").replace("\\", "_")
    (d / f"{safe}.txt").write_text(f"{username}:{password}")

def delete_accounts(guild_id: Optional[int]):
    d = get_accounts_dir(guild_id)
    for f in d.glob("*.txt"):
        f.unlink()

# ─── Config / Settings helpers ────────────────────────────────────────────

CONFIG_FILE = Path("config.json")

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"accounts": {}, "guild_settings": {}, "saved_accounts": {}}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"accounts": {}, "guild_settings": {}, "saved_accounts": {}}

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

SETTING_DEFAULTS = {
    "speed": 10,
    "min_accuracy": 85,
    "max_accuracy": 92,
    "stealth_enabled": True,
    "concurrency": 3,
    "rounds": 20,
    "dm_progress": False,
}

def get_guild_settings(guild_id: Optional[int]) -> dict:
    cfg = load_config()
    gs = cfg.get("guild_settings", {}).get(str(guild_id or 0), {})
    return {**SETTING_DEFAULTS, **gs}

def set_guild_setting(guild_id: Optional[int], key: str, value):
    cfg = load_config()
    cfg.setdefault("guild_settings", {}).setdefault(str(guild_id or 0), {})[key] = value
    save_config(cfg)

# ─── Saved accounts (per guild, stored in config.json) ────────────────────

def load_saved_accounts(guild_id: int) -> dict:
    cfg = load_config()
    return cfg.get("saved_accounts", {}).get(str(guild_id), {})

def save_saved_account(guild_id: int, label: str, username: str, password: str, token: str = ""):
    cfg = load_config()
    cfg.setdefault("saved_accounts", {}).setdefault(str(guild_id), {})[label] = {
        "username": username,
        "password": password,
        "token": token,
    }
    save_config(cfg)

def delete_saved_account(guild_id: int, label: str):
    cfg = load_config()
    saved = cfg.get("saved_accounts", {}).get(str(guild_id), {})
    saved.pop(label, None)
    save_config(cfg)

# ─── LN API helpers ───────────────────────────────────────────────────────

async def do_login(username: str, password: str) -> Tuple[bool, str]:
    """Login using LNApiClient. Returns (success, token_or_error)."""
    try:
        client = LNApiClient()
        result = await client.login(username, password)
        if client.token:
            return True, client.token
        return False, result.get("msg", "Login returned no token")
    except Exception as e:
        return False, str(e)

async def get_homeworks(token: str) -> list:
    """Get all viewable homeworks."""
    try:
        client = LNApiClient()
        client.token = token
        data = await client.call_lnut("assignmentController/getViewableAll",
                                       {"token": token})
        homeworks = data.get("list", data.get("homework", []))
        if isinstance(homeworks, list):
            return homeworks
        return []
    except Exception as e:
        logger.warning(f"get_homeworks failed: {e}")
        return []

async def check_health(username: str, password: str) -> dict:
    """Check account health. Returns dict with banned/status/stats/error_message."""
    try:
        ok, token = await do_login(username, password)
        if not ok:
            return {"banned": True, "status": "login_failed", "error_message": token, "stats": {}}
        client = LNApiClient()
        client.token = token
        try:
            stats = await client.call_lnut("stats/get", {"token": token})
        except Exception:
            stats = {}
        try:
            profile = await client.call_lnut("profile/get", {"token": token})
        except Exception:
            profile = {}
        return {
            "banned": False,
            "status": "healthy",
            "stats": stats or {},
            "profile": profile or {},
            "error_message": "",
            "token": token,
        }
    except Exception as e:
        return {"banned": True, "status": "error", "error_message": str(e), "stats": {}}

# ─── Hub embed builder ────────────────────────────────────────────────────

def build_hub_embed(guild_id: Optional[int]) -> discord.Embed:
    uname, _ = load_account(guild_id)
    settings = get_guild_settings(guild_id)
    saved = load_saved_accounts(guild_id or 0)
    e = discord.Embed(title="🌍 LanguageNut Control Hub", colour=BLUE)
    e.add_field(name="👤 Logged In", value=uname or "Not logged in", inline=True)
    e.add_field(name="💾 Saved", value=str(len(saved)), inline=True)
    e.add_field(name="⚡ Speed", value=f"{settings['speed']}x", inline=True)
    e.add_field(name="🎯 Accuracy", value=f"{settings['min_accuracy']}-{settings['max_accuracy']}%", inline=True)
    e.add_field(name="🔄 Rounds", value=str(settings['rounds']), inline=True)
    e.add_field(name="📬 DM", value="✅" if settings['dm_progress'] else "❌", inline=True)
    e.set_footer(text="LanguageNut Farmer")
    return e

# ─── Views ────────────────────────────────────────────────────────────────

class LoginModal(ui.Modal, title="Login to LanguageNut"):
    def __init__(self, guild_id: Optional[int]):
        super().__init__()
        self.guild_id = guild_id

    username = ui.TextInput(label="Username", placeholder="Enter your LN username")
    password = ui.TextInput(label="Password", placeholder="Enter your LN password",
                            style=discord.TextStyle.short)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, msg = await do_login(self.username.value, self.password.value)
        if ok:
            save_account(self.guild_id, self.username.value, self.password.value)
            e = discord.Embed(title="✅ Logged In", colour=GREEN,
                              description=f"Account: **{self.username.value}**")
        else:
            e = discord.Embed(title="❌ Login Failed", colour=RED,
                              description=f"Error: {msg}")
        await interaction.followup.send(embed=e, ephemeral=True)

class SaveAccountModal(ui.Modal, title="Save LanguageNut Account"):
    def __init__(self, guild_id: Optional[int]):
        super().__init__()
        self.guild_id = guild_id

    label = ui.TextInput(label="Label", placeholder="e.g. Main, Alt1, School")
    username = ui.TextInput(label="Username", placeholder="LN username")
    password = ui.TextInput(label="Password", placeholder="LN password", style=discord.TextStyle.short)

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(self.username.value, self.password.value)
        if ok:
            save_saved_account(self.guild_id or 0, self.label.value,
                               self.username.value, self.password.value, token)
            e = discord.Embed(title="✅ Account Saved", colour=GREEN,
                              description=f"**{self.label.value}** → `{self.username.value}`")
        else:
            e = discord.Embed(title="❌ Login Failed", colour=RED,
                              description=f"Could not verify credentials: {token}")
        await interaction.followup.send(embed=e, ephemeral=True)

class HubView(ui.View):
    def __init__(self, guild_id: Optional[int]):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @ui.button(label="🔑 Login", style=discord.ButtonStyle.success, row=0)
    async def login_btn(self, interaction: Interaction, btn: ui.Button):
        await interaction.response.send_modal(LoginModal(self.guild_id))

    @ui.button(label="🚪 Logout", style=discord.ButtonStyle.danger, row=0)
    async def logout_btn(self, interaction: Interaction, btn: ui.Button):
        delete_accounts(self.guild_id)
        await interaction.response.send_message("✅ Logged out.", ephemeral=True)
        e = build_hub_embed(self.guild_id)
        v = HubView(self.guild_id)
        await interaction.edit_original_response(embed=e, view=v)

    @ui.button(label="📋 Homeworks", style=discord.ButtonStyle.primary, row=0)
    async def homeworks_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        if not hws:
            return await interaction.followup.send("No homeworks found.", ephemeral=True)
        lines = []
        for hw in hws[:15]:
            title = hw.get("title", hw.get("name", "Untitled"))
            status = "✅" if hw.get("completed") else "📝"
            lines.append(f"{status} **{title}**")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n\n*(truncated)*"
        e = discord.Embed(title="📋 Homeworks", description=text, colour=BLUE)
        await interaction.followup.send(embed=e, ephemeral=True)

    @ui.button(label="🥇 Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def leaderboard_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        try:
            client = LNApiClient()
            client.token = token
            data = await client.call_lnut("highscoreController/studentsAllAccount",
                                          {"token": token, "accountUid": ""})
        except Exception as e:
            return await interaction.followup.send(f"Error: {e}", ephemeral=True)
        students = data.get("list", []) if isinstance(data, dict) else []
        if isinstance(students, list) and students:
            lines = []
            for i, s in enumerate(students[:15]):
                name = s.get("name", f"P{i+1}")
                pts = int(s.get("score", 0))
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`#{i+1}`"
                lines.append(f"{medal} **{name}** — {pts:,} pts")
            e = discord.Embed(title="🥇 Leaderboard", description="\n".join(lines), colour=AMBER)
        else:
            e = discord.Embed(title="🥇 Leaderboard", description="No data.", colour=AMBER)
        await interaction.followup.send(embed=e, ephemeral=True)

    @ui.button(label="❤️ Health", style=discord.ButtonStyle.secondary, row=1)
    async def health_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        health = await check_health(uname, pwd)
        if health.get("banned"):
            e = discord.Embed(title="❌ Account Issue",
                              description=f"**{health['status']}**: {health['error_message']}",
                              colour=RED)
        else:
            stats = health.get("stats", {})
            e = discord.Embed(title="✅ Healthy", colour=GREEN)
            e.add_field(name="Tasks", value=str(stats.get("tasks", "N/A")), inline=True)
            e.add_field(name="Points", value=f"{int(stats.get('points', 0)):,}", inline=True)
            e.add_field(name="XP", value=f"{int(stats.get('totalXp', stats.get('xp', 0))):,}", inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    @ui.button(label="⚡ Farm XP", style=discord.ButtonStyle.success, row=1)
    async def farm_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in. Use Login first.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        languages = set()
        for hw in hws:
            lang = hw.get("language", "")
            if lang:
                languages.add(lang.lower())
        if not languages:
            languages = set(CURRICULUM_UIDS.keys())
        embed = discord.Embed(title="⚡ Farm XP", description="Select a language:", colour=GREEN)
        view = FarmLanguageSelect(self.guild_id or 0, token, sorted(languages))
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @ui.button(label="💾 Saved", style=discord.ButtonStyle.secondary, row=1)
    async def saved_btn(self, interaction: Interaction, btn: ui.Button):
        accounts = load_saved_accounts(self.guild_id or 0)
        if not accounts:
            return await interaction.response.send_message("No saved accounts. Use `/save` to add one.", ephemeral=True)
        lines = []
        for label, info in accounts.items():
            un = info.get("username", label)
            tok = "🔑" if info.get("token") else "🔒"
            lines.append(f"• **{label}** (`{un}`) {tok}")
        e = discord.Embed(title="💾 Saved Accounts", description="\n".join(lines), colour=PURPLE)
        view = ui.View(timeout=300)
        view.add_item(ui.Button(label="➕ Add", style=discord.ButtonStyle.success, custom_id="add_saved"))
        async def add_cb(i: Interaction):
            await i.response.send_modal(SaveAccountModal(self.guild_id))
        view.children[0].callback = add_cb
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.secondary, row=2)
    async def settings_btn(self, interaction: Interaction, btn: ui.Button):
        settings = get_guild_settings(self.guild_id)
        lines = []
        for k, v in settings.items():
            lines.append(f"• **{k.replace('_', ' ').title()}**: `{v}`")
        e = discord.Embed(title="⚙️ Settings", description="\n".join(lines), colour=AMBER)
        view = SettingsView(self.guild_id)
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    @ui.button(label="📌 Pin Hub", style=discord.ButtonStyle.secondary, row=2)
    async def pin_btn(self, interaction: Interaction, btn: ui.Button):
        e = build_hub_embed(self.guild_id)
        v = HubView(self.guild_id)
        msg = await interaction.channel.send(embed=e, view=v)
        try:
            await msg.pin()
            await interaction.response.send_message("📌 Hub pinned!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("📌 Hub sent!", ephemeral=True)

    @ui.button(label="📬 DM Toggle", style=discord.ButtonStyle.secondary, row=2)
    async def dm_btn(self, interaction: Interaction, btn: ui.Button):
        settings = get_guild_settings(self.guild_id)
        new_val = not settings.get("dm_progress", False)
        set_guild_setting(self.guild_id, "dm_progress", new_val)
        await interaction.response.send_message(f"📬 DM progress: **{'On' if new_val else 'Off'}**", ephemeral=True)

    @ui.button(label="🔄 Refresh", style=discord.ButtonStyle.gray, row=2)
    async def refresh_btn(self, interaction: Interaction, btn: ui.Button):
        await interaction.response.defer()
        e = build_hub_embed(self.guild_id)
        v = HubView(self.guild_id)
        await interaction.edit_original_response(embed=e, view=v)

# ─── Farm Language Select + Farm Runner ───────────────────────────────────

class FarmLanguageSelect(ui.View):
    def __init__(self, guild_id: int, token: str, languages: list):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.token = token
        options = []
        for lang in languages:
            cid = CURRICULUM_UIDS.get(lang.lower())
            if cid:
                label = lang.title()
                options.append(discord.SelectOption(
                    label=label, value=f"{lang.lower()}|{cid}",
                    emoji="🌐",
                ))
        if not options:
            options.append(discord.SelectOption(label="No languages", value="none"))
        self.add_item(FarmLangSelect(options))

class FarmLangSelect(ui.Select):
    def __init__(self, options: list):
        super().__init__(placeholder="Choose a language...", options=options[:25], row=0)

    async def callback(self, interaction: Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("No languages available.", ephemeral=True)
        lang, cid = self.values[0].split("|")
        view = self.view
        settings = get_guild_settings(view.guild_id)
        embed = discord.Embed(
            title=f"⚡ Farming {lang.title()}",
            description=f"Rounds: {settings['rounds']}\nAccuracy: {settings['min_accuracy']}-{settings['max_accuracy']}%\nSpeed: {settings['speed']}x\n\nStarting farm...",
            colour=GREEN,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        # Run farm in background
        asyncio.create_task(run_xp_farm(interaction, view.guild_id, view.token, int(cid), lang, settings))

async def run_xp_farm(interaction: Interaction, guild_id: int, token: str,
                       curriculum_uid: int, language: str, settings: dict):
    """Run the XP farm loop."""
    uname, pwd = load_account(guild_id)
    if not uname:
        return await interaction.edit_original_response(
            embed=discord.Embed(title="❌ Error", description="Not logged in.", colour=RED))
    client = LNApiClient()
    client.token = token
    rounds = settings.get("rounds", 20)
    stealth = StealthManager(
        speed=settings.get("speed", 10),
        min_accuracy=settings.get("min_accuracy", 85),
        max_accuracy=settings.get("max_accuracy", 92),
    )
    stealth.username = uname
    total_xp = 0
    try:
        for r in range(1, rounds + 1):
            try:
                vocab = await client.get_game_vocab(curriculum_uid)
                items = vocab.get("vocab", vocab.get("list", []))
                if not items:
                    await asyncio.sleep(3)
                    continue
                correct_indices, incorrect_indices = stealth.determine_accuracy(len(items))
                correct_uids = [items[i].get("uid", "") for i in correct_indices if i < len(items)]
                incorrect_uids = [items[i].get("uid", "") for i in incorrect_indices if i < len(items)]
                result = await client.add_game_score(correct_uids, incorrect_uids)
                xp = int(result.get("score", result.get("xp", 0)))
                total_xp += xp
                if r % 5 == 0 or r == rounds:
                    embed = discord.Embed(
                        title=f"⚡ Farming {language.title()}",
                        description=f"Round {r}/{rounds}\nXP: **{total_xp:,}**",
                        colour=GREEN,
                    )
                    await interaction.edit_original_response(embed=embed)
                await asyncio.sleep(stealth.delay_between_tasks())
            except Exception as e:
                logger.warning(f"Farm round {r} error: {e}")
                await asyncio.sleep(5)
        embed = discord.Embed(
            title=f"✅ Farm Complete - {language.title()}",
            description=f"Rounds: {rounds}\nTotal XP: **{total_xp:,}**\nAccount: `{uname}`",
            colour=GREEN,
        )
        await interaction.edit_original_response(embed=embed)
        # Send DM if enabled
        if settings.get("dm_progress") and interaction.user.dm_channel:
            dm = discord.Embed(title=f"✅ Farm Complete - {language.title()}",
                               description=f"Rounds: {rounds}\nTotal XP: **{total_xp:,}**",
                               colour=GREEN)
            try:
                await interaction.user.send(embed=dm)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Farm error: {traceback.format_exc()}")
        embed = discord.Embed(title="❌ Farm Error", description=str(e), colour=RED)
        await interaction.edit_original_response(embed=embed)

# ─── Settings View ────────────────────────────────────────────────────────

SETTING_OPTIONS = {
    "speed": ("Speed", [(f"{v}x", v) for v in [5, 8, 10, 12, 15]]),
    "min_accuracy": ("Min Accuracy", [(f"{v}%", v) for v in [75, 80, 85, 88, 90, 92]]),
    "max_accuracy": ("Max Accuracy", [(f"{v}%", v) for v in [88, 90, 92, 95, 98]]),
    "rounds": ("Rounds", [(str(v), v) for v in [5, 10, 15, 20, 30, 40, 50]]),
}

class SettingsView(ui.View):
    def __init__(self, guild_id: Optional[int]):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        settings = get_guild_settings(guild_id)
        ROW_MAP = {"speed": 0, "min_accuracy": 0, "max_accuracy": 1, "rounds": 1}
        for key, (label, options) in SETTING_OPTIONS.items():
            row = ROW_MAP.get(key, 0)
            current = settings.get(key)
            opts = []
            for opt_label, opt_val in options:
                is_def = opt_val == current
                opts.append(discord.SelectOption(
                    label=f"{opt_label}" + (" ✓" if is_def else ""),
                    value=f"{key}:{opt_val}",
                    default=is_def,
                ))
            select = ui.Select(placeholder=f"{label}: {current}", options=opts[:25], row=row)
            select.callback = self.make_callback(key, label)
            self.add_item(select)

    def make_callback(self, key: str, label: str):
        async def callback(interaction: Interaction):
            value = interaction.data["values"][0]
            _, val_str = value.split(":", 1)
            parsed = int(val_str) if val_str.isdigit() else val_str
            set_guild_setting(self.guild_id, key, parsed)
            e = discord.Embed(title="✅ Settings Updated",
                              description=f"**{label}** → `{parsed}`", colour=GREEN)
            await interaction.response.edit_message(embed=e, view=SettingsView(self.guild_id))
        return callback

# ─── Cog ──────────────────────────────────────────────────────────────────

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="hub", description="Open LanguageNut control hub")
    async def hub(self, interaction: Interaction):
        await interaction.response.defer()
        e = build_hub_embed(interaction.guild_id)
        v = HubView(interaction.guild_id)
        await interaction.followup.send(embed=e, view=v)

    @app_commands.command(name="login", description="Login to LanguageNut")
    async def login(self, interaction: Interaction):
        await interaction.response.send_modal(LoginModal(interaction.guild_id))

    @app_commands.command(name="logout", description="Delete saved account")
    async def logout(self, interaction: Interaction):
        delete_accounts(interaction.guild_id)
        await interaction.response.send_message(
            embed=discord.Embed(title="Logged Out", colour=RED), ephemeral=True)

    @app_commands.command(name="status", description="Account stats")
    async def status(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        health = await check_health(uname, pwd)
        if health.get("banned"):
            return await interaction.followup.send(f"Login failed: {health['error_message']}", ephemeral=True)
        stats = health.get("stats", {})
        e = discord.Embed(title="Account Status", colour=BLUE)
        e.add_field(name="Username", value=uname, inline=True)
        e.add_field(name="Tasks", value=str(stats.get("tasks", "N/A")), inline=True)
        e.add_field(name="Points", value=f"{int(stats.get('points', 0)):,}", inline=True)
        e.add_field(name="XP", value=f"{int(stats.get('totalXp', stats.get('xp', 0))):,}", inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="homeworks", description="List homeworks")
    async def homeworks(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        if not hws:
            return await interaction.followup.send("No homeworks found.", ephemeral=True)
        lines = []
        for hw in hws[:20]:
            title = hw.get("title", hw.get("name", "Unknown"))
            status = "✅" if hw.get("completed") else "📝"
            lines.append(f"{status} **{title}**")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n\n*(truncated)*"
        e = discord.Embed(title="📋 Homeworks", description=text, colour=BLUE)
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="leaderboard", description="View rankings")
    async def leaderboard(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login: {token}", ephemeral=True)
        try:
            client = LNApiClient()
            client.token = token
            data = await client.call_lnut("highscoreController/studentsAllAccount",
                                          {"token": token, "accountUid": ""})
        except Exception as e:
            return await interaction.followup.send(f"Error: {e}", ephemeral=True)
        students = data.get("list", []) if isinstance(data, dict) else []
        e = discord.Embed(title="🥇 Leaderboard", colour=AMBER)
        if isinstance(students, list) and students:
            for i, s in enumerate(students[:15]):
                name = s.get("name", f"P{i+1}")
                pts = int(s.get("score", 0))
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`#{i+1}`"
                e.add_field(name=f"{medal} {name}", value=f"{pts:,} pts", inline=False)
        else:
            e.description = "No data."
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="health", description="Check account health")
    async def account_health(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        health = await check_health(uname, pwd)
        if health.get("banned"):
            e = discord.Embed(title="❌ Account Issue",
                              description=f"Status: **{health['status']}**\n{health['error_message']}",
                              colour=RED)
        else:
            e = discord.Embed(title="✅ Healthy", colour=GREEN)
            e.add_field(name="Username", value=uname, inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="save", description="Save an account for XP farming")
    @app_commands.describe(label="A label for this account", username="LN username", password="LN password")
    async def save_account_cmd(self, interaction: Interaction, label: str, username: str, password: str):
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(username, password)
        if not ok:
            return await interaction.followup.send(f"❌ Login failed: {token}", ephemeral=True)
        save_saved_account(interaction.guild_id or 0, label, username, password, token)
        e = discord.Embed(title="✅ Account Saved", description=f"`{label}` → **{username}**", colour=GREEN)
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="unsave", description="Remove a saved account")
    @app_commands.describe(label="The saved account label to remove")
    async def unsave_account_cmd(self, interaction: Interaction, label: str):
        saved = load_saved_accounts(interaction.guild_id or 0)
        if label not in saved:
            return await interaction.response.send_message(f"❌ No saved account `{label}`.", ephemeral=True)
        delete_saved_account(interaction.guild_id or 0, label)
        await interaction.response.send_message(f"✅ Removed `{label}`.", ephemeral=True)

    @app_commands.command(name="farm", description="Farm XP on LanguageNut")
    @app_commands.describe(language="Language to farm", rounds="Number of rounds (1-50)")
    async def farm(self, interaction: Interaction, language: str, rounds: int = 20):
        uname, pwd = load_account(interaction.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer()
        rounds = max(1, min(rounds, 50))
        lang_lower = language.lower().strip()
        cid = CURRICULUM_UIDS.get(lang_lower)
        if not cid:
            known = ", ".join(k.title() for k in CURRICULUM_UIDS)
            return await interaction.followup.send(f"Unknown `{language}`. Known: {known}")
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login failed: {token}")
        settings = get_guild_settings(interaction.guild_id)
        settings["rounds"] = rounds
        embed = discord.Embed(
            title=f"⚡ Farming {language.title()}",
            description=f"Starting {rounds} rounds...\nAccount: `{uname}`",
            colour=GREEN,
        )
        await interaction.followup.send(embed=embed)
        # Running farm - send progress via followup messages or edits
        # (Simplified: uses the background runner)
        msg = await interaction.original_response()
        asyncio.create_task(run_xp_farm_direct(
            interaction, msg, interaction.guild_id, token, cid, lang_lower, settings, uname,
        ))

    @app_commands.command(name="languages", description="Show available languages")
    async def languages(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname:
            return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok:
            return await interaction.followup.send(f"Login: {token}")
        hws = await get_homeworks(token)
        langs = set()
        for hw in hws:
            lang = hw.get("language", "")
            if lang:
                langs.add(lang.title())
        if not langs:
            langs = set(k.title() for k in CURRICULUM_UIDS)
        lines = []
        for lang in sorted(langs):
            cid = CURRICULUM_UIDS.get(lang.lower())
            cid_str = f" (UID `{cid}`)" if cid else ""
            lines.append(f"{_flag(lang)} **{lang}**{cid_str}")
        e = discord.Embed(title="🌐 Available Languages", description="\n".join(lines), colour=BLUE)
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="settings", description="Configure bot behavior")
    async def settings_cmd(self, interaction: Interaction):
        settings = get_guild_settings(interaction.guild_id)
        lines = []
        for k, v in settings.items():
            lines.append(f"• **{k.replace('_', ' ').title()}**: `{v}`")
        e = discord.Embed(title="⚙️ Settings", description="\n".join(lines), colour=AMBER)
        view = SettingsView(interaction.guild_id)
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    @app_commands.command(name="dmprogress", description="Toggle DM progress notifications")
    async def dm_progress(self, interaction: Interaction):
        settings = get_guild_settings(interaction.guild_id)
        new_val = not settings.get("dm_progress", False)
        set_guild_setting(interaction.guild_id, "dm_progress", new_val)
        state = "enabled" if new_val else "disabled"
        await interaction.response.send_message(f"📬 DM progress **{state}**.", ephemeral=True)

    # ─── Admin / Owner Commands ─────────────────────────────────────────

    async def _owner_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Owner only.", ephemeral=True)
            return False
        return True

    @app_commands.command(name="shutdown", description="[Owner] Shutdown the bot")
    async def shutdown(self, interaction: Interaction):
        if not await self._owner_check(interaction):
            return
        await interaction.response.send_message("🔴 Shutting down...", ephemeral=True)
        await self.bot.close()

    @app_commands.command(name="sync", description="[Owner] Force slash command sync")
    async def sync(self, interaction: Interaction):
        if not await self._owner_check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ Synced {len(synced)} commands.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)

    @app_commands.command(name="reload", description="[Owner] Reload a cog")
    @app_commands.describe(cog="Cog name (e.g. commands.commands)")
    async def reload(self, interaction: Interaction, cog: str = "commands.commands"):
        if not await self._owner_check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.reload_extension(cog)
            await interaction.followup.send(f"✅ Reloaded `{cog}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)

    @app_commands.command(name="clear", description="[Owner] Clear messages")
    @app_commands.describe(limit="Number of messages to clear (max 100)")
    async def clear(self, interaction: Interaction, limit: int = 50):
        if not await self._owner_check(interaction):
            return
        limit = max(1, min(limit, 100))
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=limit)
            await interaction.followup.send(f"✅ Cleared {len(deleted)} messages.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)

    @app_commands.command(name="logs", description="[Owner] View recent bot logs")
    @app_commands.describe(lines="Number of lines (max 50)")
    async def logs(self, interaction: Interaction, lines: int = 20):
        if not await self._owner_check(interaction):
            return
        lines = max(5, min(lines, 50))
        await interaction.response.defer(ephemeral=True)
        try:
            log_file = Path("bot.log")
            if not log_file.exists():
                return await interaction.followup.send("No log file found.", ephemeral=True)
            content = log_file.read_text().splitlines()
            recent = content[-lines:]
            text = "\n".join(recent)
            if len(text) > 1900:
                text = text[-1900:]
            e = discord.Embed(title="📋 Recent Logs", description=f"```\n{text}\n```", colour=AMBER)
            await interaction.followup.send(embed=e, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="eval", description="[Owner] Evaluate Python code")
    async def eval_cmd(self, interaction: Interaction, code: str):
        if not await self._owner_check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            result = eval(code)
            await interaction.followup.send(f"```py\n{result}\n```", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"```py\nError: {e}\n```", ephemeral=True)

    @app_commands.command(name="setstatus", description="[Owner] Set bot status")
    @app_commands.describe(status="online, idle, dnd, or invisible")
    async def setstatus(self, interaction: Interaction, status: str):
        if not await self._owner_check(interaction):
            return
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
            "offline": discord.Status.invisible,
        }
        s = status_map.get(status.lower())
        if not s:
            return await interaction.response.send_message(
                f"Invalid status. Use: {', '.join(status_map.keys())}", ephemeral=True)
        await self.bot.change_presence(status=s)
        settings = get_guild_settings(interaction.guild_id)
        set_guild_setting(interaction.guild_id, "bot_status", status)
        await interaction.response.send_message(f"Status set to **{status}**.", ephemeral=True)

async def run_xp_farm_direct(interaction, msg, guild_id, token, curriculum_uid, language, settings, uname):
    """Direct farm runner for /farm command (separate from hub to avoid conflicts)."""
    client = LNApiClient()
    client.token = token
    rounds = settings.get("rounds", 20)
    stealth = StealthManager(
        speed=settings.get("speed", 10),
        min_accuracy=settings.get("min_accuracy", 85),
        max_accuracy=settings.get("max_accuracy", 92),
    )
    stealth.username = uname
    total_xp = 0
    try:
        for r in range(1, rounds + 1):
            try:
                vocab = await client.get_game_vocab(curriculum_uid)
                items = vocab.get("vocab", vocab.get("list", []))
                if not items:
                    await asyncio.sleep(3)
                    continue
                correct_indices, incorrect_indices = stealth.determine_accuracy(len(items))
                correct_uids = [items[i].get("uid", "") for i in correct_indices if i < len(items)]
                incorrect_uids = [items[i].get("uid", "") for i in incorrect_indices if i < len(items)]
                result = await client.add_game_score(correct_uids, incorrect_uids)
                xp = int(result.get("score", result.get("xp", 0)))
                total_xp += xp
                if r % 5 == 0 or r == rounds:
                    embed = discord.Embed(
                        title=f"⚡ Farming {language.title()}",
                        description=f"Round {r}/{rounds}\nXP: **{total_xp:,}**",
                        colour=GREEN,
                    )
                    await msg.edit(embed=embed)
                await asyncio.sleep(stealth.delay_between_tasks())
            except Exception as e:
                logger.warning(f"Farm round {r} error: {e}")
                await asyncio.sleep(5)
        embed = discord.Embed(
            title=f"✅ Farm Complete - {language.title()}",
            description=f"Rounds: {rounds}\nTotal XP: **{total_xp:,}**",
            colour=GREEN,
        )
        await msg.edit(embed=embed)
    except Exception as e:
        logger.error(f"Farm error: {traceback.format_exc()}")
        embed = discord.Embed(title="❌ Farm Error", description=str(e), colour=RED)
        await msg.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(Commands(bot))
    logger.info("Commands cog loaded")
