from __future__ import annotations

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
    time_limit: float = Field(default=3.0, gt=0, le=60)
    memory_limit: int = Field(default=128, ge=16, le=2048)
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
    time_limit: float = Field(default=3.0, gt=0, le=60)
    memory_limit: int = Field(default=128, ge=16, le=2048)


class SubmissionBody(StrictModel):
    problem_id: str = Field(min_length=1, max_length=80)
    language: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=200_000)
