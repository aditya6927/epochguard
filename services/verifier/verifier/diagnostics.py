"""Bounded metadata only. Never pass exception text, payloads or evidence here."""

import logging
import json

LOGGER = logging.getLogger("epochguard.verifier")
EVENTS = frozenset({"verification_failure", "retrieval_failure"})
CATEGORIES = frozenset({
    "verification_unavailable", "verification_timeout", "request_failure",
    "candidate_binding", "unsupported_claim", "claim_ahead_of_source",
    "invalid_evidence", "ambiguous_evidence", "stale_observation",
    "retrieval_unavailable", "tavily_timeout", "tavily_request_failure",
    "tavily_http_unauthorized", "tavily_http_rate_limited",
    "tavily_http_server_error", "tavily_http_failure",
    "retrieval_credentials_unavailable",
})


def failure(event, category, status=None):
    # Accept metadata by exact value/type, never stringify unknown objects.
    event = event if type(event) is str and event in EVENTS else "verification_failure"
    category = category if type(category) is str and category in CATEGORIES else "verification_unavailable"
    metadata = {"event": event, "category": category}
    if type(status) is int and 100 <= status <= 599:
        metadata["http_status"] = status
    try:
        LOGGER.warning(json.dumps(metadata, sort_keys=True), extra=metadata)
    except Exception:
        # Logging handlers must not affect the existing policy result.
        pass
