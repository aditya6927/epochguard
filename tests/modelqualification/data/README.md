# 005C draft review packet

The versioned [packet](review-packet.v1.json) contains 18 newly authored synthetic responses, each with its exact text, reference date, proposed code-point spans, factuality, temporal and fresh-evidence labels, uncertainty reasons and proposed policy mapping. All annotations are **agent-authored drafts**. No independent human review or blind held-out evaluation is claimed. The [manifest](manifest.v1.json) fixes the packet hash before model execution; changing labels requires a new version and documented review provenance.

Cases were selected from the task's categories rather than model outputs: Python release, PyPI/API versions, implicit change, history, mixed factual/opinion text, compounds, unsupported propositions, price, leadership, unresolved references, injection, neighboring omissions, repeated identical quotes and Unicode/formatting. Synthetic versions `3.88.7` / `2.88.7` are fixture observations, never current release claims. Case 14 intentionally repeats a quote: canonical draft offsets can identify occurrences, but the existing model aligner must refuse an ambiguous quote. The compound case's atomicity and the treatment of formatting deserve particular independent review.

For review, read each original response in full and check proposed spans, negation/context, labels, uncertainty and policy scope against its reference date. Record actual reviewer identity only after independent review. Preserve this version and any prior results; reviewed revisions belong in a new packet. The original 004A and 004F held-out collections and historical reports are unchanged.

Run the separate evaluation without model access:

```powershell
& .venv-003a/Scripts/python.exe tests/modelqualification/analysis.py --output artifacts/005c/analysis-offline.json
```

`--require-human-reviewed` deliberately refuses this packet. Offline mode ignores model opt-ins and credentials. Both Gemini comparisons remain null until separately authorized real execution. Mock Gemini tests establish transport, validation and failure accounting only. See [the operator guide](../../../docs/real-model-qualification.md) for the bounded live diagnostic.
