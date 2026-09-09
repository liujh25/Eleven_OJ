from __future__ import annotations

import asyncio
import os
import shlex
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil  # type: ignore[import-untyped]

from oj.config import get_settings
from oj.models import Language, Problem

FORBIDDEN_COMMAND_CHARS = set(";&|><`\n\r")


def parse_command(template: str, src: Path, exe: Path) -> list[str]:
    if not template or any(char in template for char in FORBIDDEN_COMMAND_CHARS):
        raise ValueError("command contains forbidden shell syntax")
    fields = {part[1] for part in __import__("string").Formatter().parse(template) if part[1]}
    if not fields.issubset({"src", "exe"}):
        raise ValueError("only {src} and {exe} placeholders are allowed")
    rendered = template.format(src=str(src.resolve()), exe=str(exe.resolve()))
    args = shlex.split(rendered, posix=os.name != "nt")
    if os.name == "nt":
        args = [
            arg[1:-1] if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in "\"'" else arg
            for arg in args
        ]
    if not args:
        raise ValueError("empty command")
    return args


def validate_language_commands(compile_cmd: str | None, run_cmd: str) -> None:
    fake = Path("judge")
    parse_command(run_cmd, fake.with_suffix(".txt"), fake)
    if compile_cmd:
        parse_command(compile_cmd, fake.with_suffix(".txt"), fake)
        if "{src}" not in compile_cmd or "{exe}" not in compile_cmd:
            raise ValueError("compile command requires {src} and {exe}")
        if "{exe}" not in run_cmd:
            raise ValueError("compiled language run command requires {exe}")
    elif "{src}" not in run_cmd:
        raise ValueError("interpreted language run command requires {src}")


def normalize_output(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n")).rstrip("\n")


def effective_limits(problem: Problem, language: Language) -> tuple[float, int]:
    """Resolve each judge limit independently by problem/language/system priority."""
    settings = get_settings()
    return (
        problem.time_limit or language.time_limit or settings.default_time_limit_seconds,
        problem.memory_limit or language.memory_limit or settings.default_memory_limit_mb,
    )


def _resource_limiter(memory_mb: int, cpu_seconds: int):
    def limit() -> None:
        if os.name == "posix":
            import resource

            memory_bytes = memory_mb * 1024 * 1024
            resource_api = vars(resource)
            set_limit = resource_api["setrlimit"]
            set_limit(resource_api["RLIMIT_AS"], (memory_bytes, memory_bytes))
            set_limit(resource_api["RLIMIT_CPU"], (cpu_seconds, cpu_seconds + 1))
            set_limit(
                resource_api["RLIMIT_FSIZE"],
                (16 * 1024 * 1024, 16 * 1024 * 1024),
            )
            set_limit(resource_api["RLIMIT_NPROC"], (32, 32))
            vars(os)["setsid"]()

    return limit


def _kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.Error:
        pass


async def _watch_memory(pid: int, memory_mb: int, state: dict[str, Any]) -> None:
    while True:
        try:
            proc = psutil.Process(pid)
            rss = proc.memory_info().rss + sum(
                child.memory_info().rss for child in proc.children(recursive=True)
            )
            state["peak"] = max(state["peak"], rss / 1024 / 1024)
            if state["peak"] > memory_mb:
                state["mle"] = True
                _kill_tree(pid)
                return
        except psutil.Error:
            return
        await asyncio.sleep(0.02)


@dataclass
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed: float
    memory: float
    timed_out: bool = False
    memory_exceeded: bool = False


async def run_process(
    args: list[str], stdin: str, timeout: float, memory_mb: int, cwd: Path
) -> ProcessResult:
    kwargs: dict[str, Any] = {}
    if os.name == "posix":
        kwargs["preexec_fn"] = _resource_limiter(memory_mb, max(1, int(timeout) + 1))
    elif os.name == "nt":
        kwargs["creationflags"] = 0x00000200
    started = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            # Compilers create intermediate files.  Point every platform's
            # temp convention at the isolated judge directory instead of a
            # shared or unwritable system location.
            "TMPDIR": str(cwd),
            "TEMP": str(cwd),
            "TMP": str(cwd),
        },
        **kwargs,
    )
    state: dict[str, Any] = {"peak": 0.0, "mle": False}
    watcher = asyncio.create_task(_watch_memory(proc.pid, memory_mb, state))
    timed_out = False
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin.encode()), timeout=max(timeout, 0.05)
        )
    except TimeoutError:
        timed_out = True
        if os.name == "posix":
            try:
                vars(os)["killpg"](proc.pid, vars(signal)["SIGKILL"])
            except ProcessLookupError:
                pass
        _kill_tree(proc.pid)
        stdout, stderr = await proc.communicate()
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
    return ProcessResult(
        returncode=proc.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace")[:64_000],
        stderr=stderr.decode("utf-8", errors="replace")[:64_000],
        elapsed=time.perf_counter() - started,
        memory=round(float(state["peak"]), 3),
        timed_out=timed_out,
        memory_exceeded=bool(state["mle"]),
    )


async def evaluate(problem: Problem, language: Language, code: str) -> dict[str, Any]:
    validate_language_commands(language.compile_cmd, language.run_cmd)
    time_limit, memory_limit = effective_limits(problem, language)
    suffix = language.file_ext
    with tempfile.TemporaryDirectory(prefix="async-oj-") as temporary:
        workdir = Path(temporary)
        src = workdir / f"main{suffix}"
        exe = workdir / ("program.exe" if sys.platform == "win32" else "program")
        await asyncio.to_thread(src.write_text, code, encoding="utf-8")
        compile_info = None
        if language.compile_cmd:
            compiled = await run_process(
                parse_command(language.compile_cmd, src, exe), "", 15.0, 512, workdir
            )
            if compiled.returncode != 0 or compiled.timed_out or compiled.memory_exceeded:
                message = compiled.stderr or "compiler failed"
                return {
                    "status": "success",
                    "score": 0,
                    "counts": len(problem.testcases) * 10,
                    "compile_info": {"result": "failed", "message": message},
                    "run_info": {"result": "not_started", "message": "compilation failed"},
                    "error_info": "",
                    "details": [
                        {
                            "id": 1,
                            "result": "CE",
                            "time": compiled.elapsed,
                            "memory": compiled.memory,
                        }
                    ],
                }
            compile_info = {"result": "success", "message": compiled.stderr}

        details: list[dict[str, Any]] = []
        for number, testcase in enumerate(problem.testcases, start=1):
            try:
                result = await run_process(
                    parse_command(language.run_cmd, src, exe),
                    testcase["input"],
                    time_limit,
                    memory_limit,
                    workdir,
                )
                if result.memory_exceeded:
                    verdict = "MLE"
                elif result.timed_out:
                    verdict = "TLE"
                elif result.returncode != 0:
                    verdict = "RE"
                elif normalize_output(result.stdout) == normalize_output(testcase["output"]):
                    verdict = "AC"
                else:
                    verdict = "WA"
                details.append(
                    {
                        "id": number,
                        "result": verdict,
                        "time": round(result.elapsed, 4),
                        "memory": result.memory,
                    }
                )
            except Exception:
                details.append({"id": number, "result": "UNK", "time": 0.0, "memory": 0.0})
        score = sum(10 for detail in details if detail["result"] == "AC")
        return {
            "status": "success",
            "score": score,
            "counts": len(details) * 10,
            "compile_info": compile_info,
            "run_info": {
                "result": "finished",
                "message": f"{len(details)} test cases finished",
            },
            "error_info": "",
            "details": details,
        }
