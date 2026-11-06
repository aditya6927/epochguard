"""Trusted process configuration; no request field/header can select a budget."""

import os

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimeoutSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    tavily_api_seconds: float = Field(default=3.0, ge=1, le=59)
    retrieval_seconds: float = Field(default=4.0, gt=1, le=60)
    verification_seconds: float = Field(default=4.5, gt=1, le=65)

    @model_validator(mode="after")
    def ordered(self):
        if not self.tavily_api_seconds < self.retrieval_seconds < self.verification_seconds:
            raise ValueError("require Tavily API < retrieval < verification deadlines")
        return self

    @classmethod
    def from_environment(cls):
        profile = os.getenv("EPOCHGUARD_TIMEOUT_PROFILE", "offline")
        if profile not in {"offline", "live"}:
            raise ValueError("unknown trusted timeout profile")
        values = {} if profile == "offline" else {
            "tavily_api_seconds": 19.0, "retrieval_seconds": 20.0,
            "verification_seconds": 22.0,
        }
        for field, variable in {
            "tavily_api_seconds": "EPOCHGUARD_TAVILY_API_TIMEOUT_SECONDS",
            "retrieval_seconds": "EPOCHGUARD_RETRIEVAL_TIMEOUT_SECONDS",
            "verification_seconds": "EPOCHGUARD_VERIFICATION_TIMEOUT_SECONDS",
        }.items():
            if variable in os.environ:
                values[field] = os.environ[variable]
        return cls(**values)
