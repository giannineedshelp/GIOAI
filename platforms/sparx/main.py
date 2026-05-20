#!/usr/bin/env python3
# GIOAI - Sparx Maths Platform
import discord, httpx, json, base64, re, asyncio, struct, time, random, os, sys
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared.protobuf.decoder import grpc, dec
from shared.utils.helpers import get, fmt_bar
from platforms.sparx.bookwork import bookwork

# ═══ CONFIG ═══
TOKEN = get("DISCORD_TOKEN", "MTUwNTU2NjI0Mzc5NTc2NzMwNg.GamgKq.mD0vTG6n1xpO6ipVcblru-WzCfAcyuxphDTlAU")
GEMINI_KEY = get("GEMINI_API_KEY", "AIzaSyAwzESNJQkRR3Z6TMrP7bhh6NFZTETRkjI")
GROQ_KEY = get("GROQ_API_KEY", "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")
MISTRAL_KEY = get("MISTRAL_API_KEY", "tuA0sQD2Jrjia1g3jqyLZY7vEhHfu1AY")
DEEPSEEK_KEY = get("DEEPSEEK_API_KEY", "sk-01554e4f8dba43469a4956970362ae00")
SAMBA_KEY = get("SAMBA_API_KEY", "685ad03c-6b2f-4861-8846-e2b43374895d")
FIREWORKS_KEY = get("FIREWORKS_API_KEY", "fw_KTAMYNeyqr2ozWsH5q2r2R")
OPENROUTER_KEY = get("OPENROUTER_API_KEY", "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")
MAX_ACCOUNTS = int(get("MAX_ACCOUNTS", "5"))

SCHOOLS_URL = "https://static.sparxhomework.uk/sl/spx001/data.txt"
AUTH_URL = "https://auth.sparxmaths.uk/oauth2/auth"
TOKEN_URL = "https://auth.sparxmaths.uk/oauth2/token"
STUDENT_API = "https://studentapi.api.sparxmaths.uk/sparx.swworker.v1.Sparxweb"
DASHBOARD_URL = "https://maths.sparx-learning.com/api/student"
CLIENT_ID = "sparx-maths-sw"
REDIRECT_URI = "https://studentapi.api.sparxmaths.uk/oauth/callback"
LOCAL_SCHOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache", "schools.txt")

# ═══ STORAGE ═══
school_cache = None; user_store = {}

def store(uid):
    if uid not in user_store:
        user_store[uid] = {
            'accounts': [], 'active': -1,
            'settings': {'sd': 3.0, 'mr': 3, 'ato': 30, 'bat': 'all', 'tm': 'fake', 'fmin': 10, 'fmax': 45, 'wsq': 30, 'sv': True},
            'wo': [], 'bwm': {},
        }
    return user_store[uid]

async def wo_sweep():
    while True:
        await asyncio.sleep(60); nw = time.time()
        for uid in list(user_store.keys()):
            s = user_store[uid]; s['wo'] = [w for w in s['wo'] if nw - w['t'] < 600]; bookwork.cleanup()

class School:
    def __init__(self, id, name, slug, town):
        self.id = id; self.name = name; self.slug = slug; self.town = town

# ═══ AI ─ 7 PROVIDERS ═══
class AI:
    def __init__(self): self.h = httpx.AsyncClient(timeout=60)
    def _p(self, t):
        if not t: return []
        for p in [r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', r'(\[[\s\S]*?\])']:
            m = re.search(p, t)
            if m:
                try: return json.loads(m.group(1))
                except: pass
        try: return json.loads(t.strip())
        except: return []

    async def solve(self, q):
        pr = f"Output ONLY valid JSON array with id and answer fields. Numbers = decimals. No fractions. Solve: {q}"
        for n, u, h, d in [
            ("Gemini", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}", {}, {"contents":[{"parts":[{"text":pr}]}],"generationConfig":{"temperature":0.05,"maxOutputTokens":1024}}),
            ("Groq", "https://api.groq.com/openai/v1/chat/completions", {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}, {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":pr}],"temperature":0.05}),
            ("Mistral", "https://api.mistral.ai/v1/chat/completions", {"Authorization":f"Bearer {MISTRAL_KEY}","Content-Type":"application/json"}, {"model":"mistral-small-latest","messages":[{"role":"user","content":pr}],"temperature":0.05}),
            ("DeepSeek", "https://api.deepseek.com/v1/chat/completions", {"Authorization":f"Bearer {DEEPSEEK_KEY}","Content-Type":"application/json"}, {"model":"deepseek-chat","messages":[{"role":"user","content":pr}],"temperature":0.05}),
            ("SambaNova", "https://api.sambanova.ai/v1/chat/completions", {"Authorization":f"Bearer {SAMBA_KEY}","Content-Type":"application/json"}, {"model":"Meta-Llama-3.1-8B-Instruct","messages":[{"role":"user","content":pr}],"temperature":0.05}),
            ("Fireworks", "https://api.fireworks.ai/inference/v1/chat/completions", {"Authorization":f"Bearer {FIREWORKS_KEY}","Content-Type":"application/json"}, {"model":"accounts/fireworks/models/llama-v3p1-8b-instruct","messages":[{"role":"user","content":pr}],"temperature":0.05}),
            ("OpenRouter", "https://openrouter.ai/api/v1/chat/completions", {"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json"}, {"model":"cognitivecomputations/dolphin-2.9.3-llama-3.1-8b:free","messages":[{"role":"user","content":pr}],"temperature":0.05}),
        ]:
            try:
                r = await self.h.post(u, headers=h, json=d)
                if r.status_code == 200:
                    t = (r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","") or r.json().get("choices",[{}])[0].get("message",{}).get("content","") or "")
                    a = self._p(t)
                    if a: return a
            except: pass
        return []

    async def sa(self, q):
        pr = f"Answer concisely with just the answer. Question: {q}"
        for n, u, h, d in [
            ("Gemini", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}", {}, {"contents":[{"parts":[{"text":pr}]}],"generationConfig":{"temperature":0.05,"maxOutputTokens":256}}),
            ("Groq", "https://api.groq.com/openai/v1/chat/completions", {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}, {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":pr}],"temperature":0.05}),
        ]:
            try:
                r = await self.h.post(u, headers=h, json=d)
                if r.status_code == 200:
                    t = (r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","") or r.json().get("choices",[{}])[0].get("message",{}).get("content","") or "")
                    if t: return t.strip()
            except: pass
        return None

# ═══ SPARX CLIENT ═══
class Client:
    def __init__(self):
        self.ai = AI(); self.h = httpx.AsyncClient(verify=False, follow_redirects=True, timeout=30)

    async def gs(self):
        global school_cache
        if school_cache: return school_cache
        if os.path.exists(LOCAL_SCHOOLS):
            with open(LOCAL_SCHOOLS) as f: raw = f.read()
        else:
            r = await self.h.get(SCHOOLS_URL); r.raise_for_status(); raw = r.text
            os.makedirs(os.path.dirname(LOCAL_SCHOOLS), exist_ok=True)
            with open(LOCAL_SCHOOLS, 'w') as f: f.write(raw)
        data = json.loads(base64.b64decode(raw.strip()))
        school_cache = [School(s['i'], s['n'], s['u'], s.get('t','')) for s in data]
        return school_cache

    async def ss(self, q):
        schools = await self.gs(); q = q.lower().strip()
        for fn in [
            lambda: [s for s in schools if s.name.lower() == q],
            lambda: [s for s in schools if s.slug.lower() == q],
            lambda: [s for s in schools if s.name.lower().startswith(q)],
            lambda: [s for s in schools if all(w in s.name.lower() for w in q.split())],
            lambda: [s for s in schools if q in s.name.lower()],
        ]:
            r = fn()
            if r: return r[:25]
        return []

    async def login(self, u, p, slug):
        sess = {'username': u, 'token': None, 'sid': '', 'uname': u, 'slug': slug, 'ck': {'cookie_preferences': '{"GA":false,"Hotjar":false,"PT":false,"version":4}', 'live-resolver-school': slug}}
        async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=30) as c:
            try:
                r = await c.post(TOKEN_URL, data={'client_id': CLIENT_ID, 'username': u, 'password': p, 'grant_type': 'password', 'scope': 'openid profile email'})
                if r.status_code == 200: j = r.json(); sess['token'] = j.get('access_token'); sess['sid'] = j.get('session_state', j.get('id_token','')[:32])
            except: pass
            if not sess['token']:
                try:
                    r = await c.get(AUTH_URL, params={'client_id': CLIENT_ID, 'hd': slug, 'redirect_uri': REDIRECT_URI, 'response_type': 'code', 'scope': 'openid profile email'})
                    mc = re.search(r'code=([^&\s"]+)', r.text)
                    if mc:
                        r2 = await c.post(TOKEN_URL, data={'client_id': CLIENT_ID, 'code': mc.group(1), 'redirect_uri': REDIRECT_URI, 'grant_type': 'authorization_code'})
                        if r2.status_code == 200: j = r2.json(); sess['token'] = j.get('access_token'); sess['sid'] = j.get('session_state','')
                except: pass
            if not sess['token']: raise Exception("Login failed")
            try:
                r = await c.get(DASHBOARD_URL, headers={'Authorization': f'Bearer {sess["token"]}'})
                if r.status_code == 200: sess['uname'] = r.json().get('user',{}).get('name', u)
            except: pass
        return sess

    async def gh(self, sess):
        ah = []
        for ep, tp in [('', 'hw'), ('/revision', 'rv'), ('/fixup', 'fx')]:
            try:
                r = await self.h.get(f"{DASHBOARD_URL}{ep}", headers={'Authorization': f'Bearer {sess["token"]}'})
                if r.status_code != 200: continue
                items = r.json()
                if not isinstance(items, list): items = items.get('packages', items.get('homeworks', []))
                for it in items: ah.append({'id': it.get('id',it.get('packageId','')), 'n': it.get('name','HW'), 'due': str(it.get('due','')), 't': tp, 'tq': it.get('totalQuestions',it.get('totalAmountOfQuestions',0)), 'cq': it.get('completedQuestions',it.get('completedAmountOfQuestions',0))})
            except: continue
        return ah

    async def ga(self, sess, pkg, ti, ai):
        raw = await grpc(self.h, f"{STUDENT_API}/GetActivity", [(1, 0, 1), (2, 2, [(1, 0, ti), (2, 2, pkg)]), (6, 2, [(1, 0, 0), (2, 0, ai)])], sess['token'], sess.get('sid',''), sess.get('ck',{}))
        if not raw: return None
        lo = {}
        for idx, typ, val in raw:
            if idx == 3 and isinstance(val, list):
                for f in val:
                    if isinstance(f, tuple) and len(f) >= 3:
                        fi, _, fv = f
                        if fi == 1: lo['id'] = str(fv)
                        elif fi == 4 and isinstance(fv, list): lo['c'] = fv
        return {'ai': ai, 'lo': lo}

    def eq(self, lo):
        parts = []
        try:
            for f in lo.get('c', []):
                if isinstance(f, tuple) and isinstance(f[2], list):
                    for sb in f[2]:
                        if isinstance(sb, tuple) and len(sb) >= 3 and sb[0] == 1 and isinstance(sb[2], list):
                            for tp in sb[2]:
                                if isinstance(tp, tuple) and len(tp) >= 3 and tp[0] == 1 and isinstance(tp[2], str): parts.append(tp[2])
        except: pass
        return ' '.join(parts)

    async def rs(self, sess, ai, ft=None):
        if ft is not None: ts = int(ft * 1000000)
        else: ts = int((time.time() - random.random() * 360) * 1000000)
        try: await grpc(self.h, f"{STUDENT_API}/ActivityAction", [(1, 0, 1), (2, 2, [(1, 0, ts // 1000000), (2, 0, (ts % 1000000) * 1000)]), (6, 2, [(1, 0, ai)])], sess['token'], sess.get('sid',''), sess.get('ck',{}))
        except: pass

    async def sub(self, sess, ti, ai, ans, ft=None):
        if ft is not None: ts = int(ft * 1000000)
        else: ts = int(time.time() * 1000000)
        raw = await grpc(self.h, f"{STUDENT_API}/ActivityAction", [(1, 0, 1), (2, 2, [(1, 0, ts // 1000000), (2, 0, ts % 1000000)]), (5, 2, [(1, 0, ti), (3, 2, json.dumps({"answers": ans}))])], sess['token'], sess.get('sid',''), sess.get('ck',{}))
        if not raw: return False
        for _, _, val in raw:
            if isinstance(val, list):
                for f in val:
                    if isinstance(f, tuple) and f[0] == 2: return f[2] == "SUCCESS"
        return True

    async def sq(self, q): return await self.ai.solve(q)

# ═══ DISCORD SETUP ═══
intents = discord.Intents.default(); intents.message_content = True
bot = commands.Bot(command_prefix=get("COMMAND_PREFIX", "s!"), intents=intents, help_command=None)
c = Client()

# ═══ MODALS ═══
class SetM(Modal, title="GIOAI Settings"):
    def __init__(self, s):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="Submit Delay (sec)", default=str(s.get('sd',3))))
        self.add_item(TextInput(label="Max Retries", default=str(s.get('mr',3))))
        self.add_item(TextInput(label="AI Timeout (sec)", default=str(s.get('ato',30))))
        self.add_item(TextInput(label="Batch size", default=str(s.get('bat','all'))))

    async def on_submit(self, i):
        s = store(i.user.id)
        try: s['settings']['sd'] = max(0.5, float(self.children[0].value)); s['settings']['mr'] = max(1, int(self.children[1].value)); s['settings']['ato'] = max(5, int(self.children[2].value)); s['settings']['bat'] = self.children[3].value; await i.response.send_message("Saved.", ephemeral=True)
        except: await i.response.send_message("Invalid.", ephemeral=True)

class TimeM(Modal, title="Time Mode"):
    def __init__(self, s):
        super().__init__(timeout=300)
        self.add_item(TextInput(label="Mode: fake or wait", default=s.get('tm','fake')))
        self.add_item(TextInput(label="Fake MIN secs", default=str(s.get('fmin',10))))
        self.add_item(TextInput(label="Fake MAX secs", default=str(s.get('fmax',45))))
        self.add_item(TextInput(label="Wait secs per q", default=str(s.get('wsq',30))))
        self.add_item(TextInput(label="Save working: t/f", default=str(s.get('sv',True)).lower()))

    async def on_submit(self, i):
        s = store(i.user.id); m = self.children[0].value.strip().lower()
        if m not in ('fake','wait'): await i.response.send_message("Must be fake or wait.", ephemeral=True); return
        s['settings']['tm'] = m
        try: s['settings']['fmin']=max(1,int(self.children[1].value)); s['settings']['fmax']=max(1,int(self.children[2].value))
        except: pass
        if s['settings']['fmin']>s['settings']['fmax']: s['settings']['fmin'],s['settings']['fmax']=s['settings']['fmax'],s['settings']['fmin']
        try: s['settings']['wsq']=max(1,int(self.children[3].value))
        except: pass
        s['settings']['sv']=self.children[4].value.strip().lower() in ('true','yes','1','t','on')
        await i.response.send_message(f"Mode:{m} | Fake:{s['settings']['fmin']}-{s['settings']['fmax']}s | Wait:{s['settings']['wsq']}s | Save:{s['settings']['sv']}", ephemeral=True)

# ═══ VIEWS ═══
class HV(View):
    def __init__(self, uid): super().__init__(timeout=300); self.uid = uid

    @discord.ui.button(label="📋 Homeworks", style=discord.ButtonStyle.primary, row=0)
    async def hb(self, i, b):
        s = store(i.user.id)
        if not s['accounts']: await i.response.send_message("No accounts.", ephemeral=True); return
        await i.response.defer(ephemeral=True); ems = []
        for a in s['accounts']:
            try:
                h = await c.gh(a)
                if not h: continue
                e = discord.Embed(title=f"{a.get('uname',a['username'])} @ {a.get('school_name','')}", color=0x00ffcc)
                for hw in h:
                    p = (hw['cq']/hw['tq']*100) if hw['tq']>0 else 0
                    e.add_field(name=hw['n'][:50], value=f"Due:{hw['due'][:10] or 'N/A'} | {fmt_bar(hw['cq'],hw['tq'])} ({p:.0f}%)", inline=False)
                ems.append(e)
            except: continue
        if ems: await i.followup.send(embeds=ems, ephemeral=True)
        else: await i.followup.send("No homework.", ephemeral=True)

    @discord.ui.button(label="🚀 Auto-Complete", style=discord.ButtonStyle.success, row=0)
    async def ab(self, i, b):
        s = store(i.user.id)
        if not s['accounts'] or s['active'] < 0: await i.response.send_message("Login first.", ephemeral=True); return
        await i.response.defer(ephemeral=True)
        ss = s['accounts'][s['active']]; st = s['settings']; sd=st.get('sd',3); mr=st.get('mr',3); tm=st.get('tm','fake')
        fmn=st.get('fmin',10); fmx=st.get('fmax',45); wq=st.get('wsq',30); sv=st.get('sv',True)
        s['bwm']={}; bft=time.time()
        try:
            h = await c.gh(ss); p = [x for x in h if x['cq']<x['tq']]
            if not p: await i.followup.send("No pending.", ephemeral=True); return
            rm=sum(x['tq']-x['cq'] for x in p); msg=await i.followup.send(f"Starting... {rm} qs", ephemeral=True); td=0
            for hw in p:
                await msg.edit(content=f"**{hw['n'][:30]}**... {td}/{rm}")
                try:
                    r = await c.h.get(f"{DASHBOARD_URL}/packages/{hw['id']}/tasks", headers={'Authorization': f'Bearer {ss["token"]}'})
                    ts = r.json() if r.status_code == 200 else []
                except: ts = []
                for tk in (ts if isinstance(ts,list) else ts.get('tasks',[])):
                    ti=tk.get('index',0); cq=tk.get('completedQuestions',tk.get('completedAmountOfQuestions',0)); tq=tk.get('totalQuestions',tk.get('totalAmountOfQuestions',0))
                    if cq>=tq: continue
                    for qi in range(cq,tq):
                        act = await c.ga(ss, hw['id'], ti, qi+1)
                        if not act: continue
                        qt = c.eq(act['lo'])
                        # Bookwork check detection
                        bw_code = bookwork.extract_code(qt)
                        if bookwork.is_check(qt):
                            stored = bookwork.get(bw_code) if bw_code else None
                            if stored:
                                await sub_bc(ss, ti, qi+1, stored); td+=1; await asyncio.sleep(sd); continue
                            else:
                                g=await c.ai.sa(qt)
                                if g: await sub_bc(ss, ti, qi+1, g); td+=1; await asyncio.sleep(sd); continue
                                continue
                        # Regular question
                        ans=None
                        for _ in range(mr):
                            ans=await c.sq(qt or f"Q{qi+1}")
                            if ans: break; await asyncio.sleep(1)
                        if ans:
                            ft=None
                            if tm=='fake': ft=bft-random.uniform(fmn,fmx)
                            await c.rs(ss,qi+1,ft); await asyncio.sleep(sd)
                            ok=await c.sub(ss,ti,qi+1,ans,ft)
                            if ok: td+=1
                            at=str(ans[0].get('answer',ans[0])) if isinstance(ans[0],dict) else str(ans[0])
                            # Store for bookwork
                            if bw_code: bookwork.store(bw_code, at, qt)
                            # Working out
                            if sv: nw=time.time(); s['wo'].append({'c':bw_code or '?','q':qt[:100],'a':at,'t':nw}); s['wo']=[w for w in s['wo'] if nw-w['t']<600]
                        if tm=='wait':
                            await msg.edit(content=f"⏳ {wq}s... {td}/{rm}")
                            if wq-sd-2>0: await asyncio.sleep(wq-sd-2)
                await msg.edit(content=f"**{hw['n'][:30]}** done! {td}/{rm}")
            pct=(td/rm*100) if rm else 0; await msg.edit(content=f"✅ Finished! {td}/{rm} ({pct:.0f}%)")
        except Exception as e: await i.followup.send(f"Error: `{str(e)[:150]}`", ephemeral=True)

    @discord.ui.button(label="👤 Accounts", style=discord.ButtonStyle.secondary, row=0)
    async def acb(self, i, b):
        s = store(i.user.id)
        if not s['accounts']: await i.response.send_message("No accounts.", ephemeral=True); return
        await i.response.defer(ephemeral=True)
        ls=[f"**Accounts ({len(s['accounts'])}/{MAX_ACCOUNTS}):**"]
        for idx,a in enumerate(s['accounts']): ls.append(f"{idx+1}. {a.get('uname',a['username'])}{' ◀' if idx==s['active'] else ''}")
        await i.followup.send('\n'.join(ls), view=AV(i.user.id), ephemeral=True)

    @discord.ui.button(label="🔑 Login", style=discord.ButtonStyle.primary, row=1)
    async def lb(self, i, b):
        s=store(i.user.id)
        if len(s['accounts'])>=MAX_ACCOUNTS: await i.response.send_message(f"Max {MAX_ACCOUNTS}.", ephemeral=True); return
        await i.response.send_modal(LM())

    @discord.ui.button(label="🔍 Schools", style=discord.ButtonStyle.secondary, row=1)
    async def sb(self, i, b): await i.response.send_modal(SM())

    @discord.ui.button(label="🧪 Test AI", style=discord.ButtonStyle.secondary, row=1)
    async def tb(self, i, b): await i.response.send_modal(AIM())

    @discord.ui.button(label="⏱ Time Mode", style=discord.ButtonStyle.gray, row=2)
    async def tmb(self, i, b): await i.response.send_modal(TimeM(store(i.user.id)['settings']))

    @discord.ui.button(label="⚙ Settings", style=discord.ButtonStyle.gray, row=2)
    async def setb(self, i, b): await i.response.send_modal(SetM(store(i.user.id)['settings']))

    @discord.ui.button(label="📝 Working", style=discord.ButtonStyle.gray, row=2)
    async def wb(self, i, b):
        s=store(i.user.id)
        if not s['wo']: await i.response.send_message("No working out.", ephemeral=True); return
        await i.response.defer(ephemeral=True); nw=time.time(); v=[w for w in s['wo'] if nw-w['t']<600]; s['wo']=v
        if not v: await i.followup.send("All expired.", ephemeral=True); return
        ls=[f"**Working Out ({len(v)} entries):**"]
        for w in v: ls.append(f"`{w['c']}` ({int(600-(nw-w['t']))}s): {w['a']}")
        await i.followup.send('\n'.join(ls), ephemeral=True)

    @discord.ui.button(label="📊 Status", style=discord.ButtonStyle.gray, row=3)
    async def stb(self, i, b):
        await i.response.defer(ephemeral=True); s=store(i.user.id)
        e=discord.Embed(title="GIOAI STATUS", color=0x00ffcc)
        e.add_field(name="Accounts", value=f"{len(s['accounts'])}/{MAX_ACCOUNTS}", inline=True)
        if s['accounts'] and s['active']>=0: e.add_field(name="Active", value=s['accounts'][s['active']].get('uname','?'), inline=False)
        st=s['settings']
        e.add_field(name="Settings", value=f"SD:{st.get('sd',3)}s | MR:{st.get('mr',3)} | Mode:{st.get('tm','fake')} | Fake:{st.get('fmin',10)}-{st.get('fmax',45)}s | Wait:{st.get('wsq',30)}s | Save:{st.get('sv',True)}", inline=False)
        e.add_field(name="Working", value=f"{len(s['wo'])} entries", inline=True)
        await i.followup.send(embed=e, ephemeral=True)

class AV(View):
    def __init__(self, uid):
        super().__init__(timeout=60); self.uid=uid; s=store(uid)
        opts=[discord.SelectOption(label=f"{idx+1}. {a.get('uname',a['username'])}", value=str(idx), default=(idx==s['active'])) for idx,a in enumerate(s['accounts'])]
        if opts: self.add_item(SS(opts))
    @discord.ui.button(label="🗑 Remove All", style=discord.ButtonStyle.danger, row=1)
    async def rm(self, i, b): s=store(i.user.id); s['accounts'].clear(); s['active']=-1; await i.response.send_message("All removed.", ephemeral=True)

class SS(Select):
    def __init__(self, opts): super().__init__(placeholder="Switch...", options=opts, row=0)
    async def callback(self, i): s=store(i.user.id); idx=int(self.values[0]); s['active']=idx; await i.response.send_message(f"Switched to {s['accounts'][idx].get('uname',s['accounts'][idx]['username'])}", ephemeral=True)

class LM(Modal, title="Sparx Login"):
    def __init__(self):
        super().__init__(timeout=300); self.add_item(TextInput(label="Username")); self.add_item(TextInput(label="Password")); self.add_item(TextInput(label="School name"))
    async def on_submit(self, i):
        await i.response.defer(ephemeral=True); u=self.children[0].value; p=self.children[1].value; sq=self.children[2].value
        m=await c.ss(sq)
        if not m: await i.followup.send(f"No school for '{sq}'. Use Schools button.", ephemeral=True); return
        if len(m)>1:
            ls=[f"Multiple for '{sq}':"]
            for idx,s in enumerate(m[:10]): ls.append(f"{idx+1}. {s.name} ({s.town})")
            await i.followup.send('\n'.join(ls), view=SV(m,u,p), ephemeral=True); return
        sc=m[0]; st=store(i.user.id)
        if len(st['accounts'])>=MAX_ACCOUNTS: await i.followup.send(f"Max {MAX_ACCOUNTS}.", ephemeral=True); return
        try: sess=await c.login(u,p,sc.slug); sess['school_name']=sc.name; st['accounts'].append(sess); st['active']=len(st['accounts'])-1; await i.followup.send(f"✅ Logged in: {sess.get('uname',u)} @ {sc.name}", ephemeral=True)
        except Exception as e: await i.followup.send(f"Failed: {str(e)[:100]}", ephemeral=True)

class SV(View):
    def __init__(self, schools, username, password):
        super().__init__(timeout=120); self.schools=schools[:10]; self.username=username; self.password=password
        opts=[discord.SelectOption(label=s.name[:100], value=str(idx), description=s.town or '') for idx,s in enumerate(schools[:10])]
        self.add_item(SP(opts, self))

class SP(Select):
    def __init__(self, opts, parent): super().__init__(placeholder="Select school...", options=opts); self.parent=parent
    async def callback(self, i):
        await i.response.defer(ephemeral=True); sc=self.parent.schools[int(self.values[0])]; st=store(i.user.id)
        if len(st['accounts'])>=MAX_ACCOUNTS: await i.followup.send(f"Max {MAX_ACCOUNTS}.", ephemeral=True); return
        try: sess=await c.login(self.parent.username, self.parent.password, sc.slug); sess['school_name']=sc.name; st['accounts'].append(sess); st['active']=len(st['accounts'])-1; await i.followup.send(f"✅ Logged in: {sess.get('uname',self.parent.username)} @ {sc.name}", ephemeral=True)
        except Exception as e: await i.followup.send(f"Failed: {str(e)[:100]}", ephemeral=True)

class SM(Modal, title="Search Schools"):
    def __init__(self): super().__init__(timeout=300); self.add_item(TextInput(label="School name"))
    async def on_submit(self, i):
        await i.response.defer(ephemeral=True); q=self.children[0].value; m=await c.ss(q)
        if not m: await i.followup.send(f"No schools for '{q}'. Try partial name or town.", ephemeral=True); return
        ls=[f"**Found {min(len(m),20)}:**"]
        for s in m[:20]: ls.append(f"  {s.name} ({s.town})")
        await i.followup.send('\n'.join(ls), ephemeral=True)

class AIM(Modal, title="Test AI"):
    def __init__(self): super().__init__(timeout=300); self.add_item(TextInput(label="Math question"))
    async def on_submit(self, i):
        await i.response.defer(ephemeral=True); q=self.children[0].value; ans=await c.sq(q)
        if ans: await i.followup.send(f"Q: {q}\n```json\n{json.dumps(ans, indent=2)}\n```", ephemeral=True)
        else: await i.followup.send(f"All AI failed.", ephemeral=True)

async def sub_bc(sess, ti, ai, at):
    """Submit a bookwork check answer"""
    ts = int(time.time() * 1000000)
    raw = await grpc(c.h, f"{STUDENT_API}/ActivityAction", [(1, 0, 1), (2, 2, [(1, 0, ts // 1000000), (2, 0, ts % 1000000)]), (5, 2, [(1, 0, ti), (3, 2, json.dumps({"answers": [{"id": "answer", "answer": str(at)}]}))])], sess['token'], sess.get('sid',''), sess.get('ck',{}))
    if not raw: return False
    for _, _, val in raw:
        if isinstance(val, list):
            for f in val:
                if isinstance(f, tuple) and f[0] == 2: return f[2] == "SUCCESS"
    return True

# ═══ EVENTS ═══
@bot.event
async def on_ready():
    print("╔══════════════════════════════════╗")
    print(f"║  GIOAI SPARX v2.0                ║")
    print(f"║  {bot.user}                      ")
    print("╚══════════════════════════════════╝")
    bot.loop.create_task(c.gs()); bot.loop.create_task(wo_sweep())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{get('COMMAND_PREFIX','s!')}hub"))

@bot.command(name="hub", aliases=["h","menu","help"])
async def hub(ctx):
    s=store(ctx.author.id)
    e=discord.Embed(title="GIOAI COMMAND CENTRE", description=f"Prefix: `{get('COMMAND_PREFIX','s!')}`\nClick buttons below", color=0x00ffcc)
    if s['accounts'] and s['active']>=0: a=s['accounts'][s['active']]; e.add_field(name="Active", value=f"{a.get('uname',a['username'])} @ {a.get('school_name','?')}", inline=False)
    else: e.add_field(name="Status", value="Not logged in", inline=False)
    e.add_field(name="Accounts", value=f"{len(s['accounts'])}/{MAX_ACCOUNTS}", inline=True)
    e.add_field(name="Mode", value=s['settings'].get('tm','fake'), inline=True)
    e.set_footer(text="GIOAI | s!ping")
    await ctx.send(embed=e, view=HV(ctx.author.id), delete_after=600)

@bot.command(name="ping")
async def ping(ctx): await ctx.send("pong", delete_after=5)

@bot.command(name="languagenut", aliases=["ln", "lang"])
async def langnut_cmd(ctx):
    await ctx.send("📚 **Languagenut Platform**\nModule loaded. Use `s!hub` for Sparx or type `s!help` for commands.", delete_after=30)

if __name__=="__main__":
    print("GIOAI Sparx Platform launching...")
    bot.run(TOKEN)
