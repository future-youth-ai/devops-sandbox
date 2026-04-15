# ai_review_project_init

政府项目文档 AI 审核系统 - 初始化仓库。

## 快速开始

```bash
# 1. 创建虚拟环境并安装工具链
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install ruff==0.6.9 mypy==1.11.2 pytest pytest-cov "bandit[toml]==1.7.10" pip-audit==2.7.3 pre-commit

# 2. 安装本地 pre-commit 钩子
pre-commit install --install-hooks

# 3. 本地自检
ruff check . && ruff format --check .
mypy src
pytest
bandit -c pyproject.toml -r src scripts
```

## Git 工作流

- **主干保护** + PR 强制审查
- **8 项 CI 检查**：Ruff / mypy / Commit Lint / pytest(≥70%) / Bandit / pip-audit + TruffleHog / CodeRabbit AI / 飞书同步
- **Commit 规范**：`[DEL-xx]` / `[DEL-xx][MVP]` / `[PHASE-x]` / `type: desc`

详见 [docs/git-workflow.md](docs/git-workflow.md) 和 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 目录结构

```
.
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # 8 项 CI 主流水线
│   │   ├── labeler.yml             # 按路径自动打标签
│   │   └── feishu-sync.yml         # 飞书多维表格 + 群消息
│   ├── labeler.yml                 # 标签规则
│   ├── CODEOWNERS                  # 代码所有者
│   └── pull_request_template.md    # PR 模板
├── scripts/
│   ├── commit_lint.py              # commit 消息校验器
│   └── sync_feishu.py              # 飞书同步
├── src/                            # 业务代码
├── tests/                          # 测试
├── docs/
│   └── git-workflow.md             # 工作流完整说明
├── .coderabbit.yaml                # AI 审查定制 (中文, 安全/RAG/业务)
├── .pre-commit-config.yaml         # 本地钩子 (与 CI 版本一致)
├── pyproject.toml                  # Ruff / mypy / pytest / bandit 配置
├── CONTRIBUTING.md
└── README.md
```

## 下一步需要在 GitHub 上手动完成

1. Settings → Branches → 添加 `main` 保护规则（见 [git-workflow.md §4](docs/git-workflow.md#4-必须在-github-上配置的分支保护规则)）
2. 安装 [CodeRabbit GitHub App](https://github.com/marketplace/coderabbitai)
3. Settings → Secrets → 添加飞书相关 5 个 secrets
4. 首次 push 后确认所有 8 项 check 均出现在 PR 页面
