# DevOps Template — Product Design Spec

> 将 devops-sandbox 的自动化基础设施产品化为 GitHub Template Repository，供 future-youth-ai 组织内部使用，未来可扩展为公开模板。

## 1. 背景与目标

devops-sandbox 仓库已建立一套完整的 DevOps 自动化流程：commit 规范、飞书交付同步、会议自动化、AI 代码审查、安全扫描。目前这些能力绑定在单个仓库里，其他项目无法复用。

**目标：** 创建 `future-youth-ai/devops-template` GitHub Template Repository，让组织内任何新项目一键获得全套自动化能力。

**设计原则：**
- 用户从模板创建仓库后，只需编辑一个 `config.yml` 即可启用全部功能
- 密钥通过 org-level GitHub Secrets 继承，零配置
- 模板不含业务代码，只有基础设施（workflows + scripts + 配置）
- 结构上预留开放能力，未来可公开为外部模板

## 2. 模板仓库结构

```
devops-template/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                     # 通用 CI (scripts lint + commit lint + secret scan)
│   │   ├── commit-lint.yml            # commit 消息规范校验
│   │   ├── labeler.yml                # PR 自动标签
│   │   ├── secret-scan.yml            # TruffleHog 凭证扫描
│   │   ├── feishu-sync.yml            # [DEL-]/[PHASE-]/[TASK-] → 飞书同步
│   │   ├── coderabbit-report-sync.yml # CodeRabbit → 飞书群转发
│   │   └── process-meeting.yml        # 会议 issue → LLM → 任务 → 飞书云文档归档
│   ├── ISSUE_TEMPLATE/
│   │   └── meeting.yml                # 会议记录 issue 表单
│   ├── labeler.yml                    # PR 标签规则
│   ├── CODEOWNERS                     # 代码所有权
│   └── pull_request_template.md       # PR 模板
│
├── scripts/                           # 自动化脚本
│   ├── commit_lint.py                 # commit 消息格式校验
│   ├── sync_feishu.py                 # push to main → 飞书 Bitable + 群通知
│   ├── sync_coderabbit_report.py      # CodeRabbit 审查 → 飞书群
│   ├── parse_meeting_issue.py         # 解析会议 issue 表单
│   ├── fetch_transcript_for_workflow.py # 拉取飞书转写
│   ├── extract_action_items.py        # LLM 提取行动项
│   ├── create_feishu_tasks.py         # 创建飞书 Bitable 任务
│   ├── update_feishu_task.py          # 更新任务状态
│   ├── archive_meeting.py             # 归档到飞书云文档 (不落 git)
│   ├── feishu_content.py              # 飞书 API 工具函数
│   ├── feishu_url.py                  # 飞书 URL 白名单校验
│   └── test_*.py                      # 所有测试
│
├── .claude/
│   └── skills/
│       └── commit-compliance.md       # Claude Code commit 规范 skill
│
├── config.yml                         # 项目配置 (唯一需要用户修改的文件)
├── .coderabbit.yaml                   # AI 审查规则
├── .gitignore
└── README.md                          # 使用指南
```

### 与 devops-sandbox 的差异

| 移除 | 原因 |
|------|------|
| `meeting_bot/` | 业务代码，不属于模板 |
| `.planning/` | 项目特定数据，会议归档改为飞书云文档 |
| `docs/superpowers/plans/` | 历史规划文档 |
| `.env.local` / `.mcp.json` | 含硬编码凭证 |

| 改造 | 变化 |
|------|------|
| `meeting-bot-ci.yml` → `ci.yml` | 去掉路径 filter 和 working-directory，通用化 |
| `archive_meeting.py` | 输出从 git markdown 改为飞书云文档 |
| `process-meeting.yml` | 移除 git commit/push 步骤 |
| 所有脚本 | 从 `config.yml` 读配置，env var 作为覆盖 |

## 3. config.yml 设计

用户从模板创建仓库后，唯一需要编辑的文件。

```yaml
# config.yml — 项目配置
# 使用模板后，填写以下字段即可启用全部自动化

project:
  name: "my-project"                    # 项目名称，用于飞书通知标题
  language: "python"                     # 主语言 (MVP 仅支持 python，未来扩展 node/go)

# 飞书集成
# 密钥 (APP_ID/APP_SECRET/WEBHOOK_SECRET) 从 org-level GitHub Secrets 继承
# 仓库级 Secrets 可覆盖组织默认值 (同名即覆盖)
feishu:
  bitable_app_token: ""                  # 多维表格 app token
  bitable_table_id: ""                   # 任务表 table ID
  summary_chat_id: ""                    # 通知群 chat ID
  doc_template_token: ""                 # 会议归档文档模板 token

# LLM (会议行动项提取)
# API key 从 org-level GitHub Secrets 继承
llm:
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"

# commit 规范
commit:
  delivery_tracking: true                # 启用 [DEL-xx] / [PHASE-x] 交付物追踪
  task_sync: true                        # 启用 [TASK-xxx] 飞书任务状态同步
  extra_types: []                        # 额外允许的 conventional commit types
```

### 配置读取策略

脚本读取优先级：`环境变量 > config.yml > 默认值`

```python
# 脚本入口统一读取
import yaml

def load_config():
    with open("config.yml") as f:
        return yaml.safe_load(f)

# 使用时
config = load_config()
app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN") or config["feishu"]["bitable_app_token"]
```

这保证 GitHub Secrets（通过 env var 注入）优先于 config.yml，而 config.yml 优先于硬编码默认值。

### 密钥管理

| Secret | 级别 | 说明 |
|--------|------|------|
| `FEISHU_APP_ID` | Org | 飞书自建应用 ID |
| `FEISHU_APP_SECRET` | Org | 飞书自建应用密钥 |
| `FEISHU_WEBHOOK_URL` | Org | 群机器人 webhook URL |
| `DEEPSEEK_API_KEY` | Org | LLM API key |
| 以上任一 | Repo (可选) | 仓库级覆盖，同名即生效 |

## 4. CI 通用化

### 模板自带的 CI jobs

| Job | Workflow | 触发 | 作用 |
|-----|----------|------|------|
| `scripts-lint` | `ci.yml` | 所有 PR | Ruff lint scripts/ |
| `commit-lint` | `commit-lint.yml` | PR on main/dev | commit 消息校验 |
| `secret-scan` | `secret-scan.yml` | 所有 push/PR | TruffleHog 凭证扫描 |
| `ci-gate` | `ci.yml` | always | 汇总所有 job 结果 |

### 用户项目 CI

模板不包含用户项目的 lint/test/build CI。用户自行创建 workflow，README 提供示例：

```yaml
# .github/workflows/my-project-ci.yml (示例)
name: My Project CI
on:
  pull_request:
    paths: ["my_project/**"]
jobs:
  lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: my_project
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff && ruff check .
```

## 5. 会议归档改造

### 当前流程 (devops-sandbox)

```
issue → parse → fetch → LLM → create tasks → 写 markdown 到 git → commit → push → close issue
```

问题：每次会议都加 commit，污染 git 历史。push 有并发竞争，需要 rebase 重试逻辑。

### 新流程 (devops-template)

```
issue → parse → fetch → LLM → create tasks → 写飞书云文档 → close issue (附文档链接)
```

#### archive_meeting.py 改造

```python
# 之前: 生成 markdown 写到 .planning/meetings/
# 之后: 调飞书 Docs API 从模板复制文档，写入会议内容

def archive_to_feishu(config, meeting_data):
    token = get_tenant_token(app_id, app_secret)
    # 1. 从模板复制新文档
    doc_token = copy_doc_from_template(token, config["feishu"]["doc_template_token"])
    # 2. 写入会议元数据 + 行动项表格
    write_doc_content(token, doc_token, meeting_data)
    # 3. 返回文档 URL
    return f"https://docs.feishu.cn/docx/{doc_token}"
```

#### process-meeting.yml 改造

- 移除 "Commit archive to dev" 步骤（git config、git add、rebase 重试全部删除）
- 移除 `contents: write` 权限
- "Comment on issue and close" 步骤改为贴飞书文档链接

## 6. 自动化功能清单

| 功能 | 触发方式 | 输出 |
|------|---------|------|
| commit 规范校验 | PR → CI | 校验通过/失败 |
| 飞书交付同步 | push to main 含 `[DEL-]`/`[PHASE-]` | Bitable 新行 + 群卡片 |
| 飞书任务推进 | push to main 含 `[TASK-]`/`[DONE-TASK-]` | Bitable 状态更新 |
| 会议自动化 | issue 打 `meeting` 标签 / 手动关闭 | 飞书任务 + 云文档归档 |
| CodeRabbit 同步 | CodeRabbit 评论 | 飞书群通知 |
| 安全扫描 | 所有 push/PR | TruffleHog 报告 |
| PR 自动标签 | PR opened/synced | 路径标签 |
| commit compliance | Claude Code 提交时 | 本地校验 + 建议 |

## 7. README 结构

```markdown
# devops-template

> GitHub 仓库 DevOps 自动化模板 — CI / commit 规范 / 飞书同步 / 会议自动化 / AI 代码审查

## 你能得到什么
(功能列表 + 每个功能一句话说明)

## 快速开始
1. Use this template → 创建新仓库
2. 编辑 config.yml — 填入飞书资源 ID
3. (可选) 仓库级 Secrets 覆盖组织默认值
4. 安装 CodeRabbit GitHub App
5. Done

## config.yml 配置说明
(每个字段的含义和获取方式)

## commit 提交规范
(格式表格 + 示例)

## 各 workflow 说明
(每个 workflow 一小节，说明触发条件和作用)

## 添加你自己的项目 CI
(示例 workflow 文件)

## Org-level Secrets 设置指南
(管理员操作，只需做一次)

## FAQ
```

## 8. 实施步骤

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 创建 `future-youth-ai/devops-template` 仓库 | — |
| 2 | 复制基础设施文件 (workflows, scripts, configs, skills) | 1 |
| 3 | 移除项目特定内容 (meeting_bot, .planning, plans, .mcp.json) | 2 |
| 4 | 创建 `config.yml`，改造所有脚本读取配置 | 2 |
| 5 | 改造 `archive_meeting.py` → 飞书云文档输出 | 4 |
| 6 | 改造 `process-meeting.yml` → 移除 git commit 步骤 | 5 |
| 7 | 通用化 CI → `ci.yml`，去掉路径硬编码 | 2 |
| 8 | 更新 labeler.yml, CODEOWNERS, PR template 为通用版 | 2 |
| 9 | 写 README | 4-8 |
| 10 | 标记 Template Repository | 9 |
| 11 | 烟雾测试 — 用模板创建测试仓库，验证全流程 | 10 |

## 9. 未来扩展（不在 MVP 范围）

- 定期同步脚本 `sync-from-template.yml`，让已创建的仓库跟上模板更新
- 支持非飞书平台（Slack、钉钉、企业微信）的通知适配层
- `config.yml` 的 JSON Schema 校验
- init 脚本交互式引导配置
- 多语言 CI 支持（Node.js、Go）
