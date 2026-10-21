"""GB 运行时值、内建函数与显示格式。"""

import math
import re
import sys

# v0.3.1：int/float 的字符串解析严格匹配 GB 数值字面量形式（可选前导 -），
# 拒绝 Python 扩展形式（全角数字、下划线、空白、+ 号、nan/inf、科学计数法）
_INT_TEXT = re.compile(r"-?[0-9]+$")
_FLOAT_TEXT = re.compile(r"-?([0-9]+|[0-9]+\.[0-9]+)$")


class GbError(Exception):
    """GB 运行时错误。line/col 为 0 时表示错误位置未知。"""

    def __init__(self, message, line=0, col=0):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col


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

    def check_arity(self, n, line, col):
        too_many = self.max_arity is not None and n > self.max_arity
        if n < self.min_arity or too_many:
            if self.min_arity == self.max_arity:
                expect = f"需要 {self.min_arity} 个参数"
            else:
                expect = f"需要 {self.min_arity}-{self.max_arity} 个参数"
            raise GbError(f"内建函数 {self.name} {expect}，实际 {n} 个",
                          line, col)


def display(v, _seen=None):
    """print / str 的统一显示格式。

    v0.3.1：禁止循环引用。_seen 记录当前递归路径上的数组/struct 实例
    （id 集合，离开分支即移除），检测到环时报运行时错误；无环的共享
    引用（菱形）不受影响。
    """
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
    if isinstance(v, (list, Instance)):
        if _seen is None:
            _seen = set()
        if id(v) in _seen:
            raise GbError("存在循环引用，无法显示")
        _seen.add(id(v))
        try:
            if isinstance(v, list):
                return "[" + ", ".join(display(x, _seen) for x in v) + "]"
            fields = ", ".join(display(v.values[name], _seen)
                               for name in v.struct.fields)
            return f"{v.struct.name}({fields})"
        finally:
            _seen.discard(id(v))
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
        return None  # v0.3：EOF 返回 null，与空行 "" 区分
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
        # v0.4.1：inf/nan 不可转 int（math.trunc 会抛 OverflowError/
        # ValueError，统一为运行时错误）
        if not math.isfinite(v):
            raise GbError(f"无法将 {display(v)} 转换为 int")
        return math.trunc(v)
    if isinstance(v, str):
        if _INT_TEXT.match(v):
            return int(v, 10)
        raise GbError(f"无法将 {display(v)} 转换为 int")
    raise GbError(f"无法将 {display(v)} 转换为 int")


def _to_float(args):
    v = args[0]
    if isinstance(v, bool):
        raise GbError("无法将 bool 转换为 float")
    if isinstance(v, (int, float)):
        try:
            f = float(v)
        except OverflowError:
            # v0.4.1：超大 int 超出 float64 范围
            raise GbError("整数过大，无法转换为 float") from None
        # v0.4.3：inf/nan 在语言中不可构造，防御性拒绝
        if not math.isfinite(f):
            raise GbError("浮点溢出")
        return f
    if isinstance(v, str):
        if _FLOAT_TEXT.match(v):
            f = float(v)
            # v0.4.3：400 位以上的数字串会静默溢出为 inf
            if not math.isfinite(f):
                raise GbError("浮点溢出")
            return f
        raise GbError(f"无法将 {display(v)} 转换为 float")
    raise GbError(f"无法将 {display(v)} 转换为 float")


def _to_str(args):
    return display(args[0])


def _push(args):
    arr, value = args
    if not isinstance(arr, list):
        raise GbError("push 的第一个参数必须是数组")
    arr.append(value)
    return None


def _pop(args):
    arr = args[0]
    if not isinstance(arr, list):
        raise GbError("pop 的参数必须是数组")
    if not arr:
        raise GbError("对空数组 pop")
    return arr.pop()


BUILTINS = {
    "print": Builtin("print", 0, None, _print),
    "input": Builtin("input", 0, 1, _input),
    "len": Builtin("len", 1, 1, _len),
    "int": Builtin("int", 1, 1, _to_int),
    "float": Builtin("float", 1, 1, _to_float),
    "str": Builtin("str", 1, 1, _to_str),
    "push": Builtin("push", 2, 2, _push),
    "pop": Builtin("pop", 1, 1, _pop),
}
# 可变参数：max_arity=None 表示不限制
