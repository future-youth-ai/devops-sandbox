# Git 工作流 & 分支保护

本项目采用 **Trunk-based + 保护主干** 的工作流，所有变更必须通过 Pull Request 进入 `main`。

## 1. 分支模型

```
main        ── 保护主干, 永远可部署, 禁止直接 push
 ├─ develop ── (可选) 集成分支
 └─ feature/<del-编号>-<简述>   e.g. feature/del-04-pdf-parser
    fix/<issue-id>-<简述>
    hotfix/<简述>
    chore/<简述>
```

## 2. 提交消息规范

所有 commit 消息必须匹配以下格式之一（PR 的 Commit Lint 作业会强制校验）：

| 类型 | 格式 | 示例 | 触发飞书 |
|---|---|---|---|
| 交付物完成 | `[DEL-xx] 描述` | `[DEL-04] 文档解析器 v1.0 完成` | ✅ 表格 + 群消息 |
| 里程碑达成 | `[DEL-xx][MVP\|UAT] 描述` | `[DEL-07][MVP] AI审核引擎端到端可运行` | 🏁 里程碑通知 |
| 阶段完成 | `[PHASE-x] 描述` | `[PHASE-1] Phase 1 全部交付完成` | 📦 阶段通知 |
| 普通提交 | `<type>: 描述` | `feat: 添加 PDF 表格提取功能` | ❌ 不触发 |

`type` 允许值：`feat, fix, docs, style, refactor, perf, test, chore, build, ci, revert`。

## 3. CI 流水线 (`.github/workflows/ci.yml`)

PR 必须通过以下 **8 个检查** 才能合并：

| # | 名称 | 工具 | 触发 | 失败处理 |
|---|---|---|---|---|
| 1 | Lint | Ruff | Push / PR | 本地 `ruff check --fix && ruff format` |
| 2 | Type Check | mypy | Push / PR | 修正类型注解 |
| 3 | Commit Lint | `scripts/commit_lint.py` | PR only | 用 `git rebase -i` 修正 commit 消息 |
| 4 | Test | pytest + cov (≥70%) | Lint 通过后 | 补充测试或修复用例 |
| 5 | Security SAST | Bandit | Push / PR | 按 SARIF 报告修复高危 |
| 6 | Security SCA | pip-audit + TruffleHog | Push / PR | 升级依赖 / 立即吊销泄露密钥 |
| 7 | AI Review | CodeRabbit (GitHub App) | PR only | 按 AI 评论修改 |
| 8 | Auto Label + 飞书 | labeler + `sync_feishu.py` | PR / Push to main | 自动完成 |

## 4. 必须在 GitHub 上配置的分支保护规则

> ⚠️ 以下规则无法通过代码配置，必须在仓库 **Settings → Branches → Branch protection rules** 中手动开启。

针对 `main`（和 `develop` 若使用）：

```
Branch name pattern: main

[x] Require a pull request before merging
    [x] Require approvals: 1            (至少 1 个 reviewer)
    [x] Dismiss stale pull request approvals when new commits are pushed
    [x] Require review from Code Owners
    [x] Require approval of the most recent reviewable push

[x] Require status checks to pass before merging
    [x] Require branches to be up to date before merging
    Required checks:
      - Lint (Ruff)
      - Type Check (mypy)
      - Commit Lint
      - Test (pytest)
      - Security SAST (Bandit)
      - Security SCA (pip-audit + TruffleHog)
      - CI Gate
      - CodeRabbit              (安装 GitHub App 后出现)

[x] Require conversation resolution before merging
[x] Require signed commits                 (可选)
[x] Require linear history                 (禁止 merge commit, 强制 rebase/squash)
[x] Do not allow bypassing the above settings
[x] Restrict who can push to matching branches   (仅允许 Admin + bot)

[ ] Allow force pushes                     (保持关闭)
[ ] Allow deletions                        (保持关闭)
```

## 5. CodeRabbit AI 代码审查

1. 安装 CodeRabbit GitHub App：<https://github.com/marketplace/coderabbitai>
2. 授权目标仓库。
3. 配置文件 `.coderabbit.yaml` 已按本项目定制：
   - **安全最高优先级**：OWASP Top 10 / 硬编码凭证 / 政府项目数据隔离
   - **RAG 管道质量**：Embedding 维度、Reranker 超时、Prompt 注入
   - **性能**：N+1 查询、async 阻塞、大文档内存控制
   - **业务逻辑**：审核状态机、三重防幻觉、法规条款匹配

## 6. 必须的 GitHub Secrets

在 **Settings → Secrets and variables → Actions** 添加：

| Secret | 用途 | 必需 |
|---|---|---|
| `FEISHU_APP_ID` | 飞书自建应用 App ID | ⭕ |
| `FEISHU_APP_SECRET` | 飞书自建应用 App Secret | ⭕ |
| `FEISHU_BITABLE_APP_TOKEN` | 多维表格 app_token | ⭕ |
| `FEISHU_BITABLE_TABLE_ID` | 多维表格 table_id | ⭕ |
| `FEISHU_WEBHOOK_URL` | 群机器人 webhook URL | ⭕ |

> 没有配置时, 飞书同步作业会打印 warning 但不会 fail 整个 CI。

## 7. 本地开发 (pre-commit)

```bash
pip install pre-commit
pre-commit install --install-hooks

# 手动跑一次全量
pre-commit run --all-files
```

本地钩子与 CI 保持同一版本的 Ruff / mypy / Bandit / gitleaks，可在 push 前消灭 80% 的 CI 失败。

## 8. 常用命令

```bash
# 新建功能分支
git checkout -b feature/del-04-pdf-parser main

# 本地自检
ruff check . --fix
ruff format .
mypy src
pytest
bandit -c pyproject.toml -r src scripts

# 提交 (遵循格式)
git commit -m "[DEL-04] 文档解析器 v1.0 完成"

# 推送并开 PR
git push -u origin feature/del-04-pdf-parser
gh pr create --fill
```
