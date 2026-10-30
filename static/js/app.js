(function () {
  'use strict';
  // Mobile menu
  var btn = document.getElementById('menuBtn'), side = document.getElementById('sidebar');
  if (btn && side) {
    btn.addEventListener('click', function () {
      var open = side.classList.toggle('open');
      btn.setAttribute('aria-expanded', open);
    });
    document.getElementById('content').addEventListener('click', function () { side.classList.remove('open'); });
  }
  // Confirm before risky buttons: <form data-confirm="Are you sure?">
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  });
})();

/* Chart helpers (Chart.js is loaded only on pages that need it) */
window.SmartChart = {
  ink: '#17205B', red: '#D32F4B', line: '#D9E0EF',
  defaults: function () {
    if (!window.Chart) return;
    Chart.defaults.font.family = '"Bricolage Grotesque","Segoe UI",sans-serif';
    Chart.defaults.color = '#4A5385';
    Chart.defaults.borderColor = '#D9E0EF';
  },
  thresholdLine: function (value) {
    return { id: 'threshold', afterDatasetsDraw: function (chart) {
      var y = chart.scales.y.getPixelForValue(value), a = chart.chartArea, c = chart.ctx;
      c.save(); c.setLineDash([6, 5]); c.strokeStyle = '#D32F4B'; c.lineWidth = 2;
      c.beginPath(); c.moveTo(a.left, y); c.lineTo(a.right, y); c.stroke();
      c.setLineDash([]); c.fillStyle = '#D32F4B'; c.font = '600 12px sans-serif';
      c.fillText(value + '%', a.right - 30, y - 6); c.restore();
    } };
  },
  percentBar: function (canvasId, labels, values, threshold) {
    this.defaults();
    var el = document.getElementById(canvasId); if (!el || !labels.length) return;
    var self = this;
    new Chart(el, { type: 'bar',
      data: { labels: labels, datasets: [{ data: values, borderRadius: 3,
        backgroundColor: values.map(function (v) { return v < threshold ? self.red : self.ink; }) }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + '%'; } } }, x: { grid: { display: false } } } },
      plugins: [this.thresholdLine(threshold)] });
  },
  percentLine: function (canvasId, labels, values, threshold) {
    this.defaults();
    var el = document.getElementById(canvasId); if (!el || !labels.length) return;
    var self = this;
    new Chart(el, { type: 'line',
      data: { labels: labels, datasets: [{ data: values, borderColor: this.ink, backgroundColor: this.ink, tension: .25, borderWidth: 3,
        pointRadius: 5, pointBackgroundColor: values.map(function (v) { return v < threshold ? self.red : self.ink; }) }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + '%'; } } }, x: { grid: { display: false } } } },
      plugins: [this.thresholdLine(threshold)] });
  },
  simpleBar: function (canvasId, labels, values, color) {
    this.defaults();
    var el = document.getElementById(canvasId); if (!el || !labels.length) return;
    new Chart(el, { type: 'bar', data: { labels: labels, datasets: [{ data: values, backgroundColor: color || this.ink, borderRadius: 3 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } } } });
  }
,
  combined: function (canvasId, d) {
    this.defaults();
    var el = document.getElementById(canvasId); if (!el || !d.labels.length) return;
    new Chart(el, { type: 'line',
      data: { labels: d.labels, datasets: [
        { label: 'Exam result (%)', data: d.exams, borderColor: this.ink, backgroundColor: this.ink, borderWidth: 3, tension: .25, pointRadius: 5, spanGaps: true },
        { label: 'Assignment rating (stars x 20)', data: d.assignments, borderColor: this.red, backgroundColor: this.red, borderWidth: 3, borderDash: [7, 5], tension: .25, pointRadius: 5, pointStyle: 'rectRot', spanGaps: true }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'nearest', intersect: true },
        plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: {
          title: function (items) { return d.titles[items[0].dataIndex] || ''; },
          label: function (item) { var v = item.parsed.y; return item.dataset.label.indexOf('Assignment') === 0 ? (v / 20).toFixed(1) + ' of 5 stars' : v + '%'; } } } },
        scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + '%'; } } }, x: { grid: { display: false } } } },
      plugins: [this.thresholdLine(d.threshold)] });
  }
,
  simpleBarH: function (canvasId, labels, values) {
    this.defaults();
    var el = document.getElementById(canvasId); if (!el || !labels.length) return;
    new Chart(el, { type: 'bar', data: { labels: labels, datasets: [{ data: values, backgroundColor: this.ink, borderRadius: 3 }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } } } });
  }
};
