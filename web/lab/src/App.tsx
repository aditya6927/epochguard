import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { outcomes, verify } from './api';
import type { Info, Result } from './api';

function Shield({ small = false }: { small?: boolean }) {
  return <svg width={small ? 20 : 28} height={small ? 20 : 28} viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="M14 3 24 7v7c0 6-10 11-10 11S4 20 4 14V7L14 3Z" stroke="currentColor" strokeWidth="1.6"/><path d="m9 14 3 3 7-7" stroke="currentColor" strokeWidth="1.8"/></svg>;
}

export default function App() {
  const [info, setInfo] = useState<Info | null>(null);
  const [scenario, setScenario] = useState('supported');
  const [candidate, setCandidate] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [problem, setProblem] = useState('');
  const [tab, setTab] = useState<'response' | 'record'>('response');
  const [showGrammar, setShowGrammar] = useState(false);
  const active = useRef<AbortController | null>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/demo/info', { cache: 'no-store', signal: controller.signal }).then(r => { if (!r.ok) throw new Error(); return r.json(); }).then((v: Info) => {
      if (v.evidence_mode !== 'fixture' || v.scenarios.length !== 5) throw new Error();
      setInfo(v); setCandidate(v.scenarios[0].candidate);
    }).catch(() => { if (!controller.signal.aborted) setProblem('The Lab configuration is unavailable. Check the local stack and reload.'); });
    return () => { controller.abort(); active.current?.abort(); };
  }, []);
  const preset = info?.scenarios.find(s => s.id === scenario);
  const edited = !!preset && candidate !== preset.candidate;
  const characters = [...candidate].length;
  const bytes = new TextEncoder().encode(candidate).length;
  const validSize = characters > 0 && characters <= 8192 && bytes <= 32768;
  const display = result ? outcomes[result.outcome] : null;
  function reset() { setResult(null); setProblem(''); setLatency(null); }
  function select(id: string) {
    if (pending) return;
    const entry = info?.scenarios.find(s => s.id === id);
    if (entry) { setScenario(id); setCandidate(entry.candidate); reset(); }
  }
  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (pending || !validSize || !info) return;
    reset(); setPending(true); setTab('response');
    const controller = new AbortController(); active.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 12000);
    const started = performance.now();
    try {
      const target = edited && !['missing-plugin', 'provider-error'].includes(scenario) ? 'custom' : scenario;
      const value = await verify(target, candidate, controller.signal);
      setResult(value); setLatency(performance.now() - started);
    } catch {
      setProblem(controller.signal.aborted ? 'The protected request timed out. No approved answer is available. Check the local services before trying again.' : 'The protected response is unavailable or could not be safely displayed. No approved answer is available.');
      setLatency(performance.now() - started);
    } finally { clearTimeout(timer); setPending(false); active.current = null; }
  }
  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="/" aria-label="EpochGuard Verification Lab"><span className="brand-icon"><Shield /></span>EpochGuard<span className="brand-divider"/> <span className="brand-sub">Verification Lab</span></a><div className="environment"><span className="status-dot"/>LOCAL / OFFLINE<span className="version">bounded-prose-v1</span></div></header>
    <main>
      <section className="intro"><div><div className="eyebrow">PROTECTED GATEWAY WORKBENCH <span>005A</span></div><h1>Verify before <em>release.</em></h1><p>Edit a candidate. Send it through the real gateway.<br className="desktop-break"/> Inspect what the protected boundary actually lets through.</p></div><div className="scope-note"><Shield small/><div><strong>Real enforcement. Synthetic evidence.</strong><p>Bifrost + native Go plugin + Python verifier.<br/>{' '}Controlled provider; no model or live-source calls.</p></div></div></section>

      <section className="scenario-section" aria-labelledby="scenario-heading"><div className="section-label"><h2 id="scenario-heading">01 <span>Choose a starting point</span></h2><span>Expected statuses apply to unedited presets</span></div><div className="scenario-grid">{info?.scenarios.map((entry, i) => <button className={`scenario ${entry.id === scenario ? 'selected' : ''}`} key={entry.id} aria-pressed={entry.id === scenario} onClick={() => select(entry.id)} disabled={pending}><span className="scenario-top"><span className="scenario-index">0{i+1}</span><span className={`expected s${entry.expected_status}`}>{entry.expected_status}</span></span><strong>{entry.label}</strong><span className="scenario-description">{entry.description}</span></button>) ?? <div className="configuration-loading">Loading local configuration…</div>}</div></section>

      <div className="workbench">
        <section className="panel editor-panel" aria-labelledby="editor-heading"><div className="panel-heading"><h2 id="editor-heading"><span className="step">02</span> Candidate response</h2><span className="tiny-tag">{edited ? 'CUSTOM INPUT' : 'EDITABLE PRESET'}</span></div><div className="editor-description">This is your input, <strong>not an approved answer.</strong> The provider fixture returns it verbatim; EpochGuard evaluates that exact text.</div>
          <form onSubmit={submit}><label className="sr-only" htmlFor="candidate">Candidate response</label><div className="code-editor"><div className="editor-file"><span className="file-dot"/> candidate.txt <span>UTF-8</span></div><textarea id="candidate" ref={editor} value={candidate} disabled={pending || !info} maxLength={16384} spellCheck={false} autoCapitalize="off" autoCorrect="off" onChange={e => { setCandidate(e.target.value); reset(); }} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); void submit(); } }}/></div>
          <div className="editor-meta"><span className={!validSize && candidate ? 'invalid' : ''}>{characters.toLocaleString()} / 8,192 code points <span>·</span> {bytes.toLocaleString()} / 32,768 bytes</span><span>SP · TAB · CR · LF separators</span></div>
          {['missing-plugin', 'provider-error'].includes(scenario) && <p className="scenario-warning">{scenario === 'missing-plugin' ? 'This scenario selects only the fixed no-plugin gateway behind protected ingress.' : 'This scenario sends your text with the fixture’s system-role failure control. It tests an upstream error, not the truth of the text.'}</p>}
          <div className="submit-row"><span>Buffered delivery only <span className="keyboard">Ctrl ↵</span></span><button className="primary" type="submit" disabled={pending || !info || !validSize}>{pending ? <><span className="spinner"/> Awaiting protected response</> : <>Run verification <span aria-hidden="true">↗</span></>}</button></div></form>
          <button className="grammar-toggle" onClick={() => setShowGrammar(!showGrammar)} aria-expanded={showGrammar}> <span>{showGrammar ? '−' : '+'}</span> Supported language & limits</button>{showGrammar && <div className="grammar"><p>Exactly nine ASCII sentence forms; one to eight claims. Case, internal spacing and punctuation are exact. No extra prose, Markdown, greetings or safety claims.</p><code>Python.org currently lists Python V as its latest stable Windows release.<br/>PyPI reports requests version V.</code><p>Other Python forms: “Python.org lists Python V as its latest stable Windows release.”, “Python.org lists V as the latest stable Windows release.”, “Python.org lists Python V as its latest stable release for Windows.”, and “The latest stable Python 3 release for Windows listed on Python.org is V.”</p><p>Other requests forms: “The PyPI JSON API reports requests version V.”, “According to the PyPI JSON API, the version of requests is V.”, and “The version reported for requests by the PyPI JSON API is V.”</p><p>Python V: 3.minor.patch (minor 0–99, patch 0–999). Requests V: three components 0–999. No leading zeros or suffixes. Duplicate policy/version claims are refused. Unicode and unfamiliar text are sent to the real gate and cannot authorize release. All fixture versions are synthetic observations.</p></div>}
        </section>

        <section className={`panel result-panel ${display?.tone ?? ''}`} aria-labelledby="result-heading"><div className="panel-heading"><h2 id="result-heading"><span className="step">03</span> Protected response</h2><span className="tiny-tag">{pending ? 'PENDING' : result ? 'OBSERVED RESULT' : 'NO RESPONSE YET'}</span></div><div className="result-body" aria-live="polite" aria-busy={pending}>
          {pending ? <div className="empty-state"><span className="waiting-ring"><Shield /></span><h3>Holding the candidate</h3><p>Waiting for the buffered protected response.<br/>No answer is displayed while checks are pending.</p></div> : problem ? <div className="problem-state" role="alert"><span className="empty-symbol">!</span><h3>No approved answer available</h3><p>{problem}</p>{latency !== null && <span className="mono">{latency.toFixed(1)} ms · browser round trip</span>}</div> : result && display ? <>
            <div className="outcome-heading"><div className="outcome-badge">{result.outcome === 'ALLOW' ? '✓' : '⊘'}</div><div><div className="outcome-code">{result.outcome}<span>HTTP {result.status}</span></div><h3>{display.title}</h3></div></div><p className="outcome-explanation">{display.explanation}</p>
            <div className="measurements"><div><span>Browser round trip</span><strong>{latency?.toFixed(1)} <small>ms</small></strong></div><div><span>Reported boundary</span><strong className="boundary">{result.boundary.replaceAll('_', ' ')}</strong></div></div>
            <div className="inspector-tabs" role="tablist" aria-label="Result inspector"><button role="tab" aria-selected={tab === 'response'} onClick={() => setTab('response')}>Client response</button><button role="tab" aria-selected={tab === 'record'} onClick={() => setTab('record')}>Safe JSON record</button></div>
            {tab === 'response' ? <div className="response-content" role="tabpanel">{result.status === 200 && result.outcome === 'ALLOW' ? <><div className="release-label"><span className="status-dot"/>RELEASED ASSISTANT CONTENT<span>Exact match</span></div><pre data-testid="released-content">{result.content}</pre></> : <><div className="release-label blocked">NO CANDIDATE CONTENT RELEASED</div><p className="safe-error">{result.error}</p></>}</div> : <pre className="json-record" role="tabpanel">{JSON.stringify(result, null, 2)}</pre>}
            <div className="result-footnote">{result.upstream_status === null ? 'No completed protected-ingress HTTP response was observed.' : `Protected-ingress HTTP ${result.upstream_status}.`} No receipts, internal headers or provider metadata are exposed.</div>
          </> : <div className="empty-state"><span className="empty-symbol"><Shield /></span><h3>The boundary speaks last.</h3><p>Run a candidate to observe an actual HTTP outcome.<br/>This inspector never invents a verdict.</p><div className="empty-statuses"><span>200 allow</span><span>403 reject</span><span>503 unavailable</span></div></div>}
        </div></section>
      </div>

      <section className="pipeline panel" aria-labelledby="path-heading"><div className="panel-heading"><h2 id="path-heading">The release path</h2><span className="tiny-tag">CONCEPTUAL · NOT STAGE TELEMETRY</span></div><div className="pipeline-track">{[['01','Browser + Lab','Same-origin local entry'],['02','Protected ingress','Retain request · fresh nonce'],['03','Bifrost + Go plugin','Provider fixture · enforcement'],['04','Python verifier','Two fixed evidence policies'],['05','Protected release','v2 receipt · exact body binding']].map(([n,title,sub]) => <div className="pipeline-node" key={n}><span>{n}</span><strong>{title}</strong><small>{sub}</small></div>)}</div><div className="pipeline-note">Actual execution returns through Bifrost signing and independent ingress validation before the Lab receives it. Only the end-to-end browser latency above is measured.</div></section>

      <div className="bottom-grid"><section className="evidence-panel"><h2>Evidence for this session <span className="tiny-tag">SIMULATED</span></h2>{info?.policies.map(p => <div className="policy" key={p.id}><span className="policy-icon">{p.id.startsWith('python') ? 'Py' : '{ }'}</span><div><strong>{p.label}</strong><span>{p.id}</span></div><div className="fixture-version"><small>FIXTURE VERSION</small><strong>{p.fixture_version}</strong></div></div>)}<p>Fixed-source HTTP transports are simulated. Real parsers, Go validation and receipt enforcement run for every request. No external source is contacted.</p></section><section className="honesty-panel"><div className="eyebrow">SEPARATE QUALIFICATION RECORD</div><h2>Real sources. Narrow claims.</h2><p>{info?.live_qualification ?? 'A separately reviewed real-source qualification is recorded in the repository documentation.'}</p><p className="muted">This offline Lab does not replay a live observation, prove general prose completeness or attest origin freshness.</p></section></div>
      <footer><span>EpochGuard <span className="footer-separator">/</span> Verification Lab</span><span>Local only · no cache · no stored request history</span></footer>
    </main>
  </div>;
}
