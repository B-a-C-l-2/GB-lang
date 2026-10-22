"""GB 性能测试的 Python 对照实现：与 benchmarks/bench.gb 算法逐行对应。

从 stdin 读两行（用例名 + 重复次数），输出 N 行 "case <名字> <校验和>"。
校验和必须与 GB 版完全一致，否则两个实现已经不等价。

单独运行：python benchmarks/bench.py < 用例名
对比计时：python benchmarks/compare.py（它在进程内直接调用本模块的用例，
避开 Python 自己的进程启动开销）
"""

import sys


class P:
    """与 GB 的 struct 对应：固定字段的数据容器。"""

    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y


def add3(a, b, c):
    return a + b + c


def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def case_arith():
    acc = 0
    i = 0
    while i < 40000:
        acc = acc + i * 3 - (i % 7)
        i += 1
    print("case arith", acc)


def case_calls():
    acc = 0
    i = 0
    while i < 20000:
        acc = acc + add3(i, i + 1, i + 2)
        i += 1
    print("case calls", acc)


def case_recur():
    print("case recur", fib(21))


def case_arrays():
    arr = []
    i = 0
    while i < 20000:
        arr.append(i % 100)
        i += 1
    s = 0
    for v in arr:
        s += v
    while len(arr) > 0:
        s += arr.pop()
    print("case arrays", s)


def case_strings():
    s = ""
    i = 0
    while i < 6000:
        s = s + "abc"
        i += 1
    t = 0
    j = 0
    while j < 6000:
        t = t + len(s[0:10])
        j += 1
    print("case strings", len(s) + t)


def case_structs():
    acc = 0
    i = 0
    while i < 20000:
        p = P(i, i * 2)
        p.x = p.x + 1
        acc = acc + p.x + p.y
        i += 1
    print("case structs", acc)


def case_sort():
    n = 150
    a = []
    i = 0
    while i < n:
        a.append(n - i)
        i += 1
    for i in range(n):
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                t = a[j]
                a[j] = a[j + 1]
                a[j + 1] = t
    s = 0
    for v in a:
        s += v * (v % 3)
    print("case sort", s + a[0] * 1000000 + a[n - 1])


CASES = {
    "arith": case_arith,
    "calls": case_calls,
    "recur": case_recur,
    "arrays": case_arrays,
    "strings": case_strings,
    "structs": case_structs,
    "sort": case_sort,
}

NAMES = ["arith", "calls", "recur", "arrays", "strings", "structs", "sort"]


def run_case(name):
    """按名字执行一个用例；未知名字（如 startup）不做事。"""
    fn = CASES.get(name)
    if fn is not None:
        fn()


def main():
    which = sys.stdin.readline().strip()
    reps_text = sys.stdin.readline().strip()
    reps = int(reps_text) if reps_text.isdigit() else 1
    names = NAMES if not which or which == "all" else [which]
    for name in names:
        for _ in range(reps):
            run_case(name)


if __name__ == "__main__":
    main()
