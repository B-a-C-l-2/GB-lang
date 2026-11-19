# 给编程 Agent 的 GB 使用指南

目标：使用 GB 编写应用，不修改解释器。语言规则以 docs/design.md 为准。

## 工作流程
1. 阅读本指南及 README.md，确认需求能在现有功能中实现。
2. 用 struct 定义记录，用数组保存记录，用函数拆分交互和业务逻辑。
3. 在项目根目录运行 `python -m gb 路径/程序.gb`。
4. 为菜单准备固定输入，验证输出与退出码；运行 `python -m gb tests/selftest.gb`。
5. 保存真实开发记录与 Git 提交，不编造 Agent 对话或测试结果。

## 最小示例
```gb
struct Student { id, name, score }
let students = [];
push(students, Student(1, "小明", 85));
fun passed(s) { return s.score >= 60; }
for (let s in students) {
    if (passed(s)) { print(s.name, s.score); }
}
```

## 语法和数据
- let 必须有初值；语句用分号结束；块用花括号；注释用 //。
- 支持 int、float、bool、string、null、数组、struct。没有字典、类或 import。
- 字符串只用双引号，支持 \n、\t、\"、\\，不支持插值。
- 数组与 struct 按引用传递；字段固定；切片是浅拷贝。
- 下标从 0 开始，不允许负下标；切片两端必填，不支持步长。
- 函数声明会提升；let 不提升。函数可以递归和读取词法外层环境，但不能作为值传递。
- 用 return 返回一个值；不写 return 时返回 null。可用 struct 返回多个字段。

## 控制流与易错点
- if / else、while、C 风格 for；无 ++、+=，写 i = i + 1。
- 区间 for (let i in [1, 5]) 包含 1 和 5；步长固定 +1。
- 遍历数组先存入变量，特别是两元素数组：[1, 2] 在 for 头中会解释为区间。
- 数组遍历采用浅快照。删除任意位置可从该位置起左移元素，最后 pop。
- 只有 false、null 为假；0、空串、空数组为真。
- and/or 短路且返回布尔；not 优先级高；比较不要连写。
- / 总是返回 float；赋值先求右侧，再求左侧目标。

## 内建与输入验证
print、input、len、int、float、str、push、pop、is_int、is_float。
input 返回字符串；EOF 返回 null。先判 EOF，再判断格式，最后转换。
转换错误会终止程序，没有 try/catch；数值输入先用 is_int/is_float 检查。
分数等有范围约束的输入还要检查上下界。空数组 pop 会报错。
当前没有文件持久化、网络、随机数和时钟接口；应用应说明数据仅在本次运行有效。

## 自动黑盒测试
run_gb(source, stdin?) 返回含 stdout、stderr、exit_code 的实例。
测试源码和预期结果可直接写在 GB 字符串中；输入省略即 EOF。
子程序错误返回非零退出码，父测试继续。子程序超过 5 秒则接口报错。
GB 没有文件读取接口；对独立应用文件的端到端测试可用外部运行器提供 stdin。

## 诊断
错误分词法、语法、运行时三类，通常带行列号、源码和 ^。
先按位置修复，再重跑最小用例。不要为了应用便利修改语言语义。
