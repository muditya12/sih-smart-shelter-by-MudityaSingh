// SIH26051 - climate preset fill + history table
const sel = document.getElementById('climate');
if (sel) sel.addEventListener('change', e => {
  const o = e.target.selectedOptions[0];
  if (!o.dataset.temp) return;
  document.getElementById('t_out').value = o.dataset.temp;
  document.getElementById('irr').value = o.dataset.irr;
  document.getElementById('wind').value = o.dataset.wind;
});

const tbl = document.getElementById('history-table');
if (tbl) fetch('/api/history').then(r => r.json()).then(rows => {
  rows.forEach(d => {
    const tr = tbl.insertRow();
    [d.id, d.created_at.slice(11, 16), d.wall, d.roof,
     d.t_after.toFixed(1), d.cost.toFixed(0), d.score.toFixed(0)]
      .forEach(v => tr.insertCell().textContent = v);
  });
});