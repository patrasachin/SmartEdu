/* SmartEdu landing page interactions. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------- Answer sheet ---------------- */
  var sheet = document.getElementById('sheet');
  if (sheet) {
    var MCQ = {
      q1: { correct: 'B', topic: 'Algebra' },
      q2: { correct: 'B', topic: 'Calculus' }
    };
    var KEYWORDS = ['symbols', 'mathematics', 'equation', 'variable'];
    var MARKS = 5, MAX = 15;

    var answer = document.getElementById('answer');
    var scoreNum = document.getElementById('scoreNum');
    var verdict = document.getElementById('verdict');
    var srStatus = document.getElementById('srStatus');
    var chips = sheet.querySelectorAll('.chip');
    var shownScore = 0, tweenId = null, srTimer = null;

    function fmt(n) { return String(Number(n.toFixed(2))); }

    function chosen(name) {
      var el = sheet.querySelector('input[name="' + name + '"]:checked');
      return el ? el.value : null;
    }

    function setState(q, state, note) {
      var li = sheet.querySelector('[data-q="' + q + '"]');
      var noteEl = sheet.querySelector('[data-note="' + q + '"]');
      li.setAttribute('data-state', state);
      noteEl.textContent = note || '';
    }

    function tweenScore(to) {
      if (tweenId) cancelAnimationFrame(tweenId);
      if (reduceMotion) { shownScore = to; scoreNum.textContent = fmt(to); return; }
      var from = shownScore, start = null, dur = 350;
      function step(ts) {
        if (start === null) start = ts;
        var t = Math.min(1, (ts - start) / dur);
        shownScore = from + (to - from) * t;
        scoreNum.textContent = fmt(shownScore);
        if (t < 1) tweenId = requestAnimationFrame(step);
      }
      tweenId = requestAnimationFrame(step);
    }

    function render() {
      var score = 0, wrongByTopic = {}, totalByTopic = {}, attempted = 0;

      Object.keys(MCQ).forEach(function (q) {
        var picked = chosen(q), cfg = MCQ[q];
        totalByTopic[cfg.topic] = (totalByTopic[cfg.topic] || 0) + 1;
        if (!picked) { setState(q, 'none', ''); wrongByTopic[cfg.topic] = (wrongByTopic[cfg.topic] || 0) + 1; return; }
        attempted++;
        if (picked === cfg.correct) { score += MARKS; setState(q, 'right', 'Correct.'); }
        else {
          wrongByTopic[cfg.topic] = (wrongByTopic[cfg.topic] || 0) + 1;
          setState(q, 'wrong', 'Marked wrong. Correct was ' + cfg.correct + '.');
        }
      });

      // Written answer: keyword match, same substring check as subjective_evaluator.py
      var text = answer.value.toLowerCase();
      var found = KEYWORDS.filter(function (k) { return text.indexOf(k) !== -1; });
      chips.forEach(function (c) { c.classList.toggle('is-found', found.indexOf(c.getAttribute('data-kw')) !== -1); });

      totalByTopic.Algebra = (totalByTopic.Algebra || 0) + 1;
      if (text.trim()) {
        attempted++;
        var ratio = found.length / KEYWORDS.length;
        score += MARKS * ratio;
        if (ratio < 0.5) wrongByTopic.Algebra = (wrongByTopic.Algebra || 0) + 1;
        var missing = KEYWORDS.filter(function (k) { return found.indexOf(k) === -1; });
        setState('q3', ratio >= 0.5 ? 'right' : 'wrong',
          missing.length ? 'Add: ' + missing.join(', ') : 'Full marks.');
      } else {
        wrongByTopic.Algebra = (wrongByTopic.Algebra || 0) + 1;
        setState('q3', 'none', '');
      }

      tweenScore(score);

      if (attempted === 3) {
        var pct = Math.round(score / MAX * 100);
        var weak = Object.keys(totalByTopic).filter(function (t) {
          return (wrongByTopic[t] || 0) / totalByTopic[t] >= 0.5;
        });
        var low = pct < 70;
        verdict.classList.toggle('is-low', low);
        verdict.textContent = pct + '% overall. ' +
          (low ? 'Flagged below 70%. ' : 'At or above 70%. ') +
          (weak.length ? 'Weak topic: ' + weak.join(', ') + '.' : 'No weak topics.');
      } else {
        verdict.classList.remove('is-low');
        verdict.textContent = 'Answer all three questions to see the result.';
      }

      // Announce to screen readers once things settle, not on every keystroke.
      clearTimeout(srTimer);
      srTimer = setTimeout(function () {
        srStatus.textContent = 'Score ' + fmt(score) + ' out of ' + MAX + '. ' + verdict.textContent;
      }, 900);
    }

    sheet.addEventListener('change', render);
    answer.addEventListener('input', render);

    /* Opening moment: the sheet marks itself once, then the visitor takes over. */
    var cancelled = false, timers = [];
    function later(fn, ms) { timers.push(setTimeout(function () { if (!cancelled) fn(); }, ms)); }
    function stopAuto() { cancelled = true; timers.forEach(clearTimeout); }
    function pick(name, val) { sheet.querySelector('input[name="' + name + '"][value="' + val + '"]').checked = true; render(); }

    var SAMPLE = 'Algebra uses symbols and a variable to write an equation.';

    if (reduceMotion) {
      pick('q1', 'B'); pick('q2', 'A'); answer.value = SAMPLE; render();
    } else {
      sheet.addEventListener('pointerdown', stopAuto);
      sheet.addEventListener('keydown', stopAuto);
      later(function () { pick('q1', 'B'); }, 700);
      later(function () { pick('q2', 'A'); }, 1500);
      later(function () {
        var i = 0;
        (function type() {
          if (cancelled) return;
          i++;
          answer.value = SAMPLE.slice(0, i);
          render();
          if (i < SAMPLE.length) timers.push(setTimeout(type, 38));
        })();
      }, 2300);
    }

    document.getElementById('clearSheet').addEventListener('click', function () {
      stopAuto();
      sheet.querySelectorAll('input[type="radio"]').forEach(function (r) { r.checked = false; });
      answer.value = '';
      render();
      sheet.querySelector('input[name="q1"]').focus();
    });
  }

})();
