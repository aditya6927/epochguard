import asyncio
from decimal import Decimal
import os
from pathlib import Path
import re

from pydantic import Field, model_validator
from .schema import Strict


class Settings(Strict):
    model: str = Field(pattern=r"^gemini-[a-z0-9][a-z0-9.-]{0,95}$")
    max_requests: int = Field(ge=1, le=50)
    max_output_tokens: int = Field(default=1536, ge=512, le=4096)
    search_seconds: float = Field(default=8.0, ge=0.1, le=15, allow_inf_nan=False)
    model_seconds: float = Field(default=25.0, ge=0.1, le=35, allow_inf_nan=False)
    input_usd_per_million: float = Field(ge=0, le=1000, allow_inf_nan=False)
    output_usd_per_million: float = Field(ge=0, le=1000, allow_inf_nan=False)
    search_request_usd: float = Field(ge=0, le=5, allow_inf_nan=False)
    max_request_usd: float = Field(gt=0, le=5, allow_inf_nan=False)
    max_run_usd: float = Field(gt=0, le=25, allow_inf_nan=False)

    @model_validator(mode="after")
    def deadlines(self):
        if self.search_seconds + self.model_seconds > 40:
            raise ValueError("deadline hierarchy")
        return self


def offline_settings():
    return Settings(model="gemini-offline-fixture", max_requests=50,
        input_usd_per_million=0.0, output_usd_per_million=0.0, search_request_usd=0.0,
        max_request_usd=1.0, max_run_usd=1.0)


class Failure(Exception):
    """Fixed reason codes only; never provider or input-bearing exception text."""


class Budget:
    def __init__(self, settings):
        self.settings, self.requests, self.reserved = settings, 0, Decimal(0)
        self.lock = asyncio.Lock()

    async def admit(self):
        s = self.settings
        # Maximum serialized text/schema envelope is separately bounded below.
        # Bytes-as-tokens plus output ceiling is a planning reservation, not billing.
        cost = (Decimal(131072)*Decimal(str(s.input_usd_per_million)) +
                Decimal(s.max_output_tokens)*Decimal(str(s.output_usd_per_million)))/Decimal(1_000_000)
        cost += Decimal(str(s.search_request_usd))
        async with self.lock:
            if self.requests >= s.max_requests or cost > Decimal(str(s.max_request_usd)) or self.reserved+cost > Decimal(str(s.max_run_usd)):
                raise Failure("BUDGET_EXHAUSTED")
            self.requests += 1
            self.reserved += cost  # Retained even after failure, cancellation or no model call.


def require_live():
    if any(os.getenv(name) != "1" for name in ("EPOCHGUARD_005I_ALLOW_GEMINI", "EPOCHGUARD_005I_ALLOW_TAVILY")):
        raise ValueError("separate Gemini and Tavily authorization required")
    if any(os.getenv(name) for name in ("GEMINI_API_KEY", "TAVILY_API_KEY")):
        raise ValueError("runtime secret files required")


def repository_root():
    for path in Path(__file__).resolve().parents:
        if (path/"AGENTS.md").is_file() or (path/"services/verifier/requirements.lock").is_file():
            return path
    return Path("/app")


def private_file(value, root=None):
    path = Path(value).resolve(strict=True)
    if path.is_relative_to(root or repository_root()) or not path.is_file():
        raise ValueError("private file must be outside repository")
    return path


def read_key(value):
    try:
        path = private_file(value)
        with path.open("rb") as stream:
            raw = stream.read(259)
        key = raw.decode("ascii").rstrip("\r\n")
        if len(raw)>258 or not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", key):
            raise ValueError()
        return key
    except Exception:
        raise ValueError("invalid private credential file") from None
