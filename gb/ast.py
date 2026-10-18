"""GB 语法树节点定义。"""

from dataclasses import dataclass


# ---------------- 语句 ----------------

@dataclass
class Module:
    statements: list


@dataclass
class Let:
    name: str
    value: object


@dataclass
class Fun:
    name: str
    params: list           # list[str]
    body: list             # list[语句]


@dataclass
class Struct:
    name: str
    fields: list           # list[str]


@dataclass
class Return:
    value: object          # None 表示 return;


@dataclass
class Block:
    statements: list


@dataclass
class If:
    condition: object
    then_body: list
    else_body: object      # list 或 None


@dataclass
class While:
    condition: object
    body: list


@dataclass
class ForC:
    """C 风格 for：for (init; cond; update) body"""
    init: object           # Let / ExprStmt / None
    condition: object      # 表达式或 None
    update: object         # 表达式或 None
    body: list


@dataclass
class ForRange:
    """区间 for：for (let name in interval) body"""
    name: str
    interval: object       # Interval
    body: list


@dataclass
class Break:
    pass


@dataclass
class Continue:
    pass


@dataclass
class ExprStmt:
    expression: object


# ---------------- 表达式 ----------------

@dataclass
class Number:
    value: object          # int 或 float


@dataclass
class String:
    value: str


@dataclass
class Bool:
    value: bool


@dataclass
class Null:
    pass


@dataclass
class Array:
    elements: list


@dataclass
class Interval:
    """区间 for 专用，不是语言值"""
    start: object
    end: object
    left_inclusive: bool
    right_inclusive: bool


@dataclass
class Var:
    name: str


@dataclass
class Assign:
    target: object         # Var / Index / Get
    value: object


@dataclass
class Unary:
    op: str                # "-" 或 "not"
    operand: object


@dataclass
class Binary:
    op: str
    left: object
    right: object


@dataclass
class Logical:
    op: str                # "and" 或 "or"
    left: object
    right: object


@dataclass
class Call:
    callee: object
    args: list


@dataclass
class Index:
    object: object
    index: object


@dataclass
class Slice:
    object: object
    start: object
    end: object


@dataclass
class Get:
    object: object
    name: str
