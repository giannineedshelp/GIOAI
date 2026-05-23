"""
commands.py — Hub, Login, Settings, Health, Homeworks, Leaderboard, Farm XP,
              Saved Accounts, DM Toggle, Pin Hub, Task Autocomplete
              All with progress bars using embeds.py pattern.
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
from shared.utils.embed_builder import EmbedBuilder

logger = logging.getLogger("lnut-bot")

GREEN = discord.Colour(0x00FF88)
RED = discord.Colour(0xFF0044)
BLUE = discord.Colour(0x0088FF)
AMBER = discord.Colour(0xFFAA00)
PURPLE = discord.Colour(0x8833FF)

OWNER_ID = 1453752725324955656

CURRICULUM_UIDS = {
    "spanish": 54, "french": 55, "german": 56, "italian": 57,
    "mandarin": 58, "arabic": 59, "polish": 60, "irish": 61,
    "welsh": 62, "latin": 63, "japanese": 64,
}

def _progress_bar(fraction: float, length: int = 15) -> str:
    """Text-based progress bar matching embeds.py pattern."""
    filled = max(0, min(length, round(fraction * length)))
    empty = length - filled
    return "█" * filled + "░" * empty

# ─── Account file helpers ─────────────────────────────────────────────────

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

# ─── Config helpers ───────────────────────────────────────────────────────

CONFIG_FILE = Path("config.json")

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"guild_settings": {}, "saved_accounts": {}}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"guild_settings": {}, "saved_accounts": {}}

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

SETTING_DEFAULTS = {
    "speed": 10, "min_accuracy": 85, "max_accuracy": 92,
    "stealth_enabled": True, "concurrency": 3, "rounds": 20, "dm_progress": False,
}

def get_guild_settings(guild_id: Optional[int]) -> dict:
    cfg = load_config()
    gs = cfg.get("guild_settings", {}).get(str(guild_id or 0), {})
    return {**SETTING_DEFAULTS, **gs}

def set_guild_setting(guild_id: Optional[int], key: str, value):
    cfg = load_config()
    cfg.setdefault("guild_settings", {}).setdefault(str(guild_id or 0), {})[key] = value
    save_config(cfg)

def load_saved_accounts(guild_id: int) -> dict:
    cfg = load_config()
    return cfg.get("saved_accounts", {}).get(str(guild_id), {})

def save_saved_account(guild_id: int, label: str, username: str, password: str, token: str = ""):
    cfg = load_config()
    cfg.setdefault("saved_accounts", {}).setdefault(str(guild_id), {})[label] = {"username": username, "password": password, "token": token}
    save_config(cfg)

def delete_saved_account(guild_id: int, label: str):
    cfg = load_config()
    cfg.get("saved_accounts", {}).get(str(guild_id), {}).pop(label, None)
    save_config(cfg)

# ─── API helpers ──────────────────────────────────────────────────────────

async def do_login(username: str, password: str) -> Tuple[bool, str]:
    try:
        client = LNApiClient()
        result = await client.login(username, password)
        if client.token or result.get("newToken"):
            if not client.token:
                client.token = result.get("newToken")
        return True, client.token
        return False, result.get("msg", "No token")
    except Exception as e:
        return False, str(e)

async def get_homeworks(token: str) -> list:
    try:
        client = LNApiClient()
        client.token = token
        data = await client.call_lnut("assignmentController/getViewableAll", {"token": token})
        hws = data.get("assignments", data.get("list", data.get("homework", [])))
        if isinstance(hws, dict):
            return list(hws.values())
        return hws if isinstance(hws, list) else []
    except Exception as e:
        logger.warning(f"get_homeworks failed: {e}")
        return []

async def check_health(username: str, password: str) -> dict:
    try:
        ok, token = await do_login(username, password)
        if not ok:
            return {"banned": True, "status": "login_failed", "error_message": token, "stats": {}}
        client = LNApiClient(); client.token = token
        try:
            stats = await client.call_lnut("stats/get", {"token": token})
        except Exception:
            stats = {}
        return {"banned": False, "status": "healthy", "stats": stats or {}, "error_message": "", "token": token}
    except Exception as e:
        return {"banned": True, "status": "error", "error_message": str(e), "stats": {}}

# ─── Hub embed ────────────────────────────────────────────────────────────

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

# ─── Login Modal ──────────────────────────────────────────────────────────

class LoginModal(ui.Modal, title="Login to LanguageNut"):
    def __init__(self, guild_id: Optional[int]):
        super().__init__(); self.guild_id = guild_id
    username = ui.TextInput(label="Username")
    password = ui.TextInput(label="Password", style=discord.TextStyle.short)
    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, msg = await do_login(self.username.value, self.password.value)
        if ok:
            save_account(self.guild_id, self.username.value, self.password.value)
            e = EmbedBuilder.success("Logged In", f"Account: **{self.username.value}**", footer_text="Languagenut | Powered by Manus AI")
        else:
            e = EmbedBuilder.error("Login Failed", str(msg), footer_text="Languagenut | Powered by Manus AI")
        await interaction.followup.send(embed=e, ephemeral=True)

# ─── Save Account Modal ───────────────────────────────────────────────────

class SaveAccountModal(ui.Modal, title="Save Account"):
    def __init__(self, guild_id: Optional[int]):
        super().__init__(); self.guild_id = guild_id
    label = ui.TextInput(label="Label", placeholder="e.g. Main, Alt1")
    username = ui.TextInput(label="Username")
    password = ui.TextInput(label="Password", style=discord.TextStyle.short)
    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(self.username.value, self.password.value)
        if ok:
            save_saved_account(self.guild_id or 0, self.label.value, self.username.value, self.password.value, token)
            e = EmbedBuilder.success("Account Saved", f"**{self.label.value}** → `{self.username.value}`", footer_text="Languagenut | Powered by Manus AI")
        else:
            e = EmbedBuilder.error("Login Failed", token, footer_text="Languagenut | Powered by Manus AI")
        await interaction.followup.send(embed=e, ephemeral=True)

# ─── Hub View ─────────────────────────────────────────────────────────────

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
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        if not hws: return await interaction.followup.send("No homeworks found.", ephemeral=True)
        lines = []
        for hw in hws[:15]:
            title = hw.get("title", hw.get("name", "Untitled"))
            status = "✅" if hw.get("completed") else "📝"
            lines.append(f"{status} **{title}**")
        e = EmbedBuilder.homework_embed("Homeworks", "\n".join(lines), EmbedBuilder.COLORS["info"], footer_text="Languagenut | Powered by Manus AI")
        await interaction.followup.send(embed=e, ephemeral=True)

    @ui.button(label="🥇 Leaderboard", style=discord.ButtonStyle.primary, row=0)
    async def leaderboard_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        try:
            client = LNApiClient(); client.token = token
            data = await client.call_lnut("highscoreController/studentsAllAccount", {"token": token, "accountUid": ""})
        except Exception as e: return await interaction.followup.send(f"Error: {e}", ephemeral=True)
        students = data.get("list", []) if isinstance(data, dict) else []
        if isinstance(students, list) and students:
            lines = []
            for i, s in enumerate(students[:15]):
                name = s.get("name", f"P{i+1}")
                pts = int(s.get("score", 0))
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`#{i+1}`"
                lines.append(f"{medal} **{name}** — {pts:,} pts")
            e = EmbedBuilder.info("Leaderboard", "\n".join(lines), footer_text="Languagenut | Powered by Manus AI")
        else:
            e = EmbedBuilder.warning("Leaderboard", "No data.", footer_text="Languagenut | Powered by Manus AI")
        await interaction.followup.send(embed=e, ephemeral=True)

    @ui.button(label="❤️ Health", style=discord.ButtonStyle.secondary, row=1)
    async def health_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        health = await check_health(uname, pwd)
        if health.get("banned"):
            e = EmbedBuilder.error("Account Issue", f"**{health['status']}**: {health['error_message']}")
        else:
            stats = health.get("stats", {})
            e = EmbedBuilder.success("Healthy", f"Tasks: **{stats.get('tasks', 'N/A')}**\nPoints: **{int(stats.get('points', 0)):,}**")
        await interaction.followup.send(embed=e, ephemeral=True)

    @ui.button(label="⚡ Farm XP", style=discord.ButtonStyle.success, row=1)
    async def farm_btn(self, interaction: Interaction, btn: ui.Button):
        uname, pwd = load_account(self.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        languages = set()
        for hw in hws:
            lang = hw.get("language", "")
            if lang: languages.add(lang.lower())
        if not languages: languages = set(CURRICULUM_UIDS.keys())
        view = FarmLanguageSelect(self.guild_id or 0, token, sorted(languages))
        e = EmbedBuilder.info("Farm XP", "Select a language:")
        await interaction.followup.send(embed=e, view=view, ephemeral=True)

    @ui.button(label="📝 Auto-Task", style=discord.ButtonStyle.success, row=1)
    async def task_btn(self, interaction: Interaction, btn: ui.Button):
        """Select & autocomplete a homework task with progress bar."""
        uname, pwd = load_account(self.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login failed: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        if not hws: return await interaction.followup.send("No homeworks found.", ephemeral=True)
        view = HomeworkSelectView(self.guild_id or 0, token, hws)
        e = EmbedBuilder.info("Auto-Task", "Select a homework, then a task to autocomplete:\n\nThe bot will submit game data to complete the task and report progress.")
        await interaction.followup.send(embed=e, view=view, ephemeral=True)

    @ui.button(label="💾 Saved", style=discord.ButtonStyle.secondary, row=1)
    async def saved_btn(self, interaction: Interaction, btn: ui.Button):
        accounts = load_saved_accounts(self.guild_id or 0)
        if not accounts:
            return await interaction.response.send_message("No saved accounts. Use `/save` to add one.", ephemeral=True)
        lines = []
        for label, info in accounts.items():
            lines.append(f"• **{label}** (`{info.get('username', label)}`)")
        e = EmbedBuilder.info("Saved Accounts", "\n".join(lines))
        await interaction.response.send_message(embed=e, ephemeral=True)

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.secondary, row=2)
    async def settings_btn(self, interaction: Interaction, btn: ui.Button):
        settings = get_guild_settings(self.guild_id)
        lines = [f"• **{k.replace('_', ' ').title()}**: `{v}`" for k, v in settings.items()]
        e = EmbedBuilder.info("Settings", "\n".join(lines))
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
        await interaction.response.send_message(f"📬 DM: **{'On' if new_val else 'Off'}**", ephemeral=True)

    @ui.button(label="🔄 Refresh", style=discord.ButtonStyle.gray, row=2)
    async def refresh_btn(self, interaction: Interaction, btn: ui.Button):
        await interaction.response.defer()
        e = build_hub_embed(self.guild_id)
        v = HubView(self.guild_id)
        await interaction.edit_original_response(embed=e, view=v)

# ─── Homework Select (for task autocomplete) ──────────────────────────────

class HomeworkSelectView(ui.View):
    def __init__(self, guild_id: int, token: str, homeworks: list):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.token = token
        self.homeworks = homeworks
        opts = []
        for i, hw in enumerate(homeworks[:25]):
            title = hw.get("title", hw.get("name", f"HW {i+1}"))
            emoji = "✅" if hw.get("completed") else "📝"
            opts.append(discord.SelectOption(label=title[:50], value=str(i), emoji=emoji))
        if not opts:
            opts.append(discord.SelectOption(label="No homeworks", value="-1"))
        self.add_item(HomeworkSelect(opts))

class HomeworkSelect(ui.Select):
    def __init__(self, options: list):
        super().__init__(placeholder="Choose a homework...", options=options, row=0)
    async def callback(self, interaction: Interaction):
        idx = int(self.values[0])
        if idx < 0: return await interaction.response.send_message("No homeworks.", ephemeral=True)
        view = self.view
        hw = view.homeworks[idx]
        tasks = hw.get("tasks", [])
        if not tasks: return await interaction.response.send_message("No tasks.", ephemeral=True)
        # Calculate overall progress for this homework
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("gameResults", {}).get("percentage", 0) >= 100)
        pct = done / total if total > 0 else 0
        opts = []
        for i, t in enumerate(tasks):
            name = t.get("translation", t.get("name", f"Task {i+1}"))
            try:
                p = int(t.get("gameResults", {}).get("percentage", 0))
            except (ValueError, TypeError):
                p = 0
            emoji = "✅" if p >= 100 else "🟡" if p > 0 else "⬜"
            opts.append(discord.SelectOption(label=f"{name[:40]} ({p}%)", value=str(i), emoji=emoji))
        embed = discord.Embed(
            title=f"📝 {hw.get('title', hw.get('name', 'Homework'))}",
            colour=GREEN,
            description=f"Progress: `{_progress_bar(pct)}` **{done}/{total}**\nSelect a task to autocomplete:"
        )
        task_view = TaskSelectView(view.guild_id, view.token, view.homeworks, idx, tasks)
        await interaction.response.edit_message(embed=embed, view=task_view)

class TaskSelectView(ui.View):
    def __init__(self, guild_id: int, token: str, homeworks: list, hw_idx: int, tasks: list):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.token = token
        self.homeworks = homeworks
        self.hw_idx = hw_idx
        self.tasks = tasks
        opts = []
        for i, t in enumerate(tasks):
            name = t.get("translation", t.get("name", f"Task {i+1}"))
            try:
                p = int(t.get("gameResults", {}).get("percentage", 0))
            except (ValueError, TypeError):
                p = 0
            emoji = "✅" if p >= 100 else "🟡" if p > 0 else "⬜"
            opts.append(discord.SelectOption(label=f"{name[:40]} ({p}%)", value=str(i), emoji=emoji))
        self.add_item(TaskSelect(opts))

class TaskSelect(ui.Select):
    def __init__(self, options: list):
        super().__init__(placeholder="Select a task...", options=options, row=0)
    async def callback(self, interaction: Interaction):
        idx = int(self.values[0])
        view = self.view
        task = view.tasks[idx]
        await interaction.response.defer()
        embed = discord.Embed(title="⏳ Auto-completing...", colour=AMBER,
                              description=f"Task: **{task.get('translation', task.get('name', 'Task'))}**\n")
        msg = await interaction.followup.send(embed=embed)
        asyncio.create_task(autocomplete_task(interaction, msg, view.guild_id, view.token, task))

# ─── Task Autocomplete Runner ─────────────────────────────────────────────

async def autocomplete_task(interaction, msg, guild_id, token, task):
    """Auto-complete a single task with progress bar."""
    client = LNApiClient(); client.token = token
    uname, _ = load_account(guild_id)
    stealth = StealthManager(speed=10, min_accuracy=88, max_accuracy=95)
    stealth.username = uname or "unknown"
    language = task.get("language", "spanish").lower()
    curriculum_uid = task.get("curriculumUid") or CURRICULUM_UIDS.get(language, 54)

    total_xp = 0
    rounds = 6  # 6 rounds for a full task completion
    try:
        for rnd in range(1, rounds + 1):
            try:
                vocab = await client.get_game_vocab(curriculum_uid)
                items = vocab.get("vocab", vocab.get("list", []))
                if not items:
                    await asyncio.sleep(2)
                    continue
                ci, ii = stealth.determine_accuracy(len(items))
                correct_uids = [items[i].get("uid", "") for i in ci if i < len(items)]
                incorrect_uids = [items[i].get("uid", "") for i in ii if i < len(items)]
                result = await client.add_game_score(correct_uids, incorrect_uids)
                xp = int(result.get("score", result.get("xp", 0)))
                total_xp += xp
                # Progress bar
                pct = rnd / rounds
                bar = _progress_bar(pct)
                embed = discord.Embed(title=f"📝 {task.get('translation', 'Task')}", colour=AMBER,
                    description=f"`{bar}` **{rnd}/{rounds}** ({int(pct*100)}%)\nXP: **{total_xp:,}**")
                await msg.edit(embed=embed)
                await asyncio.sleep(stealth.delay_between_tasks())
            except Exception as e:
                logger.warning(f"Task round {rnd}: {e}")
                await asyncio.sleep(3)
        # Complete!
        bar = _progress_bar(1.0)
        embed = discord.Embed(title="✅ Task Completed!", colour=GREEN,
            description=f"**{task.get('translation', 'Task')}**\n`{bar}` **100%**\nXP earned: **{total_xp:,}**")
        await msg.edit(embed=embed)
    except Exception as e:
        logger.error(f"Autocomplete error: {traceback.format_exc()}")
        embed = discord.Embed(title="❌ Failed", colour=RED, description=str(e))
        await msg.edit(embed=embed)

# ─── Farm Language Select ─────────────────────────────────────────────────

class FarmLanguageSelect(ui.View):
    def __init__(self, guild_id: int, token: str, languages: list):
        super().__init__(timeout=120)
        self.guild_id = guild_id; self.token = token
        opts = []
        for lang in languages:
            cid = CURRICULUM_UIDS.get(lang.lower())
            if cid: opts.append(discord.SelectOption(label=lang.title(), value=f"{lang.lower()}|{cid}", emoji="🌐"))
        if not opts: opts.append(discord.SelectOption(label="No languages", value="none"))
        self.add_item(FarmLangSelect(opts))

class FarmLangSelect(ui.Select):
    def __init__(self, options: list):
        super().__init__(placeholder="Choose language...", options=options[:25], row=0)
    async def callback(self, interaction: Interaction):
        if self.values[0] == "none": return await interaction.response.send_message("No languages.", ephemeral=True)
        lang, cid_str = self.values[0].split("|")
        cid = int(cid_str)
        view = self.view
        await interaction.response.defer()
        settings = get_guild_settings(view.guild_id)
        rounds = settings.get("rounds", 20)
        embed = discord.Embed(title=f"⚡ Farming {lang.title()}", colour=GREEN,
                              description=f"Starting {rounds} rounds...")
        msg = await interaction.followup.send(embed=embed)
        asyncio.create_task(run_xp_farm(view.guild_id, view.token, cid, lang, settings, msg))

async def run_xp_farm(guild_id, token, curriculum_uid, language, settings, msg):
    """Farm XP with progress bar."""
    client = LNApiClient(); client.token = token
    uname, _ = load_account(guild_id)
    rounds = settings.get("rounds", 20)
    stealth = StealthManager(speed=settings.get("speed", 10), min_accuracy=settings.get("min_accuracy", 85), max_accuracy=settings.get("max_accuracy", 92))
    stealth.username = uname or "unknown"
    total_xp = 0
    try:
        for r in range(1, rounds + 1):
            try:
                vocab = await client.get_game_vocab(curriculum_uid)
                items = vocab.get("vocab", vocab.get("list", []))
                if not items:
                    await asyncio.sleep(3); continue
                ci, ii = stealth.determine_accuracy(len(items))
                correct_uids = [items[i].get("uid", "") for i in ci if i < len(items)]
                incorrect_uids = [items[i].get("uid", "") for i in ii if i < len(items)]
                result = await client.add_game_score(correct_uids, incorrect_uids)
                xp = int(result.get("score", result.get("xp", 0)))
                total_xp += xp
                if r % 3 == 0 or r == rounds:
                    pct = r / rounds
                    bar = _progress_bar(pct)
                    embed = discord.Embed(title=f"⚡ {language.title()}", colour=GREEN,
                        description=f"Round `{r}/{rounds}`\n`{bar}` **{int(pct*100)}%**\nXP: **{total_xp:,}**")
                    await msg.edit(embed=embed)
                await asyncio.sleep(stealth.delay_between_tasks())
            except Exception as e:
                logger.warning(f"Farm round {r}: {e}"); await asyncio.sleep(5)
        bar = _progress_bar(1.0)
        embed = discord.Embed(title=f"✅ Farm Complete - {language.title()}", colour=GREEN,
            description=f"`{bar}` **100%**\nRounds: {rounds}\nTotal XP: **{total_xp:,}**")
        await msg.edit(embed=embed)
        if settings.get("dm_progress"):
            try: await msg.author.send(embed=embed)
            except: pass
    except Exception as e:
        logger.error(f"Farm error: {traceback.format_exc()}")
        embed = discord.Embed(title="❌ Farm Error", colour=RED, description=str(e))
        await msg.edit(embed=embed)

# ─── Settings View ────────────────────────────────────────────────────────

SETTING_OPTIONS = {
    "speed":           ("Speed",          [(f"{v}x", v) for v in [5, 8, 10, 12, 15]]),
    "min_accuracy":    ("Min Accuracy",   [(f"{v}%", v) for v in [75, 80, 85, 88, 90, 92]]),
    "max_accuracy":    ("Max Accuracy",   [(f"{v}%", v) for v in [88, 90, 92, 95, 98]]),
    "rounds":          ("Rounds",         [(str(v), v) for v in [5, 10, 15, 20, 30, 40, 50]]),
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
                opts.append(discord.SelectOption(label=f"{opt_label}" + (" ✓" if is_def else ""), value=f"{key}:{opt_val}", default=is_def))
            select = ui.Select(placeholder=f"{label}: {current}", options=opts[:25], row=row, custom_id=f"st_{key}_{id(self)}")
            async def cb(interaction: Interaction, k=key, l=label):
                val = interaction.data["values"][0].split(":", 1)[1]
                parsed = int(val) if val.lstrip("-").isdigit() else val
                set_guild_setting(self.guild_id, k, parsed)
                e = EmbedBuilder.success("Settings Updated", f"**{l}** → `{parsed}`")
                await interaction.response.edit_message(embed=e, view=SettingsView(self.guild_id))
            select.callback = cb
            self.add_item(select)

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
        await interaction.response.send_message(embed=EmbedBuilder.success("Logged Out", ""), ephemeral=True)

    @app_commands.command(name="status", description="Account stats")
    async def status(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        health = await check_health(uname, pwd)
        if health.get("banned"): return await interaction.followup.send(f"Login failed: {health['error_message']}", ephemeral=True)
        stats = health.get("stats", {})
        e = discord.Embed(title="Status", colour=BLUE)
        e.add_field(name="Username", value=uname, inline=True)
        e.add_field(name="Tasks", value=str(stats.get("tasks", "N/A")), inline=True)
        e.add_field(name="Points", value=str(stats.get("points", "N/A")), inline=True)
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="homeworks", description="List homeworks")
    async def homeworks(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        if not hws: return await interaction.followup.send("No homeworks found.", ephemeral=True)
        lines = []
        for hw in hws[:20]:
            title = hw.get("title", hw.get("name", "Unknown"))
            tasks = hw.get("tasks", [])
            done = sum(1 for t in tasks if t.get("gameResults", {}).get("percentage", 0) >= 100)
            total = len(tasks)
            bar = _progress_bar(done/total if total > 0 else 0, 10)
            status = "✅" if hw.get("completed") else "📝"
            lines.append(f"{status} **{title}**\n`{bar}` {done}/{total}")
        e = EmbedBuilder.homework_embed("Homeworks", "\n".join(lines), EmbedBuilder.COLORS["info"], footer_text="Languagenut | Powered by Manus AI")
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="leaderboard", description="View rankings")
    async def leaderboard(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login: {token}", ephemeral=True)
        try:
            client = LNApiClient(); client.token = token
            data = await client.call_lnut("highscoreController/studentsAllAccount", {"token": token, "accountUid": ""})
        except Exception as e: return await interaction.followup.send(f"Error: {e}", ephemeral=True)
        students = data.get("list", []) if isinstance(data, dict) else []
        e = discord.Embed(title="🥇 Leaderboard", colour=AMBER)
        if isinstance(students, list) and students:
            for i, s in enumerate(students[:15]):
                name = s.get("name", f"P{i+1}")
                pts = int(s.get("score", 0))
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`#{i+1}`"
                e.add_field(name=f"{medal} {name}", value=f"{pts:,} pts", inline=False)
        else: e.description = "No data."
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name="save", description="Save an account")
    async def save_cmd(self, interaction: Interaction, label: str, username: str, password: str):
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(username, password)
        if not ok: return await interaction.followup.send(f"❌ {token}", ephemeral=True)
        save_saved_account(interaction.guild_id or 0, label, username, password, token)
        await interaction.followup.send(embed=EmbedBuilder.success("Saved", f"`{label}` → **{username}**"), ephemeral=True)

    @app_commands.command(name="settings", description="Configure bot")
    async def settings_cmd(self, interaction: Interaction):
        settings = get_guild_settings(interaction.guild_id)
        lines = [f"• **{k.replace('_', ' ').title()}**: `{v}`" for k, v in settings.items()]
        e = EmbedBuilder.info("Settings", "\n".join(lines))
        await interaction.response.send_message(embed=e, view=SettingsView(interaction.guild_id), ephemeral=True)

    @app_commands.command(name="autotask", description="Auto-complete a homework task")
    async def autotask(self, interaction: Interaction):
        uname, pwd = load_account(interaction.guild_id)
        if not uname: return await interaction.response.send_message("Not logged in.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, token = await do_login(uname, pwd)
        if not ok: return await interaction.followup.send(f"Login: {token}", ephemeral=True)
        hws = await get_homeworks(token)
        if not hws: return await interaction.followup.send("No homeworks.", ephemeral=True)
        view = HomeworkSelectView(interaction.guild_id or 0, token, hws)
        await interaction.followup.send(embed=EmbedBuilder.info("Auto-Task", "Select a homework, then a task to autocomplete:"), view=view, ephemeral=True)

    @app_commands.command(name="dmprogress", description="Toggle DM notifications")
    async def dm_progress(self, interaction: Interaction):
        settings = get_guild_settings(interaction.guild_id)
        new_val = not settings.get("dm_progress", False)
        set_guild_setting(interaction.guild_id, "dm_progress", new_val)
        await interaction.response.send_message(f"📬 DM: **{'On' if new_val else 'Off'}**", ephemeral=True)

    @app_commands.command(name="shutdown", description="[Owner] Shutdown")
    async def shutdown(self, interaction: Interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Owner only.", ephemeral=True)
        await interaction.response.send_message("🔴 Shutting down...", ephemeral=True)
        await self.bot.close()

    @app_commands.command(name="sync", description="[Owner] Sync commands")
    async def sync(self, interaction: Interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Owner only.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ Synced {len(synced)}.", ephemeral=True)
        except Exception as e: await interaction.followup.send(f"❌ {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Commands(bot))
    logger.info("Commands cog loaded")
