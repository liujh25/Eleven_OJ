from __future__ import annotations

import shutil
import sys

import pytest

from oj.evaluator import (
    effective_limits,
    evaluate,
    normalize_output,
    parse_command,
    validate_language_commands,
)
from oj.models import Language, Problem


def make_problem(time_limit: float = 0.5) -> Problem:
    return Problem(
        id="sum",
        title="sum",
        description="sum",
        input_description="two ints",
        output_description="sum",
        samples=[{"input": "1 2\n", "output": "3\n"}],
        constraints="small",
        testcases=[{"input": "1 2\n", "output": "3\n"}],
        time_limit=time_limit,
        memory_limit=128,
    )


def python_language() -> Language:
    return Language(
        name="python-test",
        file_ext=".py",
        compile_cmd=None,
        run_cmd=f'"{sys.executable}" {{src}}',
        time_limit=1,
        memory_limit=128,
    )


def test_command_validation_and_normalization(tmp_path):
    assert normalize_output("3  \r\n\r\n") == "3"
    args = parse_command("python {src}", tmp_path / "a.py", tmp_path / "a")
    assert args[0] == "python"
    with pytest.raises(ValueError):
        parse_command("python {src}; rm -rf /", tmp_path / "a.py", tmp_path / "a")
    with pytest.raises(ValueError):
        validate_language_commands(None, "python -c print(1)")


def test_effective_limits_resolve_each_field_independently():
    problem = make_problem()
    language = python_language()
    problem.time_limit = 0
    problem.memory_limit = 64
    language.time_limit = 2
    language.memory_limit = 256
    assert effective_limits(problem, language) == (2, 64)

    problem.memory_limit = 0
    assert effective_limits(problem, language) == (2, 256)

    language.time_limit = 0
    language.memory_limit = 0
    assert effective_limits(problem, language) == (3.0, 128)


@pytest.mark.parametrize(
    ("code", "verdict"),
    [
        ("a,b=map(int,input().split());print(a+b)", "AC"),
        ("print(4)", "WA"),
        ("raise RuntimeError('x')", "RE"),
        ("while True: pass", "TLE"),
    ],
)
async def test_python_verdicts(code, verdict):
    # Interpreter startup is slower on loaded Windows CI hosts; only the
    # infinite-loop case needs the deliberately tight deadline.
    result = await evaluate(
        make_problem(0.15 if verdict == "TLE" else 0.75), python_language(), code
    )
    assert result["status"] == "success"
    assert result["details"][0]["result"] == verdict


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ is unavailable")
async def test_cpp_compile_error():
    language = Language(
        name="cpp-test",
        file_ext=".cpp",
        compile_cmd="g++ {src} -std=c++14 -o {exe}",
        run_cmd="{exe}",
        time_limit=1,
        memory_limit=128,
    )
    result = await evaluate(make_problem(), language, "int main( {")
    assert result["details"][0]["result"] == "CE"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is unavailable")
async def test_dynamically_registered_c_language_can_judge():
    language = Language(
        name="c-test",
        file_ext=".c",
        compile_cmd="gcc {src} -std=c11 -O2 -o {exe}",
        run_cmd="{exe}",
        time_limit=1,
        memory_limit=128,
    )
    code = '#include <stdio.h>\nint main(void){long long a,b;scanf("%lld%lld",&a,&b);printf("%lld\\n",a+b);}'  # noqa: E501
    result = await evaluate(make_problem(), language, code)
    assert result["details"][0]["result"] == "AC", result
