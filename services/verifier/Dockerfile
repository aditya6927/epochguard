FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY verifier/ ./verifier/
COPY tests/ ./tests/
COPY pytest.ini ./pytest.ini
RUN python -m pytest -q
USER 10001:10001
CMD ["python", "-m", "uvicorn", "verifier.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
