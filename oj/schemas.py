from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(StrictModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=128)


class RoleUpdate(StrictModel):
    role: str

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"user", "admin", "banned"}:
            raise ValueError("role must be user, admin or banned")
        return value


class Sample(StrictModel):
    input: str
    output: str


class ProblemBody(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    input_description: str = Field(min_length=1)
    output_description: str = Field(min_length=1)
    samples: list[Sample] = Field(min_length=1)
    constraints: str = Field(min_length=1)
    testcases: list[Sample] = Field(min_length=1)
    hint: str = ""
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    # None means that the judge should fall back to the language, then the
    # system-wide default.  The public problem response still exposes 3/128
    # when no problem-specific value was configured.
    time_limit: float | None = Field(default=None, gt=0, le=60)
    memory_limit: int | None = Field(default=None, ge=16, le=2048)
    author: str = ""
    difficulty: str = ""

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        cleaned = [tag.strip() for tag in tags if tag.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("tags must be unique")
        return cleaned


class VisibilityBody(StrictModel):
    public_cases: bool = False


class LanguageBody(StrictModel):
    name: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_+-]*$")
    file_ext: str = Field(min_length=2, max_length=16, pattern=r"^\.[A-Za-z0-9]+$")
    compile_cmd: str | None = None
    run_cmd: str = Field(min_length=1, max_length=500)
    time_limit: float | None = Field(default=None, gt=0, le=60)
    memory_limit: int | None = Field(default=None, ge=16, le=2048)


class SubmissionBody(StrictModel):
    problem_id: str = Field(min_length=1, max_length=80)
    language: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=200_000)


class AIConfigBody(StrictModel):
    provider_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=1, max_length=500)
    input_price: float = Field(default=0.0, ge=0)
    output_price: float = Field(default=0.0, ge=0)
    price_unit: int = Field(default=1_000_000, gt=0)

    @field_validator("provider_url")
    @classmethod
    def valid_provider_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "provider_url must be an http(s) base URL without credentials, query or fragment"
            )
        return value.rstrip("/")


TestStrategy = Literal[
    "basic",
    "normal",
    "boundary",
    "performance",
    "corner",
    "overflow",
    "adversarial",
    "randomized",
]


def default_test_strategies() -> list[TestStrategy]:
    return ["basic", "normal", "boundary", "corner"]


class AITestPlan(StrictModel):
    strategies: list[TestStrategy] = Field(
        default_factory=default_test_strategies, min_length=1, max_length=8
    )
    target_count: int = Field(default=10, ge=1, le=50)
    case_counts: dict[TestStrategy, int] = Field(default_factory=dict)
    preserve_existing: bool = True
    custom_requirements: str = Field(default="", max_length=3000)

    @field_validator("strategies")
    @classmethod
    def unique_strategies(cls, strategies: list[TestStrategy]) -> list[TestStrategy]:
        if len(strategies) != len(set(strategies)):
            raise ValueError("test strategies must be unique")
        return strategies

    @field_validator("case_counts")
    @classmethod
    def valid_case_counts(cls, counts: dict[TestStrategy, int]) -> dict[TestStrategy, int]:
        if any(count < 1 or count > 20 for count in counts.values()):
            raise ValueError("each test strategy count must be between 1 and 20")
        if sum(counts.values()) > 50:
            raise ValueError("total test strategy count must not exceed 50")
        return counts


class AITaskBody(StrictModel):
    requirement: str = Field(min_length=10, max_length=10_000)
    problem_id: str | None = Field(default=None, max_length=80)
    test_plan: AITestPlan = Field(default_factory=AITestPlan)


class AIIterationBody(StrictModel):
    feedback: str = Field(min_length=3, max_length=5000)
    test_plan: AITestPlan | None = None


class AITestRefinementBody(StrictModel):
    test_plan: AITestPlan


class LuoguTaskBody(StrictModel):
    problem_id: str = Field(min_length=1, max_length=20)
    mode: Literal["similar", "extension"] = "similar"
    additional_requirement: str = Field(default="", max_length=3000)
    test_plan: AITestPlan = Field(default_factory=AITestPlan)

    @field_validator("problem_id")
    @classmethod
    def valid_problem_id(cls, value: str) -> str:
        from oj.luogu import normalize_luogu_problem_id

        return normalize_luogu_problem_id(value)
