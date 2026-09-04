from __future__ import annotations

import shutil
import sys

import pytest

from oj.evaluator import evaluate, normalize_output, parse_command, validate_language_commands
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
    result = await evaluate(make_problem(0.15), python_language(), code)
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
