"""对比 GB 与 Python 跑同一批工作负载的耗时。

测量方法（关键）：两边都必须扣掉进程启动开销，否则 Python 侧 60–80ms 的
启动会把它只有几毫秒的计算淹没掉。

- GB：脚本没有时钟，只能外部计时。同一用例分别跑 1 次与 4 次，
  取两次总时长之差 / 3 作为单次计算时间——进程启动被斜率消掉。
- Python：在进程内直接调用同一批函数，用 perf_counter 计时，
  自然不含进程启动。

两边必须输出完全相同的校验和，否则以非零码退出：校验和不一致说明算法
已经不等价，比时间没有意义。

用法：
    python benchmarks/compare.py              # 每个用例测 2 轮取最优
    python benchmarks/compare.py --runs 3
    python benchmarks/compare.py --case sort

表格用 ASCII 输出：Windows 控制台默认代码页 936 时，中文会被按 UTF-8
解码成乱码，基准工具不该有这种环境依赖。
"""

import argparse
import contextlib
import io
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))

import bench as pybench  # noqa: E402  （需要先设置 sys.path）

GB_CMD = [sys.executable, "-m", "gb", "benchmarks/bench.gb"]
GB_REPS = 4  # GB 侧斜率法的第二个采样点

LABELS = {
    "arith": "int arithmetic loop x40k",
    "calls": "function calls x20k",
    "recur": "recursive fib(21)",
    "arrays": "array push/iterate/pop x20k",
    "strings": "string concat + slice x6k",
    "structs": "struct build + field rw x20k",
    "sort": "bubble sort 150 elems",
}


def gb_run(case, reps):
    """跑一次 GB 脚本，返回 (耗时秒, 输出去掉首尾空白)。"""
    start = time.perf_counter()
    proc = subprocess.run(
        GB_CMD, cwd=ROOT, input=f"{case}\n{reps}\n",
        capture_output=True, text=True, timeout=600,
    )
    elapsed = time.perf_counter() - start
    if proc.returncode != 0:
        sys.exit(f"GB run failed ({case} x{reps}):\n{proc.stderr.strip()}")
    return elapsed, proc.stdout.strip()


def gb_work_per_iter(case, runs):
    """单次计算时间（秒）：用 reps=1 与 reps=GB_REPS 的斜率消掉启动开销。"""
    best = None
    for _ in range(runs):
        t1, out1 = gb_run(case, 1)
        tn, outn = gb_run(case, GB_REPS)
        if outn != "\n".join([out1] * GB_REPS):
            sys.exit(f"GB output not repeatable ({case})")
        work = (tn - t1) / (GB_REPS - 1)
        best = work if best is None else min(best, work)
    return best, out1


def py_run(case, reps):
    """进程内跑 reps 次，返回 (耗时秒, 输出)。"""
    buf = io.StringIO()
    start = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        for _ in range(reps):
            pybench.run_case(case)
    return time.perf_counter() - start, buf.getvalue().strip()


def py_work_per_iter(case, runs):
    best = None
    out = ""
    for _ in range(runs):
        elapsed, out = py_run(case, 1)
        best = elapsed if best is None else min(best, elapsed)
    return best, out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2,
                        help="measurements per case (best taken)")
    parser.add_argument("--case", default=None, help="run a single case")
    args = parser.parse_args()

    cases = [args.case] if args.case else pybench.NAMES
    print("GB vs Python - per-iteration compute time "
          f"(best of {args.runs}; process start canceled)\n")
    print(f"{'case':<36}{'GB/iter':>11}{'Python/iter':>13}{'ratio':>9}")
    print("-" * 69)

    total_gb = total_py = 0.0
    for case in cases:
        gb, gb_out = gb_work_per_iter(case, args.runs)
        py, py_out = py_work_per_iter(case, args.runs)
        if gb_out != py_out:
            sys.exit(f"checksum mismatch ({case}): "
                     f"GB={gb_out!r} Python={py_out!r}")
        total_gb += gb
        total_py += py
        print(f"{case + ' ' + LABELS.get(case, ''):<36}"
              f"{gb * 1000:>10.2f}ms{py * 1000:>12.2f}ms{gb / py:>8.1f}x")

    print("-" * 69)
    print(f"{'total':<36}{total_gb * 1000:>10.2f}ms"
          f"{total_py * 1000:>12.2f}ms{total_gb / total_py:>8.1f}x")

    start, _ = gb_run("startup", 1)
    print(f"\nchecksums identical for every case. "
          f"GB process start (import included): {start * 1000:.0f}ms")


if __name__ == "__main__":
    main()
