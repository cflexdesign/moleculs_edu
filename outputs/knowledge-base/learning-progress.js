(function () {
'use strict';
var storageKey = 'molecula-learning-modules-v1';
var parameter = 'mlp';
var tasks = Array.isArray(window.LEARNING_TASKS) ? window.LEARNING_TASKS : [];
var known = Object.create(null), done = Object.create(null), storageDenied = false, historyDenied = false;
var fallbackKey = storageKey + '-address-fallback';
var registryValid = tasks.length === 27;
tasks.forEach(function (task) {
  if (!task || typeof task.id !== 'string' || !/^[a-z0-9-]+$/.test(task.id) || known[task.id]) registryValid = false;
  else known[task.id] = true;
});
function hash(text) {
  var value = 2166136261;
  for (var i = 0; i < text.length; i++) value = Math.imul(value ^ text.charCodeAt(i), 16777619) >>> 0;
  return value.toString(16).padStart(8, '0');
}
if (!registryValid) { message('Не удалось определить версию списка заданий. Экспорт и перенос кода недоступны.'); return; }
var schema = hash(tasks.map(function (t) { return t.id; }).join('|'));
var page;
try { page = new URL(location.href); } catch (error) { page = null; }
var isFile = !!page && page.protocol === 'file:';
function each(selector, callback) { document.querySelectorAll(selector).forEach(callback); }
function message(text) { each('[data-learning-message]', function (el) { el.textContent = text; }); }
function portableCode() {
  if (!registryValid) return '';
  var mask = 0;
  tasks.forEach(function (task, i) { if (done[task.id] === true) mask |= (1 << i); });
  var payload = 'M1.' + schema + '.' + mask.toString(16).padStart(7, '0');
  return payload + '.' + hash(payload);
}
function decode(code) {
  if (!registryValid || typeof code !== 'string') return null;
  var parts = /^M1\.([0-9a-f]{8})\.([0-9a-f]{7})\.([0-9a-f]{8})$/.exec(code);
  if (!parts || parts[1] !== schema || hash(code.slice(0, code.lastIndexOf('.'))) !== parts[3]) return null;
  var mask = parseInt(parts[2], 16);
  if (mask > 0x7ffffff) return null;
  var result = Object.create(null);
  tasks.forEach(function (task, i) { if (mask & (1 << i)) result[task.id] = true; });
  return result;
}
function persist() {
  try { localStorage.setItem(storageKey, JSON.stringify(done)); return true; }
  catch (error) { storageDenied = true; return false; }
}
try {
  var stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
  if (stored && typeof stored === 'object' && !Array.isArray(stored)) {
    tasks.forEach(function (task) { if (Object.prototype.hasOwnProperty.call(stored, task.id) && stored[task.id] === true) done[task.id] = true; });
  }
} catch (error) { storageDenied = true; }
var initialMessage = '';
if (isFile && page.searchParams.has(parameter)) {
  var incoming = page.searchParams.getAll(parameter);
  var restored = incoming.length === 1 ? decode(incoming[0]) : null;
  if (restored) {
    // A denied replaceState can leave an old code in the address on reload.
    // Use the fallback only for a known reload, never for a new incoming link.
    try {
      var entries = window.performance && window.performance.getEntriesByType('navigation');
      var fallback = JSON.parse(localStorage.getItem(fallbackKey) || 'null');
      if (entries && entries[0] && entries[0].type === 'reload' && fallback && fallback.addressCode === incoming[0] && fallback.latestCode === portableCode()) {
        restored = decode(fallback.latestCode) || restored;
      }
    } catch (error) {}
    done = restored; persist();
  }
  else initialMessage = 'Код в ссылке не распознан. Текущие отметки сохранены; восстановите их по исправному коду.';
}
function localPage(raw, element) {
  if (!isFile || !raw || raw.charAt(0) === '#' || (element && element.hasAttribute('download'))) return null;
  var target;
  try { target = new URL(raw, page.href); } catch (error) { return null; }
  if (target.protocol !== 'file:' || target.host !== page.host) return null;
  var slash = target.pathname.lastIndexOf('/');
  if (target.pathname.slice(0, slash + 1) !== page.pathname.slice(0, page.pathname.lastIndexOf('/') + 1)) return null;
  var filename = target.pathname.slice(slash + 1);
  if (!/^(?:index|program|reference|[0-9]{3}(?:-[a-z]+)?|module-[0-9]{2}(?:-[1-3])?)\.html$/.test(filename)) return null;
  return target;
}
function rewriteLinks() {
  var code = portableCode();
  if (!isFile || !code) return;
  each('a[href]', function (a) {
    var target = localPage(a.getAttribute('href'), a);
    if (!target) return;
    target.searchParams.set(parameter, code);
    if (a.getAttribute('href') !== target.href) a.setAttribute('href', target.href);
  });
}
function updateAddress(code) {
  if (!isFile || !code) return;
  // replaceState changes this entry's query without navigating or adding history.
  // Some file: browsers reject it; link transfer and manual code still work.
  try {
    var current = new URL(location.href);
    current.searchParams.set(parameter, code);
    if (current.href !== location.href) {
      if (!window.history || !window.history.replaceState) throw new Error('History unavailable');
      window.history.replaceState(window.history.state, '', current.href);
    }
  } catch (error) {
    historyDenied = true;
    try {
      var address = new URL(location.href).searchParams.getAll(parameter);
      if (address.length === 1 && decode(address[0])) localStorage.setItem(fallbackKey, JSON.stringify({ addressCode: address[0], latestCode: code }));
    } catch (storageError) {}
    return;
  }
  try { if (localStorage.removeItem) localStorage.removeItem(fallbackKey); } catch (error) {}
}
function render() {
  var count = tasks.filter(function (t) { return done[t.id] === true; }).length;
  each('[data-learning-progress]', function (el) { el.textContent = 'Выполнено ' + count + ' из ' + tasks.length + ' заданий'; });
  var next = tasks.find(function (t) { return done[t.id] !== true; });
  each('[data-learning-resume]', function (el) {
    el.setAttribute('href', next ? next.href : 'index.html#program');
    el.textContent = next ? (count ? 'Продолжить обучение →' : 'Начать с первого задания →') : 'Все задания отмечены →';
  });
  each('[data-module-state]', function (el) {
    var id = Number(el.dataset.moduleState);
    var list = tasks.filter(function (t) { return t.module === id; });
    var completed = list.filter(function (t) { return done[t.id] === true; }).length;
    el.textContent = list.length && completed === list.length ? '✓' : completed ? completed + '/' + list.length : '';
  });
  each('[data-job-done]', function (button) {
    var yes = done[button.dataset.jobDone] === true;
    button.textContent = yes ? 'Выполнено · нажмите, чтобы снять отметку' : 'Отметить задание выполненным';
    button.classList.toggle('done', yes);
    button.setAttribute('aria-pressed', yes ? 'true' : 'false');
  });
  var code = portableCode();
  each('[data-learning-code]', function (el) { el.textContent = code; });
  updateAddress(code);
  rewriteLinks();
}
function storageNote() {
  var note = storageDenied ? ' Хранилище браузера недоступно: скопируйте код для отдельного открытия страницы или другого браузера.' : '';
  if (historyDenied) note += ' Браузер не обновил код в адресе: для переноса используйте ссылки внутри базы или сохранённый код.';
  return note;
}
each('[data-job-done]', function (button) {
  button.addEventListener('click', function () {
    var id = button.dataset.jobDone;
    if (!known[id]) return;
    if (done[id] === true) delete done[id]; else done[id] = true;
    persist(); render();
    message('Отметки обновлены.' + storageNote());
  });
});
function controlsFor(button) {
  return button.closest('[data-learning-portable]') || document;
}
each('[data-learning-import]', function (button) {
  button.addEventListener('click', function () {
    var scope = controlsFor(button);
    var input = scope.querySelector('[data-learning-import-code]');
    var restored = input ? decode(input.value.trim()) : null;
    if (!restored) {
      message('Код не распознан или относится к другой версии заданий. Текущие отметки не изменены.');
      if (input) input.setAttribute('aria-invalid', 'true');
      return;
    }
    done = restored; // Whole snapshot: zero bits remove old marks as well.
    persist(); render();
    input.removeAttribute('aria-invalid');
    message('Отметки восстановлены из кода. Он заменил предыдущий набор отметок.' + storageNote());
  });
});
// Optional reset controls: the compact UI can omit them entirely.
each('[data-learning-reset]', function (button) {
  button.addEventListener('click', function () {
    var confirm = controlsFor(button).querySelector('[data-learning-reset-confirm]');
    if (!confirm || !confirm.checked) {
      message('Для сброса сначала подтвердите снятие всех отметок. Прогресс пока не изменён.');
      return;
    }
    done = Object.create(null); confirm.checked = false;
    persist(); render();
    message('Все отметки сняты. Сохраните новый код, если хотите перенести этот результат.' + storageNote());
  });
});
var currentName = page ? page.pathname.split('/').pop() : (location.pathname || '').split('/').pop();
each('.module-side a', function (a) {
  var name;
  try { name = new URL(a.getAttribute('href'), page ? page.href : 'https://example.invalid/').pathname.split('/').pop(); }
  catch (error) { return; }
  if (name === currentName) { a.classList.add('active'); a.setAttribute('aria-current', 'page'); }
});
function reveal() {
  if (!location.hash) return;
  var id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch (error) { return; }
  var el = document.getElementById(id);
  if (!el) return;
  for (var p = el; p; p = p.parentElement) if (p.tagName === 'DETAILS') p.open = true;
}
window.addEventListener('hashchange', reveal);
window.addEventListener('beforeprint', function () {
  each('.learning-job,.optional-repeat,.role-route,.trial-full,.trial-sample details,.profile-learning details', function (d) { d.open = true; });
});
window.addEventListener('pageshow', function (event) {
  if (event.persisted) {
    try {
      var latest = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (latest && typeof latest === 'object' && !Array.isArray(latest)) {
        done = Object.create(null);
        tasks.forEach(function (task) { if (Object.prototype.hasOwnProperty.call(latest, task.id) && latest[task.id] === true) done[task.id] = true; });
      }
    } catch (error) {}
  }
  render(); reveal();
  if (event.persisted && isFile) message('Возвращена ранее открытая страница. Если отметки менялись в другой странице или вкладке, перейдите из неё по ссылке внутри базы либо восстановите сохранённый код.');
});
if (isFile && typeof MutationObserver !== 'undefined' && document.body) {
  // Only childList is observed: our href writes cannot recursively retrigger it.
  new MutationObserver(function (records) {
    if (records.some(function (record) { return record.addedNodes.length; })) rewriteLinks();
  }).observe(document.body, { childList: true, subtree: true });
}
render(); reveal();
if (!registryValid) message('Не удалось определить версию списка заданий. Экспорт и перенос кода недоступны.');
else if (initialMessage) message(initialMessage + storageNote());
else if (storageDenied || historyDenied) message('Отметки работают на этой странице.' + storageNote());
})();
