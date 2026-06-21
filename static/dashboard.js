const SEVERITY_COLORS = {
  CRITICAL: 'var(--critical)',
  HIGH: 'var(--high)',
  MEDIUM: 'var(--medium)',
  LOW: 'var(--low)',
  NONE: 'var(--none)',
};

let ALL_EXCEPTIONS = [];
let SUMMARY = null;
let typeChart = null;
let deptChart = null;
let ACTIVE_EVOLUTION_BUCKET = null;

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}`);
  return res.json();
}

function fmtPct(part, total) {
  if (!total) return '0%';
  return `${((part / total) * 100).toFixed(1)}%`;
}

function getBucketExceptions(bucket, exceptions) {
  const active = exceptions.filter(r => r.status === "ACTIVE");
  const today = new Date("2026-04-15");
  return exceptions.filter(r => {
    if (r.status !== "ACTIVE") return false;
    const start = new Date(r.start_date);
    const age = Math.ceil((today - start) / (1000 * 60 * 60 * 24));
    if (bucket === 'new') return age <= 30;
    if (bucket === 'aging') return age > 30 && age <= 90;
    if (bucket === 'long') return age > 90 && age <= 180;
    if (bucket === 'chronic') return age > 180;
    return true;
  });
}

function computePortfolioSummary(exceptions) {
  const active = exceptions.filter(r => r.status === "ACTIVE");
  const expiredNotRevoked = exceptions.filter(r => r.status === "ACTIVE" && new Date(r.end_date) < new Date("2026-04-15"));
  
  const expiring30 = exceptions.filter(r => {
    if (r.status !== "ACTIVE") return false;
    const end = new Date(r.end_date);
    const today = new Date("2026-04-15");
    const diffTime = end - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays >= 0 && diffDays <= 30;
  });
  
  const overdueReviews = exceptions.filter(r => {
    return r.alerts.some(a => a.startsWith("STALLED_REVIEW") || a.startsWith("HIGH_RISK_LONG") || a.startsWith("LONG_RUNNING"));
  });
  
  const criticalCount = active.filter(r => r.computed_severity === "CRITICAL").length;
  const highCount = active.filter(r => r.computed_severity === "HIGH").length;
  
  const longRunning = active.filter(r => {
    const start = new Date(r.start_date);
    const today = new Date("2026-04-15");
    const diffDays = Math.ceil((today - start) / (1000 * 60 * 60 * 24));
    return diffDays > 90 && diffDays <= 180;
  });
  
  const chronic = active.filter(r => {
    const start = new Date(r.start_date);
    const today = new Date("2026-04-15");
    const diffDays = Math.ceil((today - start) / (1000 * 60 * 60 * 24));
    return diffDays > 180;
  });
  
  const c_expired = expiredNotRevoked.length * 0.84;
  const c_overdue = overdueReviews.length * 0.116;
  const c_critical = criticalCount * 0.43;
  const c_long = longRunning.length * 0.037;
  
  const rawScore = c_expired + c_overdue + c_critical + c_long;
  const policyDebtScore = Math.min(100, Math.max(0, Math.round(rawScore)));
  
  let p_expired = 0, p_overdue = 0, p_critical = 0, p_long = 0;
  const total = c_expired + c_overdue + c_critical + c_long;
  if (total > 0) {
    p_expired = Math.round((c_expired / total) * 100);
    p_overdue = Math.round((c_overdue / total) * 100);
    p_critical = Math.round((c_critical / total) * 100);
    p_long = Math.round((c_long / total) * 100);
    const diff = 100 - (p_expired + p_overdue + p_critical + p_long);
    p_expired += diff;
  }
  
  let auditExposure = "LOW";
  if (policyDebtScore >= 81) auditExposure = "CRITICAL";
  else if (policyDebtScore >= 61) auditExposure = "HIGH";
  else if (policyDebtScore >= 31) auditExposure = "MEDIUM";
  
  function getTopOwners(key) {
    const scores = {};
    const critCounts = {};
    const highCounts = {};
    active.forEach(r => {
      const val = r[key] || "Unknown";
      scores[val] = (scores[val] || 0) + (r.computed_risk_score || 0);
      if (r.computed_severity === "CRITICAL") critCounts[val] = (critCounts[val] || 0) + 1;
      if (r.computed_severity === "HIGH") highCounts[val] = (highCounts[val] || 0) + 1;
    });
    const sorted = Object.keys(scores).map(name => ({
      name,
      cumulative_score: scores[name],
      critical_count: critCounts[name] || 0,
      high_count: highCounts[name] || 0
    })).sort((a, b) => b.cumulative_score - a.cumulative_score);
    return sorted.slice(0, 5);
  }
  
  const flagged = exceptions.filter(r => r.is_flagged);
  flagged.sort((a, b) => {
    if (a.computed_risk_score !== b.computed_risk_score) {
      return b.computed_risk_score - a.computed_risk_score;
    }
    const ageA = Math.ceil((new Date("2026-04-15") - new Date(a.start_date)) / (1000 * 60 * 60 * 24));
    const ageB = Math.ceil((new Date("2026-04-15") - new Date(b.start_date)) / (1000 * 60 * 60 * 24));
    return ageB - ageA;
  });
  
  const recommendedActions = [];
  if (expiredNotRevoked.length) {
    recommendedActions.push(`Revoke ${expiredNotRevoked.length} Expired Exceptions`);
  }
  if (overdueReviews.length) {
    recommendedActions.push(`Review ${overdueReviews.length} Overdue Exceptions`);
  }
  const deptScores = getTopOwners("department");
  if (deptScores.length) {
    recommendedActions.push(`Review ${deptScores[0].name} Department Risk`);
  }
  const longRunningVendor = active.filter(r => r.type === "vendor_access_waiver" && r.alerts.some(a => a.startsWith("LONG_RUNNING")));
  if (longRunningVendor.length) {
    recommendedActions.push(`Escalate Long Running Vendor Waivers`);
  }
  if (!recommendedActions.length) {
    recommendedActions.push("No immediate remediation actions detected.");
  }
  
  return {
    total_active: active.length,
    expired_not_revoked: expiredNotRevoked.length,
    overdue_reviews: overdueReviews.length,
    expiring_30_days: expiring30.length,
    policy_debt_score: policyDebtScore,
    audit_exposure: auditExposure,
    policy_debt_contributors: {
      expired_active: expiredNotRevoked.length,
      overdue_reviews: overdueReviews.length,
      long_running: longRunning.length,
      critical_active: criticalCount
    },
    top_high_risk: flagged,
    recommended_actions: recommendedActions,
    top_risk_departments: getTopOwners("department"),
    top_risk_requesters: getTopOwners("requester"),
    top_risk_approvers: getTopOwners("approver"),
    risk_evolution: {
      new_count: active.filter(r => {
        const age = Math.ceil((new Date("2026-04-15") - new Date(r.start_date)) / (1000 * 60 * 60 * 24));
        return age <= 30;
      }).length,
      aging_count: active.filter(r => {
        const age = Math.ceil((new Date("2026-04-15") - new Date(r.start_date)) / (1000 * 60 * 60 * 24));
        return age > 30 && age <= 90;
      }).length,
      long_running_count: longRunning.length,
      chronic_count: chronic.length,
      expired_active_count: expiredNotRevoked.length,
      aged_beyond_90: longRunning.length + chronic.length
    }
  };
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

function renderExecutiveAlert(summary) {
  document.getElementById('banner-expired-count').textContent = summary.expired_not_revoked;
  document.getElementById('banner-overdue-count').textContent = summary.overdue_reviews;
}

function renderExecutiveKPIs(summary) {
  // Global stats remain global and do not change with interactive filters
  document.getElementById('debt-score-value').textContent = summary.policy_debt_score;
  const badge = document.getElementById('debt-badge');
  badge.textContent = summary.audit_exposure;
  badge.className = `debt-badge badge-${summary.audit_exposure}`;
  
  const c = summary.policy_debt_contributors;
  document.getElementById('driver-expired-val').textContent = c.expired_active;
  document.getElementById('driver-overdue-val').textContent = c.overdue_reviews;
  document.getElementById('driver-long-val').textContent = c.long_running;
  document.getElementById('driver-critical-val').textContent = c.critical_active;

  document.getElementById('kpi-expired').textContent = summary.expired_not_revoked;
  document.getElementById('kpi-overdue').textContent = summary.overdue_reviews;
  document.getElementById('kpi-expiring').textContent = summary.expiring_30_days;
}

function renderRecommendedActions(actions) {
  const container = document.getElementById('recommended-actions-grid');
  container.innerHTML = '';
  
  actions.forEach((action) => {
    let title = action;
    let impact = 'Reduces accumulated policy deviation';
    let priority = 'Low';
    let reduction = '-2 Policy Debt Score';
    
    if (action.includes('Revoke')) {
      const match = action.match(/\d+/);
      const count = match ? match[0] : '';
      title = `Revoke ${count} Expired Exceptions`;
      impact = 'Eliminates orphaned access exposure';
      priority = 'Critical';
      reduction = '-12 Policy Debt Score';
    } else if (action.includes('Review') && action.includes('Overdue')) {
      const match = action.match(/\d+/);
      const count = match ? match[0] : '';
      title = `Review ${count} Overdue Exceptions`;
      impact = 'Clears compliance review backlog';
      priority = 'High';
      reduction = '-8 Policy Debt Score';
    } else if (action.includes('Department') || action.includes('Risk')) {
      title = action;
      impact = 'Reduces department exposure concentration';
      priority = 'Medium';
      reduction = '-5 Policy Debt Score';
    } else if (action.includes('Vendor')) {
      title = 'Escalate Long Running Vendor Waivers';
      impact = 'Mitigates supply chain compliance gaps';
      priority = 'Medium';
      reduction = '-4 Policy Debt Score';
    }
    
    const card = document.createElement('div');
    card.className = 'bento-action-card';
    card.innerHTML = `
      <div class="action-card-header">
        <span class="action-badge">NEXT BEST ACTION</span>
        <span class="action-priority priority-${priority.toLowerCase()}">${priority}</span>
      </div>
      <div class="action-card-title">${title}</div>
      <div class="action-card-body">
        <div class="action-meta-item"><span>Business Impact</span> <strong>${impact}</strong></div>
        <div class="action-meta-item"><span>Expected Reduction</span> <strong class="reduction-text">${reduction}</strong></div>
      </div>
    `;
    
    card.addEventListener('click', () => {
      if (action.includes('Revoke')) {
        document.getElementById('filter-status').value = 'ACTIVE';
        document.getElementById('ledger-panel').scrollIntoView({ behavior: 'smooth' });
      } else if (action.includes('Review') && action.includes('Overdue')) {
        document.getElementById('filter-status').value = 'RENEWAL_REQUESTED';
        document.getElementById('ledger-panel').scrollIntoView({ behavior: 'smooth' });
      } else if (action.includes('Department')) {
        const parts = action.split(' ');
        const deptName = parts.slice(1, parts.length - 2).join(' ');
        document.getElementById('search-box').value = deptName;
        document.getElementById('ledger-panel').scrollIntoView({ behavior: 'smooth' });
      }
      renderTable();
    });
    
    container.appendChild(card);
  });
}

function renderRiskEvolution(summary) {
  const ev = summary.risk_evolution;
  const total = ev.new_count + ev.aging_count + ev.long_running_count + ev.chronic_count;
  
  const pctNew = total ? (ev.new_count / total) * 100 : 0;
  const pctAging = total ? (ev.aging_count / total) * 100 : 0;
  const pctLong = total ? (ev.long_running_count / total) * 100 : 0;
  const pctChronic = total ? (ev.chronic_count / total) * 100 : 0;
  
  const bar = document.getElementById('evolution-stacked-bar');
  bar.innerHTML = `
    <div class="evol-seg seg-new ${ACTIVE_EVOLUTION_BUCKET === 'new' ? 'active-segment' : ''}" style="width: ${pctNew}%; background: var(--low);" title="New: ${ev.new_count}"></div>
    <div class="evol-seg seg-aging ${ACTIVE_EVOLUTION_BUCKET === 'aging' ? 'active-segment' : ''}" style="width: ${pctAging}%; background: var(--medium);" title="Aging: ${ev.aging_count}"></div>
    <div class="evol-seg seg-long ${ACTIVE_EVOLUTION_BUCKET === 'long' ? 'active-segment' : ''}" style="width: ${pctLong}%; background: var(--high);" title="Long Running: ${ev.long_running_count}"></div>
    <div class="evol-seg seg-chronic ${ACTIVE_EVOLUTION_BUCKET === 'chronic' ? 'active-segment' : ''}" style="width: ${pctChronic}%; background: var(--critical);" title="Chronic: ${ev.chronic_count}"></div>
  `;
  
  const legend = document.getElementById('stacked-bar-legend');
  legend.innerHTML = `
    <div class="legend-item"><span class="legend-dot" style="background:var(--low);"></span>New (&lt;30d) · <strong>${ev.new_count}</strong></div>
    <div class="legend-item"><span class="legend-dot" style="background:var(--medium);"></span>Aging (31-90d) · <strong>${ev.aging_count}</strong></div>
    <div class="legend-item"><span class="legend-dot" style="background:var(--high);"></span>Long Running (91-180d) · <strong>${ev.long_running_count}</strong></div>
    <div class="legend-item"><span class="legend-dot" style="background:var(--critical);"></span>Chronic (&gt;180d) · <strong>${ev.chronic_count}</strong></div>
  `;
  
  const interpretation = document.getElementById('evolution-interpretation');
  interpretation.innerHTML = `
    <p class="interpretation-text"><strong>Executive Analysis:</strong> ${ev.aged_beyond_90} exceptions have aged beyond 90 days, indicating temporary waivers are evolving into persistent organizational risk.</p>
  `;
  
  // Attach segment click events
  const segs = [
    { selector: '.seg-new', bucket: 'new', label: 'New Exceptions (<30d)' },
    { selector: '.seg-aging', bucket: 'aging', label: 'Aging Exceptions (31-90d)' },
    { selector: '.seg-long', bucket: 'long', label: 'Long Running Exceptions (91-180d)' },
    { selector: '.seg-chronic', bucket: 'chronic', label: 'Chronic Exceptions (>180d)' }
  ];
  
  segs.forEach(s => {
    const el = bar.querySelector(s.selector);
    if (el) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => selectEvolutionBucket(s.bucket, s.label));
    }
  });
}

function selectEvolutionBucket(bucket, label) {
  ACTIVE_EVOLUTION_BUCKET = bucket;
  
  // Show active indicator
  const wrap = document.getElementById('filter-indicator-wrap');
  wrap.classList.remove('hidden');
  document.getElementById('active-filter-label').textContent = label;
  
  // Mark active segment
  document.querySelectorAll('.evol-seg').forEach(s => s.classList.remove('active-segment'));
  const activeSeg = document.querySelector(`.seg-${bucket}`);
  if (activeSeg) activeSeg.classList.add('active-segment');
  
  // Recalculate context (Recommended Actions, Risk Concentration, Priority Queue, Ledger)
  const bucketExceptions = getBucketExceptions(bucket, ALL_EXCEPTIONS);
  const bucketSummary = computePortfolioSummary(bucketExceptions);
  
  renderRecommendedActions(bucketSummary.recommended_actions);
  renderRiskConcentration(bucketSummary);
  renderPriorityQueue(bucketExceptions);
  renderTable();
}

function resetEvolutionBucket() {
  ACTIVE_EVOLUTION_BUCKET = null;
  
  // Hide active indicator
  document.getElementById('filter-indicator-wrap').classList.add('hidden');
  document.querySelectorAll('.evol-seg').forEach(s => s.classList.remove('active-segment'));
  
  // Restore views
  renderRecommendedActions(SUMMARY.recommended_actions);
  renderRiskConcentration(SUMMARY);
  renderPriorityQueue(ALL_EXCEPTIONS);
  renderTable();
}

let AUDIT_MODE = false;

function filterAuditFindings(exception) {
  return exception.alerts.some((alert) =>
    alert.startsWith('EXPIRED_ACTIVE_EXCEPTION') ||
    alert.startsWith('STALLED_REVIEW') ||
    alert.startsWith('HIGH_RISK_LONG_EXCEPTION') ||
    alert.startsWith('LONG_RUNNING_EXCEPTION') ||
    exception.computed_severity === 'CRITICAL' ||
    !exception.approver
  );
}

function renderPriorityQueue(exceptions) {
  const container = document.getElementById('priority-queue-list');
  container.innerHTML = '';
  
  // Filter exceptions in active view to CRITICAL first
  let criticals = exceptions.filter(r => r.computed_severity === 'CRITICAL');
  
  // Sort by computed risk score descending, then age descending
  criticals.sort((a, b) => {
    if (b.computed_risk_score !== a.computed_risk_score) {
      return b.computed_risk_score - a.computed_risk_score;
    }
    const ageA = Math.ceil((new Date("2026-04-15") - new Date(a.start_date)) / (1000 * 60 * 60 * 24));
    const ageB = Math.ceil((new Date("2026-04-15") - new Date(b.start_date)) / (1000 * 60 * 60 * 24));
    return ageB - ageA;
  });

  const displayList = criticals.slice(0, 5);

  if (!displayList.length) {
    container.innerHTML = '<p style="color:var(--text-faint);font-size:13px;padding:24px;text-align:center;width:100%;">No critical exceptions identified in this context.</p>';
    return;
  }

  displayList.forEach((r) => {
    let daysOverdue = 0;
    const today = new Date("2026-04-15");
    const end = new Date(r.end_date);
    if (end < today) {
      daysOverdue = Math.ceil((today - end) / (1000 * 60 * 60 * 24));
    } else if (r.review_requested_date) {
      const req = new Date(r.review_requested_date);
      daysOverdue = Math.ceil((today - req) / (1000 * 60 * 60 * 24));
    }

    const card = document.createElement('div');
    card.className = `queue-card sev-${r.computed_severity}`;
    card.innerHTML = `
      <div class="queue-card-header">
        <span class="qid">${r.exception_id}</span>
        <span class="badge badge-${r.computed_severity}">${r.computed_severity}</span>
      </div>
      <div class="queue-card-body">
        <div class="q-meta-item"><span>Type</span><strong>${r.type.replace(/_/g, ' ')}</strong></div>
        <div class="q-meta-item"><span>Dept</span><strong>${r.department}</strong></div>
        <div class="q-meta-item"><span>Overdue</span><strong class="critical-text">${daysOverdue} Days Overdue</strong></div>
        <div class="q-meta-item"><span>Risk Score</span><strong class="score-text">${r.computed_risk_score}</strong></div>
      </div>
      <div class="queue-card-action">
        <span>Remediation Action</span>
        <strong>${r.recommendation}</strong>
      </div>
    `;
    card.addEventListener('click', () => openModal(r));
    container.appendChild(card);
  });
}

function renderAuditFindings(summary) {
  const findings = summary.audit_findings || {};
  const container = document.getElementById('audit-findings');
  container.innerHTML = `
    <div class="audit-finding-card">
      <div class="af-label">Expired active</div>
      <div class="af-value critical">${findings.expired_active || 0}</div>
      <div class="af-note">Active exceptions past expiry</div>
    </div>
    <div class="audit-finding-card">
      <div class="af-label">Stalled reviews</div>
      <div class="af-value high">${findings.stalled_reviews || 0}</div>
      <div class="af-note">Pending review requests overdue</div>
    </div>
    <div class="audit-finding-card">
      <div class="af-label">Critical active</div>
      <div class="af-value critical">${findings.critical_active || 0}</div>
      <div class="af-note">Active exceptions scoring Critical</div>
    </div>
    <div class="audit-finding-card">
      <div class="af-label">Missing approvals</div>
      <div class="af-value medium">${findings.missing_approvals || 0}</div>
      <div class="af-note">Active exceptions without an approver</div>
    </div>
  `;
}

function renderRiskConcentration(summary) {
  const container = document.getElementById('risk-concentration');
  const sections = [
    { title: 'Top Risk Departments', items: summary.top_risk_departments || [] },
    { title: 'Top Risk Requesters', items: summary.top_risk_requesters || [] },
    { title: 'Top Risk Approvers', items: summary.top_risk_approvers || [] },
  ];

  let maxScore = 0;
  sections.forEach(s => {
    s.items.forEach(item => {
      if (item.cumulative_score > maxScore) maxScore = item.cumulative_score;
    });
  });

  container.innerHTML = sections.map((section) => `
    <div class="concentration-card">
      <div class="concentration-title">${section.title}</div>
      <div class="leaderboard">
        ${section.items.map(item => {
          const pct = maxScore ? (item.cumulative_score / maxScore) * 100 : 0;
          return `
            <div class="leaderboard-item">
              <div class="leaderboard-meta">
                <span class="leaderboard-name">${item.name}</span>
                <span class="leaderboard-score">${item.cumulative_score}</span>
              </div>
              <div class="leaderboard-bar-wrap">
                <div class="leaderboard-bar" style="width: ${pct}%; background: var(--accent-gold);"></div>
              </div>
              <div class="leaderboard-details">
                <span>Critical: <strong>${item.critical_count}</strong></span>
                <span>High: <strong>${item.high_count}</strong></span>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </div>
  `).join('');
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
  select.innerHTML = '<option value="">All statuses</option>';
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

  let list = ALL_EXCEPTIONS;
  if (ACTIVE_EVOLUTION_BUCKET) {
    list = getBucketExceptions(ACTIVE_EVOLUTION_BUCKET, ALL_EXCEPTIONS);
  }

  return list.filter((r) => {
    if (AUDIT_MODE && !filterAuditFindings(r)) return false;
    if (statusFilter && r.status !== statusFilter) return false;
    if (severityFilter && (r.computed_severity || r.primary_severity) !== severityFilter) return false;
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
      va = SEV_RANK[a.computed_severity] ?? 0;
      vb = SEV_RANK[b.computed_severity] ?? 0;
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
      <td><span class="badge badge-${r.computed_severity || r.primary_severity}">${r.computed_severity || r.primary_severity}</span></td>
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
  
  const stepsHTML = Array.isArray(r.lifecycle_timeline) && r.lifecycle_timeline.length ? r.lifecycle_timeline.map((item, index) => {
    const isLast = index === r.lifecycle_timeline.length - 1;
    return `
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-dot"></div>
          ${!isLast ? '<div class="step-line"></div>' : ''}
        </div>
        <div class="step-content">
          <span class="step-title">${item.title}</span>
          <span class="step-date">${item.date}</span>
        </div>
      </div>
    `;
  }).join('') : '<p style="color:var(--text-faint)">No timeline data.</p>';

  content.innerHTML = `
    <div class="modal-header-block">
      <span class="modal-title-id">${r.exception_id}</span>
      <span class="badge badge-${r.computed_severity || r.primary_severity}">${r.computed_severity || r.primary_severity}</span>
    </div>
    
    <div class="modal-body-grid">
      <!-- Left Column: Summary and Lifecycle -->
      <div class="modal-left-col">
        <div class="modal-section-card">
          <h4 class="section-title">Exception Summary</h4>
          <div class="summary-details">
            <div class="detail-row"><span>Type</span><strong>${r.type.replace(/_/g, ' ').toUpperCase()}</strong></div>
            <div class="detail-row"><span>Requester</span><strong>${r.requester}</strong></div>
            <div class="detail-row"><span>Approver</span><strong>${r.approver || '—'}</strong></div>
            <div class="detail-row"><span>Department</span><strong>${r.department}</strong></div>
            <div class="detail-row"><span>Justification</span><p class="justification-text">${r.justification || 'No justification provided.'}</p></div>
          </div>
        </div>

        <div class="modal-section-card">
          <h4 class="section-title">Lifecycle Timeline</h4>
          <div class="timeline-flow">
            ${stepsHTML}
          </div>
        </div>
      </div>

      <!-- Right Column: Risk Score, Severity, Drivers, Recommendation -->
      <div class="modal-right-col">
        <div class="modal-section-card score-card">
          <h4 class="section-title">Computed Risk Engine</h4>
          <div class="modal-score-wrap">
            <span class="modal-score-val">${r.computed_risk_score ?? 0}</span>
            <span class="modal-score-den">/100</span>
          </div>
          <span class="modal-severity-label">${r.computed_severity || 'LOW'} SEVERITY</span>
        </div>

        <div class="modal-section-card">
          <h4 class="section-title">Risk Drivers</h4>
          <div class="drivers-checkmark-list">
            ${Array.isArray(r.risk_breakdown) && r.risk_breakdown.length ? r.risk_breakdown.map(item => `
              <div class="driver-check-item">
                <span class="check-icon">*</span>
                <span class="driver-label-text">${item.label}</span>
                <span class="driver-weight-badge">+${item.weight}</span>
              </div>
            `).join('') : '<div class="driver-check-item">No risk drivers.</div>'}
          </div>
        </div>

        <div class="modal-recommendation-card">
          <span class="rec-title">RECOMMENDED ACTION</span>
          <p class="rec-action-text">${r.recommendation}</p>
        </div>
      </div>
    </div>
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
  renderExecutiveAlert(summary);
  renderExecutiveKPIs(summary);
  renderRecommendedActions(summary.recommended_actions || []);
  renderRiskEvolution(summary);
  renderRiskConcentration(summary);
  renderPriorityQueue(exceptions);
  renderAuditFindings(summary);
  renderReadiness(readiness);
  populateStatusFilter(exceptions);
  renderTable();
  setupSortHeaders();

  document.getElementById('search-box').addEventListener('input', renderTable);
  document.getElementById('filter-status').addEventListener('change', renderTable);
  document.getElementById('filter-severity').addEventListener('change', renderTable);
  document.getElementById('filter-flagged-only').addEventListener('change', renderTable);
  
  document.getElementById('btn-reset-filter').addEventListener('click', resetEvolutionBucket);

  document.getElementById('btn-view-all-critical').addEventListener('click', () => {
    document.getElementById('filter-severity').value = 'CRITICAL';
    renderTable();
    document.getElementById('ledger-panel').scrollIntoView({ behavior: 'smooth' });
  });

  document.getElementById('audit-mode-toggle').addEventListener('click', () => {
    AUDIT_MODE = !AUDIT_MODE;
    const btn = document.getElementById('audit-mode-toggle');
    btn.classList.toggle('active', AUDIT_MODE);
    btn.textContent = AUDIT_MODE ? 'Audit mode: ON' : 'Audit mode';
    
    const banner = document.getElementById('audit-banner');
    if (AUDIT_MODE) {
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
    renderTable();
  });

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

  document.getElementById('methodology-toggle').addEventListener('click', () => {
    const content = document.getElementById('methodology-content');
    const icon = document.querySelector('.methodology-toggle .toggle-icon');
    const isHidden = content.classList.contains('hidden');
    if (isHidden) {
      content.classList.remove('hidden');
      icon.textContent = '▲';
    } else {
      content.classList.add('hidden');
      icon.textContent = '▼';
    }
  });
}

init();
