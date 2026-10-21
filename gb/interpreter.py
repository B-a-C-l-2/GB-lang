"""GB 树遍历解释器：遍历 AST 求值。"""

import sys

from gb import ast

# v0.3.1：默认 1000 的宿主递归上限对深层数据（如千层嵌套数组的
# 显示/比较，每层消耗数帧）过于拮据，提高到 10000；GB 函数递归
# 深度上限也随之升至约千层
sys.setrecursionlimit(10000)
from gb.builtins import (
    BUILTINS, Builtin, Function, StructDef, Instance, GbError,
)


def _binding_kind(value):
    """重复声明报错时已有绑定的种类名称。"""
    if isinstance(value, Function):
        return "函数"
    if isinstance(value, StructDef):
        return "struct"
    return "变量"


class Environment:
    """作用域帧。read_only 帧（内建外层）可读、可遮蔽，不能赋值改写。"""

    __slots__ = ("vars", "parent", "read_only")

    def __init__(self, parent=None, read_only=False):
        self.vars = {}
        self.parent = parent
        self.read_only = read_only

    def declare(self, name, value, line=0, col=0):
        if name in self.vars:
            raise GbError(
                f"名字 {name} 已声明为{_binding_kind(self.vars[name])}，"
                f"不能在当前作用域重复声明", line, col)
        self.vars[name] = value

    def get(self, name, line=0, col=0):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise GbError(f"变量 {name} 未定义", line, col)

    def assign(self, name, value, line=0, col=0):
        env = self
        while env is not None:
            if name in env.vars:
                if env.read_only:
                    break  # 内建帧不可写：按未定义赋值处理，促使先 let
                env.vars[name] = value
                return
            env = env.parent
        raise GbError(f"变量 {name} 未定义，无法赋值", line, col)


def make_global_env():
    # 内建位于全局用户环境之外的只读外层帧
    builtin_env = Environment(read_only=True)
    for name, builtin in BUILTINS.items():
        builtin_env.vars[name] = builtin
    return Environment(builtin_env)


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


def _gb_equal(a, b, line=0, col=0, _seen=None):
    if a is None:
        return b is None
    if isinstance(a, bool):
        return isinstance(b, bool) and a == b
    if _is_num(a):
        return _is_num(b) and a == b
    if isinstance(a, str):
        return isinstance(b, str) and a == b
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            return False
        # v0.3.1：禁止循环引用。_seen 记录递归路径上的 (id(a), id(b))
        # 对，再次遇到同一对即成环；菱形共享不受影响
        if _seen is None:
            _seen = set()
        pair = (id(a), id(b))
        if pair in _seen:
            raise GbError("存在循环引用，无法比较", line, col)
        _seen.add(pair)
        try:
            return all(_gb_equal(x, y, line, col, _seen)
                       for x, y in zip(a, b))
        finally:
            _seen.discard(pair)
    # struct 实例与函数值：身份比较
    return a is b


def _gb_compare(a, b, line, col, _seen=None):
    """有序比较，返回 -1/0/1；不可比较则运行时错误。"""
    if _is_num(a) and _is_num(b):
        return (a > b) - (a < b)
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    if isinstance(a, list) and isinstance(b, list):
        # v0.3.1：禁止循环引用，同 _gb_equal
        if _seen is None:
            _seen = set()
        pair = (id(a), id(b))
        if pair in _seen:
            raise GbError("存在循环引用，无法比较", line, col)
        _seen.add(pair)
        try:
            for x, y in zip(a, b):
                c = _gb_compare(x, y, line, col, _seen)
                if c != 0:
                    return c
        finally:
            _seen.discard(pair)
        return (len(a) > len(b)) - (len(a) < len(b))
    raise GbError("这两个类型的值不能使用大小比较", line, col)


class Interpreter:
    def __init__(self, global_env=None):
        self.env = global_env if global_env is not None else make_global_env()
        self.loop_depth = 0
        self.function_depth = 0
        # 调用栈帧：(函数名, 调用点行, 调用点列)，用于错误诊断（v0.3）
        self.call_stack = []

    def run(self, module):
        self._hoist(module.statements, self.env)
        for stmt in module.statements:
            self._exec(stmt, self.env)

    def _hoist(self, statements, env):
        """进入作用域时先注册本层直接包含的 fun/struct（声明提升）。"""
        for node in statements:
            t = type(node)
            if t is ast.Fun:
                env.declare(node.name,
                            Function(node.name, node.params, node.body,
                                     env, node.line),
                            node.line, node.col)
            elif t is ast.Struct:
                env.declare(node.name,
                            StructDef(node.name, node.fields, node.line),
                            node.line, node.col)

    # ---------- 语句 ----------

    def _exec(self, node, env):
        t = type(node)

        if t is ast.Let:
            env.declare(node.name, self._eval(node.value, env),
                        node.line, node.col)

        elif t is ast.Fun or t is ast.Struct:
            # 已在进入作用域时提升注册，执行到声明语句无需再做任何事
            pass

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

        elif t is ast.ForIn:
            it = node.iterable

            loop_env = Environment(env)
            if node.declare:
                # let：循环专用环境中的块级变量
                loop_env.declare(node.name, None,
                                 node.name_line, node.name_col)

                def bind(v):
                    loop_env.vars[node.name] = v
            else:
                # 无 let：向外层已声明变量赋值；未声明时报错位置指向变量名
                def bind(v):
                    env.assign(node.name, v,
                               node.name_line, node.name_col)

            if type(it) is ast.Interval:
                start = self._eval(it.start, env)
                end = self._eval(it.end, env)
                if not _is_num(start) or isinstance(start, float) \
                        or not _is_num(end) or isinstance(end, float):
                    raise GbError("区间端点必须是 int", it.line, it.col)
                lo = start if it.left_inclusive else start + 1
                hi = end if it.right_inclusive else end - 1
                values = range(lo, hi + 1)
                if not node.declare:
                    # 区间 for 无 let：先赋起点（与 C 风格 for 的初始化
                    # 子句一致），即使循环零次
                    bind(lo)
            else:
                # v0.4 数组遍历：快照遍历——循环前浅拷贝，循环体内的
                # push/pop/清空不影响本轮的元素序列与轮数
                arr = self._eval(it, env)
                if not isinstance(arr, list):
                    raise GbError("for 只能遍历区间或数组",
                                  it.line, it.col)
                values = list(arr)

            self.loop_depth += 1
            try:
                for v in values:
                    bind(v)
                    try:
                        self._exec_body(node.body, loop_env)
                    except _Continue:
                        pass
            except _Break:
                pass
            finally:
                self.loop_depth -= 1

        elif t is ast.Return:
            if self.function_depth == 0:
                raise GbError("return 只能出现在函数中", node.line, node.col)
            value = None if node.value is None else self._eval(
                node.value, env)
            raise _Return(value)

        elif t is ast.Break:
            if self.loop_depth == 0:
                raise GbError("break 只能出现在循环中", node.line, node.col)
            raise _Break()

        elif t is ast.Continue:
            if self.loop_depth == 0:
                raise GbError("continue 只能出现在循环中",
                              node.line, node.col)
            raise _Continue()

        elif t is ast.ExprStmt:
            self._eval(node.expression, env)

        else:
            raise GbError(f"未知语句 {type(node).__name__}")

    def _exec_body(self, statements, parent_env):
        env = Environment(parent_env)
        self._hoist(statements, env)
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
            value = env.get(node.name, node.line, node.col)
            if not as_callee and isinstance(
                    value, (Function, Builtin, StructDef)):
                kind = ("struct" if isinstance(value, StructDef)
                        else "函数")
                raise GbError(
                    f"{node.name} 是{kind}，不能作为值传递或赋值",
                    node.line, node.col)
            return value

        if t is ast.Assign:
            return self._assign(node, env)

        if t is ast.Unary:
            v = self._eval(node.operand, env)
            if node.op == "-":
                if not _is_num(v):
                    raise GbError("一元减号只能用于数值",
                                  node.line, node.col)
                return -v
            return not _truthy(v)

        if t is ast.Binary:
            return self._binary(node, env)

        if t is ast.Logical:
            # v0.3：and/or 短路求值，结果恒为布尔（借鉴 Java）
            left = self._eval(node.left, env)
            if node.op == "and":
                return _truthy(left) and _truthy(
                    self._eval(node.right, env))
            return _truthy(left) or _truthy(self._eval(node.right, env))

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
                              node.line, node.col)
            if node.name not in obj.struct.fields:
                raise GbError(
                    f"{obj.struct.name} 没有字段 {node.name}",
                    node.line, node.col)
            return obj.values[node.name]

        raise GbError(f"未知表达式 {type(node).__name__}")

    def _binary(self, node, env):
        op = node.op
        a = self._eval(node.left, env)
        b = self._eval(node.right, env)
        line, col = node.line, node.col

        if op == "+":
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            if _is_num(a) and _is_num(b):
                return a + b
            raise GbError("+ 只能用于数值或两个字符串", line, col)
        if op in ("-", "*"):
            if _is_num(a) and _is_num(b):
                return a - b if op == "-" else a * b
            raise GbError(f"{op} 只能用于数值", line, col)
        if op == "/":
            if _is_num(a) and _is_num(b):
                if b == 0:
                    raise GbError("除数为零", line, col)
                return a / b
            raise GbError("/ 只能用于数值", line, col)
        if op == "%":
            if _is_num(a) and _is_num(b):
                if b == 0:
                    raise GbError("对零取模", line, col)
                return a % b
            raise GbError("% 只能用于数值", line, col)
        if op == "==":
            return _gb_equal(a, b, line, col)
        if op == "!=":
            return not _gb_equal(a, b, line, col)
        if op in ("<", "<=", ">", ">="):
            c = _gb_compare(a, b, line, col)
            return {"<": c < 0, "<=": c <= 0,
                    ">": c > 0, ">=": c >= 0}[op]
        raise GbError(f"未知运算符 {op}", line, col)

    def _assign(self, node, env):
        target = node.target
        value = self._eval(node.value, env)
        t = type(target)
        if t is ast.Var:
            env.assign(target.name, value, target.line, target.col)
        elif t is ast.Index:
            obj = self._eval(target.object, env)
            idx = self._eval(target.index, env)
            if isinstance(obj, str):
                raise GbError("字符串不可变，不能修改其字符",
                              target.line, target.col)
            if not isinstance(obj, list):
                raise GbError("只能对数组元素赋值",
                              target.line, target.col)
            if not _is_num(idx) or isinstance(idx, float):
                raise GbError("数组下标必须是 int",
                              target.line, target.col)
            if not 0 <= idx < len(obj):
                raise GbError("数组下标越界", target.line, target.col)
            obj[idx] = value
        elif t is ast.Get:
            obj = self._eval(target.object, env)
            if not isinstance(obj, Instance):
                raise GbError("只能给 struct 实例的字段赋值",
                              target.line, target.col)
            if target.name not in obj.struct.fields:
                raise GbError(
                    f"{obj.struct.name} 没有字段 {target.name}",
                    target.line, target.col)
            obj.values[target.name] = value
        else:
            raise GbError("赋值目标非法", node.line, node.col)
        return value

    def _check_int_index(self, idx, line, col):
        if not _is_num(idx) or isinstance(idx, float):
            raise GbError("下标必须是 int", line, col)

    def _index(self, node, env):
        obj = self._eval(node.object, env)
        idx = self._eval(node.index, env)
        if not isinstance(obj, (list, str)):
            raise GbError("只有数组和字符串可以索引", node.line, node.col)
        self._check_int_index(idx, node.line, node.col)
        if not 0 <= idx < len(obj):
            raise GbError("下标越界", node.line, node.col)
        return obj[idx]

    def _slice(self, node, env):
        obj = self._eval(node.object, env)
        start = self._eval(node.start, env)
        end = self._eval(node.end, env)
        if not isinstance(obj, (list, str)):
            raise GbError("只有数组和字符串可以切片", node.line, node.col)
        self._check_int_index(start, node.line, node.col)
        self._check_int_index(end, node.line, node.col)
        length = len(obj)
        # v0.4.1：负端点为运行时错误（原先静默钳到 0，与「不支持负
        # 下标」矛盾）；正越界端点仍钳制到 len
        if start < 0 or end < 0:
            raise GbError("切片端点不能为负", node.line, node.col)
        lo = min(start, length)
        hi = min(end, length)
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
                    f"实际 {n} 个", node.line, node.col)
            call_env = Environment(callee.closure)
            for name, value in zip(callee.params, args):
                call_env.declare(name, value)
            # 函数边界重置 loop_depth：break/continue 不能跨函数逃逸
            saved_loop_depth = self.loop_depth
            self.loop_depth = 0
            self.function_depth += 1
            self.call_stack.append((callee.name, node.line, node.col))
            try:
                self._exec_body(callee.body, call_env)
            except _Return as ret:
                return ret.value
            except (GbError, RecursionError) as e:
                # 最内层帧快照完整调用栈，供入口打印诊断（v0.3）
                if getattr(e, "gb_frames", None) is None:
                    e.gb_frames = list(self.call_stack)
                raise
            finally:
                self.function_depth -= 1
                self.loop_depth = saved_loop_depth
                self.call_stack.pop()
            return None

        if isinstance(callee, Builtin):
            callee.check_arity(n, node.line, node.col)
            try:
                return callee.fn(args)
            except GbError as e:
                if not e.line:
                    e.line = node.line
                    e.col = node.col
                raise

        if isinstance(callee, StructDef):
            if n != len(callee.fields):
                raise GbError(
                    f"构造 {callee.name} 需要 {len(callee.fields)} 个参数，"
                    f"实际 {n} 个", node.line, node.col)
            return Instance(callee, dict(zip(callee.fields, args)))

        raise GbError("该值不是可调用对象", node.line, node.col)
