#!/usr/bin/env python3
# GIOAI - Sparx Maths Platform v3.2
# Fixed: Cloudflare 403, login flow, status channel, all button responses ephemeral

import discord, json, base64, re, asyncio, time, random, os, sys, logging
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from datetime import datetime
from curl_cffi import requests as curl_req

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared.protobuf.decoder import grpc, dec
from shared.utils.helpers import load_env, get, fmt_bar
from platforms.sparx.bookwork import bookwork
from platforms.sparx.display import progress_bar, create_task_message, create_completion_message, random_color
from shared.utils.embed_builder import EmbedBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GIOAI-Sparx")

# ═══════════════════════════════════════════
# LOAD ENVIRONMENT
# ═══════════════════════════════════════════
load_env()

TOKEN = os.getenv("DISCORD_TOKEN") or get("SPARX_TOKEN")
GUILD_ID = int(os.getenv("SPARX_GUILD_ID") or get("GUILD_ID", "0"))
OWNER_ID = int(os.getenv("SPARX_OWNER_ID") or get("OWNER_ID", "0"))
ADMIN_ROLE_ID = int(os.getenv("SPARX_ADMIN_ROLE_ID") or get("ADMIN_ROLE_ID", "0"))
TEXT_CHANNEL_ID = int(os.getenv("SPARX_TEXT_CHANNEL_ID") or get("TEXT_CHANNEL_ID", "0"))
VOICE_CHANNEL_ID = int(os.getenv("SPARX_VOICE_CHANNEL_ID") or get("VOICE_CHANNEL_ID", "0"))
COMMAND_PREFIX = os.getenv("SPARX_PREFIX") or get("COMMAND_PREFIX", "s!")
MAX_ACCOUNTS = int(get("MAX_ACCOUNTS", "5"))

GEMINI_KEY = get("GEMINI_API_KEY")
GROQ_KEY = get("GROQ_API_KEY")
MISTRAL_KEY = get("MISTRAL_API_KEY")
DEEPSEEK_KEY = get("DEEPSEEK_API_KEY")
SAMBA_KEY = get("SAMBA_API_KEY")
FIREWORKS_KEY = get("FIREWORKS_API_KEY")
OPENROUTER_KEY = get("OPENROUTER_API_KEY")

if not TOKEN:
    print("❌ No DISCORD_TOKEN or SPARX_TOKEN found in .env")
    sys.exit(1)

# Validate critical IDs
if not GUILD_ID:
    print("❌ GUILD_ID not set in .env")
    sys.exit(1)

# ═══════════════════════════════════════════
# SPARX API CONSTANTS
# ═══════════════════════════════════════════
SCHOOLS_URL = "https://static.sparxhomework.uk/sl/spx001/data.txt"
TOKEN_URL = "https://auth.sparxmaths.uk/oauth2/token"
AUTH_URL = "https://auth.sparxmaths.uk/oauth2/auth"
STUDENT_API = "https://studentapi.api.sparxmaths.uk/sparx.swworker.v1.Sparxweb"
DASHBOARD = "https://maths.sparx-learning.com/api/student"
CLIENT_ID = "sparx-maths-sw"
REDIRECT_URI = "https://studentapi.api.sparxmaths.uk/oauth/callback"

# ═══════════════════════════════════════════
# BOT STATUS TRACKER
# ═══════════════════════════════════════════
class BotStatus:
    def __init__(self):
        self.platforms = {
            "sparx": {"name": "Sparx Maths", "status": "offline", "last_seen": None},
            "languagenut": {"name": "Languagenut", "status": "offline", "last_seen": None},
            "core": {"name": "GIOAI Core", "status": "online", "last_seen": time.time()},
        }

    def set(self, platform, status):
        if platform in self.platforms:
            self.platforms[platform]["status"] = status
            self.platforms[platform]["last_seen"] = time.time()

    def get_all(self):
        return self.platforms

    def status_emoji(self, status):
        return {"online": "🟢", "idle": "🟡", "dnd": "🔴", "offline": "🔴"}.get(status, "⚪")

    def status_text(self, status):
        return {"online": "Online", "idle": "Idle", "dnd": "Do Not Disturb", "offline": "Offline"}.get(status, "Unknown")

    def to_embed(self):
        e = EmbedBuilder._base(EmbedBuilder.COLORS["primary"])
        e.title = "GIOAI Platform Status"
        for key, p in self.platforms.items():
            emoji = self.status_emoji(p["status"])
            text = self.status_text(p["status"])
            last = f" \u2014 {int(time.time() - p['last_seen'])}s ago" if p["last_seen"] else ""
            e.add_field(name=f"{emoji} {p['name']}", value=f"`{text}`{last}", inline=False)
        e.set_footer(text="GIOAI Status Monitor | Powered by Manus AI")
        return e

bot_status = BotStatus()

# ═══════════════════════════════════════════
# STORAGE
# ═══════════════════════════════════════════
school_cache = None
user_store = {}

def store(uid):
    if uid not in user_store:
        user_store[uid] = {
            'accounts': [], 'active': -1,
            'settings': {
                'submit_delay': 2.5, 'max_retries': 3, 'ai_timeout': 30,
                'batch_size': 'all', 'time_mode': 'fake',
                'fake_min_secs': 10, 'fake_max_secs': 45,
                'wait_secs_per_q': 30, 'save_working': True,
            },
            'working_out': [], 'bookwork_map': {},
            'dm_update': True, 'auto_xp': 0, 'auto_correct': 0, 'auto_total': 0,
        }
    return user_store[uid]

async def working_out_sweeper():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for uid in list(user_store.keys()):
            s = user_store[uid]
            s['working_out'] = [w for w in s['working_out'] if now - w['timestamp'] < 600]

class School:
    def __init__(self, id, name, slug, town):
        self.id = id; self.name = name; self.slug = slug; self.town = town

# ═══════════════════════════════════════════
# AI ENGINE
# ═══════════════════════════════════════════
class AIEngine:
    def __init__(self):
        self.http = curl_req.AsyncSession(impersonate="chrome120", timeout=60)

    def _parse(self, t):
        if not t: return []
        for p in [r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', r'(\[[\s\S]*?\])']:
            m = re.search(p, t)
            if m:
                try: return json.loads(m.group(1))
                except: pass
        try: return json.loads(t.strip())
        except: return []

    async def solve(self, q):
        prompt = f"Output ONLY valid JSON array with id and answer fields. Numbers = decimals. No fractions. Solve: {q}"
        apis = [
            ("Gemini", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}", {}, {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.05,"maxOutputTokens":1024}}),
            ("Groq", "https://api.groq.com/openai/v1/chat/completions", {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}, {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
            ("Mistral", "https://api.mistral.ai/v1/chat/completions", {"Authorization":f"Bearer {MISTRAL_KEY}","Content-Type":"application/json"}, {"model":"mistral-small-latest","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
            ("DeepSeek", "https://api.deepseek.com/v1/chat/completions", {"Authorization":f"Bearer {DEEPSEEK_KEY}","Content-Type":"application/json"}, {"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
            ("SambaNova", "https://api.sambanova.ai/v1/chat/completions", {"Authorization":f"Bearer {SAMBA_KEY}","Content-Type":"application/json"}, {"model":"Meta-Llama-3.1-8B-Instruct","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
            ("Fireworks", "https://api.fireworks.ai/inference/v1/chat/completions", {"Authorization":f"Bearer {FIREWORKS_KEY}","Content-Type":"application/json"}, {"model":"accounts/fireworks/models/llama-v3p1-8b-instruct","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
            ("OpenRouter", "https://openrouter.ai/api/v1/chat/completions", {"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json"}, {"model":"cognitivecomputations/dolphin-2.9.3-llama-3.1-8b:free","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
        ]
        for name, url, headers, data in apis:
            try:
                r = await self.http.post(url, headers=headers, json=data)
                if r.status_code == 200:
                    t = (r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","") or r.json().get("choices",[{}])[0].get("message",{}).get("content","") or "")
                    a = self._parse(t)
                    if a: return a
            except: pass
        return []

    async def simple_answer(self, q):
        prompt = f"Answer concisely with just the answer. Question: {q}"
        for name, url, headers, data in [
            ("Gemini", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}", {}, {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.05,"maxOutputTokens":256}}),
            ("Groq", "https://api.groq.com/openai/v1/chat/completions", {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}, {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"temperature":0.05}),
        ]:
            try:
                r = await self.http.post(url, headers=headers, json=data)
                if r.status_code == 200:
                    t = (r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","") or r.json().get("choices",[{}])[0].get("message",{}).get("content","") or "")
                    if t: return t.strip()
            except: pass
        return None

# ═══════════════════════════════════════════
# SPARX CLIENT — FIXED: curl_cffi bypasses Cloudflare 403
# ═══════════════════════════════════════════
class SparxClient:
    def __init__(self):
        self.ai = AIEngine()
        self.http = curl_req.AsyncSession(impersonate="chrome124", verify=False, timeout=30)

    async def get_schools(self):
        global school_cache
        if school_cache: return school_cache
        r = await self.http.get(SCHOOLS_URL); r.raise_for_status()
        data = json.loads(base64.b64decode(r.text.strip()))
        school_cache = [School(s['i'], s['n'], s['u'], s.get('t','')) for s in data]
        logger.info(f"Loaded {len(school_cache)} schools")
        return school_cache

    async def search_schools(self, q):
        schools = await self.get_schools()
        q = q.lower().strip()
        for func in [
            lambda: [s for s in schools if s.name.lower() == q],
            lambda: [s for s in schools if s.slug.lower() == q],
            lambda: [s for s in schools if s.name.lower().startswith(q)],
            lambda: [s for s in schools if all(w in s.name.lower() for w in q.split())],
            lambda: [s for s in schools if q in s.name.lower()],
            lambda: [s for s in schools if q in s.town.lower()],
            lambda: [s for s in schools if any(w in s.name.lower() for w in q.split())],
            lambda: [s for s in schools if any(w in s.slug.lower() for w in q.split())],
        ]:
            r = func()
            if r: return r[:25]
        return []

    async def login(self, username, password, school):
        """FIXED: Uses curl_cffi with Chrome impersonation to bypass Cloudflare"""
        async with curl_req.AsyncSession(impersonate="chrome124", verify=False, timeout=30) as c:
            c.cookies.set('live-resolver-school', school.id, domain='auth.sparxmaths.uk')
            c.cookies.set('cookie_preferences', '{"GA":false,"Hotjar":false,"PT":false,"version":4}', domain='auth.sparxmaths.uk')
            c.cookies.set('live-resolver-school', school.id, domain='maths.sparx-learning.com')
            c.cookies.set('cookie_preferences', '{"GA":false,"Hotjar":false,"PT":false,"version":4}', domain='maths.sparx-learning.com')
            c.cookies.set('live-resolver-school', school.id, domain='maths.sparx-learning.com')
            c.cookies.set('cookie_preferences', '{"GA":false,"Hotjar":false,"PT":false,"version":4}', domain='maths.sparx-learning.com')
            # Warm up: hit the auth domain to pass browser check
            try:
                warm = await c.get('https://auth.sparxmaths.uk/', headers=headers)
                logger.info(f'Warm-up status: {warm.status_code}')
            except Exception as we:
                logger.warning(f'Warm-up failed (non-fatal): {we}')

            # Attempt 1 — password grant
            r = await c.post(TOKEN_URL, data={
                'client_id': CLIENT_ID, 'hd': school.id, 'username': username,
                'password': password, 'grant_type': 'password', 'scope': 'openid profile email',
            }, headers=headers)
            logger.info(f'Password grant attempt: {r.status_code}')
            if r.status_code == 403:
                logger.warning('Cloudflare block — retrying with fresh session')
                if isinstance(c, curl_req.AsyncSession):
                    await c.close()
                c = curl_req.AsyncSession(impersonate="chrome124")
                c.cookies.set('live-resolver-school', school.id, domain='auth.sparxmaths.uk')
                c.cookies.set('live-resolver-school', school.id, domain='maths.sparx-learning.com')
                c.cookies.set('cookie_preferences', '{"GA":false,"Hotjar":false,"PT":false,"version":4}', domain='auth.sparxmaths.uk')
                c.cookies.set('cookie_preferences', '{"GA":false,"Hotjar":false,"PT":false,"version":4}', domain='maths.sparx-learning.com')
                await asyncio.sleep(3)
                r = await c.post(TOKEN_URL, data={
                    'client_id': CLIENT_ID, 'hd': school.id, 'username': username,
                    'password': password, 'grant_type': 'password', 'scope': 'openid profile email',
                }, headers=headers)
                logger.info(f'Password grant retry: {r.status_code}')

            if r.status_code == 200:
                j = r.json()
                token = j.get('access_token')
                if token:
                    session_id = j.get('session_state', j.get('id_token', ''))[:32]
                    user_name = username
                    try:
                        r2 = await c.get(DASHBOARD, headers={'Authorization': f'Bearer {token}'})
                        if r2.status_code == 200:
                            user_name = r2.json().get('user', {}).get('name', username)
                    except: pass
                    logger.info(f"Login OK: {username} @ {school.name}")
                    return {
                        'token': f'Bearer {token}', 'session_id': session_id,
                        'username': username, 'user_name': user_name,
                        'school_name': school.name,
                        'cookies': {'live-resolver-school': school.id, 'cookie_preferences': '{"GA":false,"Hotjar":false,"PT":false,"version":4}'},
                    }

            # Fallback: auth code flow
            state = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip('=')
            await c.get(AUTH_URL, params={
                'client_id': CLIENT_ID, 'hd': school.id,
                'redirect_uri': REDIRECT_URI, 'response_type': 'code',
                'scope': 'openid profile email', 'state': state
            })

            r3 = await c.post(AUTH_URL, data={
                'username': username, 'password': password, 'client_id': CLIENT_ID,
                'hd': school.id, 'redirect_uri': REDIRECT_URI, 'response_type': 'code',
                'scope': 'openid profile email', 'state': state,
            }, follow_redirects=False)

            location = r3.headers.get('location', '')
            if 'code=' in location:
                code = re.search(r'code=([^&]+)', location)
                if code:
                    code = code.group(1)
                    r4 = await c.post(TOKEN_URL, data={
                        'client_id': CLIENT_ID, 'code': code,
                        'redirect_uri': REDIRECT_URI, 'grant_type': 'authorization_code',
                    })
                    if r4.status_code == 200:
                        j = r4.json()
                        token = j.get('access_token')
                        if token:
                            session_id = j.get('session_state', '')
                            user_name = username
                            try:
                                r5 = await c.get(DASHBOARD, headers={'Authorization': f'Bearer {token}'})
                                if r5.status_code == 200:
                                    user_name = r5.json().get('user', {}).get('name', username)
                            except: pass
                            logger.info(f"Login OK: {username} @ {school.name} (auth code)")
                            return {
                                'token': f'Bearer {token}', 'session_id': session_id,
                                'username': username, 'user_name': user_name,
                                'school_name': school.name,
                                'cookies': {'live-resolver-school': school.id, 'cookie_preferences': '{"GA":false,"Hotjar":false,"PT":false,"version":4}'},
                            }

            debug = f"Status: {r.status_code}"
            try: debug += f" | {r.json()}"
            except:
                try: debug += f" | {r.text[:200]}"
                except: pass
            raise Exception(f"Login failed for {username} @ {school.name}\nDebug: {debug}\n\n1. Some schools only allow Google/Microsoft SSO\n2. Try logging in at https://maths.sparx-learning.com first\n3. Make sure you have a Sparx password (not SSO-only)")

    async def get_homeworks(self, sess):
        all_hw = []
        for ep, typ in [('', 'homework'), ('/revision', 'revision'), ('/fixup', 'fixup')]:
            try:
                r = await self.http.get(f"{DASHBOARD}{ep}", headers={'Authorization': sess['token']})
                if r.status_code != 200: continue
                items = r.json()
                if not isinstance(items, list): items = items.get('packages', items.get('homeworks', []))
                for it in items:
                    all_hw.append({
                        'id': it.get('id',it.get('packageId','')), 'name': it.get('name','Homework'),
                        'due': str(it.get('due','')), 'type': typ,
                        'total_qs': it.get('totalQuestions',it.get('totalAmountOfQuestions',0)),
                        'completed_qs': it.get('completedQuestions',it.get('completedAmountOfQuestions',0)),
                    })
            except: continue
        return all_hw

    async def get_activity(self, sess, pkg_id, task_idx, act_idx):
        raw = await grpc(self.http, f"{STUDENT_API}/GetActivity", [
            (1, 0, 1), (2, 2, [(1, 0, task_idx), (2, 2, pkg_id)]),
            (6, 2, [(1, 0, 0), (2, 0, act_idx)]),
        ], sess['token'], sess.get('session_id',''), sess.get('cookies',{}))
        if not raw: return None
        layout = {}
        for idx, typ, val in raw:
            if idx == 3 and isinstance(val, list):
                for f in val:
                    if isinstance(f, tuple) and len(f) >= 3:
                        fi, _, fv = f
                        if fi == 1: layout['id'] = str(fv)
                        elif fi == 4 and isinstance(fv, list): layout['content'] = fv
        return {'act_idx': act_idx, 'layout': layout}

    def extract_q(self, layout):
        parts = []
        try:
            for f in layout.get('content', []):
                if isinstance(f, tuple) and isinstance(f[2], list):
                    for sb in f[2]:
                        if isinstance(sb, tuple) and len(sb) >= 3 and sb[0] == 1 and isinstance(sb[2], list):
                            for tp in sb[2]:
                                if isinstance(tp, tuple) and len(tp) >= 3 and tp[0] == 1 and isinstance(tp[2], str): parts.append(tp[2])
        except: pass
        return ' '.join(parts)

    def extract_bookwork_code(self, layout):
        return bookwork.extract_code(self.extract_q(layout))

    def is_bookwork_check(self, layout):
        return bookwork.is_check(self.extract_q(layout))

    async def reg_start(self, sess, act_idx, fake_time=None):
        if fake_time is not None: ts = int(fake_time * 1000000)
        else: ts = int((time.time() - random.random() * 360) * 1000000)
        try: await grpc(self.http, f"{STUDENT_API}/ActivityAction", [(1, 0, 1), (2, 2, [(1, 0, ts // 1000000), (2, 0, (ts % 1000000) * 1000)]), (6, 2, [(1, 0, act_idx)])], sess['token'], sess.get('session_id',''), sess.get('cookies',{}))
        except: pass

    async def submit(self, sess, task_idx, act_idx, answers, fake_time=None):
        if fake_time is not None: ts = int(fake_time * 1000000)
        else: ts = int(time.time() * 1000000)
        raw = await grpc(self.http, f"{STUDENT_API}/ActivityAction", [(1, 0, 1), (2, 2, [(1, 0, ts // 1000000), (2, 0, ts % 1000000)]), (5, 2, [(1, 0, task_idx), (3, 2, json.dumps({"answers": answers}))])], sess['token'], sess.get('session_id',''), sess.get('cookies',{}))
        if not raw: return False
        for _, _, val in raw:
            if isinstance(val, list):
                for f in val:
                    if isinstance(f, tuple) and f[0] == 2: return f[2] == "SUCCESS"
        return True

    async def submit_bookwork_check(self, sess, task_idx, act_idx, answer_text):
        ts = int(time.time() * 1000000)
        raw = await grpc(self.http, f"{STUDENT_API}/ActivityAction", [(1, 0, 1), (2, 2, [(1, 0, ts // 1000000), (2, 0, ts % 1000000)]), (5, 2, [(1, 0, task_idx), (3, 2, json.dumps({"answers": [{"id": "answer", "answer": str(answer_text)}]}))])], sess['token'], sess.get('session_id',''), sess.get('cookies',{}))
        if not raw: return False
        for _, _, val in raw:
            if isinstance(val, list):
                for f in val:
                    if isinstance(f, tuple) and f[0] == 2: return f[2] == "SUCCESS"
        return True

    async def solve_q(self, q): return await self.ai.solve(q)

# ═══════════════════════════════════════════
# DISCORD BOT SETUP
# ═══════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
sparx = SparxClient()

# ═══════════════════════════════════════════
# STATUS CHANNEL & VOICE CHANNEL
# ═══════════════════════════════════════════
status_message = None
_last_voice_name = None
_last_voice_update = 0

async def update_status_channel():
    global status_message
    if not TEXT_CHANNEL_ID:
        logger.warning("No TEXT_CHANNEL_ID configured")
        return
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if not channel:
        logger.warning(f"Text channel {TEXT_CHANNEL_ID} not found")
        return
    embed = bot_status.to_embed()
    if status_message:
        try:
            await status_message.edit(embed=embed)
            return
        except:
            status_message = None
    try:
        async for msg in channel.history(limit=50):
            if msg.author == bot.user and msg.embeds and msg.embeds[0].title and "Platform Status" in msg.embeds[0].title:
                status_message = msg
                await status_message.edit(embed=embed)
                return
    except:
        pass
    status_message = await channel.send(embed=embed)

async def update_voice_channel():
    global _last_voice_name, _last_voice_update
    if not VOICE_CHANNEL_ID:
        logger.warning("No VOICE_CHANNEL_ID configured")
        return
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if not channel:
        logger.warning(f"Voice channel {VOICE_CHANNEL_ID} not found")
        return
    all_statuses = [p["status"] for p in bot_status.get_all().values()]
    if any(s == "offline" for s in all_statuses): status_str = "offline"
    elif any(s == "idle" for s in all_statuses): status_str = "idle"
    elif any(s == "dnd" for s in all_statuses): status_str = "maintenance"
    else: status_str = "online"
    emoji = {"online": "🟢", "idle": "🟡", "maintenance": "🟠", "offline": "🔴"}.get(status_str, "⚪")
    new_name = f"sparx: {emoji} {status_str}"
    now = time.time()
    if new_name == _last_voice_name and now - _last_voice_update < 15:
        return
    try:
        await channel.edit(name=new_name)
        _last_voice_name = new_name
        _last_voice_update = now
    except discord.HTTPException:
        pass

# ═══════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════
def is_owner_or_admin():
    async def predicate(ctx):
        if ctx.author.id == OWNER_ID: return True
        if ADMIN_ROLE_ID and ADMIN_ROLE_ID in [r.id for r in ctx.author.roles]: return True
        return False
    return commands.check(predicate)

@bot.command(name="sync")
@is_owner_or_admin()
async def cmd_sync(ctx):
    await ctx.send("Syncing commands...", delete_after=5)
    await bot.tree.sync()
    await ctx.send("✅ Commands synced!", delete_after=10)

@bot.command(name="setstatus")
@is_owner_or_admin()
async def cmd_setstatus(ctx, platform: str = None, status: str = None):
    if not platform or not status:
        plist = "\n".join([f"  `{k}` \u2014 {v['name']} ({bot_status.status_text(v['status'])})" for k, v in bot_status.get_all().items()])
        await ctx.send(f"Usage: `{COMMAND_PREFIX}setstatus <platform> <online/idle/dnd/offline>`\nPlatforms:\n{plist}", delete_after=30)
        return
    if platform not in bot_status.get_all():
        await ctx.send(f"Unknown: `{platform}`", delete_after=10)
        return
    if status not in ("online", "idle", "dnd", "offline"):
        await ctx.send("Must be: `online/idle/dnd/offline`", delete_after=10)
        return
    bot_status.set(platform, status)
    await update_status_channel()
    await update_voice_channel()
    await ctx.send(f"✅ Set `{platform}` to `{status}`", delete_after=10)

# ═══════════════════════════════════════════
# MODALS
# ═══════════════════════════════════════════
class SettingsModal(Modal, title="Bot Settings"):
    def __init__(self, current_settings):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="Submit Delay (sec)", default=str(current_settings.get('submit_delay', 2.5))))
        self.add_item(TextInput(label="Max AI Retries", default=str(current_settings.get('max_retries', 3))))
        self.add_item(TextInput(label="AI Timeout (sec)", default=str(current_settings.get('ai_timeout', 30))))
        self.add_item(TextInput(label="Questions per batch", default=str(current_settings.get('batch_size', 'all'))))
    async def on_submit(self, interaction: discord.Interaction):
        s = store(interaction.user.id)
        try:
            s['settings']['submit_delay'] = max(0.5, float(self.children[0].value))
            s['settings']['max_retries'] = max(1, int(self.children[1].value))
            s['settings']['ai_timeout'] = max(5, int(self.children[2].value))
            s['settings']['batch_size'] = self.children[3].value
            await interaction.response.send_message("✅ Settings saved", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Invalid: {e}", ephemeral=True)

class TimeModeModal(Modal, title="Time Mode Settings"):
    def __init__(self, current_settings):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="Mode: fake or wait", default=current_settings.get('time_mode', 'fake')))
        self.add_item(TextInput(label="Fake MIN secs/q", default=str(current_settings.get('fake_min_secs', 10))))
        self.add_item(TextInput(label="Fake MAX secs/q", default=str(current_settings.get('fake_max_secs', 45))))
        self.add_item(TextInput(label="Wait secs/q", default=str(current_settings.get('wait_secs_per_q', 30))))
        self.add_item(TextInput(label="Save working: true/false", default=str(current_settings.get('save_working', True)).lower()))
    async def on_submit(self, interaction: discord.Interaction):
        s = store(interaction.user.id)
        mode = self.children[0].value.strip().lower()
        if mode not in ('fake', 'wait'):
            await interaction.response.send_message("❌ Must be 'fake' or 'wait'", ephemeral=True)
            return
        s['settings']['time_mode'] = mode
        try:
            s['settings']['fake_min_secs'] = max(1, int(self.children[1].value))
            s['settings']['fake_max_secs'] = max(1, int(self.children[2].value))
            if s['settings']['fake_min_secs'] > s['settings']['fake_max_secs']:
                s['settings']['fake_min_secs'], s['settings']['fake_max_secs'] = s['settings']['fake_max_secs'], s['settings']['fake_min_secs']
        except:
            s['settings']['fake_min_secs'] = 10
            s['settings']['fake_max_secs'] = 45
        try:
            s['settings']['wait_secs_per_q'] = max(1, int(self.children[3].value))
        except:
            s['settings']['wait_secs_per_q'] = 30
        sw = self.children[4].value.strip().lower()
        s['settings']['save_working'] = sw in ('true', 'yes', '1', 'on')
        await interaction.response.send_message(f"✅ Mode: `{mode}` | Fake: `{s['settings']['fake_min_secs']}-{s['settings']['fake_max_secs']}s` | Wait: `{s['settings']['wait_secs_per_q']}s` | Save: `{s['settings']['save_working']}`", ephemeral=True)

# ═══════════════════════════════════════════
# VIEWS — ALL EPHEMERAL
# ═══════════════════════════════════════════
class HubView(View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
        self._build()

    def _build(self):
        s = store(self.user_id)
        has_acc = bool(s['accounts']) and s['active'] >= 0

        if has_acc:
            self.add_item(Button(label="📋 Homeworks", style=discord.ButtonStyle.primary, row=0, custom_id="hws"))
            self.add_item(Button(label="▶ Auto-Complete", style=discord.ButtonStyle.success, row=0, custom_id="auto"))
            self.add_item(Button(label="👤 Accounts", style=discord.ButtonStyle.secondary, row=0, custom_id="acc"))
        self.add_item(Button(label="🔑 Login", style=discord.ButtonStyle.primary, row=1, custom_id="login", disabled=len(s['accounts']) >= MAX_ACCOUNTS))
        self.add_item(Button(label="🏫 Schools", style=discord.ButtonStyle.secondary, row=1, custom_id="schools"))
        self.add_item(Button(label="🤖 Test AI", style=discord.ButtonStyle.secondary, row=1, custom_id="ai"))
        self.add_item(Button(label="⏱ Time Mode", style=discord.ButtonStyle.gray, row=2, custom_id="time"))
        self.add_item(Button(label="⚙ Settings", style=discord.ButtonStyle.gray, row=2, custom_id="settings"))
        self.add_item(Button(label="📝 Working Out", style=discord.ButtonStyle.gray, row=2, custom_id="wo"))
        self.add_item(Button(label="📊 Status", style=discord.ButtonStyle.gray, row=3, custom_id="status"))
        if has_acc:
            label = "📩 DM: ON" if s.get('dm_update', True) else "📩 DM: OFF"
            style = discord.ButtonStyle.success if s.get('dm_update', True) else discord.ButtonStyle.danger
            self.add_item(Button(label=label, style=style, row=3, custom_id="dm"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def callback_handler(self, interaction: discord.Interaction, custom_id: str):
        s = store(interaction.user.id)

        if custom_id == "hws":
            if not s['accounts']:
                await interaction.response.send_message("❌ No accounts", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            for acc in s['accounts']:
                try:
                    hws = await sparx.get_homeworks(acc)
                    if not hws: continue
                    e = EmbedBuilder._base(EmbedBuilder.COLORS["sparx"])
                    e.title = f"📚 Homework for {acc.get('user_name',acc['username'])} @ {acc.get('school_name','?')}"
                    e.set_footer(text="Sparx Maths | Powered by Manus AI")
                    for h in hws:
                        pct = (h['completed_qs']/h['total_qs']*100) if h['total_qs']>0 else 0
                        e.add_field(name=f"{progress_bar(pct)} {h['name'][:40]}", value=f"Due: `{h['due'][:10] or 'N/A'}` | `{h['completed_qs']}/{h['total_qs']}`", inline=False)
                    await interaction.followup.send(embed=e, ephemeral=True)
                except: continue

        elif custom_id == "auto":
            if not s['accounts'] or s['active'] < 0:
                await interaction.response.send_message("❌ Login first", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("📋 Fetching homeworks...", ephemeral=True)
            try:
                acc = s['accounts'][s['active']]
                hws = await sparx.get_homeworks(acc)
                if not hws:
                    await interaction.followup.send("❌ No homeworks", ephemeral=True)
                    return
                pkg_id = hws[0]['id']
                hw_name = hws[0]['name']
                if s.get("dm_update", True):
                    dm_channel = interaction.user.dm_channel or await interaction.user.create_dm()
                    dm_embed = EmbedBuilder.info(f"▶ Auto-completing **{hw_name}**", "Starting homework auto-completion...", footer_text="Sparx Maths | Powered by Manus AI")
                    dm_msg = await dm_channel.send(embed=dm_embed)
                else:
                    dm_msg = None
                msg = await interaction.followup.send(f"▶ Auto-completing **{hw_name}**...", ephemeral=True)
                
                # GetTaskList
                raw = await grpc(sparx.http, f"{STUDENT_API}/GetTaskList",
                    [(1, 0, 1), (2, 2, [(3, 2, pkg_id)])],
                    acc['token'], acc.get('session_id',''), acc.get('cookies',{}))
                if not raw:
                    await interaction.followup.send("❌ No task data", ephemeral=True)
                    return
                    
                tasks = []
                for _, _, val in raw:
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, tuple) and len(item) >= 3 and item[0] == 1 and isinstance(item[2], list):
                                tasks.append(item[2])
                if not tasks:
                    await interaction.followup.send("❌ No tasks found", ephemeral=True)
                    return
                
                total = len(tasks)
                for t_idx, task in enumerate(tasks):
                    task_name = ""
                    acts = []
                    for f in task:
                        if isinstance(f, tuple):
                            fi, _, fv = f
                            if fi == 1 and isinstance(fv, str): task_name = fv[:50]
                            elif fi == 4 and isinstance(fv, list): acts = fv
                    if not acts: continue
                    for a_idx, act_val in enumerate(acts):
                        act_id = act_val[2] if isinstance(act_val, tuple) and len(act_val) >= 3 and act_val[0] == 5 else a_idx
                        layout_data = await sparx.get_activity(acc, pkg_id, t_idx, act_id)
                        if not layout_data: continue
                        layout = layout_data.get('layout', {})
                        q_text = sparx.extract_q(layout)
                        if not q_text: continue
                        
                        code_ = sparx.extract_bookwork_code(layout)
                        if code_:
                            known = bookwork.find(code_)
                            if known:
                                ans = known.get('answer', known)
                                if isinstance(ans, str): await sparx.submit_bookwork_check(acc, t_idx, act_id, ans)
                                else: await sparx.submit(acc, t_idx, act_id, ans)
                            continue
                        
                        solved = await sparx.solve_q(q_text)
                        if not solved: continue
                        await sparx.reg_start(acc, act_id)
                        per_q = random.uniform(s['settings'].get('fake_min_secs', 4), s['settings'].get('fake_max_secs', 8)) if s['settings'].get('time_mode') == 'fake' else s['settings'].get('wait_secs_per_q', 5)
                        await asyncio.sleep(per_q)
                        await sparx.submit(acc, t_idx, act_id, solved)
                    
                    pct = (t_idx + 1) / total * 100

                    await interaction.edit_original_response(content=f"▶ **{hw_name}**
{bar} Task **{t_idx+1}/{total}**")
                
                await interaction.edit_original_response(content=f"✅ **{hw_name}** complete!")
            except Exception as e:
                await interaction.edit_original_response(content=f"❌ {str(e)[:2000]}")

        elif custom_id == "acc":
            if not s['accounts']:
                await interaction.response.send_message("❌ No accounts", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            lines = [f"**Accounts (`{len(s['accounts'])}/{MAX_ACCOUNTS}`):**"]
            for idx, acc in enumerate(s['accounts']):
                marker = " ◀ **ACTIVE**" if idx == s['active'] else ""
                lines.append(f"`{idx+1}.` {acc.get('user_name',acc['username'])} @ {acc.get('school_name','?')}{marker}")
            await interaction.followup.send('\n'.join(lines), view=AccountManageView(interaction.user.id), ephemeral=True)

        elif custom_id == "login":
            if len(s['accounts']) >= MAX_ACCOUNTS:
                await interaction.response.send_message(f"❌ Max `{MAX_ACCOUNTS}` accounts", ephemeral=True)
                return
            await interaction.response.send_modal(LoginModal())

        elif custom_id == "schools":
            await interaction.response.send_modal(SchoolSearchModal())

        elif custom_id == "ai":
            await interaction.response.send_modal(AITestModal())

        elif custom_id == "time":
            await interaction.response.send_modal(TimeModeModal(s['settings']))

        elif custom_id == "settings":
            await interaction.response.send_modal(SettingsModal(s['settings']))

        elif custom_id == "wo":
            if not s['working_out']:
                await interaction.response.send_message("No working out saved", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            now = time.time()
            valid = [w for w in s['working_out'] if now - w['timestamp'] < 600]
            s['working_out'] = valid
            if not valid:
                await interaction.followup.send("All expired", ephemeral=True)
                return
            lines = [f"**Working Out (`{len(valid)}` entries):**"]
            for w in valid:
                remaining_secs = int(600 - (now - w['timestamp']))
                lines.append(f"`{w['code']}` (`{remaining_secs}s`): {w['answer']}")
            await interaction.followup.send('\n'.join(lines), ephemeral=True)

        elif custom_id == "status":
            await interaction.response.defer(ephemeral=True)
            e = EmbedBuilder._base(EmbedBuilder.COLORS["primary"])
            e.title = "📊 Bot Status"
            e.set_footer(text="Sparx Maths | Powered by Manus AI")
            e.add_field(name="Accounts", value=f"`{len(s['accounts'])}/{MAX_ACCOUNTS}`")
            if s['accounts'] and s['active'] >= 0:
                a = s['accounts'][s['active']]
                e.add_field(name="Active", value=f"{a.get('user_name',a['username'])} @ {a.get('school_name','?')}", inline=False)
            st = s['settings']
            e.add_field(name="Settings", value=f"Delay: `{st.get('submit_delay',2.5)}s` | Retry: `{st.get('max_retries',3)}` | Mode: `{st.get('time_mode','fake')}`", inline=False)
            e.add_field(name="Working", value=f"`{len(s['working_out'])}` entries")
            for key, p in bot_status.get_all().items():
                emoji = bot_status.status_emoji(p["status"])
                e.add_field(name=f"{emoji} {p['name']}", value=f"`{bot_status.status_text(p['status'])}`", inline=True)
            await interaction.followup.send(embed=e, ephemeral=True)

        elif custom_id == "dm":
            s['dm_update'] = not s.get('dm_update', True)
            status = "ON" if s['dm_update'] else "OFF"
            await interaction.response.send_message(f"📩 DM updates: **{status}**", ephemeral=True)

# Override on_message for button handling
@bot.listen()
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        # Route to the view's callback handler
        view = interaction.message.view if interaction.message else None
        if isinstance(view, HubView):
            custom_id = interaction.data.get("custom_id", "")
            await view.callback_handler(interaction, custom_id)

class AccountManageView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        s = store(user_id)
        opts = [discord.SelectOption(label=f"{idx+1}. {acc.get('user_name',acc['username'])}", value=str(idx), default=(idx == s['active'])) for idx, acc in enumerate(s['accounts'])]
        if opts: self.add_item(SwitchSelect(opts))
    @discord.ui.button(label="🗑 Remove All", style=discord.ButtonStyle.danger, row=1)
    async def remove_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = store(interaction.user.id)
        s['accounts'].clear(); s['active'] = -1
        await interaction.response.send_message("✅ All removed", ephemeral=True)

class SwitchSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Switch account...", options=options, row=0)
    async def callback(self, interaction: discord.Interaction):
        s = store(interaction.user.id)
        idx = int(self.values[0])
        s['active'] = idx
        await interaction.response.send_message(f"✅ Switched to `{s['accounts'][idx].get('user_name',s['accounts'][idx]['username'])}`", ephemeral=True)

class LoginModal(Modal, title="Sparx Login"):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="Username"))
        self.add_item(TextInput(label="Password"))
        self.add_item(TextInput(label="School name"))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = self.children[0].value; pwd = self.children[1].value; school_q = self.children[2].value
        matches = await sparx.search_schools(school_q)
        if not matches:
            await interaction.followup.send(f"❌ No schools for `{school_q}`", ephemeral=True); return
        if len(matches) > 1:
            e = EmbedBuilder.info("Select your school", f"Found `{len(matches)}`", footer_text="Sparx Maths | Powered by Manus AI")
            for idx, s in enumerate(matches[:10]): e.add_field(name=f"`{idx+1}.` {s.name}", value=s.town or "\u2014", inline=False)
            await interaction.followup.send(embed=e, view=SchoolSelectView(matches, user, pwd), ephemeral=True); return
        school = matches[0]
        st = store(interaction.user.id)
        if len(st['accounts']) >= MAX_ACCOUNTS:
            await interaction.followup.send(f"❌ Max `{MAX_ACCOUNTS}`", ephemeral=True); return
        try:
            sess = await sparx.login(user, pwd, school)
            st['accounts'].append(sess); st['active'] = len(st['accounts']) - 1
            e = EmbedBuilder.success("Login Successful", f"**{sess.get('user_name',user)}**\n{school.name}", footer_text="Sparx Maths | Powered by Manus AI")
            await interaction.followup.send(embed=e, ephemeral=True)
        except Exception as e:
            e = EmbedBuilder.error("Login Failed", str(e)[:2000], footer_text="Sparx Maths | Powered by Manus AI")
            await interaction.followup.send(embed=e, ephemeral=True)

class SchoolSelectView(View):
    def __init__(self, schools, username, password):
        super().__init__(timeout=120)
        self.schools = schools[:10]; self.username = username; self.password = password
        opts = [discord.SelectOption(label=s.name[:100], value=str(idx), description=s.town or '') for idx, s in enumerate(schools[:10])]
        self.add_item(SchoolPickSelect(opts, self))
class SchoolPickSelect(Select):
    def __init__(self, opts, parent):
        super().__init__(placeholder="Select school...", options=opts); self.parent = parent
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        school = self.parent.schools[int(self.values[0])]
        st = store(interaction.user.id)
        if len(st['accounts']) >= MAX_ACCOUNTS:
            await interaction.followup.send(f"❌ Max `{MAX_ACCOUNTS}`", ephemeral=True); return
        try:
            sess = await sparx.login(self.parent.username, self.parent.password, school)
            st['accounts'].append(sess); st['active'] = len(st['accounts']) - 1
            e = EmbedBuilder.success("Login Successful", f"**{sess.get('user_name',self.parent.username)}**\n{school.name}", footer_text="Sparx Maths | Powered by Manus AI")
            await interaction.followup.send(embed=e, ephemeral=True)
        except Exception as e:
            e = EmbedBuilder.error("Login Failed", str(e)[:2000], footer_text="Sparx Maths | Powered by Manus AI")
            await interaction.followup.send(embed=e, ephemeral=True)

class SchoolSearchModal(Modal, title="Search Schools"):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="School name"))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        q = self.children[0].value
        matches = await sparx.search_schools(q)
        if not matches:
            await interaction.followup.send(f"❌ No schools for `{q}`", ephemeral=True); return
        e = EmbedBuilder.info(f"🏫 Schools matching `{q}`", f"Found `{min(len(matches),20)}`", footer_text="Sparx Maths | Powered by Manus AI")
        for s in matches[:20]: e.add_field(name=s.name, value=s.town or "\u2014", inline=False)
        if len(matches) > 20: e.set_footer(text=f"+{len(matches)-20} more")
        await interaction.followup.send(embed=e, ephemeral=True)

class AITestModal(Modal, title="Test AI Solver"):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="Math question", style=discord.TextStyle.long))
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        q = self.children[0].value
        ans = await sparx.solve_q(q)
        if ans:
            e = EmbedBuilder.success("AI Solved", f"**Q:** {q}\n```json\n{json.dumps(ans, indent=2)}\n```", footer_text="Sparx Maths | Powered by Manus AI")
            await interaction.followup.send(embed=e, ephemeral=True)
        else: await interaction.followup.send("❌ All AI failed", ephemeral=True)

# ═══════════════════════════════════════════
# TEXT COMMANDS
# ═══════════════════════════════════════════
@bot.command(name="login")
async def cmd_login(ctx, *, school_name: str = None):
    s = store(ctx.author.id)
    if len(s['accounts']) >= MAX_ACCOUNTS:
        await ctx.send(f"❌ Max `{MAX_ACCOUNTS}`", delete_after=10); return
    if not school_name:
        await ctx.send(f"Usage: `{COMMAND_PREFIX}login <school>`", delete_after=10); return
    await ctx.send("🔍 Searching...", delete_after=5)
    matches = await sparx.search_schools(school_name)
    if not matches:
        await ctx.send(f"❌ No schools for `{school_name}`", delete_after=10); return
    school = matches[0]
    def check(m): return m.author == ctx.author and m.channel == ctx.channel
    try:
        await ctx.send(f"🏫 **{school.name}**\nReply with **username**:", delete_after=60)
        msg1 = await bot.wait_for('message', timeout=60.0, check=check)
        username = msg1.content.strip(); await msg1.delete()
        await ctx.send("🔑 Reply with **password**:", delete_after=60)
        msg2 = await bot.wait_for('message', timeout=60.0, check=check)
        password = msg2.content.strip(); await msg2.delete()
        await ctx.send("⏳ Logging in...", delete_after=10)
        sess = await sparx.login(username, password, school)
        s['accounts'].append(sess); s['active'] = len(s['accounts']) - 1
        e = EmbedBuilder.success("Login Successful", f"**{sess.get('user_name',username)}**\n{school.name}", footer_text="Sparx Maths | Powered by Manus AI")
        await ctx.send(embed=e, delete_after=30)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timed out", delete_after=10)
    except Exception as e:
        e = EmbedBuilder.error("Login Failed", str(e)[:2000], footer_text="Sparx Maths | Powered by Manus AI")
        await ctx.send(embed=e, delete_after=60)

@bot.command(name="schools")
async def cmd_schools(ctx, *, query: str):
    await ctx.send("🔍 Searching...", delete_after=5)
    matches = await sparx.search_schools(query)
    if not matches:
        await ctx.send(f"❌ No schools for `{query}`", delete_after=10); return
    e = EmbedBuilder.info(f"🏫 Schools matching `{query}`", f"Found `{min(len(matches),20)}`", footer_text="Sparx Maths | Powered by Manus AI")
    for s in matches[:20]: e.add_field(name=s.name, value=s.town or "\u2014", inline=False)
    if len(matches) > 20: e.set_footer(text=f"+{len(matches)-20} more")
    await ctx.send(embed=e, delete_after=60)

@bot.command(name="homework", aliases=["hw"])
async def cmd_homework(ctx):
    s = store(ctx.author.id)
    if not s['accounts']:
        await ctx.send("❌ No accounts. Use `s!login`", delete_after=10); return
    await ctx.send("📋 Fetching...", delete_after=5)
    for acc in s['accounts']:
        try:
            hws = await sparx.get_homeworks(acc)
            if not hws: continue
                    e = EmbedBuilder._base(EmbedBuilder.COLORS["sparx"])
                    e.title = f"📚 Homework for {acc.get(\'user_name\',acc[\'username\'])} @ {acc.get(\'school_name\',\'?\')}"
                    e.set_footer(text="Sparx Maths | Powered by Manus AI")
                    for h in hws:
                        pct = (h["completed_qs"]/h["total_qs"]) if h["total_qs"]>0 else 0
                        bar = EmbedBuilder._progress_bar(pct)
                        status = "✅" if h["completed_qs"] >= h["total_qs"] else "⏳"
                        e.add_field(name=f"{status} {bar} {h["name"][:40]}", value=f"Due: `{h["due"][:10] or 'N/A'}` | `{h["completed_qs"]}/{h["total_qs"]}`", inline=False)
                    await ctx.send(embed=e, delete_after=120)
        except: continue

@bot.command(name="accounts", aliases=["acc"])
async def cmd_accounts(ctx):
    s = store(ctx.author.id)
    if not s['accounts']:
        await ctx.send("❌ No accounts", delete_after=10); return
    lines = [f"**Accounts (`{len(s['accounts'])}/{MAX_ACCOUNTS}`):**"]
    for idx, acc in enumerate(s['accounts']):
        marker = " ◀ **ACTIVE**" if idx == s['active'] else ""
        lines.append(f"`{idx+1}.` {acc.get('user_name',acc['username'])} @ {acc.get('school_name','?')}{marker}")
    await ctx.send('\n'.join(lines), delete_after=30)

@bot.command(name="switch")
async def cmd_switch(ctx, index: int = None):
    s = store(ctx.author.id)
    if not s['accounts']:
        await ctx.send("❌ No accounts", delete_after=10); return
    if index is None or index < 1 or index > len(s['accounts']):
        await ctx.send(f"Usage: `{COMMAND_PREFIX}switch <1-{len(s['accounts'])}>`", delete_after=10); return
    s['active'] = index - 1
    acc = s['accounts'][s['active']]
    await ctx.send(f"✅ Switched to **{acc.get('user_name',acc['username'])}**", delete_after=15)

@bot.command(name="working", aliases=["wo"])
async def cmd_working(ctx):
    s = store(ctx.author.id)
    if not s['working_out']:
        await ctx.send("No working out saved", delete_after=10); return
    now = time.time()
    valid = [w for w in s['working_out'] if now - w['timestamp'] < 600]
    s['working_out'] = valid
    if not valid:
        await ctx.send("All expired", delete_after=10); return
    lines = [f"**Working Out (`{len(valid)}` entries):**"]
    for w in valid:
        remaining_secs = int(600 - (now - w['timestamp']))
        lines.append(f"`{w['code']}` (`{remaining_secs}s`): {w['answer']}")
    await ctx.send('\n'.join(lines), delete_after=60)

@bot.command(name="status")
async def cmd_status(ctx):
    s = store(ctx.author.id)
    e = EmbedBuilder._base(EmbedBuilder.COLORS["primary"])
    e.title = "📊 Bot Status"
    e.set_footer(text="Sparx Maths | Powered by Manus AI")
    e.add_field(name="Accounts", value=f"`{len(s['accounts'])}/{MAX_ACCOUNTS}`")
    if s['accounts'] and s['active'] >= 0:
        a = s['accounts'][s['active']]
        e.add_field(name="Active", value=f"{a.get('user_name',a['username'])} @ {a.get('school_name','?')}", inline=False)
    st = s['settings']
    e.add_field(name="Settings", value=f"Delay: `{st.get('submit_delay',2.5)}s` | Retry: `{st.get('max_retries',3)}` | Mode: `{st.get('time_mode','fake')}`", inline=False)
    for key, p in bot_status.get_all().items():
        emoji = bot_status.status_emoji(p["status"])
        e.add_field(name=f"{emoji} {p['name']}", value=f"`{bot_status.status_text(p['status'])}`", inline=True)
    await ctx.send(embed=e, delete_after=30)

@bot.command(name="dmupdate", aliases=["dm"])
async def cmd_dmupdate(ctx, toggle: str = None):
    s = store(ctx.author.id)
    if toggle and toggle.lower() in ("on", "true", "yes", "1"):
        s['dm_update'] = True
        await ctx.send("✅ DM updates **enabled**", delete_after=10)
    elif toggle and toggle.lower() in ("off", "false", "no", "0"):
        s['dm_update'] = False
        await ctx.send("✅ DM updates **disabled**", delete_after=10)
    else:
        await ctx.send(f"DM updates: `{'ON' if s.get('dm_update', True) else 'OFF'}`\nUse `{COMMAND_PREFIX}dmupdate on/off`", delete_after=15)

@bot.command(name="hub", aliases=["h", "menu", "help"])
async def cmd_hub(ctx):
    s = store(ctx.author.id)
    has_accounts = bool(s['accounts']) and s['active'] >= 0
    e = EmbedBuilder._base(EmbedBuilder.COLORS["primary"])
    e.title = "🤖 Sparx Command Centre"
    e.set_footer(text="Sparx Maths | Powered by Manus AI")
    if has_accounts:
        a = s['accounts'][s['active']]
        e.add_field(name="Active", value=f"{a.get('user_name',a['username'])} @ {a.get('school_name','?')}", inline=False)
    else:
        e.add_field(name="Status", value="❌ Not logged in", inline=False)
    e.add_field(name="Accounts", value=f"`{len(s['accounts'])}/{MAX_ACCOUNTS}`", inline=True)
    e.add_field(name="Mode", value=f"`{s['settings'].get('time_mode','fake')}`", inline=True)
    cmds = [f"`{COMMAND_PREFIX}{c}" for c in [
        "login <school>`", "schools <name>`", "homework` / `s!hw`",
        "accounts` / `s!acc`", "switch <n>`", "working` / `s!wo`",
        "status`", "dmupdate on/off`", "ping`"
    ]]
    e.add_field(name="Commands", value='\n'.join(cmds), inline=False)
    for key, p in bot_status.get_all().items():
        emoji = bot_status.status_emoji(p["status"])
        e.add_field(name=f"{emoji} {p['name']}", value=f"`{bot_status.status_text(p['status'])}`", inline=True)
    e.set_footer(text="GIOAI Sparx v3.2")
    await ctx.send(embed=e, view=HubView(ctx.author.id), delete_after=600)

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`", delete_after=5)

# ═══════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════
@bot.event
async def on_ready():
    print("")
    print("GIOAI Sparx v3.2")
    print(f"Logged in: {bot.user}")
    print(f"Guild: {GUILD_ID}")
    print("")

    # Validate channels
    if TEXT_CHANNEL_ID:
        tc = bot.get_channel(TEXT_CHANNEL_ID)
        if tc: logger.info(f"Status channel: #{tc.name}")
        else: logger.warning(f"Text channel {TEXT_CHANNEL_ID} not found")
    if VOICE_CHANNEL_ID:
        vc = bot.get_channel(VOICE_CHANNEL_ID)
        if vc: logger.info(f"Voice channel: {vc.name}")
        else: logger.warning(f"Voice channel {VOICE_CHANNEL_ID} not found")

    asyncio.create_task(sparx.get_schools())
    asyncio.create_task(working_out_sweeper())

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{COMMAND_PREFIX}hub"))

    bot_status.set("sparx", "online")
    await update_status_channel()
    await update_voice_channel()

    async def periodic_status():
        while True:
            await asyncio.sleep(300)
            await update_status_channel()
            await update_voice_channel()
    asyncio.create_task(periodic_status())
    logger.info("Bot is fully operational")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission", delete_after=10)
    else:
        await ctx.send(f"❌ Error: `{error}`", delete_after=15)

# ═══════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════
if __name__ == "__main__":
    print("GIOAI Sparx Platform launching...")
    bot.run(TOKEN)
