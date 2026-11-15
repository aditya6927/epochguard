export interface Scenario { id: string; label: string; description: string; candidate: string; expected_status: number }
export interface Policy { id: string; label: string; fixture_version: string; source: string }
export interface Info { scenarios: Scenario[]; policies: Policy[]; evidence_mode: 'fixture'; receipt_protocol: string; live_qualification: string }
export type Outcome = 'ALLOW' | 'REJECT' | 'UNAVAILABLE' | 'INGRESS_REFUSED' | 'PROVIDER_ERROR';
export interface Result { status: number; upstream_status: number | null; outcome: Outcome; boundary: string; content: string | null; error: string | null; exact_content_match: boolean; evidence_mode: 'fixture' }
export const outcomes: Record<Outcome, { title: string; explanation: string; tone: string }> = {
  ALLOW: { title: 'Approved content released', explanation: 'The protected ingress returned the exact submitted content after the required evidence and receipt checks.', tone: 'green' },
  REJECT: { title: 'Contradicted claim blocked', explanation: 'A validated older-version contradiction caused a terminal policy refusal. The candidate was not released.', tone: 'red' },
  UNAVAILABLE: { title: 'Verification unavailable', explanation: 'This response could not be authorized. Unsupported content or unavailable verification cannot become an approved answer.', tone: 'amber' },
  INGRESS_REFUSED: { title: 'Protected ingress refused', explanation: 'Ingress could not validate the protected response. This does not identify a specific internal failure or establish factual support.', tone: 'amber' },
  PROVIDER_ERROR: { title: 'Provider operation failed', explanation: 'A genuine upstream failure was preserved with safe error fields. This is an operation failure, not a factual verification verdict.', tone: 'violet' },
};

export async function verify(scenario: string, candidate: string, signal: AbortSignal): Promise<Result> {
  const response = await fetch('/api/demo/verify', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-EpochGuard-Lab': '1' }, body: JSON.stringify({ scenario, candidate }), cache: 'no-store', signal });
  const value = await response.json() as Result;
  if (value.status !== response.status || !Object.hasOwn(outcomes, value.outcome) || value.evidence_mode !== 'fixture' || !['policy','ingress','provider','infrastructure','lab','protected_ingress'].includes(value.boundary)) throw new Error('invalid-response');
  if (response.status === 200) {
    if (value.outcome !== 'ALLOW' || value.content !== candidate || value.exact_content_match !== true || value.error !== null) throw new Error('invalid-allow');
  } else if (value.outcome === 'ALLOW' || value.content !== null || typeof value.error !== 'string' || value.error.length > 256) throw new Error('invalid-refusal');
  return value;
}
