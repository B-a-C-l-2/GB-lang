# GB 语言设计（v0.1）

## 1. 目标与原则

一门解释型通用脚本语言，用于个人 demo。原则：**简单优先，不过度设计**。

## 2. 最终功能集（v0.1 范围）

- 基本类型：整数、浮点数、布尔、字符串、null
- 复合类型：动态数组、struct（纯数据结构）
- 基本输入输出：`print` / `input`
- 控制流：`if`/`else`、`while`、C 风格 `for`、`break`、`continue`
- 函数：定义、调用、词法闭包

## 3. 实现方式

- 宿主语言：Python 3（标准库，无第三方依赖）
- 架构：**树遍历解释器**，无字节码、无单独编译产物
- 流水线：源码 → 词法分析 → 语法分析（AST）→ 遍历求值
- 计划文件：

  ```
  gb/lexer.py        词法分析
  gb/ast.py          AST 节点
  gb/parser.py       语法分析
  gb/interpreter.py  求值、环境、运行时错误
  gb/builtins.py     内建函数
  gb/__main__.py     入口：python -m gb <file.gb>
  ```

- 词法/语法/运行时错误输出到 stderr，带行号，进程非零退出；语言本身无异常处理机制，运行时错误即终止

## 4. 词法规则

- 标识符：`[A-Za-z_][A-Za-z0-9_]*`
- 整数字面量：`[0-9]+`；浮点字面量：`[0-9]+\.[0-9]+`（小数点后必须有数字）
- 字符串：双引号，支持转义 `\" \\ \n \t`，其余转义为错误
- 注释：`//` 到行尾
- 语句以分号结束；空白与换行不影响语义（不做换行敏感语法）
- 关键字：`let fun return if else while for break continue struct true false null and or not`

## 5. 类型与运算

| 类型 | 字面量 | 要点 |
|---|---|---|
| int | `1` | 整数，精度随宿主（Python int） |
| float | `1.5` | 浮点 |
| bool | `true` `false` | |
| string | `"hi"` | 不可变 |
| null | `null` | 空值 |
| array | `[1, 2]` | 动态、异构、引用语义 |
| struct 实例 | `Point(1, 2)` | 字段固定，引用语义 |

- 算术：`+ - * %`；int 与 int 运算得 int，**`/` 永远得 float**（如 `3 / 2 == 1.5`），混合 int/float 得 float
- `+` 可用于字符串拼接；其余类型混用均为运行时错误（不做隐式转换）
- 比较：`== != < <= > >=`；数组按内容比较，struct 实例按身份比较
- 逻辑：`and or not`，短路求值；真假规则：仅 `false` 和 `null` 为假，其余皆真
- 无复合赋值、无自增自减；赋值只有 `=`

## 6. 语法（EBNF，已按优先级从低到高给出）

```
program    := statement*
statement  := letDecl | funDecl | structDecl | return | block
            | if | while | for | break | continue | exprStmt
letDecl    := 'let' IDENT '=' expr ';'                 // 必须有初值
funDecl    := 'fun' IDENT '(' params? ')' block
structDecl := 'struct' IDENT '{' IDENT (',' IDENT)* ','? '}'
return     := 'return' expr? ';'
block      := '{' statement* '}'
if         := 'if' expr block ('else' (if | block))?
while      := 'while' expr block
for        := 'for' '(' (letDecl | exprStmt)? ';' expr? ';' expr? ')' block
exprStmt   := expr ';'

expr       := assignment
assignment := (postfix '=')? expr                     // 左值须为变量/下标/字段
logic_or   := logic_and ('or' logic_and)*
logic_and  := equality ('and' equality)*
equality   := comparison (('=='|'!=') comparison)*
comparison := additive (('<'|'<='|'>'|'>=') additive)*
additive   := multiplicative (('+'|'-') multiplicative)*
multiplicative := unary (('*'|'/'|'%') unary)*
unary      := ('-'|'not') unary | postfix
postfix    := primary ('(' args? ')' | '[' expr ']' | '.' IDENT)*
primary    := NUMBER | STRING | 'true' | 'false' | 'null'
            | '[' (expr (',' expr)* ','?)? ']' | IDENT | '(' expr ')'
params     := IDENT (',' IDENT)*
args       := expr (',' expr)*
```

## 7. 语义要点

- **作用域**：`let` 为块级作用域，可嵌套遮蔽；给未声明变量赋值是错误
- **函数**：位置参数，实参数量必须匹配；无 `return` 或 `return;` 返回 `null`；函数词法捕获外层环境（闭包）；函数不是一等值（不能传参/赋值）
- **struct**：声明时给出字段名列表，编译器（解释器）自动生成同序位置构造函数；可访问/修改已声明字段，访问不存在的字段、构造参数数量不符均为运行时错误；struct 无方法、无继承
- **数组**：0 起始下标，负下标越界；下标必须为 int，越界为运行时错误

## 8. 内建函数

| 函数 | 说明 |
|---|---|
| `print(...)` | 输出任意个参数，空格分隔，末尾换行；字符串不加引号 |
| `input(prompt?)` | 可选提示语（不带换行），读取一行输入，返回去掉换行的字符串 |
| `len(x)` | 数组长度或字符串字符数（Unicode 码点） |
| `int(x)` / `float(x)` / `str(x)` | 类型转换；`int(float)` 向零取整，`int("12")` 解析字符串 |
| `push(arr, x)` | 数组末尾追加元素 |

## 9. 示例程序

```
struct Point { x, y }

fun dist2(p) {
    return p.x * p.x + p.y * p.y;
}

let p = Point(3, 4);
print("dist2 =", dist2(p));      // dist2 = 25

let a = [1, 2, 3];
push(a, 4);
for (let i = 0; i < len(a); i = i + 1) {
    if (a[i] % 2 == 0) {
        print(a[i], "even");
    } else {
        print(a[i], "odd");
    }
}
```

## 10. v0.1 明确不做

类/继承/方法、字典等其他容器、模块与 import、异常处理、匿名函数与高阶函数、复合赋值与自增、多返回值、REPL、负数下标。
