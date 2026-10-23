'use strict';
const report = window.REPORT;
const labels = {implemented:'Implemented', partial:'Partial', planned:'Planned'};
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.querySelector('#test-count').textContent = report.tests;
document.querySelector('#trigger-count').textContent = report.triggersPerStation;
document.querySelector('#snapshot-date').textContent = 'Updated ' + report.snapshotDate;
document.querySelector('#updated-at').textContent = 'Last verified and updated: ' + report.snapshotDate;
document.querySelector('#migration-count').textContent = report.migration;
document.querySelector('#test-detail').textContent = `${report.tests} automated tests passed at the recorded checkpoint.`;
document.querySelector('#test-coverage').innerHTML = report.verification.map(t=>`<li>${escapeHTML(t)}</li>`).join('');
document.querySelector('#status-counts').innerHTML = Object.entries(labels).map(([key,label])=>`<span class="count"><b>${report.roadmap.filter(r=>r.status===key).length}</b> ${label}</span>`).join('');
document.querySelector('#history-items').innerHTML = report.history.map(item=>`<article class="timeline-item"><span class="timeline-icon" aria-hidden="true">${escapeHTML(item.icon)}</span><div><span class="timeline-date">${escapeHTML(item.phase)}</span><h3>${escapeHTML(item.title)}</h3><p>${escapeHTML(item.body)}</p></div></article>`).join('');
document.querySelector('#setup-items').innerHTML = report.setup.map(t=>`<li>${escapeHTML(t)}</li>`).join('');
document.querySelector('#next-items').innerHTML = report.next.map(t=>`<li>${escapeHTML(t)}</li>`).join('');
let filter = 'all';
function renderRoadmap() {
  const query = document.querySelector('#search').value.toLowerCase().trim();
  const entries = report.roadmap.filter(item=>(filter==='all'||item.status===filter) && [item.title,item.summary,item.remaining,...item.built].join(' ').toLowerCase().includes(query));
  document.querySelector('#roadmap-items').innerHTML = entries.map(item=>`<details class="roadmap-item" id="work-${escapeHTML(item.id)}"><summary><span class="roadmap-number">${String(item.priority).padStart(2,'0')}</span><div class="roadmap-title"><h3>${escapeHTML(item.title)}</h3><p>${escapeHTML(item.summary)}</p></div><span class="badge ${item.status}">${labels[item.status]}</span><span class="chevron" aria-hidden="true">⌄</span></summary><div class="roadmap-detail"><div><h4>Already built</h4><ul>${item.built.map(t=>`<li>${escapeHTML(t)}</li>`).join('')}</ul></div><div class="remaining-box"><h4>Limits / next step</h4><p>${escapeHTML(item.remaining)}</p></div></div></details>`).join('') || '<p class="no-results">No work items match this search. Try another feature or status.</p>';
  document.querySelector('#results-status').textContent = `${entries.length} roadmap items shown.`;
}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{
  filter=button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  renderRoadmap();
}));
document.querySelector('#search').addEventListener('input',renderRoadmap);
renderRoadmap();
const detailsBeforePrint = new Map();
window.addEventListener('beforeprint',()=>{
  document.querySelectorAll('.roadmap-item').forEach(d=>{detailsBeforePrint.set(d.id,d.open);d.open=true;});
});
window.addEventListener('afterprint',()=>{
  document.querySelectorAll('.roadmap-item').forEach(d=>{d.open=detailsBeforePrint.get(d.id)||false;});
  detailsBeforePrint.clear();
});
document.querySelector('#print-report').addEventListener('click',()=>window.print());
document.querySelector('#download-report').addEventListener('click',()=>{
  const parts=[`# ${report.title}`,`Updated: ${report.snapshotDate}`,`Published snapshot; not a live business-data connection.`,`${report.tests} tests passed at last verification. Migration ${report.migration}. ${report.triggersPerStation} date-lock triggers per station.`, '\n## Development roadmap'];
  report.roadmap.forEach(r=>parts.push(`\n### ${r.priority}. ${r.title} — ${labels[r.status]}`,r.summary,...r.built.map(b=>'- '+b),'Limits / next step: '+r.remaining));
  parts.push('\n## Work history',...report.history.flatMap(h=>['\n### '+h.phase+' — '+h.title,h.body]));
  parts.push('\n## Owner setup',...report.setup.map((s,i)=>`${i+1}. ${s}`),'\n## Remaining development',...report.next.map(s=>'- '+s));
  parts.push('\nThe pump software remains a local development prototype. Tax is disabled; owner-approved shift discounts are enabled. No live bank, HPCL or IndianOil integration is claimed.');
  const url=URL.createObjectURL(new Blob([parts.join('\n\n')],{type:'text/markdown;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='pandey-pump-project-report.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
const observer=new IntersectionObserver(entries=>{
  entries.forEach(entry=>{if(entry.isIntersecting){document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+entry.target.id));}});
},{rootMargin:'-10% 0px -65% 0px'});
document.querySelectorAll('main>section[id]').forEach(section=>observer.observe(section));
