# 005F frozen synthetic comparison packet

`candidates.json` contains 24 manually specified input/label rows frozen before
gateway execution. The expected outcomes and source counts are input data; the
runner does not derive them from EpochGuard's grammar or observed verdicts.
Labels are agent-authored controlled expectations, not independently reviewed
human gold or measurements of real-world detection accuracy.

LF-normalized input-file SHA-256:
`00bc7980901364e475e7dbeeaedbd4118da8348af8f0e915d9925d936edbefa9`.
Loading altered data refuses execution. Policy observations are synthetic Python
`3.15.2` and requests `2.34.2`, supplied by the existing G simulated transports.
These are not claims about current releases. No production code imports labels.

The packet has six admitted supported answers, four older/mixed contradictions,
two correct unsupported paraphrases, four unsupported-neighbor answers, four
repeated-policy answers, three unavailable/malformed-evidence cases and one
missing-plugin control. Truth labels identify eight known unsafe, twelve correct
and four unknown/inconclusive cases. An unassessed future-release neighbor and
all three faulted-evidence cases stay unknown; matching a healthy fixture label
does not turn missing/malformed observations into supported evidence.

Five correct but policy-unsupported answers form the unnecessary-refusal
denominator: two paraphrases, a harmless courtesy and two same-value repeats.
“Unnecessary” describes retrospective content truth under these authored labels;
it does not mean the finite grammar made an enforcement error. Missing-plugin
refusal is necessary protection and is reported separately, even though its
candidate is labelled correct. Older versions, inconsistent policy assertions
and explicit false neighbors are unsafe by the fixture labels; rejecting an
unknown neighbor does not prove it false.

Each row declares the expected protected outcome and per-source invocation
counts. Those are compared with observations from real processes. Baseline A
is an actual **unprotected Bifrost gateway** with no EpochGuard plugin, sharing the
controlled provider with protected path B. Bifrost's built-in plugins are retained
on both paths; the loaded inventory must differ only by EpochGuard, with no cache.
Direct-provider HTTP delivery is not
measured. All rows, including source faults and missing-plugin controls, retain
identical candidate and request-body bytes across the matched pair.
