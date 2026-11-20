const editor = document.querySelector('#claim');
const run = document.querySelector('#run');
const result = document.querySelector('#result');
const progress = document.querySelector('#progress');
let generation = 0, active;
function reset() { generation++; active?.abort(); result.hidden = true; document.querySelector('#sources').replaceChildren(); progress.textContent = ''; run.disabled = false; }
editor.addEventListener('input', reset);
for (const [id, text] of [['stable', 'The chemical symbol for gold is Au.'], ['unclear', 'The number of unrecorded birds alive yesterday was exactly 99.']]) {
  document.querySelector('#'+id).addEventListener('click', () => { reset(); editor.value = text; });
}
function item(tag, text) { const node = document.createElement(tag); node.textContent = text; return node; }
fetch('/api/info', {cache:'no-store'}).then(r => r.json()).then(info => {
  if (info.mode !== 'experimental-evidence' || info.authorization !== false) throw new Error();
  document.querySelector('#mode').textContent = info.evidence_mode === 'simulated'
    ? 'SIMULATED search + simulated Gemini replies · frozen offline packet; unfamiliar statements have no simulated evidence.'
    : 'LIVE Tavily search + Gemini assessment · explicitly enabled, bounded provider calls.';
}).catch(() => { document.querySelector('#mode').textContent = 'Service unavailable.'; run.disabled = true; });
run.addEventListener('click', async () => {
  reset(); const ticket = generation, claim = editor.value;
  if (!claim.trim() || new TextEncoder().encode(claim).length > 2048) { progress.textContent = 'Enter a claim within the stated size limit.'; return; }
  const controller = new AbortController(); active = controller; run.disabled = true; progress.textContent = 'Retrieving evidence and assessing this statement…';
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch('/api/assess', {method:'POST', cache:'no-store', signal:controller.signal,
      headers:{'Content-Type':'application/json','X-EpochGuard-Explorer':'1'}, body:JSON.stringify({claim})});
    const value = await response.json();
    if (ticket !== generation) return;
    if (!response.ok || value.mode !== 'experimental-evidence' || value.authorization !== false || value.claim !== claim ||
      !['SUPPORTED','CONTRADICTED','INSUFFICIENT_EVIDENCE'].includes(value.assessment)) throw new Error();
    document.querySelector('#assessment').textContent = 'AI-assessed ' + value.assessment;
    document.querySelector('#explanation').textContent = value.explanation;
    document.querySelector('#uncertainty').replaceChildren(...value.uncertainty.map(text => item('li', text)));
    const sources = document.querySelector('#sources');
    for (const source of value.sources) {
      const url = new URL(source.url);
      if (url.protocol !== 'https:' || url.username || url.password) throw new Error();
      const article = document.createElement('article');
      const link = item('a', `${source.id}${value.citation_ids.includes(source.id) ? ' · cited' : ''} · ${source.title}`);
      link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      article.append(link, item('p', source.snippet), item('small', `${url.hostname} · Retrieved ${source.retrieved_at} · Publication ${source.published_at ?? 'unknown'} (unverified search metadata)`));
      sources.append(article);
    }
    progress.textContent = `${value.evidence_mode === 'simulated' ? 'SIMULATED' : 'LIVE'} · ${value.reason_code}`;
    result.hidden = false;
  } catch { if (ticket === generation) { result.hidden = true; progress.textContent = 'No assessment is available. No gateway authorization was issued.'; } }
  finally { clearTimeout(timer); if (ticket === generation) run.disabled = false; }
});
