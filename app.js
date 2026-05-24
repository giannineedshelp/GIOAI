// ── State ──
let speed = 10000;       // base ms per question
let token = null;         // LN auth token
let homeworks = [];       // cached assignments
let translations = {};    
let moduleTranslations = {};

// ── Helpers ──
function secsToStr(s) {
    const parts = [];
    for (const [l, d] of [['y',31536000],['d',86400],['h',3600],['m',60]]) {
        const v = Math.floor(s / d);
        if (v) { parts.push(v + l); s %= d; }
    }
    parts.push(Math.round(s) + 's');
    return parts.join(' ');
}

function setAllChecks(state) {
    document.querySelectorAll('#taskList input[type="checkbox"]').forEach(c => c.checked = state);
}

// ── Concurrency Pool ──
async function asyncPool(arr, limit) {
    const results = [];
    const pool = [];
    const leave = e => pool.splice(pool.indexOf(e), 1);
    for (const fn of arr) {
        const p = Promise.resolve(fn());
        results.push(p);
        const e = p.then(() => leave(e));
        pool.push(e);
        if (pool.length >= limit) await Promise.race(pool);
    }
    return Promise.all(results);
}

// ── Task Completer ──
class TaskCompleter {
    constructor(token, task, langCode) {
        this.tk = token;
        this.task = task;
        this.lang = langCode;
        this.mode = this.detectType();
        this.hwId = task.base?.[0];
        this.catUid = task.catalog_uid || task.base?.[task.base.length - 1];
        this.gameUid = task.game_uid;
        this.gameType = task.type;
    }

    detectType() {
        const l = this.task.gameLink || '';
        if (l.includes('sentenceCatalog')) return 'sentence';
        if (l.includes('verbUid')) return 'verbs';
        if (l.includes('phonicCatalogUid')) return 'phonics';
        if (l.includes('examUid')) return 'exam';
        return 'vocabs';
    }

    async fetchAnswers() {
        switch (this.mode) {
            case 'sentence': return this._get('sentenceTranslationController/getSentenceTranslations', {
                catalogUid: this.catUid, toLanguage: this.lang, fromLanguage: 'en-US', token: this.tk
            }).then(r => r.sentenceTranslations);
            case 'verbs': return this._get('verbTranslationController/getVerbTranslations', {
                verbUid: this.catUid, toLanguage: this.lang, fromLanguage: 'en-US', token: this.tk
            }).then(r => r.verbTranslations);
            case 'phonics': return this._get('phonicsController/getPhonicsData', {
                phonicCatalogUid: this.catUid, toLanguage: this.lang, fromLanguage: 'en-US', token: this.tk
            }).then(r => r.phonics);
            case 'exam': return this._get('examTranslationController/getExamTranslationsCorrect', {
                gameUid: this.gameUid, examUid: this.catUid, toLanguage: this.lang, fromLanguage: 'en-US', token: this.tk
            }).then(r => r.examTranslations);
            default: return this._get('vocabTranslationController/getVocabTranslations', {
                'catalogUid[]': this.catUid, toLanguage: this.lang, fromLanguage: 'en-US', token: this.tk
            }).then(r => r.vocabTranslations);
        }
    }

    async submit(vocabs) {
        if (!vocabs || !vocabs.length) return null;
        const ts = Math.floor((speed + (Math.random() - 0.5) / 10 * speed)) * 1000;
        const data = {
            moduleUid: this.catUid, gameUid: this.gameUid, gameType: this.gameType,
            isTest: true, toietf: this.lang, fromietf: 'en-US',
            score: vocabs.length * 200,
            correctVocabs: vocabs.map(x => x.uid).join(','), incorrectVocabs: [],
            homeworkUid: this.hwId,
            isSentence: this.mode === 'sentence', isALevel: false,
            isVerb: this.mode === 'verbs', verbUid: this.mode === 'verbs' ? this.catUid : '',
            phonicUid: this.mode === 'phonics' ? this.catUid : '',
            sentenceScreenUid: this.mode === 'sentence' ? 100 : '',
            sentenceCatalogUid: this.mode === 'sentence' ? this.catUid : '',
            grammarCatalogUid: this.catUid, isGrammar: false, isExam: this.mode === 'exam',
            correctStudentAns: '', incorrectStudentAns: '',
            timeStamp: ts, vocabNumber: vocabs.length,
            rel_module_uid: this.task.rel_module_uid,
            dontStoreStats: true, product: 'secondary', token: this.tk,
        };
        return this._get('gameDataController/addGameScore', data);
    }

    async _get(url, data) {
        const p = new URLSearchParams(data).toString();
        const r = await fetch(`https://api.languagenut.com/${url}?${p}`);
        return r.json();
    }
}

// ── API Calls ──
async function api(url, data) {
    const p = new URLSearchParams(data).toString();
    const r = await fetch(`https://api.languagenut.com/${url}?${p}`);
    return r.json();
}

function log(msg, type = 'info') {
    const box = document.getElementById('logBox');
    const d = document.createElement('div');
    d.className = 'log-line log-' + type;
    d.textContent = msg;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
}

function renderTasks() {
    const list = document.getElementById('taskList');
    const count = document.getElementById('taskCount');
    list.innerHTML = '';
    count.textContent = `${homeworks.length} assignment(s)`;

    if (!homeworks.length) {
        list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--dim);font-size:13px;">No assignments found.</div>';
        return;
    }

    homeworks.forEach((hw, hi) => {
        const group = document.createElement('div');
        group.className = 'task-group';

        const header = document.createElement('div');
        header.className = 'task-group-header';

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.name = 'boxcheck';
        cb.onclick = function(e) {
            e.stopPropagation();
            const body = this.parentNode.nextElementSibling;
            if (body) body.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = this.checked);
        };

        const name = document.createElement('span');
        name.className = 'task-group-name';
        name.textContent = hw.name || 'Untitled';

        const arrow = document.createElement('span');
        arrow.className = 'task-group-arrow';
        arrow.textContent = '▶';

        header.append(cb, name, arrow);
        header.onclick = function() {
            const body = this.nextElementSibling;
            body.classList.toggle('open');
            this.querySelector('.task-group-arrow').classList.toggle('open');
        };

        const body = document.createElement('div');
        body.className = 'task-group-body';

        (hw.tasks || []).forEach((task, ti) => {
            const row = document.createElement('div');
            row.className = 'task-item';

            const tcb = document.createElement('input');
            tcb.type = 'checkbox';
            tcb.name = 'boxcheck';
            tcb.id = `${hi}-${ti}`;

            const lbl = document.createElement('label');
            lbl.htmlFor = tcb.id;
            const pct = task.gameResults?.percentage ?? '-';
            const disp = translations[task.translation] || 'Task';
            let tname = task.verb_name || 'Task';
            if (task.module_translations && task.module_translations.length && moduleTranslations[task.module_translations[0]])
                tname = moduleTranslations[task.module_translations[0]];
            else if (task.module_translation && moduleTranslations[task.module_translation])
                tname = moduleTranslations[task.module_translation];
            lbl.textContent = `${disp} — ${tname}`;

            const pctEl = document.createElement('span');
            pctEl.className = 'task-pct';
            pctEl.textContent = `${pct}%`;

            row.append(tcb, lbl, pctEl);
            body.appendChild(row);
        });

        group.append(header, body);
        list.appendChild(group);
    });

    document.getElementById('selectAllCb').onclick = function() {
        document.querySelectorAll('#taskList input[type="checkbox"]').forEach(c => c.checked = this.checked);
    };
}

// ── Login ──
document.getElementById('loginBtn').onclick = async function() {
    const username = document.getElementById('usernameInput').value.trim();
    const password = document.getElementById('passwordInput').value;
    const platform = document.getElementById('platformSelect').value;

    if (!username || !password) {
        document.getElementById('loginStatus').textContent = '⚠️ Fill in both fields';
        return;
    }

    if (platform !== 'languagenut') {
        document.getElementById('loginStatus').textContent = '⚠️ Only LanguageNut is supported';
        return;
    }

    this.textContent = 'Logging in...';
    this.disabled = true;

    try {
        const r = await api('loginController/attemptLogin', { username, pass: password });
        token = r.newToken;
        if (!token) throw new Error(r.error || 'Login failed');

        log('✅ Logged in as ' + username, 'ok');

        document.getElementById('loginScreen').classList.remove('active');
        document.getElementById('dashScreen').classList.add('active');
        document.getElementById('dashTitle').textContent = '🌍 LanguageNut';
        document.getElementById('dashStatus').className = 'topbar-badge on';
        document.getElementById('dashStatus').textContent = 'Connected';

        // Load data
        log('📡 Loading assignments...', 'info');
        const [hwData, transData, modData] = await Promise.all([
            api('assignmentController/getViewableAll', { token }),
            api('publicTranslationController/getTranslations', {}),
            api('translationController/getUserModuleTranslations', { token }),
        ]);

        translations = transData.translations || {};
        moduleTranslations = modData.translations || {};
        homeworks = (hwData.homework || []).reverse();
        log(`📋 ${homeworks.length} assignment(s) loaded`, 'ok');
        renderTasks();

    } catch (e) {
        log('❌ ' + e.message, 'err');
        document.getElementById('loginStatus').textContent = '❌ ' + e.message;
    }

    this.textContent = 'Log In';
    this.disabled = false;
};

// Enter key to login
document.getElementById('passwordInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('loginBtn').click();
});

// ── Logout ──
document.getElementById('logoutBtn').onclick = function() {
    token = null;
    homeworks = [];
    document.getElementById('dashScreen').classList.remove('active');
    document.getElementById('loginScreen').classList.add('active');
    document.getElementById('logBox').innerHTML = '<div class="log-muted">Ready</div>';
    document.getElementById('taskList').innerHTML = '';
    document.getElementById('usernameInput').value = '';
    document.getElementById('passwordInput').value = '';
    document.getElementById('loginStatus').textContent = 'Authorized pentest — credentials stay local';
};

// ── Settings ──
document.getElementById('settingsBtn').onclick = () => document.getElementById('settingsModal').showModal();
document.getElementById('speedSlider').oninput = function() {
    speed = Math.pow(10, parseFloat(this.value));
    const label = secsToStr(speed / 1000);
    document.getElementById('speedLabel').textContent = label;
    document.getElementById('dashSpeed').textContent = '⏱ ' + label;
};

// ── Farm ──
document.getElementById('farmBtn').onclick = async function() {
    const checks = document.querySelectorAll('.task-item input[type="checkbox"]:checked');
    const total = checks.length;
    if (!total) { log('⚠️ No tasks selected', 'warn'); return; }

    log(`▶️ Running ${total} task(s)...`, 'info');
    const bar = document.getElementById('progressFill');
    const text = document.getElementById('progressText');
    bar.style.width = '0%';
    text.textContent = '0%';

    const funcs = [];
    let done = 0;

    checks.forEach(cb => {
        const [hi, ti] = cb.id.split('-').map(Number);
        const task = homeworks[hi]?.tasks?.[ti];
        if (!task) return;

        const doer = new TaskCompleter(token, task, homeworks[hi].languageCode);
        funcs.push(() => (async () => {
            log(`📥 Fetching task ${done + 1}...`, 'info');
            const answers = await doer.fetchAnswers();
            if (!answers || !answers.length) {
                log(`⚠️ No answers for task ${done + 1}`, 'warn');
                done++;
                const p = Math.round((done / total) * 100);
                bar.style.width = p + '%';
                text.textContent = p + '%';
                return;
            }
            done++;
            bar.style.width = Math.round((done / total) * 50) + '%';
            text.textContent = Math.round((done / total) * 50) + '%';

            const result = await doer.submit(answers);
            const score = result?.score || 0;
            log(`✅ Task ${done} — score ${score}`, 'ok');
            done++;
            bar.style.width = Math.round((done / total) * 100) + '%';
            text.textContent = Math.round((done / total) * 100) + '%';
        })());
    });

    await asyncPool(funcs, 5);
    log('🏁 All done!', 'ok');
    text.textContent = '✅ Done';
};
