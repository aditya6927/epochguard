FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONPATH=/app:/app/claims
WORKDIR /app
COPY services/verifier/requirements.lock ./requirements.lock
COPY services/evidence_assessment/requirements-extra.lock ./requirements-extra.lock
RUN pip install --no-cache-dir -r requirements.lock -r requirements-extra.lock
COPY services/claim_analysis/claim_analysis/ ./claims/claim_analysis/
COPY services/evidence_assessment/evidence_assessment/ ./evidence_assessment/
COPY services/evidence_assessment/data/ ./data/
COPY services/evidence_assessment/tests/ ./assessment_tests/
RUN --network=none python -B -m pytest -p no:cacheprovider assessment_tests -q
USER 10001:10001
CMD ["python", "-m", "uvicorn", "evidence_assessment.app:app", "--factory", "--host", "0.0.0.0", "--port", "8791", "--workers", "1", "--no-access-log", "--no-proxy-headers", "--log-level", "critical", "--timeout-keep-alive", "5", "--backlog", "32"]
