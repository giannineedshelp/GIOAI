#!/usr/bin/env python3
# GIOAI - Multi-Platform Discord Bot Controller
# One bot, one status channel, slash commands for each platform

import discord, os, sys, asyncio, time, logging
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GIOAI")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "0"))
STATUS_CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "0"))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", "0"))

if not TOKEN:
    print("❌ DISCORD_TOKEN not set")
    sys.exit(1)

class PlatformStatus:
    def __init__(self):
        self.platforms = {
            "sparx": {"name": "Sparx Maths", "emoji": "📐", "status": "offline", "prefix": "s!"},
            "languagenut": {"name": "Languagenut", "emoji": "🌍", "status": "offline", "prefix": "ln!"},
        }
    def set(self, key, status):
        if key in self.platforms:
            self.platforms[key]["status"] = status
            self.platforms[key]["last_seen"] = time.time()
    def get(self, key):
        return self.platforms.get(key)
    def get_all(self):
        return self.platforms
    def to_embed(self):
        e = discord.Embed(title="GIOAI Platform Status", color=0x5865F2, timestamp=discord.utils.utcnow())
        for key, p in self.platforms.items():
            em = {"online": "🟢", "idle": "🟡", "offline": "🔴"}.get(p["status"], "⚪")
            e.add_field(name=f"{p['emoji']} {p['name']}", value=f"{em} `{p['status'].upper()}`\nPrefix: `{p['prefix']}`", inline=False)
        e.set_footer(text="GIOAI Controller")
        return e

platforms = PlatformStatus()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="g!", intents=intents, help_command=None)
bot.status_message = None
bot._last_voice_name = None
bot._last_voice_update = 0

async def update_status():
    if not STATUS_CHANNEL_ID: return
    ch = bot.get_channel(STATUS_CHANNEL_ID)
    if not ch: return
    embed = platforms.to_embed()
    if bot.status_message:
        try: await bot.status_message.edit(embed=embed); return
        except: bot.status_message = None
    async for msg in ch.history(limit=20):
        if msg.author == bot.user and msg.embeds:
            bot.status_message = msg
            await msg.edit(embed=embed)
            return
    bot.status_message = await ch.send(embed=embed)

async def update_voice():
    if not VOICE_CHANNEL_ID: return
    ch = bot.get_channel(VOICE_CHANNEL_ID)
    if not ch: return
    now = time.time()
    if now - bot._last_voice_update < 15: return
    sts = [p["status"] for p in platforms.get_all().values()]
    if any(s == "offline" for s in sts): overall = "offline"
    elif any(s == "idle" for s in sts): overall = "idle"
    else: overall = "online"
    em = {"online": "🟢", "idle": "🟡", "offline": "🔴"}[overall]
    name = f"gioai: {em} {overall}"
    if name == bot._last_voice_name: return
    try:
        await ch.edit(name=name)
        bot._last_voice_name = name
        bot._last_voice_update = now
    except: pass

@bot.event
async def on_ready():
    logger.info(f"GIOAI Controller online: {bot.user}")
    platforms.set("sparx", "online")
    platforms.set("languagenut", "online")
    await update_status()
    await update_voice()
    asyncio.create_task(periodic_status())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="g!hub | /sparx /languagenut"))

async def periodic_status():
    while True:
        await asyncio.sleep(120)
        await update_status()
        await update_voice()

@bot.tree.command(name="sparx", description="Open Sparx Maths hub")
async def slash_sparx(interaction: discord.Interaction):
    p = platforms.get("sparx")
    em = {"online": "🟢", "idle": "🟡", "offline": "🔴"}.get(p["status"], "⚪")
    e = discord.Embed(title="📐 Sparx Maths", description=f"Status: {em} `{p['status'].upper()}`\nPrefix: `s!`", color=0x57F287 if p["status"]=="online" else 0xED4245)
    e.add_field(name="Commands", value="`s!hub` — Open the Sparx hub\n`s!login <school>` — Login to your school\n`s!homework` — View homework\n`s!dmupdate on/off` — Toggle DM progress", inline=False)
    e.set_footer(text="Type s!hub in any channel to open the full menu")
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="languagenut", description="Open Languagenut hub")
async def slash_languagenut(interaction: discord.Interaction):
    p = platforms.get("languagenut")
    em = {"online": "🟢", "idle": "🟡", "offline": "🔴"}.get(p["status"], "⚪")
    e = discord.Embed(title="🌍 Languagenut", description=f"Status: {em} `{p['status'].upper()}`\nPrefix: `ln!`", color=0x9B59B6)
    e.add_field(name="Commands", value="`ln!hub` — Open the Languagenut hub\n`ln!start` — Start farming\n`ln!status` — Check progress", inline=False)
    e.set_footer(text="Type ln!hub in any channel to open the full menu")
    await interaction.response.send_message(embed=e, ephemeral=True)

@bot.tree.command(name="status", description="View all platform statuses")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.send_message(embed=platforms.to_embed(), ephemeral=True)

@bot.command(name="hub", aliases=["h", "menu"])
async def cmd_hub(ctx):
    e = discord.Embed(title="GIOAI Controller", color=0x5865F2)
    e.add_field(name="Slash Commands", value="</sparx> — Sparx\n</languagenut> — Languagenut\n</status> — All platforms", inline=False)
    e.add_field(name="Prefix", value="`g!hub` — This menu\n`g!ping` — Latency", inline=False)
    for k, p in platforms.get_all().items():
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
    await ctx.send("✅ Synced", delete_after=10)

@bot.command(name="setstatus")
async def cmd_setstatus(ctx, platform: str = None, status: str = None):
    if ctx.author.id != OWNER_ID and ADMIN_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ No permission", delete_after=10)
        return
    if not platform or status not in ("online", "idle", "offline"):
        p = "\n".join(f"`{k}` — {v['name']}" for k, v in platforms.get_all().items())
        await ctx.send(f"Usage: `g!setstatus <platform> <online/idle/offline>`\n{p}", delete_after=20)
        return
    platforms.set(platform, status)
    await update_status()
    await update_voice()
    await ctx.send(f"✅ `{platform}` → `{status}`", delete_after=10)

if __name__ == "__main__":
    logger.info("Starting GIOAI Controller...")
    bot.run(TOKEN)
