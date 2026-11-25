/* Questionnaire editor. Vanilla JS, no build step.
   State lives in `doc`; text inputs write to it directly and are never
   re-rendered while typing. Structural changes re-render the question list. */
(function () {
  'use strict';

  var root = document.getElementById('bd-root');
  var initialEl = document.getElementById('builder-initial');
  if (!root || !initialEl) return;

  /* ---------- Runtime strings ---------- */
  var EN = {
    'status.draft': 'Draft', 'status.published': 'Registration open', 'status.closed': 'Registration closed',
    'save.saving': 'Saving…', 'save.saved': 'All changes saved', 'save.dirty': 'Unsaved changes',
    'save.retry': 'Couldn’t save. Retrying…', 'save.error': 'Not saved. Fix the problem above.',
    'act.publish': 'Open registration', 'act.close': 'Close registration', 'act.reopen': 'Reopen registration', 'ph.rounds': 'Rounds', 'act.preview': 'Preview',
    'act.answers': 'Answers ({n})', 'act.copy': 'Copy link', 'act.copied': 'Copied',
    'act.newlink': 'New link', 'act.newlink_warn': 'The old link will stop working.',
    'act.newlink_yes': 'Make a new link', 'act.cancel': 'Cancel',
    'act.linklabel': 'Link for participants',
    'cover.add': 'Add cover', 'cover.replace': 'Replace cover', 'cover.remove': 'Remove cover',
    'cover.big': 'The picture is over 2 MB. Choose a smaller one.', 'cover.uploading': 'Uploading…',
    'q.n': 'Question {n}', 'q.label': 'Question', 'q.help': 'Hint under the question',
    'q.helpl': 'Hint for question {n}', 'q.kind': 'Type of question {n}',
    'q.required': 'Required', 'q.other': 'Allow “Other”',
    'q.opt': 'Option {n}', 'q.optl': 'Option {n} of question {q}', 'q.addopt': 'Add option',
    'q.rmopt': 'Remove option {n}', 'q.up': 'Move up', 'q.down': 'Move down',
    'q.dup': 'Duplicate', 'q.del': 'Delete', 'q.add': 'Add question', 'q.menu': 'Question type',
    'q.deleted': 'Question deleted.', 'q.undo': 'Undo', 'q.restored': 'Question restored.',
    'q.addedlive': 'Question added.', 'q.otherline': 'Other',
    'k.short_text': 'Short answer', 'k.long_text': 'Paragraph', 'k.number': 'Number', 'k.date': 'Date',
    'k.single': 'One choice', 'k.dropdown': 'Dropdown', 'k.multiple': 'Several choices',
    'ph.title': 'Competition name', 'ph.desc': 'Description (optional)',
    'ph.q': 'Question', 'ph.help': 'Hint under the question',
    'pub.done': 'Registration is open. Share the link.', 'closed.done': 'Registration closed. No new answers.',
    'link.done': 'New link created.',
    'err.generic': 'Something went wrong. Try again.',
    'err.network': 'No connection. Your changes will be saved when it returns.',
    'err.invalid': 'Some of the values are not valid. Check the highlighted fields.',
    'err.consent': 'Please confirm you have permission to collect participants’ data.',
    'err.title': 'Give the competition a name.',
    'err.no_questions': 'Add at least one question before opening registration.',
    'err.empty_label': 'This question needs text.',
    'err.options': 'Add at least two non-empty options.',
    'err.state': 'This can’t be done in the current state of the questionnaire.',
    'err.cover': 'That picture can’t be used. Choose a PNG, JPEG or WebP under 2 MB.',
    'err.delete': 'This questionnaire can’t be deleted because it already has entries.'
  };
  var RU = {
    'status.draft': 'Черновик', 'status.published': 'Приём заявок открыт', 'status.closed': 'Приём заявок закрыт',
    'save.saving': 'Сохраняем…', 'save.saved': 'Все изменения сохранены', 'save.dirty': 'Есть несохранённые изменения',
    'save.retry': 'Не удалось сохранить. Пробуем снова…', 'save.error': 'Не сохранено. Исправьте ошибку выше.',
    'act.publish': 'Открыть приём заявок', 'act.close': 'Закрыть приём заявок', 'act.reopen': 'Открыть приём снова', 'ph.rounds': 'Туры', 'act.preview': 'Предпросмотр',
    'act.answers': 'Ответы ({n})', 'act.copy': 'Скопировать ссылку', 'act.copied': 'Скопировано',
    'act.newlink': 'Новая ссылка', 'act.newlink_warn': 'Старая ссылка перестанет работать.',
    'act.newlink_yes': 'Создать новую', 'act.cancel': 'Отмена',
    'act.linklabel': 'Ссылка для участников',
    'cover.add': 'Добавить обложку', 'cover.replace': 'Заменить обложку', 'cover.remove': 'Убрать обложку',
    'cover.big': 'Картинка больше 2 МБ. Выберите поменьше.', 'cover.uploading': 'Загружаем…',
    'q.n': 'Вопрос {n}', 'q.label': 'Вопрос', 'q.help': 'Подсказка под вопросом',
    'q.helpl': 'Подсказка к вопросу {n}', 'q.kind': 'Тип вопроса {n}',
    'q.required': 'Обязательный', 'q.other': 'Добавить вариант «Другое»',
    'q.opt': 'Вариант {n}', 'q.optl': 'Вариант {n} вопроса {q}', 'q.addopt': 'Добавить вариант',
    'q.rmopt': 'Убрать вариант {n}', 'q.up': 'Выше', 'q.down': 'Ниже',
    'q.dup': 'Дублировать', 'q.del': 'Удалить', 'q.add': 'Добавить вопрос', 'q.menu': 'Тип вопроса',
    'q.deleted': 'Вопрос удалён.', 'q.undo': 'Отменить', 'q.restored': 'Вопрос вернули.',
    'q.addedlive': 'Вопрос добавлен.', 'q.otherline': 'Другое',
    'k.short_text': 'Короткий ответ', 'k.long_text': 'Абзац', 'k.number': 'Число', 'k.date': 'Дата',
    'k.single': 'Один вариант', 'k.dropdown': 'Список', 'k.multiple': 'Несколько вариантов',
    'ph.title': 'Название конкурса', 'ph.desc': 'Описание (необязательно)',
    'ph.q': 'Вопрос', 'ph.help': 'Подсказка под вопросом',
    'pub.done': 'Приём заявок открыт. Отправьте ссылку.', 'closed.done': 'Приём заявок закрыт. Новых ответов нет.',
    'link.done': 'Новая ссылка создана.',
    'err.generic': 'Что-то пошло не так. Попробуйте ещё раз.',
    'err.network': 'Нет связи. Изменения сохранятся, когда связь появится.',
    'err.invalid': 'Некоторые значения некорректны. Проверьте выделенные поля.',
    'err.consent': 'Подтвердите, что у вас есть разрешение собирать данные участников.',
    'err.title': 'Дайте конкурсу название.',
    'err.no_questions': 'Добавьте хотя бы один вопрос перед открытием приёма заявок.',
    'err.empty_label': 'У вопроса должен быть текст.',
    'err.options': 'Добавьте минимум два непустых варианта.',
    'err.state': 'В текущем состоянии анкеты это сделать нельзя.',
    'err.cover': 'Эту картинку использовать нельзя. Выберите PNG, JPEG или WebP до 2 МБ.',
    'err.delete': 'Эту анкету нельзя удалить: в ней уже есть ответы.'
  };
  function t(key, vars) {
    var dict = document.documentElement.lang === 'ru' ? RU : EN;
    var s = dict[key];
    if (s === undefined) s = EN[key];
    if (s === undefined) s = key;
    if (vars) Object.keys(vars).forEach(function (k) { s = s.replace('{' + k + '}', vars[k]); });
    return s;
  }

  /* ---------- Constants and helpers ---------- */
  var KINDS = ['short_text', 'long_text', 'number', 'date', 'single', 'dropdown', 'multiple'];
  var CHOICE = { single: 1, dropdown: 1, multiple: 1 };
  var OTHER_OK = { single: 1, dropdown: 1, multiple: 1 };
  var MAX_COVER = 2 * 1024 * 1024;

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'text') n.textContent = v;
      else if (k === 'class') n.className = v;
      else if (k === 'value') n.value = v;
      else if (k === 'on') Object.keys(v).forEach(function (e) { n.addEventListener(e, v[e]); });
      else n.setAttribute(k, v === true ? '' : v);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  var keySeq = 0;
  function newKey() { keySeq += 1; return 'k' + keySeq; }
  function csrf() { var m = document.querySelector('meta[name=csrf-token]'); return m ? m.content : ''; }
  function announce(msg) { var l = $('bd-live'); l.textContent = ''; setTimeout(function () { l.textContent = msg; }, 30); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function isoToLocal(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function localToIso(v) {
    if (!v) return null;
    var d = new Date(v);
    if (isNaN(d.getTime())) return null;
    return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
  }
  function intOrNull(v) {
    var n = parseInt(v, 10);
    return isNaN(n) || n < 1 ? null : n;
  }

  /* ---------- State ---------- */
  var urls = {
    form: root.dataset.formJson, publish: root.dataset.publish, close: root.dataset.close,
    link: root.dataset.link, cover: root.dataset.cover, preview: root.dataset.preview,
    responses: root.dataset.responses
  };
  var doc = JSON.parse(initialEl.textContent);
  doc.questions = (doc.questions || []).map(function (q) { return hydrateQuestion(q); });

  function hydrateQuestion(q) {
    return {
      _k: newKey(), id: q.id === undefined ? null : q.id, kind: q.kind || 'short_text',
      label: q.label || '', help_text: q.help_text || '',
      is_required: !!q.is_required, allows_other: !!q.allows_other,
      options: (q.options || []).map(function (o) { return { _k: newKey(), id: o.id === undefined ? null : o.id, label: o.label || '' }; })
    };
  }

  function serialize() {
    var out = {};
    Object.keys(doc).forEach(function (k) { if (k !== 'questions') out[k] = doc[k]; });
    out.questions = doc.questions.map(function (q) {
      var choice = !!CHOICE[q.kind];
      return {
        id: q.id, kind: q.kind, label: q.label, help_text: q.help_text,
        is_required: q.is_required, allows_other: choice && !!OTHER_OK[q.kind] && q.allows_other,
        options: choice ? q.options.map(function (o) { return { id: o.id, label: o.label }; }) : []
      };
    });
    return out;
  }

  /* ---------- API ---------- */
  function api(url, method, body) {
    var headers = { 'X-CSRF-Token': csrf(), 'Accept': 'application/json' };
    var init = { method: method, headers: headers, credentials: 'same-origin' };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
    return fetch(url, init).then(function (r) {
      return r.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  /* ---------- Errors ---------- */
  var errBox = $('bd-error');
  function errText(key) {
    key = String(key || '').replace(/^b\.err\./, '');
    var full = 'err.' + key;
    return (key && EN[full] !== undefined) ? t(full) : t('err.generic');
  }
  function clearErrors() {
    errBox.hidden = true; errBox.textContent = '';
    document.querySelectorAll('.bd-field-err').forEach(function (n) { n.hidden = true; n.textContent = ''; });
    document.querySelectorAll('.bq-err').forEach(function (n) { n.hidden = true; n.textContent = ''; });
    document.querySelectorAll('[aria-invalid]').forEach(function (n) { n.removeAttribute('aria-invalid'); });
    lastError = null;
  }
  var lastError = null;
  function showError(data, fallbackKey) {
    var key = data && data.error ? data.error : fallbackKey;
    lastError = { data: data, key: key };
    var msg = errText(key);
    var shown = false;
    if (data && typeof data.question_index === 'number') {
      var q = doc.questions[data.question_index];
      var block = q && document.querySelector('.bq[data-k="' + q._k + '"]');
      if (block) {
        var e = block.querySelector('.bq-err');
        e.textContent = msg; e.hidden = false;
        var inp = block.querySelector('.bq-label');
        if (inp) inp.setAttribute('aria-invalid', 'true');
        shown = true;
      }
    }
    if (data && data.field) {
      var fe = document.querySelector('[data-err-for="' + data.field + '"]');
      if (fe) { fe.textContent = msg; fe.hidden = false; shown = true; }
    }
    errBox.textContent = msg;
    errBox.hidden = false;
    if (shown) announce(msg);
  }

  /* ---------- Save state ---------- */
  var version = 0, savedVersion = 0, inflight = false, timer = null, retryTimer = null;
  var retryDelay = 0, blocked = false, saveState = 'saved';

  function setSave(state) { saveState = state; paintSave(); }
  function paintSave(silent) {
    var n = $('bd-save');
    var msg = t('save.' + saveState);
    n.textContent = msg;
    n.className = 'bd-save' + (saveState === 'error' || saveState === 'retry' ? ' is-bad' : '');
    if (saveState !== 'dirty' && !silent) announce(msg);
  }
  function touch() {
    version += 1; blocked = false;
    clearTimeout(timer); clearTimeout(retryTimer); retryTimer = null;
    if (lastError) clearErrors();
    setSave('dirty');
    timer = setTimeout(flush, 800);
  }
  function unsaved() { return version !== savedVersion; }

  function flush() {
    clearTimeout(timer);
    if (inflight || !unsaved() || blocked) return Promise.resolve(!unsaved());
    inflight = true;
    var v = version;
    var qkeys = doc.questions.map(function (q) { return { k: q._k, opts: q.options.map(function (o) { return o._k; }) }; });
    var payload = serialize();
    setSave('saving');
    return api(urls.form, 'PUT', payload).then(function (res) {
      inflight = false;
      if (res.ok) {
        retryDelay = 0;
        savedVersion = Math.max(savedVersion, v);
        applyServer(res.data, qkeys);
        if (unsaved()) { setSave('dirty'); timer = setTimeout(flush, 300); }
        else setSave('saved');
        return !unsaved();
      }
      if (res.status === 400 || res.status === 403 || res.status === 404) {
        blocked = true;
        showError(res.data, 'invalid');
        setSave('error');
        return false;
      }
      return failRetry();
    }, function () {
      inflight = false;
      return failRetry();
    });
  }
  function failRetry() {
    retryDelay = Math.min(30000, retryDelay ? retryDelay * 2 : 2000);
    setSave('retry');
    clearTimeout(retryTimer);
    retryTimer = setTimeout(function () { retryTimer = null; flush(); }, retryDelay);
    return false;
  }
  // Used before publish/close: finish any pending save first.
  function flushNow() {
    clearTimeout(timer); clearTimeout(retryTimer); retryTimer = null;
    function step() {
      if (inflight) return new Promise(function (r) { setTimeout(r, 80); }).then(step);
      if (!unsaved()) return Promise.resolve(true);
      if (blocked) return Promise.resolve(false);
      return flush().then(function () {
        if (!unsaved()) return true;
        if (blocked || saveState === 'retry') return false;
        return step();
      });
    }
    return step();
  }

  // Copy server-assigned ids back by array index; update meta fields. Never touches inputs.
  function applyServer(data, qkeys) {
    if (!data || typeof data !== 'object') return;
    if (Array.isArray(data.questions)) {
      qkeys.forEach(function (snap, i) {
        var sq = data.questions[i];
        if (!sq) return;
        var cur = null;
        for (var j = 0; j < doc.questions.length; j++) if (doc.questions[j]._k === snap.k) cur = doc.questions[j];
        if (!cur) return;
        if (sq.id !== undefined && sq.id !== null) cur.id = sq.id;
        // Options of non-choice kinds were sent as [], so only map when the server returned a matching list.
        var sopts = sq.options || [];
        if (sopts.length === snap.opts.length) {
          snap.opts.forEach(function (ok, n) {
            for (var m = 0; m < cur.options.length; m++) if (cur.options[m]._k === ok && sopts[n].id != null) cur.options[m].id = sopts[n].id;
          });
        }
      });
    }
    mergeMeta(data);
  }
  function mergeMeta(data) {
    var lockedChanged = false, statusChanged = false;
    if (typeof data.entry_count === 'number') doc.entry_count = data.entry_count;
    if (typeof data.questions_locked === 'boolean' && data.questions_locked !== doc.questions_locked) { doc.questions_locked = data.questions_locked; lockedChanged = true; }
    if (data.status && data.status !== doc.status) { doc.status = data.status; statusChanged = true; }
    if (data.join_url !== undefined && data.join_url !== doc.join_url) { doc.join_url = data.join_url; statusChanged = true; }
    if (data.cover_url !== undefined) doc.cover_url = data.cover_url;
    if (data.id !== undefined) doc.id = data.id;
    if (lockedChanged) { renderQuestions(); paintKindLock(); }
    renderBar(statusChanged);
    renderDanger();
  }

  /* ---------- Bar: status, actions, join link ---------- */
  var linkConfirm = false;
  function renderBar(keepFocus) {
    var st = $('bd-status');
    st.textContent = t('status.' + doc.status);
    st.className = 'pill' + (doc.status === 'published' ? ' pill-approved' : doc.status === 'closed' ? ' pill-pending' : '');

    var act = $('bd-actions');
    var focused = document.activeElement && act.contains(document.activeElement) ? document.activeElement.dataset.act : null;
    act.textContent = '';
    if (doc.entry_count > 0) {
      act.appendChild(el('a', { class: 'bd-answers', href: urls.responses, text: t('act.answers', { n: doc.entry_count }) }));
    }
    act.appendChild(el('a', { class: 'btn-ghost bd-linkbtn', href: urls.preview, target: '_blank', rel: 'noopener', text: t('act.preview') }));
    if (doc.status === 'draft') {
      act.appendChild(el('button', { class: 'btn btn-main bd-main', type: 'button', 'data-act': 'publish', text: t('act.publish'), on: { click: openPublish } }));
    } else if (doc.status === 'published') {
      act.appendChild(el('button', { class: 'btn-ghost', type: 'button', 'data-act': 'close', text: t('act.close'), on: { click: doClose } }));
    } else {
      act.appendChild(el('button', { class: 'btn btn-main bd-main', type: 'button', 'data-act': 'reopen', text: t('act.reopen'), on: { click: doReopen } }));
    }
    if (focused) { var f = act.querySelector('[data-act="' + focused + '"]'); if (f) f.focus(); }

    var row = $('bd-linkrow');
    if (doc.status === 'published' && doc.join_url) {
      var hadFocus = row.contains(document.activeElement) ? document.activeElement.dataset.act : null;
      row.textContent = '';
      var input = el('input', { class: 'copy-field bd-linkfield', type: 'text', readonly: true, value: doc.join_url, 'aria-label': t('act.linklabel'), 'data-act': 'linkfield' });
      input.addEventListener('focus', function () { input.select(); });
      var copyBtn = el('button', { class: 'btn-ghost', type: 'button', 'data-act': 'copy', text: t('act.copy') });
      copyBtn.addEventListener('click', function () {
        function ok() { copyBtn.textContent = t('act.copied'); announce(t('act.copied')); setTimeout(function () { copyBtn.textContent = t('act.copy'); }, 1500); }
        function fb() { input.focus(); input.select(); }
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(input.value).then(ok, fb); else fb();
      });
      row.appendChild(input);
      row.appendChild(copyBtn);
      if (!linkConfirm) {
        row.appendChild(el('button', { class: 'btn-ghost', type: 'button', 'data-act': 'newlink', text: t('act.newlink'), on: { click: function () { linkConfirm = true; renderBar(); var y = row.querySelector('[data-act="newlink-yes"]'); if (y) y.focus(); } } }));
      } else {
        row.appendChild(el('span', { class: 'bd-warn', text: t('act.newlink_warn') }));
        row.appendChild(el('button', { class: 'btn-ghost', type: 'button', 'data-act': 'newlink-yes', text: t('act.newlink_yes'), on: { click: doNewLink } }));
        row.appendChild(el('button', { class: 'btn-ghost', type: 'button', 'data-act': 'newlink-no', text: t('act.cancel'), on: { click: function () { linkConfirm = false; renderBar(); var n = row.querySelector('[data-act="newlink"]'); if (n) n.focus(); } } }));
      }
      row.hidden = false;
      if (hadFocus) { var hf = row.querySelector('[data-act="' + hadFocus + '"]'); if (hf) hf.focus(); }
    } else {
      row.hidden = true; row.textContent = ''; linkConfirm = false;
    }
  }

  function applyDoc(data) { if (data && typeof data === 'object') mergeMeta(data); }

  function doClose() {
    clearErrors();
    flushNow().then(function (ok) {
      if (!ok) return;
      api(urls.close, 'POST', {}).then(function (res) {
        if (res.ok) { applyDoc(res.data); announce(t('closed.done')); }
        else showError(res.data, 'generic');
      }, function () { showError(null, 'network'); });
    });
  }
  function doReopen() {
    clearErrors();
    flushNow().then(function (ok) {
      if (!ok) return;
      api(urls.publish, 'POST', {}).then(function (res) {
        if (res.ok) { applyDoc(res.data); announce(t('pub.done')); var f = $('bd-linkrow').querySelector('input'); if (f) f.focus(); }
        else showError(res.data, 'generic');
      }, function () { showError(null, 'network'); });
    });
  }
  function doNewLink() {
    clearErrors();
    api(urls.link, 'POST', {}).then(function (res) {
      linkConfirm = false;
      if (res.ok) { applyDoc(res.data); renderBar(); announce(t('link.done')); var c = $('bd-linkrow').querySelector('[data-act="copy"]'); if (c) c.focus(); }
      else showError(res.data, 'generic');
    }, function () { showError(null, 'network'); });
  }

  /* Publish dialog */
  var dlg = $('bd-pub-dialog'), pubForm = $('bd-pub-form'), pubErr = $('bd-pub-err'), consent = $('bd-consent');
  function openPublish() {
    clearErrors();
    pubErr.hidden = true; consent.checked = false;
    flushNow().then(function (ok) {
      if (!ok) return;
      if (typeof dlg.showModal === 'function') { if (!dlg.open) dlg.showModal(); }
      else dlg.setAttribute('open', '');
      consent.focus();
    });
  }
  function closeDlg() {
    if (typeof dlg.close === 'function' && dlg.open) dlg.close(); else dlg.removeAttribute('open');
    var b = document.querySelector('#bd-actions [data-act="publish"]');
    if (b) b.focus();
  }
  $('bd-pub-cancel').addEventListener('click', closeDlg);
  dlg.addEventListener('click', function (e) { if (e.target === dlg) closeDlg(); });
  pubForm.addEventListener('submit', function (e) {
    e.preventDefault();
    if (!consent.checked) { pubErr.textContent = t('err.consent'); pubErr.hidden = false; return; }
    pubErr.hidden = true;
    api(urls.publish, 'POST', { consent: true }).then(function (res) {
      if (res.ok) {
        if (typeof dlg.close === 'function' && dlg.open) dlg.close(); else dlg.removeAttribute('open');
        applyDoc(res.data); announce(t('pub.done'));
        var f = $('bd-linkrow').querySelector('input'); if (f) f.focus();
      } else {
        var d = res.data || {};
        if (d.error === 'b.err.consent' || d.error === 'consent') { pubErr.textContent = errText(d.error); pubErr.hidden = false; }
        else { closeDlg(); showError(d, 'generic'); }
      }
    }, function () { pubErr.textContent = t('err.network'); pubErr.hidden = false; });
  });

  /* ---------- Header and settings fields ---------- */
  function bindFields() {
    var title = $('bd-title'), desc = $('bd-desc'), thanks = $('bd-thanks');
    title.value = doc.title || ''; desc.value = doc.description || ''; thanks.value = doc.thank_you_text || '';
    title.addEventListener('input', function () { doc.title = title.value; touch(); });
    desc.addEventListener('input', function () { doc.description = desc.value; touch(); });
    thanks.addEventListener('input', function () { doc.thank_you_text = thanks.value; touch(); });

    var dl = $('bd-deadline');
    dl.value = isoToLocal(doc.registration_closes_at);
    dl.addEventListener('change', function () { doc.registration_closes_at = localToIso(dl.value); touch(); });
    $('bd-deadline-clear').addEventListener('click', function () { dl.value = ''; doc.registration_closes_at = null; touch(); dl.focus(); });

    var mx = $('bd-max'); mx.value = doc.max_entries == null ? '' : doc.max_entries;
    mx.addEventListener('input', function () { doc.max_entries = intOrNull(mx.value); touch(); });

    var tm = $('bd-teammax'); tm.value = doc.team_max == null ? '' : doc.team_max;
    tm.addEventListener('input', function () { doc.team_max = intOrNull(tm.value); touch(); });

    document.querySelectorAll('input[name="bd-approval"]').forEach(function (r) {
      r.checked = r.value === (doc.manual_approval ? 'manual' : 'auto');
      r.addEventListener('change', function () { if (r.checked) { doc.manual_approval = r.value === 'manual'; touch(); } });
    });
    document.querySelectorAll('input[name="bd-kind"]').forEach(function (r) {
      r.checked = r.value === (doc.entry_kind === 'team' ? 'team' : 'individual');
      r.addEventListener('change', function () {
        if (!r.checked) return;
        doc.entry_kind = r.value;
        if (r.value !== 'team') doc.team_max = null;
        paintTeam(); touch();
      });
    });
    paintTeam();
    paintKindLock();

    var sets = $('bd-settings');
    if (window.matchMedia && matchMedia('(max-width: 640px)').matches) sets.removeAttribute('open');
  }
  function paintTeam() { $('bd-team-field').hidden = doc.entry_kind !== 'team'; }
  // Once entries exist the server keeps individual/team as it is, so the choice is frozen here too.
  function paintKindLock() {
    document.querySelectorAll('input[name="bd-kind"]').forEach(function (r) { r.disabled = !!doc.questions_locked; });
  }

  /* Cover */
  function paintCover() {
    var img = $('bd-cover-img'), add = $('bd-cover-add'), rm = $('bd-cover-remove');
    if (doc.cover_url) { img.src = doc.cover_url; img.hidden = false; } else { img.removeAttribute('src'); img.hidden = true; }
    add.textContent = doc.cover_url ? t('cover.replace') : t('cover.add');
    rm.textContent = t('cover.remove');
    rm.hidden = !doc.cover_url;
  }
  function coverErr(msg) { var n = $('bd-cover-err'); n.textContent = msg || ''; n.hidden = !msg; if (msg) announce(msg); }
  function bindCover() {
    var file = $('bd-cover-file');
    $('bd-cover-add').addEventListener('click', function () { file.click(); });
    file.addEventListener('change', function () {
      var f = file.files && file.files[0];
      file.value = '';
      coverErr('');
      if (!f) return;
      if (f.size > MAX_COVER) { coverErr(t('cover.big')); return; }
      var fd = new FormData(); fd.append('cover', f);
      var add = $('bd-cover-add'); add.disabled = true; add.textContent = t('cover.uploading');
      api(urls.cover, 'POST', fd).then(function (res) {
        add.disabled = false;
        if (res.ok && res.data) { doc.cover_url = res.data.cover_url || null; paintCover(); }
        else { paintCover(); coverErr(errText(res.data && res.data.error || 'cover')); }
      }, function () { add.disabled = false; paintCover(); coverErr(t('err.network')); });
    });
    $('bd-cover-remove').addEventListener('click', function () {
      coverErr('');
      api(urls.cover, 'DELETE').then(function (res) {
        if (res.ok) { doc.cover_url = null; paintCover(); $('bd-cover-add').focus(); }
        else coverErr(errText(res.data && res.data.error || 'cover'));
      }, function () { coverErr(t('err.network')); });
    });
    paintCover();
  }

  /* ---------- Questions ---------- */
  var focusAfter = null;
  function qIndex(k) { for (var i = 0; i < doc.questions.length; i++) if (doc.questions[i]._k === k) return i; return -1; }

  function renderQuestions() {
    var list = $('bd-qlist');
    list.textContent = '';
    var locked = !!doc.questions_locked;
    $('bd-locked').hidden = !locked;
    doc.questions.forEach(function (q, i) { list.appendChild(locked ? renderReadonly(q, i) : renderQuestion(q, i)); });
    renderAdd();
    if (focusAfter) {
      var fa = focusAfter; focusAfter = null;
      var target = list.querySelector('.bq[data-k="' + fa.k + '"] ' + fa.sel);
      if (!target && fa.alt) target = list.querySelector('.bq[data-k="' + fa.k + '"] ' + fa.alt);
      if (target && !target.disabled) target.focus();
    }
  }

  function renderReadonly(q, i) {
    var b = el('section', { class: 'bq bq-ro', 'data-k': q._k, 'aria-label': t('q.n', { n: i + 1 }) });
    b.appendChild(el('div', { class: 'bq-head' }, [
      el('span', { class: 'bq-num', 'aria-hidden': 'true', text: i + 1 }),
      el('div', { class: 'bq-ro-main' }, [
        el('p', { class: 'bq-ro-label', text: q.label + (q.is_required ? ' *' : '') }),
        q.help_text ? el('p', { class: 'hint', text: q.help_text }) : null,
        el('p', { class: 'hint', text: t('k.' + q.kind) })
      ])
    ]));
    if (CHOICE[q.kind] && q.options.length) {
      var ul = el('ul', { class: 'bq-ro-opts' });
      q.options.forEach(function (o) { ul.appendChild(el('li', { text: o.label })); });
      b.appendChild(ul);
    }
    return b;
  }

  function renderQuestion(q, i) {
    var n = i + 1, last = doc.questions.length - 1;
    var label = el('input', { class: 'bq-label', type: 'text', maxlength: '500', value: q.label, placeholder: t('ph.q'), 'aria-label': t('q.n', { n: n }) });
    label.addEventListener('input', function () { q.label = label.value; touch(); });
    var kind = el('select', { class: 'bq-kind', 'aria-label': t('q.kind', { n: n }) });
    KINDS.forEach(function (k) { var o = el('option', { value: k, text: t('k.' + k) }); if (k === q.kind) o.selected = true; kind.appendChild(o); });
    kind.addEventListener('change', function () {
      q.kind = kind.value;
      if (CHOICE[q.kind] && !q.options.length) { q.options.push({ _k: newKey(), id: null, label: '' }, { _k: newKey(), id: null, label: '' }); }
      if (!OTHER_OK[q.kind]) q.allows_other = false;
      focusAfter = { k: q._k, sel: '.bq-kind' };
      touch(); renderQuestions();
    });
    var help = el('input', { class: 'bq-help', type: 'text', maxlength: '500', value: q.help_text, placeholder: t('ph.help'), 'aria-label': t('q.helpl', { n: n }) });
    help.addEventListener('input', function () { q.help_text = help.value; touch(); });

    var block = el('section', { class: 'bq', 'data-k': q._k, 'aria-label': t('q.n', { n: n }) }, [
      el('div', { class: 'bq-head' }, [el('span', { class: 'bq-num', 'aria-hidden': 'true', text: n }), label, kind]),
      help
    ]);

    if (CHOICE[q.kind]) block.appendChild(renderOptions(q, n));

    var req = el('input', { type: 'checkbox' }); req.checked = q.is_required;
    req.addEventListener('change', function () { q.is_required = req.checked; touch(); });
    var foot = el('div', { class: 'bq-foot' });
    foot.appendChild(el('label', { class: 'bq-toggle' }, [req, el('span', { text: t('q.required') })]));
    if (OTHER_OK[q.kind]) {
      var oth = el('input', { type: 'checkbox' }); oth.checked = q.allows_other;
      oth.addEventListener('change', function () { q.allows_other = oth.checked; touch(); });
      foot.appendChild(el('label', { class: 'bq-toggle' }, [oth, el('span', { text: t('q.other') })]));
    }
    var tools = el('div', { class: 'bq-tools', role: 'group', 'aria-label': t('q.n', { n: n }) });
    tools.appendChild(toolBtn('bq-up', t('q.up'), '↑', i === 0, function () { moveQ(i, -1); }));
    tools.appendChild(toolBtn('bq-down', t('q.down'), '↓', i === last, function () { moveQ(i, 1); }));
    tools.appendChild(toolBtn('bq-dup', t('q.dup'), null, false, function () { dupQ(i); }));
    tools.appendChild(toolBtn('bq-del', t('q.del'), null, false, function () { delQ(i); }));
    foot.appendChild(tools);
    block.appendChild(foot);
    block.appendChild(el('p', { class: 'bq-err', role: 'alert', hidden: true }));
    return block;
  }

  function toolBtn(cls, name, glyph, disabled, fn) {
    var b = el('button', { class: 'bq-btn ' + cls, type: 'button', disabled: disabled, 'aria-label': name, title: name, on: { click: fn } });
    b.textContent = glyph || name;
    if (glyph) b.setAttribute('aria-label', name);
    return b;
  }

  function renderOptions(q, qn) {
    var ol = el('ol', { class: 'bq-opts' });
    q.options.forEach(function (o, oi) {
      var inp = el('input', { class: 'bq-opt', type: 'text', maxlength: '300', value: o.label, placeholder: t('q.opt', { n: oi + 1 }), 'aria-label': t('q.optl', { n: oi + 1, q: qn }) });
      inp.addEventListener('input', function () { o.label = inp.value; touch(); });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          var idx = q.options.indexOf(o);
          var no = { _k: newKey(), id: null, label: '' };
          q.options.splice(idx + 1, 0, no);
          focusAfter = { k: q._k, sel: '.bq-opts li:nth-child(' + (idx + 2) + ') .bq-opt' };
          touch(); renderQuestions();
        }
      });
      var rm = el('button', { class: 'bq-btn bq-rmopt', type: 'button', 'aria-label': t('q.rmopt', { n: oi + 1 }), title: t('q.rmopt', { n: oi + 1 }), disabled: q.options.length <= 1, text: '×',
        on: { click: function () {
          var idx = q.options.indexOf(o);
          q.options.splice(idx, 1);
          var nth = Math.min(idx + 1, q.options.length);
          focusAfter = { k: q._k, sel: '.bq-opts li:nth-child(' + nth + ') .bq-opt' };
          touch(); renderQuestions();
        } } });
      ol.appendChild(el('li', { class: 'bq-optrow' }, [el('span', { class: 'bq-mark' + (q.kind === 'multiple' ? ' is-sq' : ''), 'aria-hidden': 'true' }), inp, rm]));
    });
    var add = el('button', { class: 'bq-addopt', type: 'button', text: t('q.addopt'),
      on: { click: function () {
        q.options.push({ _k: newKey(), id: null, label: '' });
        focusAfter = { k: q._k, sel: '.bq-opts li:last-child .bq-opt' };
        touch(); renderQuestions();
      } } });
    var wrap = el('div', { class: 'bq-optwrap' }, [ol]);
    if (q.allows_other && OTHER_OK[q.kind]) wrap.appendChild(el('p', { class: 'bq-otherline', 'aria-hidden': 'true', text: t('q.otherline') }));
    wrap.appendChild(add);
    return wrap;
  }

  function moveQ(i, d) {
    var j = i + d;
    if (j < 0 || j >= doc.questions.length) return;
    var q = doc.questions[i];
    doc.questions.splice(i, 1); doc.questions.splice(j, 0, q);
    focusAfter = { k: q._k, sel: d < 0 ? '.bq-up' : '.bq-down', alt: d < 0 ? '.bq-down' : '.bq-up' };
    touch(); renderQuestions();
  }
  function dupQ(i) {
    var src = doc.questions[i];
    var c = hydrateQuestion({ kind: src.kind, label: src.label, help_text: src.help_text, is_required: src.is_required, allows_other: src.allows_other,
      options: src.options.map(function (o) { return { id: null, label: o.label }; }) });
    doc.questions.splice(i + 1, 0, c);
    focusAfter = { k: c._k, sel: '.bq-label' };
    touch(); renderQuestions(); announce(t('q.addedlive'));
  }

  var toastTimer = null, toastFocus = null;
  function delQ(i) {
    var q = doc.questions[i];
    doc.questions.splice(i, 1);
    var neighbour = doc.questions[Math.min(i, doc.questions.length - 1)];
    touch(); renderQuestions();
    showToast(t('q.deleted'), t('q.undo'), function () {
      doc.questions.splice(Math.min(i, doc.questions.length), 0, q);
      focusAfter = { k: q._k, sel: '.bq-label' };
      touch(); renderQuestions(); hideToast(); announce(t('q.restored'));
    });
    if (neighbour) { var nb = document.querySelector('.bq[data-k="' + neighbour._k + '"] .bq-label'); if (nb) nb.focus(); }
    else { var ab = document.querySelector('#bd-add .bd-addbtn'); if (ab) ab.focus(); }
  }
  function showToast(msg, actionLabel, fn) {
    var tn = $('bd-toast');
    tn.textContent = '';
    tn.appendChild(el('span', { text: msg }));
    tn.appendChild(el('button', { class: 'bd-toast-btn', type: 'button', text: actionLabel, on: { click: fn } }));
    tn.hidden = false;
    announce(msg);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 5000);
  }
  function hideToast() { clearTimeout(toastTimer); $('bd-toast').hidden = true; $('bd-toast').textContent = ''; }

  /* Add-question menu */
  var menuOpen = false;
  function renderAdd() {
    var box = $('bd-add');
    box.textContent = '';
    if (doc.questions_locked) return;
    var btn = el('button', { class: 'btn-ghost bd-addbtn', type: 'button', 'aria-haspopup': 'menu', 'aria-expanded': menuOpen ? 'true' : 'false', text: t('q.add') });
    var menu = el('div', { class: 'bd-menu', role: 'menu', 'aria-label': t('q.menu'), hidden: !menuOpen });
    KINDS.forEach(function (k) {
      menu.appendChild(el('button', { class: 'bd-menuitem', type: 'button', role: 'menuitem', tabindex: '-1', 'data-kind': k, text: t('k.' + k),
        on: { click: function () { addQ(k); } } }));
    });
    function items() { return Array.prototype.slice.call(menu.querySelectorAll('.bd-menuitem')); }
    function open(focusIdx) {
      menuOpen = true; menu.hidden = false; btn.setAttribute('aria-expanded', 'true');
      var it = items(); if (it[focusIdx || 0]) it[focusIdx || 0].focus();
    }
    function close(refocus) {
      menuOpen = false; menu.hidden = true; btn.setAttribute('aria-expanded', 'false');
      if (refocus) btn.focus();
    }
    btn.addEventListener('click', function () { menuOpen ? close(false) : open(0); });
    btn.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); open(0); }
      if (e.key === 'ArrowUp') { e.preventDefault(); open(KINDS.length - 1); }
    });
    menu.addEventListener('keydown', function (e) {
      var it = items(), idx = it.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); it[(idx + 1) % it.length].focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); it[(idx - 1 + it.length) % it.length].focus(); }
      else if (e.key === 'Home') { e.preventDefault(); it[0].focus(); }
      else if (e.key === 'End') { e.preventDefault(); it[it.length - 1].focus(); }
      else if (e.key === 'Escape') { e.preventDefault(); close(true); }
      else if (e.key === 'Tab') { close(false); }
    });
    box.appendChild(btn); box.appendChild(menu);
  }
  document.addEventListener('click', function (e) {
    if (menuOpen && !$('bd-add').contains(e.target)) { menuOpen = false; renderAdd(); }
  });
  function addQ(kind) {
    var q = hydrateQuestion({ kind: kind, is_required: true, options: CHOICE[kind] ? [{ label: '' }, { label: '' }] : [] });
    doc.questions.push(q);
    menuOpen = false;
    focusAfter = { k: q._k, sel: '.bq-label' };
    touch(); renderQuestions(); announce(t('q.addedlive'));
    var nb = document.querySelector('.bq[data-k="' + q._k + '"]');
    if (nb && nb.scrollIntoView) nb.scrollIntoView({ block: 'nearest' });
  }

  /* ---------- Delete questionnaire ---------- */
  function renderDanger() { $('bd-danger').hidden = !!doc.entry_count; }
  function bindDanger() {
    var open = $('bd-del-open'), form = $('bd-del-confirm');
    open.addEventListener('click', function () { open.hidden = true; form.hidden = false; form.querySelector('button[type=submit]').focus(); });
    $('bd-del-cancel').addEventListener('click', function () { form.hidden = true; open.hidden = false; open.focus(); });
    form.addEventListener('submit', function () { unloadGuard = false; });
  }

  /* ---------- Chrome refresh (language) ---------- */
  function paintStatic() {
    document.querySelectorAll('[data-ph]').forEach(function (n) { n.placeholder = t(n.dataset.ph); });
    document.querySelectorAll('[data-aria]').forEach(function (n) { n.setAttribute('aria-label', t(n.dataset.aria)); });
  }
  function rerenderLabels() {
    paintStatic(); renderBar(); paintSave(true); paintCover(); renderQuestions();
    // Re-announcing the save state on a language switch would be noise.
  }
  var langBtn = $('lang-switch');
  if (langBtn) langBtn.addEventListener('click', function () { setTimeout(rerenderLabels, 0); });

  /* ---------- Leave guard ---------- */
  var unloadGuard = true;
  window.addEventListener('beforeunload', function (e) {
    if (unloadGuard && (unsaved() || inflight)) { e.preventDefault(); e.returnValue = ''; return ''; }
  });
  window.addEventListener('online', function () { if (unsaved() && !inflight && !blocked) { clearTimeout(retryTimer); retryTimer = null; flush(); } });

  /* ---------- Init ---------- */
  bindFields();
  bindCover();
  bindDanger();
  paintStatic();
  renderBar();
  renderQuestions();
  renderDanger();
  $('bd-save').textContent = t('save.saved');
})();
