# GB 语言

一门解释型通用脚本语言（个人 demo）。完整设计见 [`docs/design.md`](docs/design.md)，本文件只帮你快速上手。

## 运行环境

- Python 3（无第三方依赖）
- 运行程序（在项目根目录）：

  ```bash
  python -m gb examples/example.gb
  ```

  GB 源文件后缀约定为 `.gb`。

## 5 分钟语法速览

```
// 注释以 // 开始；语句以分号结束

let n = 10;                 // 变量（必须有初值，块级作用域）
let pi = 3.14;
let s = "hello";
let a = [1, 2, 3];          // 数组
let p = Point(3, 4);        // struct 实例（见下）

print(a[0]);                // 下标从 0 开始；a[0:2] 是切片 [1, 2]
print(s[1:4]);              // 字符串也可下标和切片：ell

if (n > 5) { print("big"); } else { print("small"); }

while (n > 0) { n = n - 1; }

for (let i = 0; i < 3; i = i + 1) { print(i); }   // C 风格 for
for (let i in [1, 5]) { print(i); }               // 区间 for：1..5
// 两种 for 的循环变量都可省略 let，改为逐轮写入外层已有变量：
//   let i = 0; for (i in [1, 5]) { }   循环后 i == 5（变量须已 let 过）
// 四种区间：[1,5] 1..5 | [1,5) 1..4 | (0,5] 1..5 | (0,5) 1..4

fun add(a, b) { return a + b; }   // 函数（声明提升：支持前向调用、递归与相互递归）

struct Point { x, y }             // 纯数据结构，自动生成 Point(x, y)
fun dist2(p) { return p.x * p.x + p.y * p.y; }

print("len =", len(a));           // 内建：print input len int float str push pop
let name = input("name? ");       // 读取一行输入；遇 EOF 返回 null
```

运算要点：`/` 永远得到浮点数（`3 / 2 == 1.5`）；`%` 同 Python（余数随除数）；只有 `false` 和 `null` 为假（`0`、`""`、空数组都为真）；没有 `++`、`+=`，自增写成 `i = i + 1`；`and`/`or` 短路且结果恒为布尔。

## 自带示例

```bash
python -m gb examples/example.gb      # 功能巡礼：struct、区间 for、切片
python -m gb examples/fizzbuzz.gb     # FizzBuzz
python -m gb examples/fibonacci.gb    # 数组 + push + 区间 for
```

## 自己动手（建议练习）

1. **打招呼**：用 `input` 读入名字，输出 `hello, 名字`。
2. **素数表**：写 `fun isPrime(n)`，打印 `[1, 30]` 中的全部素数（提示：`while` 试除到 `d * d > n`）。
3. **成绩判定**：自定义 `struct Score { name, value }`，用数组装几条成绩，遍历并打印 value ≥ 60 的名字。

## 报错怎么看

- 词法/语法/运行时错误都输出到 stderr，**带行列号和出错源码行**，退出码非 0，例如：

  ```
  运行时错误（第 2 行，第 7 列）：下标越界
  print(a[5]);
        ^
  ```

  语法错误还会指出实际遇到的 token（文件末尾时显示「文件末尾」）。

- 运行时错误发生在函数调用中时，会在下方附加最近至多 5 帧调用栈（由近及远）：

  ```
  运行时错误（第 1 行，第 22 列）：除数为零
  fun inner() { return 1 / 0; }
                     ^
    在 inner（第 2 行，第 22 列）调用
    在 outer（第 3 行，第 7 列）调用
  ```

- 常见坑：漏分号；给未 `let` 的变量赋值；用浮点数当下标；省略 `let` 的区间 for 变量必须是外层已声明的变量。
- `fun`/`struct` 声明会被提升到所在作用域开头，因此可以前向调用和相互递归；但 `let` 不提升。内建函数名（如 `len`）可用同名声明遮蔽，不能裸赋值改写。

## 开发与测试

```bash
python -m unittest discover -s tests    # 运行全部测试
```

源码结构：`gb/lexer.py`（词法）→ `gb/ast.py`（语法树）→ `gb/parser.py`（语法）→ `gb/interpreter.py`（求值）→ `gb/builtins.py`（内建），入口 `gb/__main__.py`。
