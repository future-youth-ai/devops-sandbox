# devops-sandbox

> future-youth-ai 组织的 DevOps / 工程工具沙箱仓库 —— 承载多个相对独立的服务，共享一套 CI / AI 审查 / 飞书同步流水线。

## 🗂 目录

```
devops-sandbox/
├── ai_review/              # 政府项目文档 AI 审核系统 (Python 骨架 + CI 模板)
│   ├── src/, tests/
│   ├── pyproject.toml
│   ├── README.md
│   └── docs/git-workflow.md
│
├── meeting_bot/            # 飞书会议妙记自动化 (FastAPI)
│   ├── src/meeting_bot/    # FastAPI + 飞书 8 个子 API + pipeline
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── README.md
│   └── docs/{feishu-setup,deployment}.md
│
├── scripts/                # 仓库级共享脚本
│   ├── commit_lint.py      # commit 消息格式校验
│   └── sync_feishu.py      # push to main 时同步 [DEL-xx]/[PHASE-x] 到飞书
│
├── .github/
│   ├── workflows/
│   │   ├── ai-review-ci.yml       # 只在 ai_review/** 变更时触发
│   │   ├── meeting-bot-ci.yml     # 只在 meeting_bot/** 变更时触发
│   │   ├── commit-lint.yml        # PR 全局 commit 消息校验
│   │   ├── labeler.yml            # PR 自动打标签
│   │   └── feishu-sync.yml        # 仓库级飞书同步
│   ├── labeler.yml
│   ├── CODEOWNERS
│   └── pull_request_template.md
│
├── .coderabbit.yaml        # AI 代码审查配置 (两个项目的规则合并)
├── .gitignore
└── README.md               # 你正在看的这个文件
```

## 🏗 项目清单

### 1. `ai_review/` — AI 审核系统（初始化阶段）

政府项目文档智能审核系统的 Python 骨架。目前仅有 CI / 工作流 / 目录结构，业务代码后续填充。

- **栈**：Python 3.11 + (计划) FastAPI + RAG
- **入口**：[`ai_review/README.md`](ai_review/README.md)
- **CI 状态**：Lint / mypy / pytest / bandit / pip-audit / TruffleHog / CodeRabbit

### 2. `meeting_bot/` — 飞书会议自动化（MVP 骨架）

会议结束 1-2 分钟内自动完成：飞书云文档 + Bitable + 任务 + 群卡片 + 邮件。

- **栈**：FastAPI + httpx + pydantic-settings + structlog
- **触发**：飞书事件订阅 webhook (`vc.meeting.meeting_ended_v1`)
- **入口**：[`meeting_bot/README.md`](meeting_bot/README.md)
- **部署**：[`meeting_bot/docs/deployment.md`](meeting_bot/docs/deployment.md)

## 🚀 本地开发

每个子项目独立管理依赖，在各自目录下开发：

```bash
# ai_review
cd ai_review
python -m venv .venv && source .venv/bin/activate
pip install -U pip ruff mypy pytest pytest-cov "bandit[toml]"
pre-commit install

# meeting_bot
cd meeting_bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## ✅ 通用提交规范

所有 commit 消息必须匹配下述格式之一（PR 时 `commit-lint` 检查强制执行）：

| 类型 | 格式 | 示例 |
|---|---|---|
| 交付物完成 | `[DEL-xx] 描述` | `[DEL-04] 文档解析器 v1.0 完成` |
| 里程碑达成 | `[DEL-xx][MVP] 描述` | `[DEL-07][MVP] AI审核引擎端到端可运行` |
| 阶段完成 | `[PHASE-x] 描述` | `[PHASE-1] Phase 1 全部交付完成` |
| 普通提交 | `<type>: 描述` | `feat(meeting_bot): 添加妙记 fallback 上传端点` |

`type` 允许值：`feat, fix, docs, style, refactor, perf, test, chore, build, ci, revert`。

## 🔐 分支保护（main）

主干保护规则必须在 GitHub Settings → Branches 中手动配置：
- 至少 1 个人工审查
- 必需 checks：`ai-review CI Gate` / `meeting-bot CI Gate` / `Commit Lint` / `CodeRabbit`
- 禁止强推 / 禁止删除 / 禁止绕过

详见各子项目的 git-workflow 文档。

## 🤝 贡献

1. 从 `main` 创建 `feature/<del-xx>-<短描述>` 分支
2. 本地跑 `pre-commit run --all-files`
3. 开 PR — 填写模板 + 等待 CI 全绿 + CodeRabbit 审查 + 人工审查
4. Squash merge 到 `main`

---

© future-youth-ai 2026
