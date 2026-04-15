# 贡献指南 (CONTRIBUTING)

感谢参与 AI 审核项目！提交代码前请阅读本指南。

## 流程速览

1. **Fork / 拉取最新 main** → 新建 `feature/<del-编号>-<简述>` 分支
2. **本地开发 + 自检**：`pre-commit run --all-files && pytest`
3. **提交**：commit 消息必须符合 [git-workflow.md](docs/git-workflow.md#2-提交消息规范)
4. **开 PR**：模板会自动加载，填写自检清单
5. **等待检查**：8 项 CI + CodeRabbit AI 审查 + 至少 1 个人工审查
6. **合并**：所有检查绿灯后由 Reviewer 通过 squash/rebase 合并

## 不接受的 PR

- ❌ 直接 push 到 `main`（会被 branch protection 阻止）
- ❌ commit 消息不符合规范
- ❌ 覆盖率 < 70% 或关键逻辑无测试
- ❌ Bandit / pip-audit / TruffleHog 有未解决的高危警告
- ❌ 包含密钥、凭证、真实业务数据
- ❌ 禁用 pre-commit 钩子（`--no-verify` 不被接受）

## 详细说明

请参阅 [docs/git-workflow.md](docs/git-workflow.md)。
