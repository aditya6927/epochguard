"""Bounded escaped static HTML; no scripts, remote assets or source fetches."""
from html import escape
from .contract import Report

LABELS = {"SUPPORTED": "Supported by the observed source", "CONTRADICTED": "Contradicted by the observed source",
          "INSUFFICIENT": "Insufficient evidence"}


def render(report):
    report = Report.model_validate(report.model_dump(warnings=False))
    def safe(value):
        return escape("not_recorded" if value is None else str(value), quote=True)
    rows = []
    for claim in report.claims:
        values = (claim.claim_id, claim.policy_id, LABELS[claim.verdict], claim.freshness_score,
                  claim.score_reason, claim.evidence_mode, claim.source_id, claim.source_url,
                  claim.observed_version, claim.observed_at, claim.evaluated_at, claim.observation_age_ms,
                  claim.observation_time_status, claim.evidence_digest)
        rows.append("<tr>" + "".join("<td>"+safe(v)+"</td>" for v in values) + "</tr>")
    if not rows:
        label = "Unsupported claim language; no partial claim mapping is admitted." if report.report_reason == "UNSUPPORTED_LANGUAGE" else "Claim details not recorded or reporting unavailable."
        rows.append('<tr><td colspan="14">'+label+'</td></tr>')
    headings = ("Claim", "Policy", "Recorded comparison", "Score", "Score reason", "Evidence mode",
                "Fixed source", "Validated source URL", "Observed version", "Observed at", "Evaluated at",
                "Observation age (ms)", "Time status", "Evidence digest")
    html = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><title>EpochGuard operator claim report</title>
<style>body{font:16px system-ui;background:#0c1320;color:#e0e7ef;margin:2rem}h1{color:#79debd}table{border-collapse:collapse;font-size:13px}td,th{padding:.6rem;border:1px solid #435064;text-align:left;overflow-wrap:anywhere}main{overflow-x:auto}code{overflow-wrap:anywhere}</style>
<h1>Operator claim report</h1><p>Diagnostic only. This is not a protected client response or proof of Go authorization.</p>
<p>100 = matched valid observation; 0 = bounded older-version contradiction; no score = a meaningful score was not established.
Fixture evidence is synthetic. Application observation time does not attest origin freshness. Historical scores are snapshots, not current verification.</p>'''
    html += "<p>Profile: <strong>"+safe(report.evidence_profile)+"</strong> | Basis: "+safe(report.basis)+" | Status: "+safe(report.report_status)+" | Reason: "+safe(report.report_reason)+"</p>"
    html += "<p>Generated at: "+safe(report.generated_at)+" | Evaluated at: "+safe(report.evaluated_at)+" | Candidate SHA-256: <code>"+safe(report.candidate_sha256)+"</code></p>"
    html += "<p>Origin publication/update time: unavailable. No score authorizes release.</p><main><table><thead><tr>"+"".join("<th>"+h+"</th>" for h in headings)+"</tr></thead><tbody>"+"".join(rows)+"</tbody></table></main></html>"
    if len(html.encode()) > 65536:
        raise ValueError("report bound")
    return html
