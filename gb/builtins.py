"""GB 运行时值、内建函数与显示格式。"""

import math
import sys


class GbError(Exception):
    """GB 运行时错误。line 为 0 时表示错误位置未知。"""

    def __init__(self, message, line=0):
        super().__init__(message)
        self.message = message
        self.line = line


class Function:
    __slots__ = ("name", "params", "body", "closure", "line")

    def __init__(self, name, params, body, closure, line=0):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.line = line


class StructDef:
    __slots__ = ("name", "fields", "line")

    def __init__(self, name, fields, line=0):
        self.name = name
        self.fields = fields
        self.line = line


class Instance:
    __slots__ = ("struct", "values")

    def __init__(self, struct, values):
        self.struct = struct
        self.values = values  # dict: 字段名 -> 值


class Builtin:
    __slots__ = ("name", "min_arity", "max_arity", "fn")

    def __init__(self, name, min_arity, max_arity, fn):
        self.name = name
        self.min_arity = min_arity
        self.max_arity = max_arity
        self.fn = fn

    def check_arity(self, n, line):
        too_many = self.max_arity is not None and n > self.max_arity
        if n < self.min_arity or too_many:
            if self.min_arity == self.max_arity:
                expect = f"需要 {self.min_arity} 个参数"
            else:
                expect = f"需要 {self.min_arity}-{self.max_arity} 个参数"
            raise GbError(f"内建函数 {self.name} {expect}，实际 {n} 个", line)


def display(v):
    """print / str 的统一显示格式。"""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(display(x) for x in v) + "]"
    if isinstance(v, Instance):
        fields = ", ".join(display(v.values[name])
                           for name in v.struct.fields)
        return f"{v.struct.name}({fields})"
    if isinstance(v, Function):
        return f"<fun {v.name}>"
    if isinstance(v, Builtin):
        return f"<builtin {v.name}>"
    if isinstance(v, StructDef):
        return f"<struct {v.name}>"
    return str(v)


# ---------------- 内建实现 ----------------

def _print(args):
    sys.stdout.write(" ".join(display(a) for a in args) + "\n")
    return None


def _input(args):
    prompt = args[0] if args else ""
    if not isinstance(prompt, str):
        raise GbError("input 的提示语必须是字符串")
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == "":
        return ""  # EOF
    if line.endswith("\n"):
        line = line[:-1]
    return line


def _len(args):
    v = args[0]
    if isinstance(v, (list, str)):
        return len(v)
    raise GbError("len 只能用于数组或字符串")


def _to_int(args):
    v = args[0]
    if isinstance(v, bool):
        raise GbError("无法将 bool 转换为 int")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return math.trunc(v)
    if isinstance(v, str):
        try:
            return int(v, 10)
        except ValueError:
            pass
    raise GbError(f"无法将 {display(v)} 转换为 int")


def _to_float(args):
    v = args[0]
    if isinstance(v, bool):
        raise GbError("无法将 bool 转换为 float")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            pass
    raise GbError(f"无法将 {display(v)} 转换为 float")


def _to_str(args):
    return display(args[0])


def _push(args):
    arr, value = args
    if not isinstance(arr, list):
        raise GbError("push 的第一个参数必须是数组")
    arr.append(value)
    return None


BUILTINS = {
    "print": Builtin("print", 0, None, _print),
    "input": Builtin("input", 0, 1, _input),
    "len": Builtin("len", 1, 1, _len),
    "int": Builtin("int", 1, 1, _to_int),
    "float": Builtin("float", 1, 1, _to_float),
    "str": Builtin("str", 1, 1, _to_str),
    "push": Builtin("push", 2, 2, _push),
}
# 可变参数：max_arity=None 表示不限制
