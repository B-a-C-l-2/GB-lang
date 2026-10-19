"""GB 语法树节点定义。

每个节点带 line/col（源码行列号，均从 1 开始），取该结构首 token 的
位置，用于错误定位；解析器不产生的节点（Module）为 0。
"""

from dataclasses import dataclass


# ---------------- 语句 ----------------

@dataclass
class Module:
    statements: list
    line: int = 0
    col: int = 0


@dataclass
class Let:
    name: str
    value: object
    line: int = 0
    col: int = 0


@dataclass
class Fun:
    name: str
    params: list           # list[str]
    body: list             # list[语句]
    line: int = 0
    col: int = 0


@dataclass
class Struct:
    name: str
    fields: list           # list[str]
    line: int = 0
    col: int = 0


@dataclass
class Return:
    value: object          # None 表示 return;
    line: int = 0
    col: int = 0


@dataclass
class Block:
    statements: list
    line: int = 0
    col: int = 0


@dataclass
class If:
    condition: object
    then_body: list
    else_body: object      # list 或 None
    line: int = 0
    col: int = 0


@dataclass
class While:
    condition: object
    body: list
    line: int = 0
    col: int = 0


@dataclass
class ForC:
    """C 风格 for：for (init; cond; update) body"""
    init: object           # Let / ExprStmt / None
    condition: object      # 表达式或 None
    update: object         # 表达式或 None
    body: list
    line: int = 0
    col: int = 0


@dataclass
class ForRange:
    """区间 for：for ((let) name in interval) body

    declare 为 True 时 name 是循环专用环境中的新变量；否则向外层赋值。
    name_line/name_col 指向标识符，用于无 let 时的赋值错误定位。
    """
    name: str
    interval: object       # Interval
    body: list
    declare: bool = True
    line: int = 0
    col: int = 0
    name_line: int = 0
    name_col: int = 0


@dataclass
class Break:
    line: int = 0
    col: int = 0


@dataclass
class Continue:
    line: int = 0
    col: int = 0


@dataclass
class ExprStmt:
    expression: object
    line: int = 0
    col: int = 0


# ---------------- 表达式 ----------------

@dataclass
class Number:
    value: object          # int 或 float
    line: int = 0
    col: int = 0


@dataclass
class String:
    value: str
    line: int = 0
    col: int = 0


@dataclass
class Bool:
    value: bool
    line: int = 0
    col: int = 0


@dataclass
class Null:
    line: int = 0
    col: int = 0


@dataclass
class Array:
    elements: list
    line: int = 0
    col: int = 0


@dataclass
class Interval:
    """区间 for 专用，不是语言值"""
    start: object
    end: object
    left_inclusive: bool
    right_inclusive: bool
    line: int = 0
    col: int = 0


@dataclass
class Var:
    name: str
    line: int = 0
    col: int = 0


@dataclass
class Assign:
    target: object         # Var / Index / Get
    value: object
    line: int = 0
    col: int = 0


@dataclass
class Unary:
    op: str                # "-" 或 "not"
    operand: object
    line: int = 0
    col: int = 0


@dataclass
class Binary:
    op: str
    left: object
    right: object
    line: int = 0
    col: int = 0


@dataclass
class Logical:
    op: str                # "and" 或 "or"
    left: object
    right: object
    line: int = 0
    col: int = 0


@dataclass
class Call:
    callee: object
    args: list
    line: int = 0
    col: int = 0


@dataclass
class Index:
    object: object
    index: object
    line: int = 0
    col: int = 0


@dataclass
class Slice:
    object: object
    start: object
    end: object
    line: int = 0
    col: int = 0


@dataclass
class Get:
    object: object
    name: str
    line: int = 0
    col: int = 0
