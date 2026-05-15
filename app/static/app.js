async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function fmtTop(items) { return items && items.length ? `${items[0][0]} (${items[0][1]})` : '-'; }

async function loadStats() {
  const s = await api('/api/stats');
  document.querySelector('#total').textContent = s.total;
  document.querySelector('#avg').textContent = s.avg_score;
  document.querySelector('#topSoftware').textContent = fmtTop(s.top_software);
  document.querySelector('#topCategory').textContent = fmtTop(s.top_categories);
}

function renderOpp(o) {
  return `
    <article class="opp">
      <div class="opp-top">
        <div>
          <h3>${o.software}</h3>
          <span class="badge">${o.category}</span>
        </div>
        <div class="score"><strong>${o.disruption_score}</strong><span>score</span></div>
      </div>
      <p class="meta">${new Date(o.created_at).toLocaleString()}</p>
      <div class="grid">
        <div class="box"><b>Complaint</b>${o.complaint}</div>
        <div class="box"><b>Workflow</b>${o.actual_workflow}</div>
        <div class="box"><b>AI-native Replacement</b>${o.ai_native_replacement}</div>
        <div class="box"><b>Scores</b>Pricing ${o.pricing_pain_score} · Bloat ${o.feature_bloat_score} · SMB ${o.smb_overkill_score} · AI ${o.ai_compression_score}</div>
      </div>
      <p class="evidence">“${o.evidence}”</p>
    </article>`;
}

async function loadFeed() {
  const min = document.querySelector('#minScore').value;
  const data = await api(`/api/opportunities?min_score=${min}`);
  document.querySelector('#feed').innerHTML = data.length ? data.map(renderOpp).join('') : '<p class="hint">暂无数据，先导入一条评论或加载种子数据。</p>';
}

async function refresh() { await loadStats(); await loadFeed(); }

document.querySelector('#seedBtn').addEventListener('click', async () => { await api('/api/seed', {method: 'POST'}); await refresh(); });
document.querySelector('#analyzeBtn').addEventListener('click', async () => {
  const content = document.querySelector('#content').value;
  const platform = document.querySelector('#platform').value;
  const source_url = document.querySelector('#sourceUrl').value;
  await api('/api/ingest/text', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content, platform, source_url}) });
  document.querySelector('#content').value = '';
  await refresh();
});
document.querySelector('#minScore').addEventListener('change', loadFeed);
refresh();
