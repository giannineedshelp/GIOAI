(function(){
'use strict';

const state = {
  token: null, userId: null, userName: null,
  platform: '',
  delayMin: 5, delayMax: 8,
  tasks: [],
  completed: 0, xpEarned: 0, errors: 0,
  running: false, abortController: null,
  theme: localStorage.getItem('gioai-theme') || 'dark',
  initialized: false
};

const $ = {};

function ge(id) {
  const el = document.getElementById(id);
  if (!el) console.warn('Missing element:', id);
  return el;
}

function cache() {
  const ids = [
    'platform-screen','login-screen','dashboard-screen','settings-screen',
    'platform','select-platform-btn','back-to-platform','login-platform-name',
    'username','password','login-btn',
    'header-platform','user-display','status-dot','logout-btn','settings-btn','settings-close',
    'fetch-tasks-btn','start-all-btn','stop-btn',
    'delay-min','delay-max','delay-label',
    'set-delay-min','set-delay-max','set-delay-label',
    'tasks-container','progress-fill','progress-text',
    'log-entries','stat-completed','stat-xp','stat-errors',
    'toast-container','dash-header','sidebar'
  ];
  ids.forEach(function(id) { $[id] = document.getElementById(id); });
  $.themeBtns = document.querySelectorAll('.theme-btn');
}

function toast(msg, level) {
  level = level || 'info';
  if (!$.toastContainer) return;
  var el = document.createElement('div');
  el.className = 'toast ' + level;
  el.textContent = msg;
  $.toastContainer.appendChild(el);
  setTimeout(function() { if (el.parentNode) el.remove(); }, 3500);
}

function log(level, msg) {
  if (!$.logEntries) return;
  var el = document.createElement('div');
  el.className = 'log-entry ' + level;
  var ts = new Date().toLocaleTimeString();
  el.innerHTML = '<span class="timestamp">[' + ts + ']</span>' + msg;
  $.logEntries.appendChild(el);
  $.logEntries.scrollTop = $.logEntries.scrollHeight;
}

function show(id) {
  document.querySelectorAll('.screen').forEach(function(s) { s.classList.remove('active'); });
  var el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function setTheme(t) {
  state.theme = t;
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('gioai-theme', t);
  $.themeBtns.forEach(function(b) {
    b.classList.toggle('active', b.dataset.theme === t);
  });
}

async function api(ep, opts) {
  opts = opts || {};
  var headers = {
    'Content-Type':'application/json',
    'Accept':'application/json, text/plain, */*',
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Origin':'https://www.languagenut.com',
    'Referer':'https://www.languagenut.com/'
  };
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  var ctrl = new AbortController();
  var timeout = setTimeout(function() { ctrl.abort(); }, 15000);
  try {
    var r = await fetch('https://api.languagenut.com' + ep, {
      ...opts,
      headers: { ...headers, ...(opts.headers || {}) },
      signal: ctrl.signal
    });
    clearTimeout(timeout);
    if (!r.ok) {
      var txt = await r.text().catch(function() { return ''; });
      throw new Error('HTTP ' + r.status + (txt ? ': ' + txt.slice(0,150) : ''));
    }
    return await r.json();
  } catch (e) {
    clearTimeout(timeout);
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  }
}

async function auth() {
  var elUser = $.username, elPass = $.password, elBtn = $.loginBtn;
  var u = elUser ? elUser.value.trim() : '';
  var p = elPass ? elPass.value : '';
  if (!u || !p) { toast('Enter username and password.', 'error'); return; }
  if (!elBtn) return;
  elBtn.disabled = true;
  elBtn.textContent = 'Authenticating...';
  try {
    var d = await api('/api/authentication', {
      method:'POST',
      body: JSON.stringify({ username:u, password:p, application:3 })
    });
    if (!d.access_token) throw new Error('No token in response');
    state.token = d.access_token;
    state.userId = d.userId || d.user_id || null;
    state.userName = d.displayName || u;
    if ($.userDisplay) $.userDisplay.textContent = state.userName;
    if ($.statusDot) $.statusDot.className = 'status-dot online';
    toast('Authenticated as ' + state.userName, 'success');
    log('success', 'Authenticated as ' + state.userName);
    show('dashboard-screen');
  } catch (e) {
    toast('Login failed: ' + e.message, 'error');
    log('error', 'Login failed: ' + e.message);
  } finally {
    if (elBtn) { elBtn.disabled = false; elBtn.textContent = 'Authenticate'; }
  }
}

async function fetchTasks() {
  if (!state.token || !$.fetchTasksBtn) return;
  $.fetchTasksBtn.disabled = true;
  $.fetchTasksBtn.textContent = 'Loading...';
  try {
    var d = await api('/api/homeworks');
    var hws = d.homeworks || d || [];
    state.tasks = [];
    if ($.tasksContainer) $.tasksContainer.innerHTML = '';
    var total = 0;
    for (var i = 0; i < hws.length; i++) {
      var hw = hws[i];
      var gid = hw.id || hw.homeworkId || Math.random().toString(36).slice(2,10);
      var gn = hw.name || hw.title || 'Homework';
      var exs = hw.exercises || hw.tasks || [];
      var g = { id:gid, name:gn, exercises:[] };
      for (var j = 0; j < exs.length; j++) {
        var ex = exs[j];
        g.exercises.push({
          id: ex.id || ex.exerciseId || Math.random().toString(36).slice(2,10),
          name: ex.name || ex.title || 'Exercise',
          type: ex.type || ex.exerciseType || 'unknown',
          status: 'pending'
        });
        total++;
      }
      state.tasks.push(g);
    }
    renderTasks();
    updateProgress();
    if ($.startAllBtn) $.startAllBtn.disabled = state.tasks.length === 0;
    toast('Loaded ' + total + ' tasks', 'success');
    log('info', 'Loaded ' + total + ' tasks across ' + state.tasks.length + ' groups');
  } catch (e) {
    toast('Failed to load tasks: ' + e.message, 'error');
    log('error', 'Failed to fetch tasks: ' + e.message);
  } finally {
    if ($.fetchTasksBtn) { $.fetchTasksBtn.disabled = false; $.fetchTasksBtn.textContent = 'Fetch Tasks'; }
  }
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function renderTasks() {
  if (!$.tasksContainer) return;
  $.tasksContainer.innerHTML = '';
  if (state.tasks.length === 0) {
    $.tasksContainer.innerHTML = '<div class="empty-state"><span class="empty-icon">&#x1F4DA;</span><p>No tasks found.</p></div>';
    return;
  }
  for (var i = 0; i < state.tasks.length; i++) {
    var g = state.tasks[i];
    var gd = document.createElement('div'); gd.className = 'task-group';
    var hd = document.createElement('div'); hd.className = 'task-group-header';
    hd.innerHTML = '<span class="group-title">' + esc(g.name) + '</span><span class="group-meta"><span>' + g.exercises.length + ' tasks</span><span class="group-toggle open">&#x25BC;</span></span>';
    var bd = document.createElement('div'); bd.className = 'task-group-body open';
    for (var j = 0; j < g.exercises.length; j++) {
      var ex = g.exercises[j];
      var it = document.createElement('div'); it.className = 'task-item';
      it.dataset.exerciseId = ex.id; it.dataset.groupId = g.id;
      it.innerHTML = '<span class="task-name">' + esc(ex.name) + '</span><span class="task-status ' + ex.status + '">' + ex.status + '</span>';
      bd.appendChild(it);
    }
    hd.addEventListener('click', function() {
      var body = this.parentNode.querySelector('.task-group-body');
      var toggle = this.querySelector('.group-toggle');
      if (body) body.classList.toggle('open');
      if (toggle) toggle.classList.toggle('open');
    });
    gd.appendChild(hd); gd.appendChild(bd);
    $.tasksContainer.appendChild(gd);
  }
}

function uts(gid, eid, st) {
  if (!$.tasksContainer) return;
  var items = $.tasksContainer.querySelectorAll('.task-item');
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    if (it.dataset.exerciseId === eid && it.dataset.groupId === gid) {
      var span = it.querySelector('.task-status');
      if (span) { span.className = 'task-status ' + st; span.textContent = st; }
      break;
    }
  }
}

function updateProgress() {
  var total = 0, done = 0;
  for (var i = 0; i < state.tasks.length; i++) {
    var g = state.tasks[i];
    for (var j = 0; j < g.exercises.length; j++) { total++; if (g.exercises[j].status === 'done') done++; }
  }
  var pct = total > 0 ? (done / total) * 100 : 0;
  if ($.progressFill) $.progressFill.style.width = pct + '%';
  if ($.progressText) $.progressText.textContent = done + ' / ' + total + ' tasks';
  if ($.statCompleted) $.statCompleted.textContent = done;
}

async function completeEx(g, ex) {
  if (state.running === false || ex.status === 'done') return;
  ex.status = 'completing';
  uts(g.id, ex.id, 'completing');
  try {
    var min = state.delayMin, max = state.delayMax;
    var delay = (min + Math.random() * (max - min)) * 1000;
    await new Promise(function(r) { setTimeout(r, delay); });
    var sd = {
      score:100,
      exerciseId:ex.id,
      userId:state.userId,
      correctVocabs:[],
      incorrectVocabs:[],
      timeTakenSeconds:Math.floor(delay/1000) + 1
    };
    await api('/api/SubmitScore', { method:'POST', body:JSON.stringify(sd) });
    ex.status = 'done';
    state.completed++;
    state.xpEarned += 200;
    uts(g.id, ex.id, 'done');
    updateProgress();
    if ($.statXp) $.statXp.textContent = state.xpEarned;
    log('success', 'Completed: ' + ex.name);
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    ex.status = 'error';
    state.errors++;
    uts(g.id, ex.id, 'error');
    if ($.statErrors) $.statErrors.textContent = state.errors;
    log('error', 'Failed: ' + ex.name + ' - ' + e.message);
  }
}

async function completeAll() {
  if (state.running) return;
  state.running = true;
  state.abortController = new AbortController();
  if ($.startAllBtn) $.startAllBtn.disabled = true;
  if ($.stopBtn) $.stopBtn.disabled = false;
  if ($.fetchTasksBtn) $.fetchTasksBtn.disabled = true;
  log('info', 'Starting batch completion...');
  try {
    for (var i = 0; i < state.tasks.length; i++) {
      if (state.running === false) break;
      var g = state.tasks[i];
      for (var j = 0; j < g.exercises.length; j++) {
        if (state.running === false) break;
        await completeEx(g, g.exercises[j]);
      }
    }
    if (state.running) toast('Batch complete!', 'success');
    log('success', 'Batch complete!');
  } catch (e) {
    if (e.name === 'AbortError') {
      toast('Stopped.', 'warning');
      log('warning', 'Stopped by user.');
    } else {
      toast('Error: ' + e.message, 'error');
      log('error', 'Batch error: ' + e.message);
    }
  } finally {
    state.running = false;
    if ($.startAllBtn) $.startAllBtn.disabled = false;
    if ($.stopBtn) $.stopBtn.disabled = true;
    if ($.fetchTasksBtn) $.fetchTasksBtn.disabled = false;
  }
}

function stopAll() {
  state.running = false;
  if (state.abortController) state.abortController.abort();
  if ($.stopBtn) $.stopBtn.disabled = true;
}

function logout() {
  state.token = null; state.userId = null; state.userName = null;
  state.tasks = []; state.completed = 0; state.xpEarned = 0; state.errors = 0;
  state.running = false;
  if ($.statusDot) $.statusDot.className = 'status-dot offline';
  if ($.tasksContainer) $.tasksContainer.innerHTML = '<div class="empty-state"><span class="empty-icon">&#x1F4DA;</span><p>Click <strong>Fetch Tasks</strong> to load your homework.</p></div>';
  if ($.progressFill) $.progressFill.style.width = '0%';
  if ($.progressText) $.progressText.textContent = '0 / 0 tasks';
  if ($.statCompleted) $.statCompleted.textContent = '0';
  if ($.statXp) $.statXp.textContent = '0';
  if ($.statErrors) $.statErrors.textContent = '0';
  if ($.logEntries) $.logEntries.innerHTML = '<div class="log-entry info">Ready. Select a platform to begin.</div>';
  if ($.userDisplay) $.userDisplay.textContent = '';
  show('platform-screen');
  toast('Logged out.', 'info');
  log('info', 'Logged out.');
}

function syncDelay() {
  var min = state.delayMin, max = state.delayMax;
  var lbl = min + 's - ' + max + 's';
  if ($.delayLabel) $.delayLabel.textContent = lbl;
  if ($.setDelayLabel) $.setDelayLabel.textContent = lbl;
  if ($.delayMin) $.delayMin.value = min;
  if ($.delayMax) $.delayMax.value = max;
  if ($.setDelayMin) $.setDelayMin.value = min;
  if ($.setDelayMax) $.setDelayMax.value = max;
}

window.addEventListener('error', function(e) {
  console.error('[GIOAI]', e.error || e.message);
  log('error', 'Uncaught: ' + (e.error ? e.error.message : e.message));
  return true;
});

window.addEventListener('unhandledrejection', function(e) {
  console.error('[GIOAI] Unhandled:', e.reason);
  log('error', 'Unhandled promise: ' + (e.reason ? e.reason.message : String(e.reason)));
});

function init() {
  if (state.initialized) return;
  cache();
  state.initialized = true;
  setTheme(state.theme);

  if ($.platform) {
    $.platform.addEventListener('change', function() {
      if ($.selectPlatformBtn) $.selectPlatformBtn.disabled = !this.value;
    });
  }
  if ($.selectPlatformBtn) {
    $.selectPlatformBtn.addEventListener('click', function() {
      var p = $.platform && $.platform.value;
      if (!p) return;
      state.platform = p;
      var names = { languagenut:'LanguageNut Autocompleter', sparx:'Sparx Maths', hegarty:'HegartyMaths' };
      if ($.loginPlatformName) $.loginPlatformName.textContent = names[p] || p;
      if ($.headerPlatform) $.headerPlatform.textContent = names[p] || p;
      show('login-screen');
      if ($.username) $.username.focus();
    });
  }
  if ($.backToPlatform) {
    $.backToPlatform.addEventListener('click', function() { show('platform-screen'); });
  }
  if ($.loginBtn) $.loginBtn.addEventListener('click', auth);
  if ($.username) $.username.addEventListener('keydown', function(e) { if (e.key === 'Enter' && $.password) $.password.focus(); });
  if ($.password) $.password.addEventListener('keydown', function(e) { if (e.key === 'Enter') auth(); });
  if ($.fetchTasksBtn) $.fetchTasksBtn.addEventListener('click', fetchTasks);
  if ($.startAllBtn) $.startAllBtn.addEventListener('click', completeAll);
  if ($.stopBtn) $.stopBtn.addEventListener('click', stopAll);
  if ($.logoutBtn) $.logoutBtn.addEventListener('click', logout);

  if ($.delayMin && $.delayMax) {
    var sync = function() {
      var min = parseFloat($.delayMin.value);
      var max = parseFloat($.delayMax.value);
      if (min > max) { min = max; $.delayMin.value = min; }
      state.delayMin = min; state.delayMax = max;
      syncDelay();
    };
    $.delayMin.addEventListener('input', sync);
    $.delayMax.addEventListener('input', sync);
  }
  if ($.setDelayMin && $.setDelayMax) {
    var sync = function() {
      var min = parseFloat($.setDelayMin.value);
      var max = parseFloat($.setDelayMax.value);
      if (min > max) { min = max; $.setDelayMin.value = min; }
      state.delayMin = min; state.delayMax = max;
      syncDelay();
    };
    $.setDelayMin.addEventListener('input', sync);
    $.setDelayMax.addEventListener('input', sync);
  }
  if ($.settingsBtn) $.settingsBtn.addEventListener('click', function() { show('settings-screen'); });
  if ($.settingsClose) $.settingsClose.addEventListener('click', function() { show('dashboard-screen'); });
  $.themeBtns.forEach(function(b) {
    b.addEventListener('click', function() { setTheme(this.dataset.theme); });
  });

  syncDelay();
  log('info', 'GIOAI v2.1 loaded. Select a platform to begin.');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

})();
