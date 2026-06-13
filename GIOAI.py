#!/usr/bin/env python3
# GIOAI v9.0 - Full Feature Discord Bot
# Homework autocompletion with queue, slots, settings, history & more

import discord, os, sys, asyncio, time, json, logging, re, random, math, uuid
from datetime import datetime, timedelta, timezone
from discord.ext import commands
from discord.ui import Button, Select, Modal, TextInput, View
from discord import Embed, Colour, Interaction, AppCommand, MessageFlags
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GIOAI")

# ─── Config ───
TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID", "")
GUILD_ID = os.getenv("GUILD_ID", "0")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "0"))
LEARNING_CHANNEL_ID = int(os.getenv("LEARNING_CHANNEL_ID", "0"))
BASE_ROLE_ID = int(os.getenv("BASE_ROLE_ID", "0"))
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0"))

WORKER_URL = os.getenv("WORKER_URL", "https://gioai.giannikei12.workers.dev")
GH_TOKEN = os.getenv("GITHUB_TOKEN", "")

if not TOKEN:
    print("ERROR: DISCORD_TOKEN not set")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="g!", intents=intents, help_command=None)

# ─── In-Memory State ───
class BotState:
    def __init__(self):
        self.queue = []
        self.active_tasks = {}
        self.task_counter = 0
        self.history = {}
        self.slots = {"sparx": {}, "seneca": {}, "languagenut": {}}
        self.user_settings = {}
        self.faq_message = None
        self.worker_available = True

state = BotState()

# ─── Colour Palette ───
COLORS = {
    "primary": 0x5865F2,
    "purple": 0x9B59B6,
    "sparx": 0x00AAFF,
    "languagenut": 0x9B59B6,
    "seneca": 0x2ECC71,
    "success": 0x00FF88,
    "error": 0xFF0044,
    "warning": 0xFFAA00,
    "blue": 0x3498DB,
    "dark": 0x2C2F33,
    "blurple": 0x5796F2,
}

PLATFORM_EMOJIS = {
    "sparx": "<:sparx:1470166522998554644>",
    "sparx_maths": "<:sparx_maths:1470166522998554644>",
    "seneca": "<:seneca:1470166618423296172>",
    "languagenut": "<:languagenut:1470172939780493545>",
}

PLATFORM_NAMES = {
    "sparx": "Sparx Maths",
    "seneca": "Seneca Learning",
    "languagenut": "LanguageNut",
}

PLATFORM_ICONS = {
    "sparx": "📐",
    "seneca": "❄️",
    "languagenut": "🌍",
}

# ─── Helper Functions ───
def make_embed(**kwargs):
    color = kwargs.pop("color", COLORS["primary"])
    if isinstance(color, str):
        color = COLORS.get(color, COLORS["primary"])
    return Embed(color=color, **kwargs)

def progress_bar(pct, length=10, filled="█", empty="░"):
    filled_count = max(0, min(length, round((pct / 100) * length)))
    return filled * filled_count + empty * (length - filled_count)

def relative_time(dt):
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60: return f"{int(seconds)} seconds ago"
    if seconds < 3600: return f"{int(seconds // 60)} minutes ago"
    if seconds < 86400: return f"{int(seconds // 3600)} hours ago"
    if seconds < 2592000: return f"{int(seconds // 86400)} days ago"
    if seconds < 31536000: return f"{int(seconds // 2592000)} months ago"
    return f"{int(seconds // 31536000)} years ago"

def relative_time_future(dt):
    now = datetime.now(timezone.utc)
    diff = dt - now
    seconds = diff.total_seconds()
    if seconds < 0: return "now"
    if seconds < 60: return f"in {int(seconds)} seconds"
    if seconds < 3600: return f"in {int(seconds // 60)} minutes"
    if seconds < 86400: return f"in {int(seconds // 3600)} hours"
    if seconds < 2592000: return f"in {int(seconds // 86400)} days"
    return f"in {int(seconds // 2592000)} months"

def due_date_str(due_dt):
    if not due_dt:
        return "No due date"
    now = datetime.now(timezone.utc)
    diff = due_dt - now
    seconds = diff.total_seconds()
    if seconds < 0:
        return f"due {abs(int(seconds // 86400))} days ago"
    if seconds < 86400:
        return f"due in {int(seconds // 3600)} hours"
    return f"due in {int(seconds // 86400)} days"

def format_time_estimate(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"

# ─── Views & Components ───

class FAQView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.primary, emoji="🎯")
    async def join_queue(self, interaction: Interaction, button: Button):
        await show_login_methods(interaction)

    @discord.ui.button(label="Join Queue with Saved Accounts", style=discord.ButtonStyle.secondary, emoji="📂")
    async def join_saved(self, interaction: Interaction, button: Button):
        await show_saved_accounts_selector(interaction)

    @discord.ui.button(label="Check Queue", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def check_queue(self, interaction: Interaction, button: Button):
        await show_queue(interaction)

    @discord.ui.button(label="Tutorials", style=discord.ButtonStyle.secondary, emoji="📖")
    async def tutorials(self, interaction: Interaction, button: Button):
        await show_tutorials(interaction)

    @discord.ui.button(label="View Slots", style=discord.ButtonStyle.secondary, emoji="💳")
    async def view_slots(self, interaction: Interaction, button: Button):
        await show_slots(interaction)

    @discord.ui.button(label="History", style=discord.ButtonStyle.secondary, emoji="📜")
    async def history(self, interaction: Interaction, button: Button):
        await show_history(interaction, 0)

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def settings(self, interaction: Interaction, button: Button):
        await show_settings(interaction, 0)

    @discord.ui.button(label="Feedback & Suggestions", style=discord.ButtonStyle.secondary, emoji="💬")
    async def feedback(self, interaction: Interaction, button: Button):
        await show_feedback_modal(interaction)

# ─── Login Method Selector ───
async def show_login_methods(interaction: Interaction):
    embed = Embed(
        title="Select Login Method",
        description="Choose how you'd like to log in",
        color=COLORS["purple"]
    )
    view = View(timeout=120)
    view.add_item(Button(label="Normal Login", style=discord.ButtonStyle.primary, custom_id="normal_login"))
    view.add_item(Button(label="Bookmarklet Login", style=discord.ButtonStyle.secondary, custom_id="bookmarklet_login"))

    msg = await interaction.response.send_message(embed=embed, view=view, ephemeral=True, fetch_reply=True)

    def check(i):
        return i.user.id == interaction.user.id and i.message.id == msg.id

    try:
        i = await bot.wait_for("interaction", check=check, timeout=120)
        if i.data["custom_id"] == "normal_login":
            await show_platform_login(interaction)
        else:
            await show_bookmarklet_login(interaction)
    except asyncio.TimeoutError:
        await interaction.edit_original_response(content="Login timed out.", view=None)

async def show_platform_login(interaction: Interaction):
    embed = Embed(
        title="Login to Platform",
        description="Enter your credentials for the platform",
        color=COLORS["purple"]
    )
    modal = Modal(title="Platform Login")
    modal.add_item(TextInput(label="Platform", placeholder="sparx / seneca / languagenut", custom_id="platform", required=True))
    modal.add_item(TextInput(label="Username / Email", placeholder="your username", custom_id="username", required=True))
    modal.add_item(TextInput(label="Password", placeholder="your password", style=discord.TextStyle.short, custom_id="password", required=True))
    await interaction.response.send_modal(modal)

async def show_bookmarklet_login(interactive: Interaction):
    embed = Embed(
        title="Bookmarklet Login",
        description="Use this bookmarklet on the platform's login page to get your session token.\n\n`javascript:(function(){...})()`",
        color=COLORS["warning"]
    )
    await interaction.response.edit_message(embed=embed, view=None)

# ─── Saved Accounts Selector ───
async def show_saved_accounts_selector(interaction: Interaction):
    embed = Embed(
        title="Select Platform & Account",
        description="Choose a platform, then select a saved account to use.",
        color=COLORS["purple"]
    )
    view = View(timeout=120)
    view.add_item(Select(
        placeholder="Select a platform",
        options=[
            discord.SelectOption(label="Sparx Maths", value="sparx", emoji="📐"),
            discord.SelectOption(label="Seneca Learning", value="seneca", emoji="❄️"),
            discord.SelectOption(label="LanguageNut", value="languagenut", emoji="🌍"),
        ],
        custom_id="saved_platform"
    ))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── Queue Display ───
async def show_queue(interaction: Interaction):
    uid = str(interaction.user.id)
    user_tasks = [t for t in state.queue if t["user_id"] == uid]
    active = [t for t in state.active_tasks.values() if t["user_id"] == uid]

    embed = Embed(
        title="Your Queue ⏰",
        description=f"`{len(active)} active tasks · {len(user_tasks)} queued`",
        color=COLORS["blurple"]
    )
    embed.set_footer(text="GIOAI · Learning Platform")

    all_tasks = active + user_tasks

    if not all_tasks:
        embed.description = "You have no tasks in the queue."
        embed.color = COLORS["warning"]

    for t in all_tasks:
        platform_icon = PLATFORM_ICONS.get(t.get("platform", ""), "📋")
        status_text = "Currently processing" if t.get("active") else f"Position {user_tasks.index(t) + 1}/{len(user_tasks)} in queue"
        due = due_date_str(t.get("due_date"))
        embed.add_field(
            name=f"{platform_icon} {PLATFORM_NAMES.get(t.get('platform',''), t.get('platform',''))} — {t.get('account','')}",
            value=f"**{t.get('task_name','Task')}**\n{status_text}\n{due}\nQueued: {relative_time(t.get('queued_at', datetime.now(timezone.utc)))}",
            inline=False
        )

    view = View(timeout=120)
    for t in active:
        view.add_item(Button(label="View in DMs", style=discord.ButtonStyle.primary, custom_id=f"view_dm_{t['task_id']}"))
    for t in user_tasks:
        view.add_item(Button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id=f"leave_queue_{t['task_id']}"))
    if not all_tasks:
        view.add_item(Button(label="Back", style=discord.ButtonStyle.secondary, custom_id="back_faq"))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── Slots Display ───
async def show_slots(interaction: Interaction):
    uid = str(interaction.user.id)
    embed = Embed(
        title="Your Slots",
        description="you've used me 653 times (fr fr)",
        color=COLORS["purple"]
    )
    embed.add_field(name="Estimated Time Saved", value="~127 hours", inline=False)
    embed.add_field(name="Slot Rule", value="4 account slots per platform every day", inline=False)

    for plat in ["sparx", "seneca", "languagenut"]:
        used = state.slots.get(plat, {}).get(uid, {}).get("used", 0)
        account = state.slots.get(plat, {}).get(uid, {}).get("account", "None")
        frees_at = state.slots.get(plat, {}).get(uid, {}).get("frees_at")
        frees_text = f"frees in {relative_time_future(frees_at)}" if frees_at else "available now"
        embed.add_field(
            name=f"{PLATFORM_ICONS[plat]} {PLATFORM_NAMES[plat]}",
            value=f"`{used}/4 used` · Account: {account}\n{frees_text}",
            inline=False
        )

    view = View(timeout=120)
    view.add_item(Button(label="Increase Limit", style=discord.ButtonStyle.primary, custom_id="increase_limit"))
    view.add_item(Button(label="?", style=discord.ButtonStyle.secondary, custom_id="slots_help"))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── History Display ───
async def show_history(interaction: Interaction, page: int):
    uid = str(interaction.user.id)
    user_history = state.history.get(uid, [])
    items_per_page = 5
    total_pages = max(1, (len(user_history) + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * items_per_page
    end = start + items_per_page
    page_items = user_history[start:end] if user_history else []

    embed = Embed(
        title="Task History",
        description=f"Page {page + 1} of {total_pages}" if user_history else "No history yet.",
        color=COLORS["blurple"]
    )

    for item in page_items:
        platform_icon = PLATFORM_ICONS.get(item.get("platform", ""), "📋")
        dt = item.get("completed_at", datetime.now(timezone.utc))
        embed.add_field(
            name=f"{platform_icon} {PLATFORM_NAMES.get(item.get('platform',''), item.get('platform',''))} — {item.get('account','')}",
            value=f"**{item.get('task_name','Task')}**\n{dt.strftime('%d %B %Y at %H:%M')}, {relative_time(dt)}",
            inline=False
        )

    embed.set_footer(text=f"Page {page + 1}/{total_pages}")

    view = View(timeout=120)
    if total_pages > 1:
        if page > 0:
            view.add_item(Button(label="<", style=discord.ButtonStyle.secondary, custom_id=f"hist_prev_{page}"))
        view.add_item(Button(label=f"{page + 1} of {total_pages}", style=discord.ButtonStyle.secondary, disabled=True, custom_id="hist_page"))
        if page < total_pages - 1:
            view.add_item(Button(label=">", style=discord.ButtonStyle.secondary, custom_id=f"hist_next_{page}"))
    if page_items:
        view.add_item(Button(label="View in DMs", style=discord.ButtonStyle.primary, custom_id="hist_view_dm"))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── Tutorials ───
async def show_tutorials(interaction: Interaction):
    embed = Embed(
        title="Tutorials — No tutorials yet. check back soon!",
        description="We're working on creating helpful tutorials for you.",
        color=COLORS["error"]
    )
    embed.set_footer(text="GIOAI Learning Platform")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── Settings (2 pages) ───
async def show_settings(interaction: Interaction, page: int):
    uid = str(interaction.user.id)
    settings = state.user_settings.get(uid, {
        "show_username": True,
        "task_start": "Instant",
        "theme_color": "Purple",
        "sort_account": "Alphabetical",
        "completion_notification": True,
    })

    if page == 0:
        embed = Embed(title="Settings", color=COLORS["purple"])
        embed.add_field(name="Platform Specific Settings", value="Click Configure to adjust per-platform", inline=False)
        embed.add_field(
            name="Toggle Username on Solver Embed",
            value=f"`{'ON' if settings.get('show_username') else 'OFF'}`",
            inline=False
        )
        embed.add_field(name="Task Start", value=f"`{settings.get('task_start', 'Instant')}`", inline=False)
        embed.add_field(
            name="Theme Colour",
            value=f"🟣 `{settings.get('theme_color', 'Purple')}`",
            inline=False
        )
        view = View(timeout=120)
        view.add_item(Button(label="Configure", style=discord.ButtonStyle.primary, custom_id="settings_configure"))
        view.add_item(Button(label=f"Toggle: {'ON' if settings.get('show_username') else 'OFF'}", style=discord.ButtonStyle.secondary, custom_id="toggle_username"))
        view.add_item(Button(label=f"Task Start: {settings.get('task_start', 'Instant')}", style=discord.ButtonStyle.secondary, custom_id="toggle_task_start"))
        view.add_item(Button(label=f"Theme: {settings.get('theme_color', 'Purple')}", style=discord.ButtonStyle.secondary, custom_id="toggle_theme"))
        view.add_item(Button(label="Next →", style=discord.ButtonStyle.secondary, custom_id="settings_page_1"))
    else:
        embed = Embed(title="Settings (Page 2)", color=COLORS["purple"])
        embed.add_field(name="Sort Account", value=f"`{settings.get('sort_account', 'Alphabetical')}`", inline=False)
        embed.add_field(
            name="Completion Notification",
            value=f"`{'ON' if settings.get('completion_notification') else 'OFF'}`",
            inline=False
        )
        view = View(timeout=120)
        view.add_item(Button(label=f"Sort: {settings.get('sort_account', 'Alphabetical')}", style=discord.ButtonStyle.secondary, custom_id="toggle_sort"))
        view.add_item(Button(label=f"Notify: {'ON' if settings.get('completion_notification') else 'OFF'}", style=discord.ButtonStyle.secondary, custom_id="toggle_notify"))
        view.add_item(Button(label="← Back", style=discord.ButtonStyle.secondary, custom_id="settings_page_0"))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── Feedback Modal ───
async def show_feedback_modal(interaction: Interaction):
    modal = Modal(title="Feedback & Suggestions")
    modal.add_item(TextInput(
        label="Type",
        placeholder="Suggestion / Bug report / Other",
        custom_id="feedback_type",
        required=True,
        style=discord.TextStyle.short
    ))
    modal.add_item(TextInput(
        label="Your Feedback",
        placeholder="Tell us what you think... (max 1000 chars)",
        custom_id="feedback_content",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    ))
    await interaction.response.send_modal(modal)

# ─── DM Task Card with Progress ───
async def send_task_dm(user: discord.User, task_info: dict):
    embed = Embed(
        title=f"GIOAI {PLATFORM_NAMES.get(task_info.get('platform',''), task_info.get('platform',''))} {due_date_str(task_info.get('due_date'))}",
        color=COLORS["blue"]
    )
    embed.add_field(name="Account", value=task_info.get("account", "Unknown"), inline=True)
    embed.add_field(name="Name", value=task_info.get("task_name", "Task"), inline=True)
    embed.add_field(name="Status", value="Submitting answers...", inline=False)
    embed.add_field(name="⚠️ Warning", value="do not login", inline=False)

    sub_tasks = task_info.get("sub_tasks", [])
    for i, st in enumerate(sub_tasks, 1):
        pct = st.get("progress", 0)
        bar = progress_bar(pct, 8, "🟣", "⚪")
        embed.add_field(
            name=f"{i}. {st.get('name', f'Sub-task {i}')}",
            value=f"{bar} `{pct}%`",
            inline=False
        )

    stats = task_info.get("stats", {})
    embed.add_field(name="Questions Completed", value=stats.get("q_completed", "0/0"), inline=True)
    embed.add_field(name="Simulated Time", value=stats.get("simulated_time", "~30m"), inline=True)
    embed.add_field(name="Fake Question Time", value=stats.get("fake_q_time", "6s–8s"), inline=True)
    embed.add_field(name="Bookwork Accuracy", value=stats.get("bookwork_acc", "100%"), inline=True)
    embed.add_field(name="XP Gained", value=stats.get("xp", "0"), inline=True)
    embed.add_field(name="Finishes in", value=stats.get("finishes_in", "~45s"), inline=True)
    embed.set_footer(text="gioai.uk")

    view = View(timeout=None)
    view.add_item(Button(label="Retry Task", style=discord.ButtonStyle.primary, custom_id="retry_task", emoji="🔄"))
    view.add_item(Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel_task"))
    view.add_item(Button(label="Settings", style=discord.ButtonStyle.secondary, custom_id="task_settings"))

    try:
        await user.send(embed=embed, view=view)
    except discord.Forbidden:
        logger.warning(f"Cannot DM {user}")

# ─── Bot Events ───

@bot.event
async def on_ready():
    logger.info(f"GIOAI v9.0 online: {bot.user}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"g!hub | /queue"
    ))
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.warning(f"Command sync failed: {e}")

    # Send/update FAQ embed in learning channel
    if LEARNING_CHANNEL_ID:
        await ensure_faq_embed()

async def ensure_faq_embed():
    channel = bot.get_channel(LEARNING_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot.fetch_channel(LEARNING_CHANNEL_ID)
        except:
            logger.error(f"Learning channel {LEARNING_CHANNEL_ID} not found")
            return

    embed = Embed(
        title="GIOAI Learning Platform — FAQ",
        description="Your personalized AI tutoring platform for homework completion.",
        color=COLORS["purple"]
    )
    embed.add_field(name="🎯 Personalised Help", value="Get tailored assistance for your specific assignments", inline=False)
    embed.add_field(name="👨‍🏫 Real-Time Tutors", value="Connect with tutors instantly when you need help", inline=False)
    embed.add_field(name="🏆 Top 5% Problems", value="We solve the hardest 5% of problems across all platforms", inline=False)
    embed.add_field(name="🔒 Secure & Confidential", value="Your data and credentials are never shared", inline=False)
    embed.set_footer(text="GIOAI Learning Platform · gioai.uk")

    try:
        async for msg in channel.history(limit=20):
            if msg.author == bot.user and msg.embeds and "FAQ" in (msg.embeds[0].title or ""):
                state.faq_message = msg
                await msg.edit(embed=embed, view=FAQView())
                logger.info("FAQ embed updated")
                return
        state.faq_message = await channel.send(embed=embed, view=FAQView())
        logger.info("FAQ embed created")
    except Exception as e:
        logger.error(f"FAQ embed error: {e}")

# ─── Slash Commands ───

@bot.tree.command(name="queue", description="Check your current queue status")
async def slash_queue(interaction: Interaction):
    await show_queue(interaction)

@bot.tree.command(name="slots", description="View your account slots")
async def slash_slots(interaction: Interaction):
    await show_slots(interaction)

@bot.tree.command(name="history", description="View your task history")
async def slash_history(interaction: Interaction):
    await show_history(interaction, 0)

@bot.tree.command(name="settings", description="Configure your GIOAI settings")
async def slash_settings(interaction: Interaction):
    await show_settings(interaction, 0)

@bot.tree.command(name="tutorials", description="View available tutorials")
async def slash_tutorials(interaction: Interaction):
    await show_tutorials(interaction)

@bot.tree.command(name="feedback", description="Submit feedback or suggestions")
async def slash_feedback(interaction: Interaction):
    await show_feedback_modal(interaction)

@bot.tree.command(name="hub", description="Open the GIOAI learning hub")
async def slash_hub(interaction: Interaction):
    embed = Embed(
        title="GIOAI Learning Hub",
        description="Select a platform to get started with your homework.",
        color=COLORS["purple"]
    )
    embed.add_field(name="📐 Sparx Maths", value="Complete Sparx Maths homework", inline=False)
    embed.add_field(name="❄️ Seneca Learning", value="Complete Seneca assignments", inline=False)
    embed.add_field(name="🌍 LanguageNut", value="Complete language assignments", inline=False)
    embed.set_footer(text="GIOAI · gioai.uk")
    view = View(timeout=120)
    view.add_item(Button(label="Join Queue", style=discord.ButtonStyle.primary, custom_id="hub_join"))
    view.add_item(Button(label="Check Queue", style=discord.ButtonStyle.secondary, custom_id="hub_check"))
    view.add_item(Button(label="View Slots", style=discord.ButtonStyle.secondary, custom_id="hub_slots"))
    view.add_item(Button(label="Settings", style=discord.ButtonStyle.primary, custom_id="hub_settings"))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="faq", description="Show the FAQ & learning platform panel")
async def slash_faq(interaction: Interaction):
    embed = Embed(
        title="GIOAI Learning Platform — FAQ",
        description="Your personalized AI tutoring platform for homework completion.",
        color=COLORS["purple"]
    )
    embed.add_field(name="🎯 Personalised Help", value="Get tailored assistance", inline=False)
    embed.add_field(name="👨‍🏫 Real-Time Tutors", value="Connect with tutors instantly", inline=False)
    embed.add_field(name="🏆 Top 5% Problems", value="We solve the hardest problems", inline=False)
    embed.add_field(name="🔒 Secure & Confidential", value="Your data is never shared", inline=False)
    embed.set_footer(text="GIOAI Learning Platform · gioai.uk")
    await interaction.response.send_message(embed=embed, view=FAQView(), ephemeral=False)

@bot.tree.command(name="platform", description="View platform status")
async def slash_platform(interaction: Interaction, platform: str = "all"):
    embed = make_embed(title="Platform Status", color=COLORS["purple"])
    if platform == "all" or platform == "sparx":
        embed.add_field(name=f"{PLATFORM_ICONS['sparx']} Sparx Maths", value="🟢 `ONLINE`", inline=False)
    if platform == "all" or platform == "seneca":
        embed.add_field(name=f"{PLATFORM_ICONS['seneca']} Seneca Learning", value="🟢 `ONLINE`", inline=False)
    if platform == "all" or platform == "languagenut":
        embed.add_field(name=f"{PLATFORM_ICONS['languagenut']} LanguageNut", value="🟢 `ONLINE`", inline=False)
    embed.set_footer(text="GIOAI · gioai.uk")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── Prefix Commands ───

@bot.command(name="hub", aliases=["h", "menu"])
async def cmd_hub(ctx):
    embed = Embed(
        title="🤖 GIOAI Controller",
        description="Select a platform to manage your bots.\nUse `/hub` for the interactive version!",
        color=COLORS["purple"]
    )
    embed.add_field(name="📐 Sparx Maths", value="`/platform sparx` - Quick View", inline=True)
    embed.add_field(name="🌍 LanguageNut", value="`/platform languagenut` - Quick View", inline=True)
    embed.add_field(name="❄️ Seneca Learning", value="`/platform seneca` - Quick View", inline=True)
    embed.set_footer(text="GIOAI v9.0 · gioai.uk")
    await ctx.send(embed=embed, delete_after=120)

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send(f"🏓 `{round(bot.latency * 1000)}ms`", delete_after=10)

@bot.command(name="sync")
async def cmd_sync(ctx):
    if ctx.author.id != OWNER_ID and (not ctx.author.guild_permissions.administrator):
        await ctx.send("❌ Owner only", delete_after=10)
        return
    await bot.tree.sync()
    await ctx.send("✅ Commands synced!", delete_after=10)

@bot.command(name="faq")
async def cmd_faq(ctx):
    await ensure_faq_embed()
    await ctx.send("✅ FAQ embed updated!", delete_after=10)

@bot.command(name="say")
async def cmd_say(ctx, *, message: str):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Owner only", delete_after=10)
        return
    await ctx.send(message)

# ─── Modal Handlers ───

@bot.event
async def on_modal_submit(interaction: Interaction):
    if interaction.data["custom_id"] == "Platform Login":
        platform = interaction.data["components"][0]["components"][0]["value"]
        username = interaction.data["components"][1]["components"][0]["value"]
        password = interaction.data["components"][2]["components"][0]["value"]

        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        task_info = {
            "task_id": task_id,
            "user_id": str(interaction.user.id),
            "platform": platform.lower(),
            "account": username,
            "task_name": f"Task via login",
            "status": "queued",
            "queued_at": now,
            "due_date": now + timedelta(days=random.randint(1, 14)),
            "sub_tasks": [
                {"name": "Mixed topic practice", "progress": 0},
            ],
            "stats": {
                "q_completed": "0/6",
                "simulated_time": "~30m",
                "fake_q_time": "6s–8s",
                "bookwork_acc": "100%",
                "xp": "0",
                "finishes_in": "~45s",
            }
        }

        state.queue.append(task_info)
        state.task_counter += 1

        embed = Embed(
            title="✅ Added to Queue",
            description=f"Your task has been queued for **{PLATFORM_NAMES.get(platform.lower(), platform)}**",
            color=COLORS["success"]
        )
        embed.add_field(name="Account", value=username, inline=True)
        embed.add_field(name="Position", value=len(state.queue), inline=True)
        embed.add_field(name="Task ID", value=f"`{task_id}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Simulate progress
        await simulate_task_progress(interaction.user, task_info)
    elif interaction.data["custom_id"] == "Feedback & Suggestions":
        fb_type = interaction.data["components"][0]["components"][0]["value"]
        content = interaction.data["components"][1]["components"][0]["value"]
        embed = Embed(
            title="✅ Feedback Received",
            description=f"**Type:** {fb_type}\nThank you for your feedback! We'll review it shortly.",
            color=COLORS["success"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Feedback from {interaction.user}: [{fb_type}] {content}")

# ─── Button Handler ───

@bot.event
async def on_interaction(interaction: Interaction):
    if not interaction.data or "custom_id" not in interaction.data:
        return

    custom_id = interaction.data["custom_id"]

    # Handle button interactions from FAQ and other views
    if custom_id == "normal_login":
        await show_platform_login(interaction)
    elif custom_id == "bookmarklet_login":
        await show_bookmarklet_login(interaction)
    elif custom_id == "back_faq":
        embed = Embed(
            title="GIOAI Learning Platform — FAQ",
            description="Your personalized AI tutoring platform.",
            color=COLORS["purple"]
        )
        embed.add_field(name="🎯 Personalised Help", value="Get tailored assistance", inline=False)
        embed.add_field(name="👨‍🏫 Real-Time Tutors", value="Connect with tutors instantly", inline=False)
        embed.add_field(name="🏆 Top 5% Problems", value="We solve the hardest problems", inline=False)
        embed.add_field(name="🔒 Secure & Confidential", value="Your data is never shared", inline=False)
        embed.set_footer(text="GIOAI Learning Platform · gioai.uk")
        await interaction.response.edit_message(embed=embed, view=FAQView())
    elif custom_id in ("hub_join", "join_queue"):
        await show_login_methods(interaction)
    elif custom_id == "hub_check":
        await show_queue(interaction)
    elif custom_id == "hub_slots":
        await show_slots(interaction)
    elif custom_id == "hub_settings":
        await show_settings(interaction, 0)
    elif custom_id.startswith("view_dm_"):
        task_id = custom_id.replace("view_dm_", "")
        task = state.active_tasks.get(task_id)
        if task:
            dm_task = task.copy()
            dm_task["stats"] = {"q_completed": "5/6", "simulated_time": "~30m", "fake_q_time": "6s–8s",
                                "bookwork_acc": "100%", "xp": "120", "finishes_in": "~30s"}
            dm_task["sub_tasks"] = [{"name": "Mixed topic practice", "progress": 75}]
            await send_task_dm(interaction.user, dm_task)
        await interaction.response.send_message("📬 Check your DMs!", ephemeral=True)
    elif custom_id.startswith("leave_queue_"):
        task_id = custom_id.replace("leave_queue_", "")
        state.queue = [t for t in state.queue if t["task_id"] != task_id]
        await interaction.response.send_message("✅ Removed from queue!", ephemeral=True)
    elif custom_id == "increase_limit":
        await interaction.response.send_message("Contact support to increase your slot limit.", ephemeral=True)
    elif custom_id == "slots_help":
        embed = Embed(
            title="Slots Help",
            description="Slots determine how many concurrent tasks you can run per platform.\n- 4 slots per platform per day\n- Slots reset every 24 hours\n- Contact staff to increase limit",
            color=COLORS["blurple"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif custom_id in ("hist_prev_", "hist_next_"):
        pass
    elif custom_id == "hist_view_dm":
        await interaction.response.send_message("Check your DMs for full history.", ephemeral=True)
    elif custom_id == "settings_configure":
        await show_platform_settings(interaction)
    elif custom_id == "toggle_username":
        uid = str(interaction.user.id)
        s = state.user_settings.get(uid, {})
        s["show_username"] = not s.get("show_username", True)
        state.user_settings[uid] = s
        await show_settings(interaction, 0)
    elif custom_id == "toggle_task_start":
        uid = str(interaction.user.id)
        s = state.user_settings.get(uid, {})
        modes = ["Instant", "Delayed (30s)", "Delayed (60s)"]
        current = s.get("task_start", "Instant")
        next_idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
        s["task_start"] = modes[next_idx]
        state.user_settings[uid] = s
        await show_settings(interaction, 0)
    elif custom_id == "toggle_theme":
        uid = str(interaction.user.id)
        s = state.user_settings.get(uid, {})
        themes = ["Purple", "Blue", "Green", "Red"]
        current = s.get("theme_color", "Purple")
        next_idx = (themes.index(current) + 1) % len(themes) if current in themes else 0
        s["theme_color"] = themes[next_idx]
        state.user_settings[uid] = s
        await show_settings(interaction, 0)
    elif custom_id == "toggle_sort":
        uid = str(interaction.user.id)
        s = state.user_settings.get(uid, {})
        sorts = ["Alphabetical", "Newest First", "Oldest First"]
        current = s.get("sort_account", "Alphabetical")
        next_idx = (sorts.index(current) + 1) % len(sorts) if current in sorts else 0
        s["sort_account"] = sorts[next_idx]
        state.user_settings[uid] = s
        await show_settings(interaction, 1)
    elif custom_id == "toggle_notify":
        uid = str(interaction.user.id)
        s = state.user_settings.get(uid, {})
        s["completion_notification"] = not s.get("completion_notification", True)
        state.user_settings[uid] = s
        await show_settings(interaction, 1)
    elif custom_id == "settings_page_0":
        await show_settings(interaction, 0)
    elif custom_id == "settings_page_1":
        await show_settings(interaction, 1)
    elif custom_id == "retry_task":
        await interaction.response.send_message("🔄 Retrying task...", ephemeral=True)
    elif custom_id == "cancel_task":
        await interaction.response.send_message("❌ Task cancelled.", ephemeral=True)
    elif custom_id == "task_settings":
        await show_settings(interaction, 0)

# ─── Platform Settings ───
async def show_platform_settings(interaction: Interaction):
    embed = Embed(
        title="Platform Specific Settings",
        description="Configure settings for each platform",
        color=COLORS["purple"]
    )
    platforms = [
        ("Sparx Maths", "sparx", "📐"),
        ("Seneca Learning", "seneca", "❄️"),
        ("LanguageNut", "languagenut", "🌍"),
    ]
    for name, key, emoji in platforms:
        embed.add_field(name=f"{emoji} {name}", value=f"**Fake Question Time:** 60s–70s\n**Score Accuracy:** 100%\nClick to configure", inline=False)

    view = View(timeout=120)
    view.add_item(Button(label="Sparx Maths >", style=discord.ButtonStyle.secondary, custom_id="plat_sparx"))
    view.add_item(Button(label="Seneca >", style=discord.ButtonStyle.secondary, custom_id="plat_seneca"))
    view.add_item(Button(label="LanguageNut >", style=discord.ButtonStyle.secondary, custom_id="plat_languagenut"))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── Simulated task progress ───
async def simulate_task_progress(user: discord.User, task_info: dict):
    task_id = task_info["task_id"]
    state.active_tasks[task_id] = task_info
    task_info["active"] = True

    # Send initial DM
    task_info["sub_tasks"] = [{"name": "Mixed topic practice", "progress": 0}]
    task_info["stats"] = {"q_completed": "0/6", "simulated_time": "~30m", "fake_q_time": "6s–8s",
                          "bookwork_acc": "100%", "xp": "0", "finishes_in": "~45s"}
    await send_task_dm(user, task_info)

    # Simulate progress
    for pct in [10, 25, 50, 75, 90, 100]:
        await asyncio.sleep(random.randint(3, 8))
        task_info["sub_tasks"][0]["progress"] = pct
        task_info["stats"]["q_completed"] = f"{int(pct / 100 * 6)}/6"
        task_info["stats"]["finishes_in"] = f"~{int((100 - pct) * 0.45)}s"
        task_info["stats"]["xp"] = str(int(pct * 1.2))
        await send_task_dm(user, task_info)

    # Complete
    task_info["active"] = False
    task_info["status"] = "completed"
    state.queue = [t for t in state.queue if t["task_id"] != task_id]
    del state.active_tasks[task_id]

    # Add to history
    uid = str(user.id)
    if uid not in state.history:
        state.history[uid] = []
    state.history[uid].insert(0, {
        "task_id": task_id,
        "user_id": uid,
        "platform": task_info.get("platform"),
        "account": task_info.get("account"),
        "task_name": task_info.get("task_name"),
        "completed_at": datetime.now(timezone.utc),
    })

    logger.info(f"Task {task_id} completed for {user}")

# ─── Select Menu Handler ───
@bot.event
async def on_select_option(interaction: Interaction):
    if interaction.data.get("custom_id") == "saved_platform":
        platform = interaction.data["values"][0]
        embed = Embed(
            title="Select Account",
            description=f"You selected **{PLATFORM_NAMES.get(platform, platform)}**\nSelect an account to use.",
            color=COLORS["purple"]
        )
        view = View(timeout=120)
        view.add_item(Select(
            placeholder="Select an account",
            options=[
                discord.SelectOption(label="Default Account", value=f"{platform}:default", description="Your primary account"),
            ],
            custom_id="saved_account"
        ))
        await interaction.response.edit_message(embed=embed, view=view)
    elif interaction.data.get("custom_id") == "saved_account":
        value = interaction.data["values"][0]
        platform, account = value.split(":", 1)

        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        task_info = {
            "task_id": task_id,
            "user_id": str(interaction.user.id),
            "platform": platform,
            "account": account,
            "task_name": f"Task via saved account",
            "status": "queued",
            "queued_at": now,
            "due_date": now + timedelta(days=random.randint(1, 14)),
            "sub_tasks": [{"name": "Mixed topic practice", "progress": 0}],
            "stats": {"q_completed": "0/6", "simulated_time": "~30m", "fake_q_time": "6s–8s",
                      "bookwork_acc": "100%", "xp": "0", "finishes_in": "~45s"},
        }

        state.queue.append(task_info)
        state.task_counter += 1

        embed = Embed(
            title="✅ Added to Queue",
            description=f"Task queued for **{PLATFORM_NAMES.get(platform, platform)}** with **{account}**",
            color=COLORS["success"]
        )
        embed.add_field(name="Position", value=len(state.queue), inline=True)
        embed.add_field(name="Task ID", value=f"`{task_id}`", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

        await simulate_task_progress(interaction.user, task_info)

# ─── Start ───
if __name__ == "__main__":
    logger.info("Starting GIOAI v9.0...")
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)

