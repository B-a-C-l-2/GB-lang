"""GB 树遍历解释器：遍历 AST 求值。"""

from gb import ast
from gb.builtins import (
    BUILTINS, Builtin, Function, StructDef, Instance, GbError,
)


class Environment:
    __slots__ = ("vars", "parent")

    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def declare(self, name, value, line=0):
        if name in self.vars:
            raise GbError(f"变量 {name} 在当前作用域重复声明", line)
        self.vars[name] = value

    def get(self, name, line=0):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise GbError(f"变量 {name} 未定义", line)

    def assign(self, name, value, line=0):
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise GbError(f"变量 {name} 未定义，无法赋值", line)


def make_global_env():
    env = Environment()
    for name, builtin in BUILTINS.items():
        env.vars[name] = builtin
    return env


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


def _is_num(v):
    """GB 的数值：int/float，但 bool 不算（严格类型）。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _truthy(v):
    """仅 false 和 null 为假。"""
    return v is not False and v is not None


def _gb_equal(a, b):
    if a is None:
        return b is None
    if isinstance(a, bool):
        return isinstance(b, bool) and a == b
    if _is_num(a):
        return _is_num(b) and a == b
    if isinstance(a, str):
        return isinstance(b, str) and a == b
    if isinstance(a, list):
        return (isinstance(b, list) and len(a) == len(b)
                and all(_gb_equal(x, y) for x, y in zip(a, b)))
    # struct 实例与函数值：身份比较
    return a is b


def _gb_compare(a, b, line):
    """有序比较，返回 -1/0/1；不可比较则运行时错误。"""
    if _is_num(a) and _is_num(b):
        return (a > b) - (a < b)
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    if isinstance(a, list) and isinstance(b, list):
        for x, y in zip(a, b):
            c = _gb_compare(x, y, line)
            if c != 0:
                return c
        return (len(a) > len(b)) - (len(a) < len(b))
    raise GbError("这两个类型的值不能使用大小比较", line)


class Interpreter:
    def __init__(self, global_env=None):
        self.env = global_env if global_env is not None else make_global_env()
        self.loop_depth = 0
        self.function_depth = 0

    def run(self, module):
        for stmt in module.statements:
            self._exec(stmt, self.env)

    # ---------- 语句 ----------

    def _exec(self, node, env):
        t = type(node)

        if t is ast.Let:
            env.declare(node.name, self._eval(node.value, env), node.line)

        elif t is ast.Fun:
            env.declare(node.name,
                        Function(node.name, node.params, node.body,
                                 env, node.line),
                        node.line)

        elif t is ast.Struct:
            env.declare(node.name, StructDef(node.name, node.fields,
                                             node.line), node.line)

        elif t is ast.Block:
            self._exec_body(node.statements, env)

        elif t is ast.If:
            body = node.then_body if _truthy(
                self._eval(node.condition, env)) else node.else_body
            if body is not None:
                self._exec_body(body, env)

        elif t is ast.While:
            self.loop_depth += 1
            try:
                while _truthy(self._eval(node.condition, env)):
                    try:
                        self._exec_body(node.body, env)
                    except _Continue:
                        pass
            except _Break:
                pass
            finally:
                self.loop_depth -= 1

        elif t is ast.ForC:
            loop_env = Environment(env)
            if node.init is not None:
                self._exec(node.init, loop_env)
            self.loop_depth += 1
            try:
                while node.condition is None or _truthy(
                        self._eval(node.condition, loop_env)):
                    try:
                        self._exec_body(node.body, loop_env)
                    except _Continue:
                        pass
                    if node.update is not None:
                        self._eval(node.update, loop_env)
            except _Break:
                pass
            finally:
                self.loop_depth -= 1

        elif t is ast.ForRange:
            iv = node.interval
            start = self._eval(iv.start, env)
            end = self._eval(iv.end, env)
            if not _is_num(start) or isinstance(start, float) \
                    or not _is_num(end) or isinstance(end, float):
                raise GbError("区间端点必须是 int", iv.line)
            lo = start if iv.left_inclusive else start + 1
            hi = end if iv.right_inclusive else end - 1

            loop_env = Environment(env)
            loop_env.declare(node.name, lo)
            i = lo
            self.loop_depth += 1
            try:
                while i <= hi:
                    loop_env.vars[node.name] = i
                    try:
                        self._exec_body(node.body, loop_env)
                    except _Continue:
                        pass
                    i += 1
            except _Break:
                pass
            finally:
                self.loop_depth -= 1

        elif t is ast.Return:
            if self.function_depth == 0:
                raise GbError("return 只能出现在函数中", node.line)
            value = None if node.value is None else self._eval(
                node.value, env)
            raise _Return(value)

        elif t is ast.Break:
            if self.loop_depth == 0:
                raise GbError("break 只能出现在循环中", node.line)
            raise _Break()

        elif t is ast.Continue:
            if self.loop_depth == 0:
                raise GbError("continue 只能出现在循环中", node.line)
            raise _Continue()

        elif t is ast.ExprStmt:
            self._eval(node.expression, env)

        else:
            raise GbError(f"未知语句 {type(node).__name__}")

    def _exec_body(self, statements, parent_env):
        env = Environment(parent_env)
        for stmt in statements:
            self._exec(stmt, env)

    # ---------- 表达式 ----------

    def _eval(self, node, env, as_callee=False):
        t = type(node)

        if t is ast.Number:
            return node.value
        if t is ast.String:
            return node.value
        if t is ast.Bool:
            return node.value
        if t is ast.Null:
            return None
        if t is ast.Array:
            return [self._eval(e, env) for e in node.elements]

        if t is ast.Var:
            value = env.get(node.name, node.line)
            if not as_callee and isinstance(
                    value, (Function, Builtin, StructDef)):
                kind = ("struct" if isinstance(value, StructDef)
                        else "函数")
                raise GbError(
                    f"{node.name} 是{kind}，不能作为值传递或赋值", node.line)
            return value

        if t is ast.Assign:
            return self._assign(node, env)

        if t is ast.Unary:
            v = self._eval(node.operand, env)
            if node.op == "-":
                if not _is_num(v):
                    raise GbError("一元减号只能用于数值", node.line)
                return -v
            return not _truthy(v)

        if t is ast.Binary:
            return self._binary(node, env)

        if t is ast.Logical:
            left = self._eval(node.left, env)
            if node.op == "and":
                return left if not _truthy(left) else self._eval(
                    node.right, env)
            return left if _truthy(left) else self._eval(node.right, env)

        if t is ast.Call:
            return self._call(node, env)

        if t is ast.Index:
            return self._index(node, env)

        if t is ast.Slice:
            return self._slice(node, env)

        if t is ast.Get:
            obj = self._eval(node.object, env)
            if not isinstance(obj, Instance):
                raise GbError("只有 struct 实例能使用 . 访问字段",
                              node.line)
            if node.name not in obj.struct.fields:
                raise GbError(
                    f"{obj.struct.name} 没有字段 {node.name}", node.line)
            return obj.values[node.name]

        raise GbError(f"未知表达式 {type(node).__name__}")

    def _binary(self, node, env):
        op = node.op
        a = self._eval(node.left, env)
        b = self._eval(node.right, env)
        line = node.line

        if op == "+":
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            if _is_num(a) and _is_num(b):
                return a + b
            raise GbError("+ 只能用于数值或两个字符串", line)
        if op in ("-", "*"):
            if _is_num(a) and _is_num(b):
                return a - b if op == "-" else a * b
            raise GbError(f"{op} 只能用于数值", line)
        if op == "/":
            if _is_num(a) and _is_num(b):
                if b == 0:
                    raise GbError("除数为零", line)
                return a / b
            raise GbError("/ 只能用于数值", line)
        if op == "%":
            if _is_num(a) and _is_num(b):
                if b == 0:
                    raise GbError("对零取模", line)
                return a % b
            raise GbError("% 只能用于数值", line)
        if op == "==":
            return _gb_equal(a, b)
        if op == "!=":
            return not _gb_equal(a, b)
        if op in ("<", "<=", ">", ">="):
            c = _gb_compare(a, b, line)
            return {"<": c < 0, "<=": c <= 0,
                    ">": c > 0, ">=": c >= 0}[op]
        raise GbError(f"未知运算符 {op}", line)

    def _assign(self, node, env):
        target = node.target
        value = self._eval(node.value, env)
        t = type(target)
        if t is ast.Var:
            env.assign(target.name, value, target.line)
        elif t is ast.Index:
            obj = self._eval(target.object, env)
            idx = self._eval(target.index, env)
            if isinstance(obj, str):
                raise GbError("字符串不可变，不能修改其字符", target.line)
            if not isinstance(obj, list):
                raise GbError("只能对数组元素赋值", target.line)
            if not _is_num(idx) or isinstance(idx, float):
                raise GbError("数组下标必须是 int", target.line)
            if not 0 <= idx < len(obj):
                raise GbError("数组下标越界", target.line)
            obj[idx] = value
        elif t is ast.Get:
            obj = self._eval(target.object, env)
            if not isinstance(obj, Instance):
                raise GbError("只能给 struct 实例的字段赋值", target.line)
            if target.name not in obj.struct.fields:
                raise GbError(
                    f"{obj.struct.name} 没有字段 {target.name}", target.line)
            obj.values[target.name] = value
        else:
            raise GbError("赋值目标非法", node.line)
        return value

    def _check_int_index(self, idx, line):
        if not _is_num(idx) or isinstance(idx, float):
            raise GbError("下标必须是 int", line)

    def _index(self, node, env):
        obj = self._eval(node.object, env)
        idx = self._eval(node.index, env)
        if not isinstance(obj, (list, str)):
            raise GbError("只有数组和字符串可以索引", node.line)
        self._check_int_index(idx, node.line)
        if not 0 <= idx < len(obj):
            raise GbError("下标越界", node.line)
        return obj[idx]

    def _slice(self, node, env):
        obj = self._eval(node.object, env)
        start = self._eval(node.start, env)
        end = self._eval(node.end, env)
        if not isinstance(obj, (list, str)):
            raise GbError("只有数组和字符串可以切片", node.line)
        self._check_int_index(start, node.line)
        self._check_int_index(end, node.line)
        length = len(obj)
        lo = min(max(start, 0), length)
        hi = min(max(end, 0), length)
        if lo >= hi:
            return [] if isinstance(obj, list) else ""
        return obj[lo:hi]

    def _call(self, node, env):
        callee = self._eval(node.callee, env, as_callee=True)
        args = [self._eval(a, env) for a in node.args]
        n = len(args)

        if isinstance(callee, Function):
            if n != len(callee.params):
                raise GbError(
                    f"函数 {callee.name} 需要 {len(callee.params)} 个参数，"
                    f"实际 {n} 个", node.line)
            call_env = Environment(callee.closure)
            for name, value in zip(callee.params, args):
                call_env.declare(name, value)
            self.function_depth += 1
            try:
                self._exec_body(callee.body, call_env)
            except _Return as ret:
                return ret.value
            finally:
                self.function_depth -= 1
            return None

        if isinstance(callee, Builtin):
            callee.check_arity(n, node.line)
            try:
                return callee.fn(args)
            except GbError as e:
                if not e.line:
                    e.line = node.line
                raise

        if isinstance(callee, StructDef):
            if n != len(callee.fields):
                raise GbError(
                    f"构造 {callee.name} 需要 {len(callee.fields)} 个参数，"
                    f"实际 {n} 个", node.line)
            return Instance(callee, dict(zip(callee.fields, args)))

        raise GbError("该值不是可调用对象", node.line)
