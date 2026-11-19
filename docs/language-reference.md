# GB 语言语法与使用规范

适用范围：当前 GB 实现（v0.4.6 功能及 run_gb 测试扩展）。本文为独立的语言规则文档，说明当前有效语法和语义，不包含历史方案讨论。

## 1. 源文件与词法

源文件约定后缀 `.gb`，使用 UTF-8（可带 BOM）。标识符区分大小写，形式为 `[A-Za-z_][A-Za-z0-9_]*`。中文可用于字符串和注释，不能用于标识符。

- 整数字面量：`[0-9]+`；浮点字面量：`[0-9]+\.[0-9]+`。负号属于一元运算符。没有科学计数法。
- 字符串用双引号，支持 `\"`、`\\`、`\n`、`\t`，不能直接跨行；其他转义报错。
- `//` 注释到行尾；空白和换行用于分隔，不决定语句边界。
- 声明变量、表达式、return、break、continue 以分号结束；函数、结构体和控制块不另加分号。
- 关键字：`let fun return if else while for in break continue struct true false null and or not`。
- print 等内建名称是普通标识符，不是关键字。

## 2. 语法（EBNF）

引号内为终结符；`?` 表示可选，`*` 表示重复零次或多次，`|` 表示选择。
NUMBER 和 STRING 由词法规则产生。此处描述结构，赋值左值、重名参数等约束见后文。

```text
program        := statement* EOF
statement      := letDecl | funDecl | structDecl | returnStmt | block
                | ifStmt | whileStmt | forStmt | breakStmt | continueStmt | exprStmt
letDecl        := 'let' IDENT '=' expr ';'
funDecl        := 'fun' IDENT '(' params? ')' block
structDecl     := 'struct' IDENT '{' IDENT (',' IDENT)* ','? '}'
returnStmt     := 'return' expr? ';'
breakStmt      := 'break' ';'
continueStmt   := 'continue' ';'
block          := '{' statement* '}'
ifStmt         := 'if' expr block ('else' (ifStmt | block))?
whileStmt      := 'while' expr block
forStmt        := cStyleFor | forIn
cStyleFor      := 'for' '(' forInit expr? ';' expr? ')' block
forInit        := letDecl | exprStmt | ';'
forIn          := 'for' '(' 'let'? IDENT 'in' (interval | expr) ')' block
interval       := ('[' | '(') expr ',' expr (']' | ')')
exprStmt       := expr ';'
expr           := assignment
assignment     := logic_or ('=' assignment)?
logic_or       := logic_and ('or' logic_and)*
logic_and      := equality ('and' equality)*
equality       := comparison (('==' | '!=') comparison)*
comparison     := additive (('<' | '<=' | '>' | '>=') additive)*
additive       := multiplicative (('+' | '-') multiplicative)*
multiplicative := unary (('*' | '/' | '%') unary)*
unary          := ('-' | 'not') unary | postfix
postfix        := primary ('(' args? ')' | '[' expr (':' expr)? ']' | '.' IDENT)*
primary        := NUMBER | STRING | 'true' | 'false' | 'null' | IDENT
                | '[' (expr (',' expr)* ','?)? ']' | '(' expr ')'
params         := IDENT (',' IDENT)*
args           := expr (',' expr)*
```

C 风格 for 总共只有两个分号；forInit 已包含第一个。赋值左侧必须是变量、下标或字段，切片不能赋值。赋值右结合，其余二元运算在同级内左结合。数组及 struct 字段允许尾逗号，函数参数和调用实参不允许。struct 至少一个字段，字段不能重名；函数参数不能重名。

`forIn` 的区间和表达式存在形状歧义：若 in 后能解析为区间，且后面立即是 for 头的右括号，优先作为区间；否则按表达式解析。例如 `[1, 2]` 是区间，而 `[1, 2][0:1]` 是数组表达式。遍历两元素数组应先赋给变量。

## 3. 类型与运算

| 类型 | 示例 | 规则 |
|---|---|---|
| int | `42` | 整数，使用 Python 整数精度 |
| float | `2.5` | 浮点数，非有限结果报错 |
| bool | `true`、`false` | 不隐式当作数字 |
| string | `"hello"` | 不可变，按 Unicode 码点索引 |
| null | `null` | 空值 |
| array | `[1, "x"]` | 动态、可变、可混合元素类型 |
| struct 实例 | `Point(3, 4)` | 可变，字段固定 |

算术 `+ - * / %` 只接受数值；`+` 还接受两个字符串。int 与 int 的 `+ - * %` 得 int，混合 float 得 float；`/` 总得 float。除零和对零取模报错。`%` 的余数符号随除数，如 `-7 % 3 == 2`。不能用 `+` 拼接数组，不存在隐式字符串转换。

数值 int/float 按值相等；bool 与数字不同；字符串按内容相等；数组逐元素递归比较内容；struct 按实例身份比较。其他跨类型相等为 false，不等为 true。`null` 只等于自身。大小比较支持数值、字符串及可比较元素组成的数组（字典序），不支持 struct 的大小比较或任意跨类型排序。

优先级从低到高：`=`、`or`、`and`、`== !=`、`< <= > >=`、`+ -`、`* / %`、一元 `- not`、调用/下标/字段。

只有 false 和 null 为假，0、空字符串、空数组都为真。and/or 短路且恒返回 bool。`not a == b` 等价于 `(not a) == b`；比较不可按数学方式连写，`1 < 2 < 3` 会先得到 bool 再与 3 比较并报错。

通常按从左到右求值，包括二元操作数、实参和数组元素。赋值先计算右侧，再计算目标对象和下标，最后写入；赋值表达式返回所赋的值。

## 4. 变量、函数与作用域

`let x = expr;` 声明块级变量，必须初始化。内层可遮蔽外层，同层不能重复声明；赋值不自动声明变量。

```gb
let x = 1;
{ let x = 2; print(x); }
print(x); // 1
fun add(a, b) { return a + b; }
print(add(2, 3)); // 5
```

进入模块、函数体或块时，先注册该层直接包含的 fun 和 struct，再执行语句。它们支持前向调用及相互递归；let 不提升。内层声明不会被提升到外层。

函数使用词法作用域，可读写定义位置的外层变量；参数绑定在函数体块外的一层环境，因此函数体内同名 let 是遮蔽参数。位置参数个数必须匹配，无默认参数；无 return 或 `return;` 返回 null。return 只能在函数中使用。

函数、内建函数和 struct 构造器不是可传递的一等值，不能赋给变量或当实参传递。内建名称可被用户声明遮蔽，但不能直接赋值改写。

## 5. 数组、字符串与结构体

```gb
struct Point { x, y }
let p = Point(3, 4);
p.x = 8;
let a = [1, 2, 3];
a[0] = 9;
print(a[1:3]); // [2, 3]
print("hello"[1:4]); // ell
```

构造器实参按字段声明顺序传入，数量必须一致；字段不能新增或删除。数组和 struct 为引用语义，赋值和传参不会复制对象。

下标必须是 int（不接受 bool），从 0 开始，负数或越界报错；字符串下标返回单字符字符串且不可赋值。
切片 `[a:b]` 左闭右开，两端均必填、必须是非负 int；超过长度的端点截到长度，a >= b 得空结果。数组切片生成新数组但只浅拷贝，内部数组/struct 仍共享引用。

不应构造循环引用。写入时不遍历检测；显示或比较递归遍历中检测到环会报错。

## 6. 分支和循环

```gb
let n = 3;
if (n > 0) { print("positive"); } else { print("other"); }
while (n > 0) { n = n - 1; }
for (let i = 0; i < 3; i = i + 1) { print(i); }
for (let i in (0, 3]) { print(i); }
let values = [10, 20];
for (let x in values) { print(x); }
```

if/while 条件可省略外围圆括号，分支和循环体必须用花括号。else 可接 if。C 风格 for 可省略初始化、条件或更新，省略条件视为真。

| 区间 | 取值 |
|---|---|
| `[a,b]` | a 到 b |
| `[a,b)` | a 到 b-1 |
| `(a,b]` | a+1 到 b |
| `(a,b)` | a+1 到 b-1 |

端点在循环前各计算一次，必须是 int；固定步长 +1，换算后起点大于终点则零次循环。区间不是可保存的语言值。

for 中有 let 时创建循环专用变量，外部不可见；省略 let 则向外层已声明变量赋值。
区间 for 无 let 时先赋换算后的起点，即使零次循环也保留该值；非空循环结束保留最后一次赋入的值。
数组 for 无 let 时逐轮赋值，空数组不进行赋值。

数组遍历在循环前浅拷贝一次；push/pop/替换原数组元素不改变本轮序列，修改共享元素内部仍可见。字符串不能用于 for-in。
break 退出最近的循环；continue 跳过本轮剩余语句（C 风格 for 仍执行更新）。两者不能跨函数边界作用于调用者的循环。

## 7. 内建函数

| 调用 | 行为 |
|---|---|
| `print(...)` | 任意个参数，空格分隔、末尾换行，返回 null |
| `input(prompt?)` | 可选字符串提示语，无换行；读取一行，去掉行尾换行；EOF 返回 null |
| `len(x)` | 数组元素数或字符串码点数 |
| `int(x)` | 数值转整数（浮点向零截断）或解析整数字符串 |
| `float(x)` | 数值转浮点或解析数值字符串 |
| `str(x)` | 按输出格式转换为字符串 |
| `push(arr,x)` | 末尾追加元素，返回 null |
| `pop(arr)` | 删除并返回末尾元素，空数组报错 |
| `is_int(x)` | 探测 int(x) 转换能否成功，不是类型判断 |
| `is_float(x)` | 探测 float(x) 转换能否成功，不是类型判断 |
| `run_gb(source,stdin?)` | 独立执行 GB 源码字符串并捕获结果 |

int/float 不接受 bool、null、数组、struct。转换字符串允许可选前导负号，int 只接受数字序列，float 接受整数形式或带小数点的形式；不接受空白、前导加号、科学计数法、全角数字、下划线、inf/nan。错误转换会终止程序，先用 is_int/is_float 探测；例如 is_int(2.9) 为 true，而 is_int("2.9") 为 false。参数自身的求值错误不会被探测函数吞掉。

print 和 str 的格式一致：null、true/false、小数保留浮点显示、字符串不加引号、数组 `[1, 2]`、结构体 `Point(3, 4)`。

run_gb 两个参数必须是字符串；stdin 默认空串，即立即 EOF。返回实例包含 stdout、stderr 字符串和整数 exit_code，不提供可直接调用的 RunResult 构造器。输出用 UTF-8 解码，换行归一为 `\n`。被测程序错误通过结果返回，父脚本继续；超时 5 秒、参数错误或启动失败在父脚本报错。子进程工作目录为项目根目录，不提供沙箱。

## 8. 错误与功能边界

先解析完整文件，再开始执行；任何位置的语法错误都会阻止整个文件执行。运行时错误终止当前程序。
正常退出码为 0，语言错误通常为 1，Ctrl+C 为 130。诊断写入 stderr，通常包含 1 起始行列号、源码行和 ^；列号按字符数，显示指针按字符宽度对齐。函数错误附最近至多 5 帧调用栈；文件读取错误和部分深度错误无源码位置。

没有类/继承/方法、字典、import、try/catch、匿名或高阶函数、多返回值、REPL、复合赋值、自增自减、负下标、省略端点切片、切片步长、倒序区间。当前未提供文件持久化、网络、随机数或时钟内建。
