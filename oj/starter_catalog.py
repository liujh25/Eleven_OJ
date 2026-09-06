from __future__ import annotations

import asyncio
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.models import Problem, SystemState
from oj.schemas import ProblemBody

CATALOG_VERSION = "luogu_starter_catalog_v1"


def _cases(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [
        {
            "input": input_data.rstrip("\n") + "\n",
            "output": output_data.rstrip("\n") + "\n",
        }
        for input_data, output_data in pairs
    ]


def _problem(
    problem_id: str,
    title: str,
    description: str,
    input_description: str,
    output_description: str,
    constraints: str,
    cases: list[dict[str, str]],
    tags: list[str],
    *,
    hint: str,
    difficulty: str = "简单",
) -> ProblemBody:
    return ProblemBody(
        id=problem_id,
        title=title,
        description=description,
        input_description=input_description,
        output_description=output_description,
        samples=[cases[0]],
        constraints=constraints,
        testcases=cases,
        hint=hint,
        source=(
            f"洛谷 {problem_id}（题面经重新表述） https://www.luogu.com.cn/problem/{problem_id}"
        ),
        tags=["洛谷", *tags],
        time_limit=1.0,
        memory_limit=128,
        author="liujh25 整理",
        difficulty=difficulty,
    )


STARTER_PROBLEMS: tuple[ProblemBody, ...] = (
    _problem(
        "P1001",
        "两数相加",
        "读取两个整数，计算并输出它们的代数和。输出中不要加入提示文字。",
        "一行包含两个以空格分隔的整数 a 和 b。",
        "输出一个整数，表示 a+b。",
        "-10^9 ≤ a,b ≤ 10^9。",
        _cases(
            ("1 2", "3"),
            ("0 0", "0"),
            ("-1 1", "0"),
            ("1000000000 -1000000000", "0"),
            ("999999999 1", "1000000000"),
        ),
        ["入门", "数学", "输入输出"],
        hint="注意负数以及 32 位有符号整数的边界。",
    ),
    _problem(
        "P5703",
        "批量物资采购",
        "每个小组需要相同数量的物资。已知小组数量和每组份数，求物资总数。",
        "一行两个正整数 x 和 n，分别表示每组份数与小组数量。",
        "输出 x×n 的值。",
        "1 ≤ x,n ≤ 10^9，且乘积不超过 2^31-1。",
        _cases(
            ("3 5", "15"),
            ("1 1", "1"),
            ("12 12", "144"),
            ("1000000000 1", "1000000000"),
            ("46340 46340", "2147395600"),
        ),
        ["入门", "数学", "乘法"],
        hint="总数等于每组份数乘以组数。",
    ),
    _problem(
        "P5704",
        "小写字母转大写",
        "把一个英文字母从小写形式转换成对应的大写形式。",
        "输入一个小写英文字母。",
        "输出对应的大写英文字母。",
        "输入一定是 a 到 z 之间的单个字符。",
        _cases(("a", "A"), ("z", "Z"), ("q", "Q"), ("m", "M"), ("x", "X")),
        ["入门", "字符", "字符串"],
        hint="可以使用语言自带的大小写转换函数，也可以利用字符编码规律。",
    ),
    _problem(
        "P5705",
        "定长小数翻转",
        "给定一个格式固定为三位整数和一位小数的数值文本，将所有字符逆序输出。",
        "输入形如 abc.d 的字符串，其中 a 不为 0，a、b、c、d 均为数字。",
        "输出将输入字符完全逆序后的结果。",
        "100.0 ≤ 输入值 < 1000.0，恰有一位小数。",
        _cases(
            ("123.4", "4.321"),
            ("100.0", "0.001"),
            ("987.6", "6.789"),
            ("101.1", "1.101"),
            ("900.5", "5.009"),
        ),
        ["入门", "字符串", "格式化"],
        hint="按字符串处理可以自然保留翻转后出现的 0。",
    ),
    _problem(
        "P5706",
        "饮料均分与杯数",
        "将 t 毫升饮料平均分给 n 人，并为每人准备两个杯子。计算每人所得饮料和杯子总数。",
        "一行包含实数 t 和正整数 n。",
        "第一行输出每人所得饮料，严格保留三位小数；第二行输出杯子总数。",
        "0 ≤ t ≤ 10000，1 ≤ n ≤ 1000。",
        _cases(
            ("500 3", "166.667\n6"),
            ("0 1", "0.000\n2"),
            ("1 8", "0.125\n16"),
            ("10000 1000", "10.000\n2000"),
            ("7.5 2", "3.750\n4"),
        ),
        ["入门", "浮点数", "格式化"],
        hint="使用固定小数格式输出 t/n；杯子数为 2n。",
    ),
    _problem(
        "P5710",
        "两个条件的逻辑组合",
        "定义条件 A：x 是偶数；条件 B：x 大于 4 且不大于 12。依次判断 A 与 B "
        "同时成立、至少一个成立、恰好一个成立、均不成立。",
        "输入一个整数 x。",
        "输出四个以空格分隔的 0 或 1，依次对应上述四种判断。",
        "0 ≤ x ≤ 1000。",
        _cases(
            ("6", "1 1 0 0"),
            ("5", "0 1 1 0"),
            ("4", "0 1 1 0"),
            ("13", "0 0 0 1"),
            ("12", "1 1 0 0"),
        ),
        ["入门", "条件判断", "布尔逻辑"],
        hint="四项分别是 AND、OR、XOR 和 NOT OR。",
    ),
    _problem(
        "P5711",
        "公历闰年判断",
        "判断给定公历年份是否为闰年。能被 400 整除，或能被 4 整除但不能被 100 整除的年份是闰年。",
        "输入一个正整数 y，表示年份。",
        "闰年输出 1，否则输出 0。",
        "1582 ≤ y ≤ 10000。",
        _cases(
            ("1582", "0"),
            ("1600", "1"),
            ("1900", "0"),
            ("2000", "1"),
            ("2020", "1"),
            ("2019", "0"),
        ),
        ["入门", "条件判断", "日期"],
        hint="整百年份必须能被 400 整除。",
    ),
    _problem(
        "P5712",
        "英文单复数输出",
        "根据吃掉的苹果数量输出一句固定英文，并正确选择 apple 的单数或复数形式。",
        "输入一个自然数 x。",
        "若 x=1，输出 Today, I ate 1 apple.；否则输出 Today, I ate x apples.。",
        "0 ≤ x ≤ 100。",
        _cases(
            ("0", "Today, I ate 0 apples."),
            ("1", "Today, I ate 1 apple."),
            ("2", "Today, I ate 2 apples."),
            ("100", "Today, I ate 100 apples."),
        ),
        ["入门", "条件判断", "字符串"],
        hint="只有数量恰好为 1 时使用单数。",
    ),
    _problem(
        "P5713",
        "两种部署方案",
        "处理 n 个任务时，本地方案每个耗时 5 分钟；云端方案有 11 分钟初始化时间，"
        "之后每个耗时 3 分钟。选择总耗时更短的方案；相同时选择云端。",
        "输入一个正整数 n。",
        "本地严格更快时输出 Local，否则输出 Cloud。",
        "1 ≤ n ≤ 100。",
        _cases(("1", "Local"), ("5", "Local"), ("6", "Cloud"), ("50", "Cloud"), ("100", "Cloud")),
        ["入门", "条件判断", "线性函数"],
        hint="比较 5n 与 3n+11，不需要模拟。",
    ),
    _problem(
        "P5714",
        "BMI 区间分类",
        "身体质量指数 BMI=m/h²，其中 m 为千克数，h 为米数。BMI 小于 18.5 输出 "
        "Underweight，低于 24 输出 Normal，否则输出 Overweight。",
        "一行输入两个实数 m 和 h。",
        "输出一个分类字符串：Underweight、Normal 或 Overweight。",
        "40 ≤ m ≤ 120，1.4 ≤ h ≤ 2.0。",
        _cases(
            ("50 1.7", "Underweight"),
            ("60 1.8", "Normal"),
            ("70 1.7", "Overweight"),
            ("96 2.0", "Overweight"),
            ("72 1.8", "Normal"),
        ),
        ["入门", "条件判断", "浮点数"],
        hint="先计算 m/(h*h)，再按从小到大的阈值判断。",
    ),
    _problem(
        "P5715",
        "三个整数排序",
        "将三个整数按照非递减顺序排列。相同的数需要全部保留。",
        "输入三个以空格分隔的整数 a、b、c。",
        "输出排序后的三个整数，以空格分隔。",
        "0 ≤ a,b,c ≤ 100。",
        _cases(
            ("3 1 2", "1 2 3"),
            ("0 0 0", "0 0 0"),
            ("100 0 50", "0 50 100"),
            ("7 7 3", "3 7 7"),
            ("1 2 3", "1 2 3"),
        ),
        ["入门", "排序", "条件判断"],
        hint="可以调用排序函数，也可以通过比较交换完成。",
    ),
    _problem(
        "P5716",
        "指定月份的天数",
        "给定年份和月份，输出该月天数。二月天数取决于该年份是否为闰年。",
        "输入两个正整数 y 和 m，表示年份和月份。",
        "输出该月的天数。",
        "1583 ≤ y ≤ 10000，1 ≤ m ≤ 12。",
        _cases(
            ("2000 2", "29"),
            ("1900 2", "28"),
            ("2020 4", "30"),
            ("2019 1", "31"),
            ("2019 11", "30"),
            ("2019 2", "28"),
        ),
        ["入门", "条件判断", "日期"],
        hint="先处理 31 天与 30 天的月份，再单独判断二月。",
    ),
    _problem(
        "P5720",
        "连续折半计数",
        "第一天有长度为 a 的整数段。从第二天开始，每天将当前长度除以 2 并向下取整。"
        "求第一次变为 1 是第几天。",
        "输入一个正整数 a。",
        "输出天数，第一天计为 1。",
        "1 ≤ a ≤ 10^9。",
        _cases(("1", "1"), ("2", "2"), ("3", "2"), ("4", "3"), ("10", "4"), ("1000000000", "30")),
        ["入门", "循环", "整数除法"],
        hint="当 a 大于 1 时不断执行 a//=2 并增加天数。",
    ),
    _problem(
        "P5721",
        "递减行数字三角形",
        "从 1 开始连续输出两位数字。第一行输出 n 个，之后每行比上一行少一个，直到"
        "最后一行只有一个；不足两位时补前导 0。",
        "输入一个正整数 n。",
        "输出共 n 行的数字三角形，行内数字之间不加空格。",
        "1 ≤ n ≤ 13。",
        _cases(
            ("1", "01"),
            ("2", "0102\n03"),
            ("3", "010203\n0405\n06"),
            ("5", "0102030405\n06070809\n101112\n1314\n15"),
        ),
        ["入门", "循环", "格式化", "图形输出"],
        hint="维护一个持续递增的计数器，使用两位宽度并以 0 补齐。",
    ),
    _problem(
        "P5722",
        "从一累加到 n",
        "计算从 1 到正整数 n 的所有整数之和。",
        "输入一个正整数 n。",
        "输出 1+2+…+n 的值。",
        "1 ≤ n ≤ 100。",
        _cases(("1", "1"), ("2", "3"), ("10", "55"), ("73", "2701"), ("100", "5050")),
        ["入门", "循环", "数学"],
        hint="可以逐项累加，也可以使用等差数列求和公式。",
    ),
    _problem(
        "P5723",
        "容量限制下的连续质数",
        "从 2 开始按升序考察质数，并依次装入容器；只要加入下一个质数后总和不超过"
        "容量 L 就继续。逐行输出被选中的质数，最后输出数量。",
        "输入一个正整数 L。",
        "每个选中的质数单独占一行，最后一行输出质数数量。若一个也放不下，只输出 0。",
        "1 ≤ L ≤ 10^5。",
        _cases(
            ("1", "0"),
            ("2", "2\n1"),
            ("5", "2\n3\n2"),
            ("20", "2\n3\n5\n7\n4"),
            ("50", "2\n3\n5\n7\n11\n13\n6"),
            ("100", "2\n3\n5\n7\n11\n13\n17\n19\n23\n9"),
        ),
        ["循环", "质数", "枚举", "基础算法"],
        hint="写一个试除到平方根的质数判断函数，并维护已经选中质数的总和。",
        difficulty="中等",
    ),
)


async def seed_starter_catalog(
    session: AsyncSession, problems: Iterable[ProblemBody] = STARTER_PROBLEMS
) -> int:
    inserted = 0
    for body in problems:
        if await session.get(Problem, body.id) is not None:
            continue
        session.add(Problem(**body.model_dump()))
        inserted += 1
    return inserted


async def install_starter_catalog_once(session: AsyncSession) -> int:
    if await session.get(SystemState, CATALOG_VERSION) is not None:
        return 0
    inserted = await seed_starter_catalog(session)
    session.add(SystemState(key=CATALOG_VERSION, value="installed"))
    return inserted


async def _cli() -> None:
    from oj.db import SessionFactory, initialize_database

    await initialize_database()
    async with SessionFactory() as session:
        total = await session.scalar(
            select(func.count(Problem.id)).where(Problem.id.in_([p.id for p in STARTER_PROBLEMS]))
        )
    print(f"Luogu starter catalog ready: {total}/{len(STARTER_PROBLEMS)} problems")


if __name__ == "__main__":
    asyncio.run(_cli())
