# Task 004F: AI-assisted natural-language claim coverage

Starting tree: clean `main` at `4b259e42d62c8ec80ddaa84c881c36ca5afbb284`.
This is an experimental analysis/evidence-planning subsystem, not an extension
of gateway ALLOW authority. **MODEL QUALITY QUALIFICATION PENDING.** No live
Gemini, Tavily or PyPI request was made. All annotations are agent-authored drafts;
there is no independent reviewer or fabricated agreement statistic.

## Design and invariants

The useful question is whether proposed assertions can be challenged independently
when their extraction is incomplete. Correct quotes and broad span coverage do
not establish semantic completeness. The new module keeps four separate concepts:
syntactic character coverage, risk-unit accounting, trusted local policy mapping,
and general semantic completeness (always NOT_PROVEN).

```text
original bounded text -> unchanged 004A ModelExtractor (optional Gemini)
                     -> exact unique-quote alignment + canonical validation
original bounded text -> independent risk scanner (no proposal input)
                     -> correspondence/classification/atomicity audit
                     -> closed, deterministic two-policy mappings
                     -> non-authorizing evidence plan
                     -> optional existing-policy comparisons on offline fixtures
                     -> PLAN_* / ANALYSIS_FAILED, authorization=false
```

Inspection covered AGENTS, README, architecture, the integration spike, Tasks
004A/004A-H/004B/C/D/E, 004A schema/model/alignment/baseline/Gemini/evaluation/
dataset/CLI and tests/reports, and the 004B grammar/pipeline/contracts/policies/
fixtures plus current Go contract validation. Existing interfaces are reused;
no Bifrost contract, gateway hook or new release mode is introduced.

All provider responses, model proposals, normalized propositions, retrieved text
and candidate instructions remain untrusted. Trusted code/configuration chooses
the extractor, budgets, mapper, source registry and clock. Model-provided hashes,
policy IDs or URLs are not accepted control fields. A normalized proposition is
retained as untrusted proposal metadata and never used to choose a comparison.

## Files and ownership

New files under `services/verifier/`:

| Paths | Responsibility |
| --- | --- |
| `verifier/prose/{schema,mapping,audit,pipeline}.py` | Frozen strict records, closed paraphrases, original-text risk units/correspondence and bounded orchestration |
| `verifier/prose/{dataset,evaluation,cli,__init__,__main__}.py` | Separate frozen dataset validation, safety metrics, stand-alone commands and opt-in diagnostics |
| `schema-004f.prose-plan.v1.json` | Exported strict result wire schema; local cross-field checks additionally recompute the audit |
| `tests_prose/{conftest,support,test_audit,test_resources_schema,test_evaluation_cli}.py` | Network-disabled model fixtures, omission/atomicity/classification/mapping/schema/resource/evaluation/CLI controls |
| `data/prose-v1/{dev.jsonl,heldout.jsonl,manifest.json,README.md}` | 66 draft cases, frozen split/source identities and independent review instructions |
| `examples/prose/{mapped.txt,omitted.txt,compound.txt,omitted.fake.json}` | Reproducible synthetic examples; deliberately partial fake extraction is not model-quality data |
| `reports/prose-v1/` | Four deterministic full JSON evaluation reports and their interpretation |

This report is new. Existing edits are limited to the verifier README,
claim-analysis README and architecture documentation. Existing implementation,
tests, datasets, reports, dependency locks, Dockerfiles, Compose/configuration,
Go code and 003A–004E behavior remain unchanged. No app imports the new prose
pipeline, and no public inference route can select it.

## Contract, identity and lifetimes

`004f.prose-plan.v1` / analysis policy `bounded-prose-audit-v1` binds a trusted
caller request ID, original candidate, full UTF-8 SHA-256 and reference date.
It records extractor identity/status, exact accepted proposals and their original
classification/normalization/qualifiers, independent risk spans, correspondences,
policy mappings, unaccounted/unsupported unit IDs, failure/resource metadata and
optional shadow observations. Offsets are Unicode code points, never byte offsets.

Records are frozen; collections are tuples. Request revalidation checks the hash,
date, UTF-8/control-character and existing 8,192-character/32,768-byte bounds.
Results rebind accepted 004A spans, enforce global quote uniqueness, recompute
risk units/mappings/status, and validate fixture shadow observations through
the existing 004B comparison contract. Strict JSON readers reject duplicates,
nonfinite values and invalid encodings; result input/output is capped at 256 KiB.
Unknown fields and attempts to serialize authorization=true or gateway ALLOW
are rejected. These are consistency checks, not authentication of an artifact.

Each Analyzer is shared per event loop, with immediate admission (default one,
trusted maximum four), no waiter queue, and no persistent candidate state.
Request work is bounded at 5s by default; the opt-in model CLI uses 60s total,
including the existing provider/extractor deadline and optional comparisons.
There are at most eight accepted proposals/mappings. The analysis-only risk limit
is 64: excess units are retained together in an explicit LIMIT_TAIL, never dropped
or treated as covered. CPU work is bounded by input/output sizes; asyncio deadlines
bound cooperative work, not arbitrary malicious synchronous Python code.

Cancellation propagates and releases admission in `finally`. Failed/ambiguous
model output is rejected as a whole, not silently repaired. Safe diagnostic
stage/code enums reuse 004A; raw envelopes, exceptions, paths and credentials are
not logged. Caller-owned result exports can include text, but default human CLI
output contains hashes, span indices, unit IDs and fixed classifications only.

## Independent audit rules

1. Derive sentence/line risk spans directly from original text, splitting at
   newlines and terminal `.?!;` followed by whitespace/end. Decimal version dots
   and `Python.org` do not split. Trim boundary whitespace only and retain every
   other character, including unknown delimiters and overflow tails.
2. Conservative context/format markers (quotes, code fences, brackets/parentheses,
   colons, Markdown prefixes, negation/modal/history/prediction/reported-speech
   cues) or any non-ASCII character make accounting ambiguous. Positions remain
   correct, but such text cannot gain a policy mapping by stripping its wrapper.
3. Compound connectors (`and`, `but`, `while`, `whereas`, `although`, `because`,
   `which`) or semicolons mark mixed units. The scanner does not claim general
   clause decomposition. A broad proposal or one overlapping predicate cannot
   discharge the whole unit.
4. Only exact closed mapped forms are KNOWN_FACT. A small predicate lexicon marks
   other potential facts as unsupported; everything else remains unrecognized.
   Absence of a lexical cue never exempts unknown text.
5. The entire nonfactual whitelist is `Hello.`, `Thanks.`, `Thank you.`. No general
   opinion, instruction, question, STABLE, HISTORICAL or NOT_REQUIRED exemption
   exists. A conflicting factual proposal about a whitelist unit stays uncertain.
6. A known unit needs exactly one proposal with identical start/end/source,
   FACTUAL/DYNAMIC/REQUIRED and no unresolved uncertainty (the old baseline's
   BASELINE_HEURISTIC marker is permitted). Partial, broad, missing, conflicting
   or uncertain proposals remain unaccounted. No classifications are rewritten.
7. PLAN_READY requires at least one mapped assertion, all units independently
   discharged by these rules, and no extraction failure. Unknown regions and
   failed decomposition prevent it. No-assertion inputs are not PLAN_READY.

BOUNDED_ACCOUNTED means this finite grammar/rule boundary was met, not general
semantic completeness. A claim spanning 100% of characters can still be unsafe;
the explicit syntactic count does not contribute to the decision. Context cues
are conservative heuristics, not a complete linguistic theory. Arbitrary prose,
anaphora, long-distance scope and multilingual interpretation remain unresolved.

## Exact policy paraphrases

Besides the two unchanged 004B exact sentences, the following full, case-sensitive
forms are recognized (`V` is a canonical policy-eligible numeric version):

```text
Python.org currently lists Python V as its latest stable Windows release.
Python.org lists Python V as its latest stable Windows release.
Python.org lists V as the latest stable Windows release.
Python.org lists Python V as its latest stable release for Windows.
PyPI reports requests version V.
The PyPI JSON API reports requests version V.
According to the PyPI JSON API, the version of requests is V.
```

Python retains `3.<0..99>.<0..999>`; PyPI retains three 0..999 components, without
leading zeros/suffixes. Internal wording, spacing, source, package, qualifiers and
punctuation are not normalized. Actual line breaks inside a form, Markdown,
quotations, negation, available/latest substitutions, safety/popularity claims,
different packages, multiple version alternatives, historical/future statements
and unrecognized paraphrases abstain. Versions here are illustrative, not current
source observations. Complete-response semantic equivalence outside this closed
boundary is not claimed.

## Evidence plans and fixture shadow checks

Each independently recognized unit retains its original span and a separately
named canonical comparison sentence/policy/version. The original candidate is
never rewritten into a gateway candidate. Optional shadow work accepts only the
existing concrete offline FixtureSource objects for the two fixed policy IDs;
real HTTP retrievers are rejected at configuration. The CLI creates only the
existing synthetic scenario with an explicit fixture clock. No source URL comes
from a proposal, and ordinary analysis has no Tavily/PyPI egress.

Shadow checks reuse unchanged `verify_claim`/004B result validation, including
mode, source, comparison, project and evidence rules. They are explicitly named
MAPPED_CLAIMS_SUPPORTED / MAPPED_CLAIM_CONTRADICTED / MAPPED_CLAIMS_INSUFFICIENT,
not whole-response verification. PLAN_READY can coexist with a contradicted or
unavailable shadow result because a ready plan is not a factual success. A
supported subset with an omitted neighbor remains PLAN_UNCERTAIN; no shadow
outcome overrides coverage. Every result keeps `authorization=false`.

## Reproduce offline

Use the existing pinned verifier dependencies; no new dependency is added:

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m verifier.prose analyze --engine baseline --text-file services/verifier/examples/prose/mapped.txt
& .venv-003a/Scripts/python.exe -m verifier.prose analyze --engine fake-model --text-file services/verifier/examples/prose/omitted.txt --fake-reply services/verifier/examples/prose/omitted.fake.json --shadow-fixtures
& .venv-003a/Scripts/python.exe -m verifier.prose analyze --engine baseline --text-file services/verifier/examples/prose/compound.txt --json
& .venv-003a/Scripts/python.exe -m verifier.prose evaluate --engine baseline --split dev --output artifacts/004f/baseline-dev.json
& .venv-003a/Scripts/python.exe -m verifier.prose evaluate --engine baseline --split heldout --output artifacts/004f/baseline-heldout.json
& .venv-003a/Scripts/python.exe -m verifier.prose evaluate --engine auditor --split dev --output artifacts/004f/auditor-dev.json
& .venv-003a/Scripts/python.exe -m verifier.prose evaluate --engine auditor --split heldout --output artifacts/004f/auditor-heldout.json
```

The omission example's fake output deliberately proposes only Python and requests,
omitting a vulnerability assertion. Observed output: two mapped COVERED_FACT
units, `unaccounted=u003`, `unsupported=u003`, PLAN_UNCERTAIN, and fixture-only
MAPPED_CLAIMS_SUPPORTED. The compound example stays unresolved even when a fake
proposal covers its entire text. These are plumbing/safety demonstrations, not
Gemini quality observations. JSON/evaluation exports are explicit text-containing
artifacts; do not send private candidates to logs or commit their exports.

## Dataset, evaluation and review

The separate [collection and review guide](../services/verifier/data/prose-v1/README.md)
has 66 cases, 33 dev/33 heldout, frozen IDs/source/file hashes and reference date
2026-11-14. All labels remain `draft`, reviewer=null. It includes both families,
omissions, multiple predicates, unsupported assertions, compounds, negation,
opinion/historical/future framing, instructions, repeated quotes, Markdown/code,
Unicode and no-checkable-assertion negatives. There are 38 adversarial cases and
23 cases with unsupported factual assertions. Input/claim/resource-limit and
invalid UTF-8 cases are additional focused tests. 004A data and its historical
fresh recall 0.232 are unchanged and are not a directly comparable benchmark.

The [four full offline reports](../services/verifier/reports/prose-v1/README.md)
retain every failure and all selected/source/dataset/implementation/prompt hashes.
Default timing/token/cost fields are null to make offline reports byte-reproducible;
`--measure` records actual analysis latency. No model-quality improvement is
inferred from fake providers. Current draft measurements:

| Method + independent audit | Split | Claim P/R/F1 | Exact P/R | Fresh P/R | Dynamic omitted / nonfresh | False complete | Unaccounted units | Failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Existing baseline | dev | .735/.893/.806 | .706/.857 | .704/.760 | 3/3 | 0/33 | 23 | 2 |
| Existing baseline | heldout | .686/.923/.787 | .629/.846 | .741/.870 | 2/1 | 0/33 | 21 | 0 |
| Independent auditor | dev | 1.000/.429/.600 | 1.000/.429 | 1.000/.480 | 13/0 | 0/33 | 29 | 1 |
| Independent auditor | heldout | 1.000/.500/.667 | 1.000/.500 | 1.000/.565 | 10/0 | 0/33 | 26 | 0 |

Baseline+audit returns PLAN_READY on 7/6 dev/held-out cases; auditor-only on 8/8.
There are 25 negative/ambiguous cases per split, all safely blocked or failed.
Correct semantic abstentions exclude extraction failures: baseline 23/25 dev and
25/25 heldout; auditor 24/25 dev and 25/25 heldout. All four reports have zero
unsupported/wrong policy-version mappings on these drafts. The individual
`false_complete_cases` arrays are empty; unsafe scoring controls deliberately
inject false completeness and wrong policy/version mappings and are detected.
An always-abstaining or failed extractor therefore cannot turn failure into
semantic coverage credit.

Claim matching reuses 004A's deterministic one-to-one greatest-IoU>=.5 rule;
exact metrics require exact spans. Fresh metrics, dynamic omissions/nonfresh
classifications, unsupported mappings, unaccounted units, correct abstentions and
extraction failure rates are separately reported. False completeness compares
the accounting claim against independently annotated spans, fresh classifications,
policy/version mappings and the expected bounded target. One broad span cannot
match several assertions. Extractor-only views have no coverage assertion and
report false-complete as null, rather than silently treating aligned spans as
proof of enumeration.

Visible failures: repeated identical text `eg004f-0035` fails both engines under
the global-unique rule; the baseline also fails code-fence case `eg004f-0041`
because its closing quote occurs inside the opening delimiter. The unchanged
baseline misses five dynamic assertions and labels four nonfresh/nonfactual across
both splits. The auditor misses 23 dynamic assertions: its policy grammar has
useful precision but intentionally poor broad recall. Zero observed false-complete
cases on 66 draft examples is not a semantic-completeness or reliability guarantee.

## Optional operator-run model diagnostic

No model run was authorized/executed here. The following is a separately selected
diagnostic, not default startup/testing. Use actual current model/rates supplied
by the operator; none are guessed. It reuses the unchanged 004A ModelExtractor,
identification schema and prompt `004a.prompt.v2`, sends the **entire original
prose**, and uses the existing Gemini provider without tools/search/retries.

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
$env:EPOCHGUARD_CLAIM_MODEL = Read-Host 'Trusted Gemini model identifier'
$env:EPOCHGUARD_CLAIM_INPUT_USD_PER_MILLION = Read-Host 'Current input USD per million tokens'
$env:EPOCHGUARD_CLAIM_OUTPUT_USD_PER_MILLION = Read-Host 'Current output USD per million tokens'
$env:EPOCHGUARD_CLAIM_MAX_REQUEST_USD = Read-Host 'Maximum planning reservation per call in USD'
$env:EPOCHGUARD_CLAIM_MAX_RUN_USD = Read-Host 'Maximum total planning reservation in USD'
$secureKey = Read-Host 'Gemini key' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
$env:EPOCHGUARD_ALLOW_MODEL_CALLS = '1'
$manifest = Get-Content services/verifier/data/prose-v1/manifest.json -Raw | ConvertFrom-Json
$selected = $manifest.diagnostic_case_ids -join ','
try {
    & .venv-003a/Scripts/python.exe -m verifier.prose evaluate --engine gemini --split dev --case-ids $selected --max-requests 10 --output artifacts/004f/gemini-diagnostic.json
} finally {
    Remove-Item Env:GEMINI_API_KEY, Env:EPOCHGUARD_ALLOW_MODEL_CALLS -ErrorAction SilentlyContinue
    Remove-Variable secureKey -ErrorAction SilentlyContinue
}
```

The frozen initial set is ten dev IDs (0001,0003,...,0019), covering both policies,
an omission and a compound. The runner refuses implicit full-dataset paid runs,
missing selections, more than ten selected cases, insufficient maximum calls,
missing opt-in/model/key/rates or invalid budgets. Calls run sequentially; failed
or cancelled attempts retain their reservation and have no retry. Estimates are
planning bounds at operator rates, not billing guarantees. Usage from a returned
ModelReply is retained even when later alignment/schema validation fails; unknown
usage is null. Empty input/budget-denied operations do not duplicate prior usage.

Reports record IDs, model/settings, source/dataset/prompt/schema hashes, validated
proposals, alignment result, audit/status, sanitized stage/code, attempted calls,
reserved cost, actual latency and reported token/estimated-cost subsets. A
successful HTTP response alone is not correct extraction. Even a diagnostic
against reviewed labels would not establish broad model suitability. Follow the
independent review procedure and `--require-human-reviewed` gate before making
human-reviewed quality claims. **MODEL QUALITY QUALIFICATION PENDING**.

## Executed checks and remaining boundary

Executed host commands:

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_prose -q
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_multiclaim services/verifier/tests_gateway services/verifier/tests_live services/verifier/tests_prose -q
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q
```

The host combined run passed 273 tests at its execution checkpoint (then 72 new
tests). Later focused controls brought the new suite to 76, all passing in 1.16s.
The unchanged 004A suite passed 176 in 1.44s; legacy verifier passed 65 with one
live case deselected and the existing Starlette warning in 4.91s. Final validation
ran **all 518 Python tests together with networking disabled**, using the existing
local image solely for its pinned dependencies and the current tree mounted
read-only. Expanded against this repository's absolute path, the command was:

```powershell
$repoRoot = (Get-Location).Path
docker run --rm --network none --mount "type=bind,source=$repoRoot,target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004e python -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/claim_analysis/tests -q
```

Actual final result: **518 passed, 1 deselected, 1 existing warning in 13.28s**.
This comprises 76 new tests, 201 existing 004B/endpoint/004E tests, 176 existing
004A tests and 65 legacy tests. No credential was forwarded. The selected live
test is deselected, not a live pass. The local dependency image was
`sha256:7c2309a77977a48312f486e112bba66af2e6a686dd6f6a92a975e5b0d4bd574f`;
source was read from the workspace mount, not the image's older implementation.

All four exact evaluation commands above were executed, then independently
rerun into `artifacts/004f/reproduced/`: all four outputs were byte-identical to
the reports prepared for review. Every exported planning record revalidated,
all implementation/dataset provenance hashes matched, and all model attempts
remained zero. The schema snapshot matches the runtime schema. AST/JSON/JSONL,
format/whitespace/newline, scoped-file and secret-pattern checks passed, as did
`git diff --check`. Safe local evidence is retained under `artifacts/004f/`.
Documentation checks passed across 27 Markdown files: 160 local links including
10 anchors resolved, with balanced fences. The scoped inventory is 29 new files
and three existing documentation edits; no credentials or private runtime exports
were added. Evaluation exit 0 means a report was produced, not that extraction,
model quality or authorization succeeded.

Only three pre-existing documentation files changed; all other 212 pre-existing
files are byte-identical, including the original 004A schema/data/reports, all
gateway policies/contracts/apps/configurations, Go plugin/ingress and deployment
files. No Go or gateway shared runtime code changed; Go unit/race and real
gateway/ingress qualification suites were therefore not rerun for this standalone
Python experiment. No new route, cache, hook or release behavior is qualified.
Live model/source tests were not run; scripted adapters are not substituted for
paid quality evidence. No assertion was relaxed or failed case removed from the
evaluation.

General semantic completeness remains unproven. The closed grammar, simple risk
scanner, annotations and evaluator can all miss distinctions outside their stated
bounds. Models may omit, hallucinate, misclassify or choose ambiguous substrings;
the current response is abstention, not guessing. Future gateway integration
requires an explicit new Go-verifiable contract, independently justified coverage
and mapping policy, full response binding, adversarial cross-language tests and
real gateway/ingress qualification. It must not reuse PLAN_READY as ALLOW or
bypass the existing 004B/004D validators. Production source freshness, verifier-hop
authentication, streaming and protected caching remain separate work.

Recommended conventional commit, not created:
`feat(prose): add non-authorizing claim coverage and evidence planning`.

Stop for maintainer review. No commit or push. **MODEL QUALITY QUALIFICATION PENDING**.
