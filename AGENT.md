# AGENT.md

## 工作区分支规则

每个 Coding Agent 开始工作前，必须先读本文件，并创建专属工作区分支：

1. 基于最新 `main` 创建分支：`git switch main && git switch -c agent/<名称>-<YYYYMMDD>`
2. 命名格式：`agent/<名称>-<YYYYMMDD>`，`<名称>` 自取（如 `claude`）；重名则追加 `-2`、`-3`
3. 所有提交只在自己的分支进行，不直接提交 `main`
