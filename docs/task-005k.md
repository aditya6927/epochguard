# 005K — Documentation reconciliation and submission evidence

## Scope and inspected baseline

Documentation reconciliation date: November 20, 2026, Asia/Calcutta. Inspected baseline: `3e7041b90ceca589cf7e51c2071094cd1bf11608`. This follow-up records later evidence without changing the historical 005I/005J reports or any implementation, schema, test, policy, fixture, dataset, Docker configuration or provider setting.

`git ls-files -- '*.md' '*.txt'` enumerated **73 tracked files: 57 Markdown and 16 text files** at the baseline. The inventory covers root policies/guides, architecture/operations/security/compatibility/evaluation, ADRs, historical reviews/task reports, service/data/report guides, five analyzer demo texts, four historical analyzer result texts, requirements text and development/verifier fixture texts. All were included in UTF-8/status/credential-pattern review; fixture and historical measurement texts were preserved verbatim. The reviewed additions comprise this report and the operator's observation Markdown, bringing the Markdown/text review set to **59 Markdown + 16 text = 75 files**, plus two supplied screenshots. Git-based inventory and preservation records are retained under ignored `artifacts/005k/`.

## Confirmed corrections

| Area | Reconciliation |
| --- | --- |
| Repository license | CONTRIBUTING now agrees with the tracked Apache-2.0 LICENSE and third-party audit. Project licensing does not clear third-party binary/image, attribution or notice obligations |
| Historical review follow-ups | Current follow-up sections in reviews 002A and 002B now identify the tracked CI workflow and present license/security/contributor facilities. Original review findings and reviewed-revision test limitations remain unchanged |
| Hosted CI | Replaced current "first hosted run pending" wording with verified November 20 run/job metadata for the baseline; historical pending statements retain their original scope |
| Local application boundary | Lab: loopback 8787, actual protected gateway, controlled provider and simulated evidence. Explorer: separate loopback 8791, simulated by default, optionally real Tavily/Gemini; always `authorization=false`, no gateway receipt or release authority |
| Measurements | README presents the 005F/005H denominators and limitations prominently. Evaluation links the existing public 005F export instead of saying publication still requires an export |
| Explorer execution evidence | Current guides link the captured November 20 result below, rather than implying no successful live displayed response has been preserved. Original 005I/005J reports remain intact |
| Result retention | Explorer backend does not persist successful HTTP responses/history; page reload loses the displayed result. Export/persistence remains future work, with no implemented save button, endpoint or database |

## Established measurements and qualification boundaries

**005F:** 24 frozen authored synthetic cases, three repetitions, **72 matched gateway pairs / 144 measured requests**. At candidate level, eight unsafe ordinary-answer cases were delivered **8/8 by unprotected Bifrost versus 0/8 protected**; six admitted supported cases were delivered by both paths. Complete matched protected-minus-unprotected latency was p50 **2.989 ms**, p95 **5.661 ms**. This is an unprotected Bifrost baseline, not direct-provider delivery or isolated plugin overhead. Fixture labels are not real-world hallucination-detection accuracy. The ordinary-answer denominator is 20: eight unsafe, eleven correct (six delivered/five policy-unsupported refusals), one unknown; four evidence/ingress controls are separate. [Historical measurement report](task-005f.md) and [public per-pair export](evidence/005f-public.json).

Reading the existing public export confirmed 24 case records, three repetitions and 72 paired observations. Recomputing nearest-rank quantiles from its stored matched path differences gives **2.988780 / 5.661154 ms**, matching the published rounded values. This was a read-only consistency check, not a new benchmark execution or independent authentication of the original measurements.

**005H:** **90 actual protected-gateway cases across 21 isolated profiles**, producing **41 ALLOW, 8 REJECT, 32 UNAVAILABLE and 9 INGRESS_REFUSED**. Distinct controlled synthetic version pairs exercise the existing two policies/nine forms; identical candidate text can change outcome when only one evidence value changes. This is finite offline qualification, not a general live-source benchmark. [Original evidence matrix and limits](task-005h.md).

**005I/005J:** **19/19 frozen offline assessment cases**, with **16 simulated search / 11 simulated model invocations**. 005I records its 1,315-test Python selection; 005J separately records 133 focused tests and 1,352 Python regressions for safe diagnostic categories. These are historical tested revisions/selections, not runtime tests repeated during this reconciliation. Mock-provider success establishes plumbing, schema, binding and abstention behavior, not real-model accuracy. The later live evidence below is a separate operator-observed execution.

Narrow protected live qualifications remain distinct: November 15 real-source evidence with a controlled provider and November 19 real Gemini with simulated evidence. **The protected 005E combined real-model/real-source path remains unexecuted/unqualified.** The Explorer's separate unsigned assessment does not change that status or approve arbitrary prose through protected ingress.

## November 20, 2026 Explorer live observations

The operator supplied a later successful displayed assessment, superseding the earlier uncaptured-success account as the latest preserved evidence. The supplied files became available during reconciliation; both screenshots were visually inspected and the displayed-text transcript was read. They were preserved unchanged. This records real Tavily retrieval and real Gemini assessment **as operator-observed execution**, with application structural/corroboration acceptance, not independent verification of provider-level records.

| Displayed/operator-supplied field | Recorded observation |
| --- | --- |
| Original claim | `Trump is Japan's prime minister.` |
| Evidence mode | LIVE |
| Assessment | CONTRADICTED |
| Reason code | AI_EVIDENCE_ASSESSMENT |
| Authorization | `false` |
| Source retrieval timestamp | `2026-11-20T09:20:25.252633Z` (14:50:25.252633 IST) |
| Retrieved / cited | Five retrieved sources; three cited: S1 White House, S4 Kyodo News, S5 Prime Minister's Office of Japan |

The operator-transcribed model explanation reads:

> The provided sources contradict the claim, establishing that Donald Trump is the President of the United States and that Sanae Takaichi is the Prime Minister of Japan.

This is the model's displayed explanation at execution time, not a new independent factual determination by this documentation review. The source pages were not fetched again. The cited URLs below were supplied in the operator's task record; screenshots/transcript show the corresponding source titles/domains and citation markers, rather than independently authenticated full hrefs:

- S1: [White House photo gallery](https://www.whitehouse.gov/gallery/president-donald-j-trump-and-japanese-prime-minister-sanae-takaichi-deliver-remarks-in-the-the-state-dining-room).
- S4: [Kyodo News article](https://english.kyodonews.net/articles/-/92077).
- S5: [Prime Minister's Office of Japan summary](https://japan.kantei.go.jp/105/diplomatic/202611/1117us.html).

| Supplied artifact | Inspected contents and provenance limit |
| --- | --- |
| [Overview screenshot](evidence/005i-live/overview.png) | LIVE mode, original claim, non-authorizing label and AI_EVIDENCE_ASSESSMENT reason; no browser/network exchange or provider headers |
| [Assessment screenshot](evidence/005i-live/assessment.png) | CONTRADICTED outcome, explanation, uncertainty and first cited source; cropped view does not independently show the full five-source set |
| [Displayed-text transcript](evidence/005i-live/observation.md) | Five source entries, S1/S4/S5 citation markers, retrieval/publication metadata and `authorization=false`; a human-readable UI record, not raw JSON/provider response capture |

Artifact SHA-256 identities, recorded to identify the inspected bytes rather than authenticate the remote execution:

- `overview.png`: `988e571ce1b768d586310f8b47271072bc911dc5069c4632bc3d1c0b1b2d793d`.
- `assessment.png`: `fe3a751e15cbdf292975ab5e00d398abb334d2db374b89d2629d778edcd6763b`.
- `observation.md`: `880294579925d700d6ae2040006aa85957027aa85a0c0fe2f7aaabde6313327b`.

The operator also reports earlier success without a preserved response, subsequent timeout, and other incomplete-output attempts. No complete attempt inventory, matched failure logs, raw HTTP response, provider token usage, runtime image identity or settings snapshot was independently reviewed for this captured assessment. It is therefore **one captured successful example, not a known total success denominator**, accuracy benchmark, provider attestation or consistent live-availability result. The original INVALID_MODEL_OUTPUT cause is not retroactively resolved. 005J's safe failure diagnostics do not store successful bodies, and its output-token recommendation is not a measured explanation of these attempts.

Retrieval time is not publication time. The displayed publication values are unverified search metadata, and different publisher groups plus application checks do not independently prove source independence, freshness or semantic correctness. No gateway receipt or protected ALLOW was produced. The original screenshots/transcript retain the source material supplied by the operator; this summary avoids repeating their lengthy excerpts.

## Hosted CI verification

[Actions run 44689491455](https://github.com/aditya6927/epochguard/actions/runs/44689491455) was fetched through the GitHub connector together with job/step summaries. Verified fields: workflow **Offline checks**, push event on `main`, exact head SHA `3e7041b90ceca589cf7e51c2071094cd1bf11608`, status **completed**, conclusion **success**. Created `2026-11-20T06:40:43Z`; last updated `2026-11-20T06:45:48Z`. Go, Python, frontend and documentation jobs and their reported steps completed successfully.

The tracked [workflow](../.github/workflows/checks.yaml) and build definitions establish the scope: pinned Go format/vet/unit/race/plugin compilation; locked Python regressions; locked frontend TypeScript/build/component tests; documentation/link/anchor/path/pattern checks. Dependency installation can use network access; build-stage tests are network-disabled. CI does **not** run paid integrations, installed-browser end-to-end tests, full native gateway loading/lifecycle qualification or an authorized combined live run. Job metadata does not independently establish every log-level test count. This successful run applies to the stated baseline; 005K documentation edits have local documentation validation only.

## Documentation validation and preservation

Executed from the repository root:

```powershell
git status --short
git rev-parse HEAD
git ls-files -- '*.md' '*.txt'
py -3.12 scripts/check_docs.py
py -3.12 -m unittest discover -s scripts -p 'test_*.py'
git diff --check
git diff --stat
git status --short
```

Documentation validation covers local links, anchors, repository references, UTF-8, structure and credential/private-path patterns. The same pattern scan also covered all baseline tracked `.txt` files and the supplied observation record without printing matched sensitive text. External source URLs were not re-fetched; GitHub CI verification was read-only. The complete documentation diff and changed link targets were reviewed. Per-file fingerprints compare non-Markdown files and historical reports against the inspected baseline; supplied evidence is separately fingerprinted and preserved.

| Executed validation | Result |
| --- | --- |
| `py -3.12 scripts/check_docs.py` | Passed: **59 Markdown files, 408 local links, 72 anchor links, 47 repository paths** |
| `py -3.12 -m unittest discover -s scripts -p 'test_*.py'` | **2 passed** |
| `git diff --check` | Passed; only configured LF/CRLF conversion notices |
| Tracked Markdown/text and supplied-observation pattern scan | No credential/private-workstation-path pattern matches; this is not an exhaustive secret audit |
| Existing 005F public export consistency check | 24 cases, 72 pairs, matching nearest-rank p50/p95; no new requests |
| Preservation fingerprints and original-review section comparison | **387 non-Markdown files, 30 historical task reports and all three supplied live artifacts unchanged**; original 002A/002B findings/verdicts unchanged |

No Docker build, gateway qualification, model/source call, unrelated regression suite, deployment or provider-setting change was performed. Existing qualifications were not rerun or rewritten. All implementation, tests, schemas, policies, fixtures, datasets, configurations and 16 tracked text files remain unchanged. This is documentation reconciliation, not a production-readiness or newly qualified security claim.

## Changed-document inventory

| File | Reason |
| --- | --- |
| [README](../README.md) | Concise evaluation highlights, correct denominators, two local applications and current live-observation scope |
| [CONTRIBUTING](../CONTRIBUTING.md) | Apache-2.0 selection, separate third-party obligations, Explorer ownership and current CI reference |
| [Architecture](architecture.md) | Current Explorer evidence, both loopback ports, protected combined boundary and retention limits |
| [Evaluation](evaluation.md) | Verified CI, captured live follow-up, existing public 005F export and protected-only qualification table |
| [Security](security.md) | Explicit application separation and limits of UI evidence; no new authorization claim |
| [Operations](operations.md) | Two independent local stacks, live reliability caveats and absent persistence/export |
| [Compatibility](compatibility.md) | Scope combined-live nonqualification to the protected path |
| [Lab guide](verification-lab.md) | Clarify port/network wording and the separate non-authorizing Explorer |
| [Explorer guide](../services/evidence_assessment/README.md) | Dated live follow-up, evidence limits, successful response non-persistence and reload behavior |
| [002A review follow-up](review-002a.md) | Current CI/license/security/contributor facilities; original findings intact |
| [002B review follow-up](review-002b.md) | Additional confirmed stale no-CI statement; original verdict/findings intact |
| [Real-model qualification guide](real-model-qualification.md) | Distinguish protected combined qualification from the separate Explorer observation |
| This report | Dated evidence/provenance, checks, corrections and residual limits |

The three files under `docs/evidence/005i-live/` were supplied by the operator and reviewed, not authored or altered by this reconciliation. Historical task reports 005F through 005J, the public 005F measurement dataset, fixtures and third-party audit retain their existing contents.

## Remaining limits

The live example demonstrates one completed non-authorizing application result. General factual accuracy, publisher independence and reliable live availability remain unqualified; unsuccessful attempts lack a complete denominator and independently reviewed provider telemetry. The protected combined 005E path remains unqualified. Third-party binary/image redistribution and notice clearance remain separate from the selected Apache-2.0 project license. Public documentation checks cannot certify every technical statement, external link's availability or credential absence. Successful-response export/persistence is future work, not submission functionality.
