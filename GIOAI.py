#!/usr/bin/env python3
# GIOAI - Multi-Platform Discord Bot Controller
# Single bot that manages Sparx, Languagenut, and future platforms
# One status channel showing all platforms
# Slash commands: /sparx, /languagenut to open each platform's hub

import discord, json, os, sys, asyncio, time, logging
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GIOAI")

# ──── Load env ────
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "0"))
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "0"))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", "0"))

if not TOKEN:
    print("❌ DISCORD_TOKEN not set in .env")
    sys.exit(1)

# ──── Platform Status Tracker ────
class PlatformStatus:
    def __init__(self):
        self.platforms = {
            "sparx": {"name": "Sparx Maths", "emoji": "📐", "status": "offline", "last_seen": None, "channel_id": 0},
            "languagenut": {"name": "Languagenut", "emoji": "🌍", "status": "offline", "last_seen": None, "channel_id": 0},
        }
    
    def set(self, key, status):
        if key in self.platforms:
            self.platforms[key]["status"] = status
            self.platforms[key]["last_seen"] = time.time()
    
    def set_channel(self, key, channel_id):
        if key in self.platforms:
            self.platforms[key]["channel_id"] = channel_id
    
    def get(self, key):
        return self.platforms.get(key)
    
    def get_all(self):
        return self.platforms
    
    @property
    def overall(self):
        sts = [p["status"] for p in self.platforms.values()]
        if any(s == "offline" for s in sts): return "offline"
        if any(s == "idle" for s in sts): return "idle"
        return "online"
    
    def to_embed(self):
        e = discord.Embed(title="GIOAI Platform Status", color=0x5865F2, timestamp=discord.utils.utcnow())
        for key, p in self.platforms.items():
            status_emoji = {"online": "🟢", "idle": "🟡", "offline": "🔴", "dnd": "🔴"}.get(p["status"], "⚪")
            last = f" — {int(time.time() - p['last_seen'])}s ago" if p["last_seen"] else ""
            e.add_field(
                name=f"{p['emoji']} {p['name']}",
                value=f"{status_emoji} `{p['status'].upper()}`{last}",
                inline=False
            )
        e.set_footer(text="GIOAI Controller")
        return e

platforms = PlatformStatus()

# ──── Import platform modules ────
sys.path.insert(0, os.path.dirname(__file__))

# ──── Discord Bot ────
intents = discord.Intents.default()
intents.message_content = True

class GIOAIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="g!", intents=intents, help_command=None)
        self.status_message = None
        self._last_voice_name = None
        self._last_voice_update = 0
    
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Slash commands synced")

bot = GIOAIBot()

# ──── Status Updates ────
async def update_status_channel():
    if not STATUS_CHANNEL_ID: return
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if not channel: return
    embed = platforms.to_embed()
    if bot.status_message:
        try:
            await bot.status_message.edit(embed=embed)
            return
        except:
            bot.status_message = None
    try:
        async for msg in channel.history(limit=30):
            if msg.author == bot.user and msg.embeds:
                bot.status_message = msg
                await msg.edit(embed=embed)
                return
    except:
        pass
    bot.status_message = await channel.send(embed=embed)

async def update_voice_channel():
    if not VOICE_CHANNEL_ID: return
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if not channel: return
    now = time.time()
    if now - bot._last_voice_update < 15: return
    
    overall = platforms.overall
    emoji_map = {"online": "🟢", "idle": "🟡", "offline": "🔴"}
    name = f"GIOAI: {emoji_map.get(overall, '⚪')} {overall}"
    
    if name == bot._last_voice_name: return
    try:
        await channel.edit(name=name)
        bot._last_voice_name = name
        bot._last_voice_update = now
    except:
        pass

async def periodic_status():
    while True:
        await asyncio.sleep(120)
        await update_status_channel()
        await update_voice_channel()

# ──── Events ────
@bot.event
async def on_ready():
    logger.info(f"GIOAI Controller logged in as {bot.user}")
    platforms.set("sparx", "online")
    platforms.set("languagenut", "online")
    await update_status_channel()
    await update_voice_channel()
    asyncio.create_task(periodic_status())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="g!hub | /sparx /languagenut"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    await ctx.send(f"❌ {error}", delete_after=10)

# ──── Slash Commands ────
@bot.tree.command(name="sparx", description="Open Sparx Maths hub")
async def slash_sparx(interaction: discord.Interaction):
    p = platforms.get("sparx")
    status_emoji = {"online": "🟢", "idle": "🟡", "offline": "🔴"}.get(p["status"], "⚪")
    e = discord.Embed(
        title=f"{p['emoji']} Sparx Maths",
        description=f"Status: {status_emoji} `{p['status'].upper()}`",
        color=0x57F287 if p["status"] == "online" else 0xED4245
    )
    e.add_field(name="What it does", value="Auto-complete Sparx Maths homework, login with school accounts, track progress", inline=False)
    e.add_field(name="Commands", value="`s!hub` — Open command centre\n`s!login <school>` — Login\n`s!homework` — View homework", inline=False)
    e.set_footer(text="Click Launch to open the Sparx hub")
    view = LaunchView("sparx", "Launch Sparx Hub")
    await interaction.response.send_message(embed=e, view=view, ephemeral=True)

@bot.tree.command(name="languagenut", description="Open Languagenut hub")
async def slash_languagenut(interaction: discord.Interaction):
    p = platforms.get("languagenut")
    status_emoji = {"online": "🟢", "idle": "🟡", "offline": "🔴"}.get(p["status"], "⚪")
    e = discord.Embed(
        title=f"{p['emoji']} Languagenut",
        description=f"Status: {status_emoji} `{p['status'].upper()}`",
        color=0x57F287 if p["status"] == "online" else 0xED4245
    )
    e.add_field(name="What it does", value="Automate Languagenut language learning exercises", inline=False)
    e.add_field(name="Commands", value="`ln!hub` — Open command centre\n`ln!start` — Start farming", inline=False)
    e.set_footer(text="Click Launch to open the Languagenut hub")
    view = LaunchView("languagenut", "Launch Languagenut Hub")
    await interaction.response.send_message(embed=e, view=view, ephemeral=True)

@bot.tree.command(name="status", description="View all platform statuses")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.send_message(embed=platforms.to_embed(), ephemeral=True)

# ──── Launch View (opens the actual platform hub) ────
class LaunchView(discord.ui.View):
    def __init__(self, platform, label):
        super().__init__(timeout=120)
        self.platform = platform
        button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, emoji="🚀")
        button.callback = self.launch_callback
        self.add_item(button)
    
    async def launch_callback(self, interaction: discord.Interaction):
        # Import and open the platform's hub
        if self.platform == "sparx":
            try:
                from platforms.sparx.display import random_color, progress_bar
                # Create Sparx hub embed
                e = discord.Embed(title="📐 Sparx Maths Command Centre", color=random_color())
                e.add_field(name="Status", value=f"{'🟢' if platforms.get('sparx')['status'] == 'online' else '🔴'} `{platforms.get('sparx')['status'].upper()}`", inline=False)
                e.add_field(name="Quick Commands", value="`s!login <school>` — Add account\n`s!homework` — View homework\n`s!hub` — Full hub\n`s!dmupdate on/off` — Toggle DMs", inline=False)
                await interaction.response.send_message(embed=e, ephemeral=True)
            except ImportError:
                await interaction.response.send_message("❌ Sparx module not loaded yet", ephemeral=True)
        
        elif self.platform == "languagenut":
            e = discord.Embed(title="🌍 Languagenut Command Centre", color=0x9B59B6)
            e.add_field(name="Status", value=f"{'🟢' if platforms.get('languagenut')['status'] == 'online' else '🔴'} `{platforms.get('languagenut')['status'].upper()}`", inline=False)
            e.add_field(name="Quick Commands", value="`ln!hub` — Full hub\n`ln!start` — Start farming\n`ln!status` — Check progress", inline=False)
            await interaction.response.send_message(embed=e, ephemeral=True)

# ──── Text Commands ────
@bot.command(name="hub", aliases=["h", "help", "menu"])
async def cmd_hub(ctx):
    e = discord.Embed(title="GIOAI Controller Hub", color=0x5865F2)
    e.add_field(name="Slash Commands", value="</sparx> — Sparx Maths hub\n</languagenut> — Languagenut hub\n</status> — Platform status", inline=False)
    e.add_field(name="Prefix Commands", value="`g!hub` — This menu\n`g!ping` — Bot latency", inline=False)
    for key, p in platforms.get_all().items():
        em = {"online": "🟢", "idle": "🟡", "offline": "🔴"}.get(p["status"], "⚪")
        e.add_field(name=f"{p['emoji']} {p['name']}", value=f"{em} `{p['status'].upper()}`", inline=True)
    await ctx.send(embed=e, delete_after=120)

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send(f"🏓 `{round(bot.latency * 1000)}ms`", delete_after=10)

@bot.command(name="sync")
async def cmd_sync(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Owner only", delete_after=10)
        return
    await bot.tree.sync()
    await ctx.send("✅ Commands synced", delete_after=10)

@bot.command(name="setstatus")
async def cmd_setstatus(ctx, platform: str = None, status: str = None):
    if ctx.author.id != OWNER_ID and ADMIN_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ No permission", delete_after=10)
        return
    if not platform or not status:
        p = "\n".join(f"`{k}` — {v['name']}" for k, v in platforms.get_all().items())
        await ctx.send(f"Usage: `g!setstatus <platform> <online/idle/offline>`\n{p}", delete_after=20)
        return
    if platform not in platforms.get_all():
        await ctx.send(f"❌ Unknown platform: `{platform}`", delete_after=10)
        return
    platforms.set(platform, status)
    await update_status_channel()
    await update_voice_channel()
    await ctx.send(f"✅ `{platform}` → `{status}`", delete_after=10)

# ──── Run ────
if __name__ == "__main__":
    logger.info("Starting GIOAI Controller...")
    bot.run(TOKEN)
