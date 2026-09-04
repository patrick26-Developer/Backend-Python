"""Contrats d'API (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class PollCreate(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=10)
    closes_at: datetime | None = None
    hide_results_until_closed: bool = False

    @field_validator("question")
    @classmethod
    def _q_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question vide")
        return v

    @field_validator("options")
    @classmethod
    def _options_clean(cls, options: list[str]) -> list[str]:
        cleaned = [o.strip() for o in options]
        if any(not o for o in cleaned):
            raise ValueError("une option est vide")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("options en double")
        return cleaned

    @field_validator("closes_at")
    @classmethod
    def _closes_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("closes_at doit porter un fuseau (UTC)")
        return v

    @model_validator(mode="after")
    def _closes_in_future(self) -> PollCreate:
        if self.closes_at is not None:
            from datetime import UTC

            if self.closes_at <= datetime.now(UTC):
                raise ValueError("closes_at doit être dans le futur")
        return self


class OptionRead(BaseModel):
    id: int
    label: str


class PollRead(BaseModel):
    id: int
    question: str
    options: list[OptionRead]
    total_votes: int
    closes_at: datetime | None
    is_closed: bool


class VoteCreate(BaseModel):
    option_id: int


class OptionResult(BaseModel):
    option_id: int
    label: str
    count: int
    percent: float


class PollResults(BaseModel):
    poll_id: int
    total_votes: int
    results: list[OptionResult]
