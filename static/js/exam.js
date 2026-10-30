/* SmartEdu exam page.
   Flow: pre-flight (camera + mic, then fullscreen) -> exam running (timer, autosave, proctoring) -> submit / cancel. */
(function () {
  'use strict';

  var cfg = JSON.parse(document.getElementById('exam-config').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var csrf = (document.querySelector('input[name=csrfmiddlewaretoken]') || {}).value || '';

  var state = {
    started: false, finished: false, paused: false,
    violations: cfg.violations, lastViolationAt: 0, dirty: false,
    endAt: Date.now() + cfg.secondsLeft * 1000, stream: null, faceCheck: true
  };
  var timers = { tick: null, save: null, frame: null, mic: null, debounce: null };

  /* ---------- helpers ---------- */
  function post(url, body, isForm) {
    var opts = { method: 'POST', headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' };
    if (isForm) { opts.body = body; }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch(url, opts).then(function (r) { return r.json().catch(function () { return {}; }); });
  }
  function toast(msg, kind) {
    var t = document.createElement('div');
    t.className = 'toast ' + (kind || '');
    t.textContent = msg;
    $('toasts').appendChild(t);
    setTimeout(function () { t.remove(); }, 5000);
  }
  function pad(n) { return String(n).padStart(2, '0'); }
  function show(el, on) { el.hidden = !on; }

  function paintPips() {
    document.querySelectorAll('#pips .pip').forEach(function (p, i) { p.classList.toggle('on', i < state.violations); });
  }
  paintPips();

  /* ---------- answers ---------- */
  function collectAnswers() {
    var answers = {};
    document.querySelectorAll('.qcard').forEach(function (card) {
      var id = card.getAttribute('data-qid');
      if (card.getAttribute('data-type') === 'MCQ') {
        var r = card.querySelector('input[type=radio]:checked');
        answers[id] = r ? r.value : '';
      } else {
        answers[id] = card.querySelector('textarea').value;
      }
    });
    return answers;
  }
  function isAnswered(card) {
    if (card.getAttribute('data-type') === 'MCQ') return !!card.querySelector('input:checked');
    return card.querySelector('textarea').value.trim().length > 0;
  }
  function refreshProgress() {
    var cards = document.querySelectorAll('.qcard'), done = 0;
    cards.forEach(function (c) {
      var ok = isAnswered(c); if (ok) done++;
      var link = document.querySelector('#qnav a[data-qid="' + c.getAttribute('data-qid') + '"]');
      if (link) link.classList.toggle('done', ok);
      var wc = c.querySelector('.wc-n');
      if (wc) { var t = c.querySelector('textarea').value.trim(); wc.textContent = t ? t.split(/\s+/).length : 0; }
    });
    $('answeredCount').textContent = done + '/' + cards.length;
    return { done: done, total: cards.length };
  }
  function markDirty() { state.dirty = true; refreshProgress(); clearTimeout(timers.debounce); timers.debounce = setTimeout(save, 2000); }
  document.addEventListener('input', function (e) { if (e.target.closest('.qcard')) markDirty(); });
  document.addEventListener('change', function (e) { if (e.target.closest('.qcard')) markDirty(); });
  document.querySelectorAll('textarea').forEach(function (t) { t.addEventListener('dragover', function (e) { e.preventDefault(); }); t.addEventListener('drop', function (e) { e.preventDefault(); }); });

  function save() {
    if (state.finished || !state.started) return Promise.resolve();
    $('saveStatus').textContent = 'Saving...';
    return post(cfg.urls.save, { answers: collectAnswers() }).then(function (d) {
      if (d.success) { state.dirty = false; var n = new Date(); $('saveStatus').textContent = 'Saved ' + n.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
      else { $('saveStatus').textContent = 'Could not save, will retry'; }
    }).catch(function () { $('saveStatus').textContent = 'Offline, will retry'; });
  }

  /* ---------- timer ---------- */
  function tick() {
    var left = Math.max(0, Math.round((state.endAt - Date.now()) / 1000));
    var el = $('timer');
    el.textContent = pad(Math.floor(left / 60)) + ':' + pad(left % 60);
    el.classList.toggle('low', left <= 300);
    if (left <= 0 && !state.finished) { toast('Time is up. Submitting your answers.', 'info'); submit(true); }
  }

  /* ---------- violations ---------- */
  var LABELS = { TAB_SWITCH: 'Left the exam tab', FULLSCREEN_EXIT: 'Left fullscreen', COPY_PASTE: 'Copy or paste attempt', NO_FACE: 'Face not visible in camera', NO_MIC: 'Microphone problem', MULTIPLE_FACE: 'More than one face' };

  function logViolation(type, details) {
    if (!state.started || state.finished) return;
    var now = Date.now();
    if (now - state.lastViolationAt < 2000) return;   // one slip = one violation, even if several events fire
    state.lastViolationAt = now;
    state.violations = Math.min(cfg.maxViolations, state.violations + 1);
    paintPips();
      toast(type === 'NO_FACE'
        ? 'Alert ' + state.violations + ' of ' + cfg.maxViolations + ': Your face was not detected. Keep your face visible in the camera.'
        : 'Violation ' + state.violations + ' of ' + cfg.maxViolations + ': ' + (LABELS[type] || type));
    if (state.violations >= cfg.maxViolations) { cancelled(); }
    post(cfg.urls.log, { submission_id: cfg.submissionId, violation_type: type, details: details || '' }).then(function (d) {
      if (typeof d.count === 'number') { state.violations = d.count; paintPips(); }
      if (d.cancelled) cancelled();
    }).catch(function () { /* the local count still applies */ });
  }

  function cancelled() {
    if (state.finished) return;
    state.finished = true;
    stopAll();
    leaveFullscreen();
    show($('pause'), false);
    $('endTitle').textContent = 'Exam cancelled';
    $('endMsg').textContent = 'You reached ' + cfg.maxViolations + ' violations, so the exam was closed. Your teacher can review the log.';
    show($('ended'), true);
    setTimeout(function () { window.location.href = cfg.urls.result; }, 3500);
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden && state.started && !state.finished) logViolation('TAB_SWITCH', 'Switched tab or minimised the browser');
  });
  window.addEventListener('blur', function () {
    if (state.started && !state.finished && !state.paused && !document.hidden) logViolation('TAB_SWITCH', 'Window lost focus');
  });
  ['copy', 'cut', 'paste'].forEach(function (ev) {
    document.addEventListener(ev, function (e) {
      if (!state.started || state.finished) return;
      e.preventDefault();
      logViolation('COPY_PASTE', ev.charAt(0).toUpperCase() + ev.slice(1) + ' attempt');
    });
  });
  document.addEventListener('contextmenu', function (e) { e.preventDefault(); if (state.started) toast('Right-click is turned off during the exam.', 'info'); });
  window.addEventListener('beforeunload', function (e) { if (state.started && !state.finished) { e.preventDefault(); e.returnValue = ''; } });

  /* fullscreen */
  var canFullscreen = !!document.documentElement.requestFullscreen;
  function enterFullscreen() { return canFullscreen ? document.documentElement.requestFullscreen() : Promise.resolve(); }
  function leaveFullscreen() { if (document.fullscreenElement && document.exitFullscreen) { document.exitFullscreen().catch(function () {}); } }
  document.addEventListener('fullscreenchange', function () {
    if (!document.fullscreenElement && state.started && !state.finished) {
      state.paused = true;
      logViolation('FULLSCREEN_EXIT', 'Exited fullscreen');
      if (!state.finished) show($('pause'), true);
    }
  });
  $('btnBack').addEventListener('click', function () {
    enterFullscreen().then(function () { state.paused = false; show($('pause'), false); }).catch(function () { toast('Your browser blocked fullscreen. Press F11 and try again.'); });
  });

  /* ---------- camera, microphone, face check ---------- */
  function setStep(id, done, msg, err) {
    var li = $(id); li.classList.toggle('done', done);
    var m = li.querySelector('.s-msg'); if (msg) { m.textContent = msg; m.classList.toggle('err', !!err); }
  }

  function startMeters(stream) {
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      var ctx = new AC(), src = ctx.createMediaStreamSource(stream), an = ctx.createAnalyser();
      an.fftSize = 256; src.connect(an);
      var buf = new Uint8Array(an.frequencyBinCount);
      timers.mic = setInterval(function () {
        an.getByteTimeDomainData(buf);
        var sum = 0; for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; sum += v * v; }
        $('micBar').style.width = Math.min(100, Math.sqrt(sum / buf.length) * 400) + '%';
      }, 150);
    } catch (e) { /* the meter is optional */ }
    stream.getTracks().forEach(function (t) {
      t.addEventListener('ended', function () {
        if (!state.started || state.finished) return;
        logViolation(t.kind === 'audio' ? 'NO_MIC' : 'NO_FACE', t.kind + ' stopped');
      });
    });
  }

  $('btnCam').addEventListener('click', function () {
    var btn = this; btn.disabled = true; btn.textContent = 'Checking...';
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStep('stepCam', false, 'This browser cannot use the camera here. Use Chrome or Edge on localhost or https.', true);
      btn.disabled = false; btn.textContent = 'Try again'; return;
    }
    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: true }).then(function (stream) {
      state.stream = stream;
      $('webcam').srcObject = stream; document.querySelector('.cam').classList.add('on');
      startMeters(stream);
      setStep('stepCam', true, 'Camera and microphone are working.');
      btn.textContent = 'Done';
      $('btnStart').disabled = false; $('stepFs').classList.remove('locked');
    }).catch(function (err) {
      setStep('stepCam', false, 'Could not use the camera or microphone (' + (err.name || 'error') + '). Allow both in the address bar, then try again.', true);
      btn.disabled = false; btn.textContent = 'Try again';
    });
  });

  function setFace(status) {
    var el = $('faceStatus');
    var map = { ok: ['Face detected', 'ok'], no_face: ['No face seen', 'warn'], multiple: ['More than one face', 'bad'], unavailable: ['Face check off', 'muted'] };
    var m = map[status] || map.unavailable; el.textContent = m[0]; el.className = 'badge ' + m[1];
  }

  function sendFrame() {
    if (!state.started || state.finished || !state.stream || !state.faceCheck) return;
    var video = $('webcam'), canvas = $('snapshot');
    if (!video.videoWidth) return;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function (blob) {
      if (!blob) return;
      var fd = new FormData(); fd.append('submission_id', cfg.submissionId); fd.append('image', blob, 'frame.jpg');
      post(cfg.urls.frame, fd, true).then(function (d) {
        setFace(d.status);
        if (d.status === 'unavailable') {
          setFace('unavailable');
          toast('Required face detection is unavailable. The exam has been stopped; contact your teacher.', 'bad');
          cancelled();
          return;
        }
        if (d.violation) {
          state.violations = d.count; paintPips();
          toast(d.violation === 'NO_FACE'
            ? 'Alert ' + d.count + ' of ' + cfg.maxViolations + ': Your face was not detected. Keep your face visible in the camera.'
            : 'Violation ' + d.count + ' of ' + cfg.maxViolations + ': ' + (LABELS[d.violation] || d.violation));
          if (d.cancelled) cancelled();
        }
      }).catch(function () {});
    }, 'image/jpeg', 0.7);
  }

  /* ---------- start ---------- */
  $('btnStart').addEventListener('click', function () {
    var btn = this; btn.disabled = true;
    if (!state.stream || !cfg.faceCheckAvailable) {
      setStep('stepCam', false, !state.stream ? 'Camera access is required before you can start.' : 'Face detection is unavailable on this server. Contact your teacher.', true);
      btn.disabled = false;
      return;
    }
    enterFullscreen().then(begin).catch(function () {
      setStep('stepFs', false, 'Fullscreen was blocked. Click Start again and allow it.', true); btn.disabled = false;
    });
  });

  function begin() {
    state.started = true;
    show($('gate'), false);
    var layout = $('layout'); layout.classList.add('live'); layout.removeAttribute('aria-hidden');
    $('submitTop').disabled = false; $('submitBottom').disabled = false;
    refreshProgress(); tick();
    timers.tick = setInterval(tick, 1000);
    timers.save = setInterval(function () { if (state.dirty) save(); }, 20000);
    if (state.faceCheck && state.stream) { setFace('ok'); $('faceStatus').textContent = 'Checking...'; $('faceStatus').className = 'badge muted'; timers.frame = setInterval(sendFrame, cfg.frameInterval * 1000); setTimeout(sendFrame, 3000); }
    state.lastViolationAt = Date.now();   // ignore the focus change that comes with entering fullscreen
  }

  /* ---------- submit ---------- */
  function stopAll() {
    Object.keys(timers).forEach(function (k) { clearInterval(timers[k]); clearTimeout(timers[k]); });
    if (state.stream) state.stream.getTracks().forEach(function (t) { t.onended = null; t.stop(); });
  }

  function submit(auto) {
    if (state.finished) return;
    state.finished = true;
    $('submitTop').disabled = true; $('submitBottom').disabled = true;
    $('endTitle').textContent = 'Submitting...'; $('endMsg').textContent = 'Saving your answers and marking them. This takes a few seconds.';
    show($('endLink'), false); show($('ended'), true);
    post(cfg.urls.submit, { answers: collectAnswers() }).then(function (d) {
      if (d.success) {
        stopAll(); leaveFullscreen();
        $('endTitle').textContent = 'Submitted';
        $('endMsg').textContent = 'Your result is ready.';
        window.location.href = cfg.urls.result;
      } else { throw new Error(d.error || 'Submit failed'); }
    }).catch(function (err) {
      state.finished = false;
      if (auto) { setTimeout(function () { submit(true); }, 3000); }   // keep trying when time is up
      $('endTitle').textContent = 'Could not submit';
      $('endMsg').textContent = (err && err.message ? err.message + '. ' : '') + 'Check your connection. ' + (auto ? 'Trying again.' : 'Your answers are still on this page.');
      if (!auto) { setTimeout(function () { show($('ended'), false); $('submitTop').disabled = false; $('submitBottom').disabled = false; }, 2500); }
    });
  }

  function askSubmit() {
    var p = refreshProgress(), left = p.total - p.done;
    $('confirmMsg').textContent = left ? 'You have not answered ' + left + ' of ' + p.total + ' questions. Unanswered questions score zero.' : 'You answered all ' + p.total + ' questions.';
    var dlg = $('confirm');
    state.lastViolationAt = Date.now() + 1000;
    if (dlg.showModal) dlg.showModal(); else if (window.confirm($('confirmMsg').textContent + ' Submit now?')) submit(false);
  }
  $('submitTop').addEventListener('click', askSubmit);
  $('submitBottom').addEventListener('click', askSubmit);
  $('confirmNo').addEventListener('click', function () { $('confirm').close(); });
  $('confirmYes').addEventListener('click', function () { $('confirm').close(); submit(false); });

  refreshProgress();
})();
