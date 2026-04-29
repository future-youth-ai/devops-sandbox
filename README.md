# devops-sandbox

> future-youth-ai 组织的 DevOps 沙箱仓库 —— 共享一套 CI / AI 审查 / 飞书同步流水线。

## 🗂 目录

```
devops-sandbox/
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
├── scripts/                          # 仓库级共享脚本
│   ├── commit_lint.py                # commit 消息格式校验
│   ├── sync_feishu.py                # push to main → 同步 [DEL-]/[PHASE-]/[TASK-] 到飞书
│   ├── sync_coderabbit_report.py     # CodeRabbit 审查 → 飞书群通知
│   ├── parse_meeting_issue.py        # 解析会议 issue 表单
│   ├── fetch_transcript_for_workflow.py  # 从飞书拉取会议转写
│   ├── extract_action_items.py       # LLM 提取行动项
│   ├── create_feishu_tasks.py        # 创建飞书 Bitable 任务
│   ├── update_feishu_task.py         # 更新任务状态
│   └── archive_meeting.py            # 归档会议记录
│
├── .github/
│   ├── workflows/
│   │   ├── meeting-bot-ci.yml        # meeting_bot/** 变更时触发 CI
│   │   ├── commit-lint.yml           # PR 全局 commit 消息校验
│   │   ├── labeler.yml               # PR 自动打标签
│   │   ├── feishu-sync.yml           # push to main → 飞书同步
│   │   ├── coderabbit-report-sync.yml  # CodeRabbit 审查 → 飞书群通知
│   │   ├── process-meeting.yml       # 会议 issue → 转写 → LLM 提取 → 任务 → 归档
│   │   └── secret-scan.yml           # TruffleHog 凭证扫描
│   ├── ISSUE_TEMPLATE/meeting.yml    # 会议记录 issue 表单
│   ├── labeler.yml
│   ├── CODEOWNERS
│   └── pull_request_template.md
│
├── .coderabbit.yaml        # CodeRabbit AI 代码审查配置
├── .gitignore
└── README.md
```

## 🏗 项目

### `meeting_bot/` — 飞书会议自动化（MVP 骨架）

会议结束 1-2 分钟内自动完成：飞书云文档 + Bitable + 任务 + 群卡片 + 邮件。

- **栈**：FastAPI + httpx + pydantic-settings + structlog
- **触发**：飞书事件订阅 webhook (`vc.meeting.meeting_ended_v1`)
- **入口**：[`meeting_bot/README.md`](meeting_bot/README.md)
- **部署**：[`meeting_bot/docs/deployment.md`](meeting_bot/docs/deployment.md)

## 🔄 CI / 自动化

### CI 工作流（分支保护 gate）

| 工作流 | 触发条件 | 用途 |
|--------|---------|------|
| `meeting-bot-ci.yml` | PR 触及 `meeting_bot/**` 或 `scripts/**` | Ruff / mypy / pytest / Bandit / pip-audit / Docker build |
| `commit-lint.yml` | PR on main/dev | 校验 commit 消息格式 |
| `secret-scan.yml` | 所有 push/PR | TruffleHog 凭证扫描 |

### 审查 / 通知自动化

| 工作流 | 触发条件 | 用途 |
|--------|---------|------|
| `labeler.yml` | PR opened/synced | 按路径自动打标签 |
| `feishu-sync.yml` | push to main | 同步 `[DEL-]`/`[PHASE-]`/`[TASK-]` 到飞书 Bitable + 群 webhook |
| `coderabbit-report-sync.yml` | CodeRabbit 评论 | 转发 AI 审查报告到飞书群 |
| `process-meeting.yml` | issue 打 `meeting` 标签 | 解析 → 拉转写 → LLM 提取行动项 → 创建任务 → 归档 |

### 代码审查

代码审查由 [CodeRabbit](https://coderabbit.ai) (GitHub App) 自动执行，规则在 `.coderabbit.yaml` 中配置。`coderabbit-report-sync.yml` 将审查结果转发到飞书群。

## 🚀 本地开发

```bash
cd meeting_bot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## ✅ 提交规范

所有 commit 消息必须匹配下述格式之一（PR 时 `commit-lint` 检查强制执行）：

| 类型 | 格式 | 示例 |
|---|---|---|
| 交付物完成 | `[DEL-xx] 描述` | `[DEL-04] 文档解析器 v1.0 完成` |
| 里程碑达成 | `[DEL-xx][MVP] 描述` | `[DEL-07][MVP] AI审核引擎端到端可运行` |
| 阶段完成 | `[PHASE-x] 描述` | `[PHASE-1] Phase 1 全部交付完成` |
| 任务状态 | `[TASK-xxx]` / `[DONE-TASK-xxx]` | `[TASK-001] 开始任务` / `[DONE-TASK-001] 完成` |
| 普通提交 | `<type>: 描述` | `feat(meeting_bot): 添加妙记 fallback 上传端点` |

`type` 允许值：`feat, fix, docs, style, refactor, perf, test, chore, build, ci, revert`。

## 🔐 分支保护（main）

GitHub Settings → Branches 中配置：
- 至少 1 个人工审查
- 必需 checks：`meeting-bot CI Gate` / `Commit Lint` / `CodeRabbit`
- 禁止强推 / 禁止删除 / 禁止绕过

## 🤝 贡献

1. 从 `main` 创建 `feature/<del-xx>-<短描述>` 分支
2. 本地跑 `pre-commit run --all-files`
3. 开 PR — 填写模板 + 等待 CI 全绿 + CodeRabbit 审查 + 人工审查
4. Squash merge 到 `main`

---

© future-youth-ai 2026
