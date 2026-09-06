from __future__ import annotations

import math

from sqlalchemy import delete, func, select

from oj.db import SessionFactory
from oj.models import Problem
from oj.starter_catalog import (
    STARTER_PROBLEMS,
    install_starter_catalog_once,
    seed_starter_catalog,
)


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    return all(value % divisor for divisor in range(2, math.isqrt(value) + 1))


def _solve(problem_id: str, raw: str) -> str:
    tokens = raw.split()
    if problem_id == "P1001":
        return str(sum(map(int, tokens)))
    if problem_id == "P5703":
        a, b = map(int, tokens)
        return str(a * b)
    if problem_id == "P5704":
        return tokens[0].upper()
    if problem_id == "P5705":
        return tokens[0][::-1]
    if problem_id == "P5706":
        total, people = float(tokens[0]), int(tokens[1])
        return f"{total / people:.3f}\n{people * 2}"
    if problem_id == "P5710":
        value = int(tokens[0])
        first = value % 2 == 0
        second = 4 < value <= 12
        return " ".join(
            map(
                str,
                (
                    int(first and second),
                    int(first or second),
                    int(first != second),
                    int(not first and not second),
                ),
            )
        )
    if problem_id == "P5711":
        year = int(tokens[0])
        return str(int(year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)))
    if problem_id == "P5712":
        count = int(tokens[0])
        noun = "apple" if count == 1 else "apples"
        return f"Today, I ate {count} {noun}."
    if problem_id == "P5713":
        count = int(tokens[0])
        return "Local" if 5 * count < 3 * count + 11 else "Cloud"
    if problem_id == "P5714":
        mass, height = map(float, tokens)
        bmi = mass / height**2
        return "Underweight" if bmi < 18.5 else "Normal" if bmi < 24 else "Overweight"
    if problem_id == "P5715":
        return " ".join(map(str, sorted(map(int, tokens))))
    if problem_id == "P5716":
        year, month = map(int, tokens)
        leap = year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)
        days = (
            29
            if month == 2 and leap
            else 28
            if month == 2
            else 30
            if month in {4, 6, 9, 11}
            else 31
        )
        return str(days)
    if problem_id == "P5720":
        length = int(tokens[0])
        days = 1
        while length > 1:
            length //= 2
            days += 1
        return str(days)
    if problem_id == "P5721":
        size = int(tokens[0])
        value = 1
        rows = []
        for width in range(size, 0, -1):
            rows.append("".join(f"{number:02d}" for number in range(value, value + width)))
            value += width
        return "\n".join(rows)
    if problem_id == "P5722":
        value = int(tokens[0])
        return str(sum(range(1, value + 1)))
    if problem_id == "P5723":
        capacity = int(tokens[0])
        selected: list[int] = []
        total = 0
        candidate = 2
        while total + candidate <= capacity:
            if _is_prime(candidate):
                selected.append(candidate)
                total += candidate
            candidate += 1
        return "\n".join([*(str(value) for value in selected), str(len(selected))])
    raise AssertionError(f"missing reference solver for {problem_id}")


def test_catalog_is_complete_and_every_expected_output_is_verified():
    assert len(STARTER_PROBLEMS) == 16
    assert len({problem.id for problem in STARTER_PROBLEMS}) == 16
    for problem in STARTER_PROBLEMS:
        assert len(problem.testcases) >= 4
        assert f"https://www.luogu.com.cn/problem/{problem.id}" in problem.source
        for testcase in problem.testcases:
            assert _solve(problem.id, testcase.input).rstrip() == testcase.output.rstrip()


async def test_catalog_seed_is_idempotent(api):
    async with SessionFactory() as session:
        assert await seed_starter_catalog(session) == 16
        await session.commit()
        assert await seed_starter_catalog(session) == 0
        total = await session.scalar(
            select(func.count(Problem.id)).where(
                Problem.id.in_([problem.id for problem in STARTER_PROBLEMS])
            )
        )
        assert total == 16


async def test_one_time_install_does_not_restore_a_deleted_problem(api):
    async with SessionFactory() as session:
        assert await install_starter_catalog_once(session) == 16
        await session.commit()
        await session.execute(delete(Problem).where(Problem.id == "P1001"))
        await session.commit()
        assert await install_starter_catalog_once(session) == 0
        assert await session.get(Problem, "P1001") is None
