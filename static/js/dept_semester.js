/* Department and semester drop-downs: after you choose a department, the semester list shows only the semesters
   that department has (8 for most, 4 for MBA and MCA). Works for every form that has both selects. */
(function () {
  'use strict';
  var el = document.getElementById('dept-sem-map');
  if (!el) return;
  var map = JSON.parse(el.textContent);

  document.querySelectorAll('select[name="department"]').forEach(function (dept) {
    var form = dept.closest('form') || document;
    var sem = form.querySelector('select[name="semester"]');
    if (!sem) return;
    var placeholder = (sem.options.length && sem.options[0].value === '') ? sem.options[0].cloneNode(true) : null;

    function rebuild() {
      var count = map[dept.value] || 8, current = sem.value;
      sem.innerHTML = '';
      if (placeholder) sem.appendChild(placeholder.cloneNode(true));
      for (var i = 1; i <= count; i++) {
        var o = document.createElement('option');
        o.value = String(i); o.textContent = 'Semester ' + i;
        sem.appendChild(o);
      }
      sem.value = (current && parseInt(current, 10) <= count) ? current : (placeholder ? '' : '1');
    }
    dept.addEventListener('change', rebuild);
    rebuild();
  });
})();
