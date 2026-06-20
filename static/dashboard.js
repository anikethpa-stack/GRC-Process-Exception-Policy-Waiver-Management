const SEVERITY_COLORS = {
  CRITICAL: '#E5484D',
  HIGH: '#F5A623',
  MEDIUM: '#5B8DEF',
  LOW: '#3FB950',
  NONE: '#3A4452',
};

let ALL_EXCEPTIONS = [];
let SUMMARY = null;
let typeChart = null;
let deptChart = null;

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}`);
  return res.json();
}

function fmtPct(part, total) {
  if (!total) return '0%';
  return `${((part / total) * 100).toFixed(1)}%`;
}

function renderPulse(riskBreakdown, total) {
  const order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
  const bar = document.getElementById('pulse-bar');
  const legend = document.getElementById('pulse-legend');
  bar.innerHTML = '';
  legend.innerHTML = '';

  order.forEach((level) => {
    const count = riskBreakdown[level] || 0;
    const pct = total ? (count / total) * 100 : 0;
    const seg = document.createElement('div');
    seg.className = 'pulse-seg';
    seg.style.width = `${pct}%`;
    seg.style.background = SEVERITY_COLORS[level];
    seg.title = `${level}: ${count}`;
    bar.appendChild(seg);

    const item = document.createElement('div');
    item.className = 'pulse-legend-item';
    item.innerHTML = `<span class="pulse-dot" style="background:${SEVERITY_COLORS[level]}"></span>${level} · ${count}`;
    legend.appendChild(item);
  });
}

function renderKPIs(summary) {
  const row = document.getElementById('kpi-row');
  const criticalCount = summary.risk_breakdown.CRITICAL || 0;
  const highCount = summary.risk_breakdown.HIGH || 0;

  row.innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Total active exceptions</div>
      <div class="kpi-value">${summary.total_active}</div>
      <div class="kpi-sub">${summary.total_flagged} flagged across full registry</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Critical risk</div>
      <div class="kpi-value critical">${criticalCount}</div>
      <div class="kpi-sub">Requires immediate attention</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">High risk</div>
      <div class="kpi-value high">${highCount}</div>
      <div class="kpi-sub">${fmtPct(highCount, summary.total_active)} of active portfolio</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Expiring (30 days)</div>
      <div class="kpi-value accent">${summary.expiring_30_days}</div>
      <div class="kpi-sub">Due for renewal decision</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Expired, not revoked</div>
      <div class="kpi-value critical">${summary.expired_not_revoked}</div>
      <div class="kpi-sub">Orphaned access — should be closed</div>
    </div>
  `;
}

function renderTypeChart(typeBreakdown) {
  const ctx = document.getElementById('chart-type');
  ctx.innerHTML = '<canvas id="type-canvas"></canvas>';
  const canvas = document.getElementById('type-canvas');
  const labels = Object.keys(typeBreakdown);
  const data = Object.values(typeBreakdown);

  if (typeChart) typeChart.destroy();
  typeChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels.map(l => l.replace(/_/g, ' ')),
      datasets: [{
        data,
        backgroundColor: '#6FE3C4',
        borderRadius: 4,
        barThickness: 16,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8B96A5', font: { size: 10 } }, grid: { color: '#1B232D' } },
        y: { ticks: { color: '#E6EDF3', font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

function renderDeptChart(deptBreakdown) {
  const ctx = document.getElementById('chart-dept');
  ctx.innerHTML = '<canvas id="dept-canvas"></canvas>';
  const canvas = document.getElementById('dept-canvas');
  const labels = Object.keys(deptBreakdown);
  const data = Object.values(deptBreakdown);

  if (deptChart) deptChart.destroy();
  deptChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: ['#6FE3C4', '#5B8DEF', '#F5A623', '#E5484D', '#3FB950',
                           '#9D7BE0', '#4FB8D6', '#E89BC4', '#C4D45B', '#7B92A8'],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#8B96A5', font: { size: 10 }, boxWidth: 10, padding: 8 },
        },
      },
    },
  });
}

function renderTopRisk(topRisk) {
  const container = document.getElementById('top-risk-list');
  container.innerHTML = '';
  if (!topRisk.length) {
    container.innerHTML = '<p style="color:var(--text-faint);font-size:12px;">No flagged exceptions — portfolio is clean.</p>';
    return;
  }
  topRisk.forEach((r) => {
    const row = document.createElement('div');
    row.className = `risk-row sev-${r.primary_severity}`;
    row.innerHTML = `
      <span class="rid">${r.exception_id}</span>
      <div>
        <div class="rmeta">${r.type.replace(/_/g, ' ')} — ${r.requester} (${r.department})</div>
        <div class="ralert">${r.alerts[0] || ''}</div>
      </div>
      <span class="badge badge-${r.primary_severity}">${r.primary_severity}</span>
    `;
    row.addEventListener('click', () => openModal(r));
    container.appendChild(row);
  });
}

function renderReadiness(readiness) {
  const grid = document.getElementById('readiness-grid');
  grid.innerHTML = `
    <div class="readiness-item">
      <div class="rv">${readiness.all_documented_pct}%</div>
      <div class="rl">All exceptions documented</div>
    </div>
    <div class="readiness-item">
      <div class="rv">${readiness.approvals_recorded_pct}%</div>
      <div class="rl">Approvals recorded</div>
    </div>
    <div class="readiness-item">
      <div class="rv">${readiness.overdue_for_review}</div>
      <div class="rl">Exceptions overdue for review</div>
    </div>
    <div class="readiness-item">
      <div class="rv">${readiness.not_revoked_after_expiry}</div>
      <div class="rl">Not revoked after expiry</div>
    </div>
  `;
}

function populateStatusFilter(exceptions) {
  const select = document.getElementById('filter-status');
  const statuses = [...new Set(exceptions.map(e => e.status))].sort();
  statuses.forEach((s) => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    select.appendChild(opt);
  });
}

function getFilteredRows() {
  const search = document.getElementById('search-box').value.toLowerCase();
  const statusFilter = document.getElementById('filter-status').value;
  const severityFilter = document.getElementById('filter-severity').value;
  const flaggedOnly = document.getElementById('filter-flagged-only').checked;

  return ALL_EXCEPTIONS.filter((r) => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (severityFilter && r.primary_severity !== severityFilter) return false;
    if (flaggedOnly && !r.is_flagged) return false;
    if (search) {
      const haystack = `${r.exception_id} ${r.requester} ${r.approver} ${r.justification}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

let sortKey = 'primary_severity';
let sortDir = -1;
const SEV_RANK = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 };

function renderTable() {
  const rows = getFilteredRows();
  rows.sort((a, b) => {
    let va = a[sortKey];
    let vb = b[sortKey];
    if (sortKey === 'primary_severity') {
      va = SEV_RANK[va] ?? 0;
      vb = SEV_RANK[vb] ?? 0;
    }
    if (va < vb) return -1 * sortDir;
    if (va > vb) return 1 * sortDir;
    return 0;
  });

  const tbody = document.getElementById('table-body');
  tbody.innerHTML = '';
  rows.forEach((r) => {
    const tr = document.createElement('tr');
    if (r.is_flagged) tr.classList.add('flagged-row');
    tr.innerHTML = `
      <td>${r.exception_id}</td>
      <td>${r.type.replace(/_/g, ' ')}</td>
      <td>${r.requester}</td>
      <td>${r.approver}</td>
      <td>${r.department}</td>
      <td>${r.end_date}</td>
      <td>${r.status}</td>
      <td><span class="badge badge-${r.primary_severity}">${r.primary_severity}</span></td>
      <td>${r.alerts.length ? r.alerts.length + ' alert' + (r.alerts.length > 1 ? 's' : '') : '—'}</td>
    `;
    tr.addEventListener('click', () => openModal(r));
    tbody.appendChild(tr);
  });

  document.getElementById('row-count').textContent = `Showing ${rows.length} of ${ALL_EXCEPTIONS.length} exceptions`;
}

function openModal(r) {
  const modal = document.getElementById('detail-modal');
  const content = document.getElementById('modal-content');
  content.innerHTML = `
    <h3>${r.exception_id}</h3>
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 16px;">${r.type.replace(/_/g, ' ')}</p>
    <div class="modal-row"><span>Requester</span><span>${r.requester}</span></div>
    <div class="modal-row"><span>Approver</span><span>${r.approver}</span></div>
    <div class="modal-row"><span>Department</span><span>${r.department}</span></div>
    <div class="modal-row"><span>Justification</span><span>${r.justification}</span></div>
    <div class="modal-row"><span>Start date</span><span>${r.start_date}</span></div>
    <div class="modal-row"><span>End date</span><span>${r.end_date}</span></div>
    <div class="modal-row"><span>Status</span><span>${r.status}</span></div>
    <div class="modal-row"><span>Severity</span><span class="badge badge-${r.primary_severity}">${r.primary_severity}</span></div>
    ${r.alerts.length ? `
      <div class="modal-alerts">
        <strong style="font-size:12px;color:var(--text-dim);">ALERTS</strong>
        ${r.alerts.map(a => `<div class="modal-alert-item">${a}</div>`).join('')}
      </div>
      <div class="modal-recommendation">${r.recommendation}</div>
    ` : '<p style="margin-top:16px;color:var(--low);font-size:13px;">No issues detected.</p>'}
  `;
  modal.classList.remove('hidden');
}

function closeModal() {
  document.getElementById('detail-modal').classList.add('hidden');
}

function setupSortHeaders() {
  document.querySelectorAll('th[data-sort]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (sortKey === key) {
        sortDir *= -1;
      } else {
        sortKey = key;
        sortDir = 1;
      }
      renderTable();
    });
  });
}

async function init() {
  const [summary, exceptions, readiness] = await Promise.all([
    fetchJSON('/api/summary'),
    fetchJSON('/api/exceptions'),
    fetchJSON('/api/audit-readiness'),
  ]);

  SUMMARY = summary;
  ALL_EXCEPTIONS = exceptions;

  document.getElementById('report-date').textContent = `Report date: ${summary.report_date}`;

  renderPulse(summary.risk_breakdown, summary.total_active);
  renderKPIs(summary);
  renderTypeChart(summary.type_breakdown);
  renderDeptChart(summary.department_breakdown);
  renderTopRisk(summary.top_high_risk);
  renderReadiness(readiness);
  populateStatusFilter(exceptions);
  renderTable();
  setupSortHeaders();

  document.getElementById('search-box').addEventListener('input', renderTable);
  document.getElementById('filter-status').addEventListener('change', renderTable);
  document.getElementById('filter-severity').addEventListener('change', renderTable);
  document.getElementById('filter-flagged-only').addEventListener('change', renderTable);

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('detail-modal').addEventListener('click', (e) => {
    if (e.target.id === 'detail-modal') closeModal();
  });

  document.getElementById('export-csv').addEventListener('click', () => {
    window.location.href = '/api/report/csv';
  });
  document.getElementById('export-audit').addEventListener('click', () => {
    window.location.href = '/api/report/audit';
  });
}

init();
