# meeting_bot_init

飞书会议妙记 → 云文档 / Bitable / 任务 / 群消息 / 邮件 的自动化 Bot。

会议结束后 1-2 分钟内自动完成：
- 📄 把妙记摘要写成**云文档**
- 📊 在**多维表格**里记一行索引
- ✅ 把行动项创建为**飞书任务**并 @ 到具体负责人
- 💬 在相关**群聊**发卡片通知
- ✉️ 给所有参会人发 **HTML 邮件**

## 架构

```
飞书视频会议 → 妙记 → 事件订阅 webhook → FastAPI /webhook/feishu
                                           │
                                           ▼
                    ┌──────────────────────────────────────┐
                    │ Pipeline.process()                   │
                    │                                       │
                    │   VCAPI     ─── 会议信息 + 参会人    │
                    │   MinutesAPI ── 妙记摘要/转写         │
                    │       ↓                               │
                    │   asyncio.gather():                  │
                    │     ├─ DocsAPI       云文档          │
                    │     ├─ BitableAPI    索引行          │
                    │     ├─ TaskAPI       任务 + assign   │
                    │     ├─ MessageAPI    群卡片          │
                    │     └─ EmailSender   SMTP 邮件       │
                    └──────────────────────────────────────┘
```

## 快速开始

```bash
# 1. 克隆并安装
git clone <repo> meeting_bot_init && cd meeting_bot_init
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

# 2. 配置飞书 (详见 docs/feishu-setup.md)
cp .env.example .env
# 编辑 .env 填入所有 FEISHU_* 和 SMTP_* 值

# 3. 本地跑
uvicorn meeting_bot.main:app --reload

# 4. 本地自检
ruff check . && ruff format --check .
mypy src
pytest
bandit -c pyproject.toml -r src scripts -ll

# 5. Docker 部署
docker compose up -d --build
```

## 目录结构

```
.
├── src/meeting_bot/
│   ├── main.py                   # FastAPI app + /webhook/feishu
│   ├── config.py                 # pydantic-settings (所有 secrets)
│   ├── models.py                 # MeetingSummary / ActionItem / Attendee
│   ├── dedup.py                  # SQLite 幂等存储
│   ├── pipeline.py               # 主编排 (并发扇出)
│   ├── email_sender.py           # aiosmtplib
│   ├── feishu/
│   │   ├── client.py             # 基础 HTTP client + token 缓存 + 重试
│   │   ├── events.py             # webhook 解密 + 签名验证
│   │   ├── vc.py                 # 视频会议 API
│   │   ├── minutes.py            # 妙记 API  ⚠️ 需要 minutes:* scope
│   │   ├── docs.py               # 云文档 (从模板复制)
│   │   ├── bitable.py            # 多维表格
│   │   ├── tasks.py              # 任务 v2 + assign
│   │   ├── contact.py            # email → open_id
│   │   └── messages.py           # IM 群卡片
│   └── templates/
│       ├── meeting_doc.md.j2     # 云文档内容
│       ├── email.html.j2         # 邮件正文
│       └── group_card.json.j2    # 飞书卡片
├── tests/
│   ├── test_events.py            # 加密/解密/签名
│   ├── test_dedup.py
│   └── test_health.py
├── scripts/
│   └── commit_lint.py            # [DEL-xx]/[PHASE-x]/conventional 校验
├── docs/
│   ├── feishu-setup.md           # 👈 飞书配置详细步骤
│   └── deployment.md             # 部署指南
├── .github/
│   ├── workflows/ci.yml          # 7 项 CI + Docker build
│   ├── CODEOWNERS
│   └── pull_request_template.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml                # Ruff / mypy / pytest / bandit
├── .coderabbit.yaml              # 中文 AI 审查: 安全/异步/飞书 API/测试
├── .pre-commit-config.yaml
└── .env.example
```

## CI (7 项 + Docker)

与 `ai_review_project_init` 一致的 8 项检查, 加一项 Docker build smoke test:

| # | 检查 | 说明 |
|---|------|------|
| 1 | Lint (Ruff) | 风格 + isort |
| 2 | Type Check (mypy) | strict mode |
| 3 | Commit Lint | `[DEL-xx]` / `[PHASE-x]` / `type: desc` |
| 4 | Test (pytest) | 覆盖率 ≥60% (初期) |
| 5 | Security SAST (Bandit) | Python 源码安全 |
| 6 | Security SCA | pip-audit + TruffleHog |
| 7 | Docker Build | 镜像构建 smoke test |
| 8 | CodeRabbit AI | 中文审查 (需装 GitHub App) |

## 关键 scope（飞书权限管理）

部署前必须申请并通过：

```
vc:meeting                     视频会议
minutes:minutes                妙记    ⚠️ 套餐限制
docx:document                  云文档
drive:drive + drive:file       模板复制
bitable:app                    多维表格
task:task                      任务 v2
contact:user.base:readonly     通讯录 (email→open_id)
im:message                     群消息
```

详见 [docs/feishu-setup.md](docs/feishu-setup.md)。

## 未完成的 TODO

代码里几处已标注 `# TODO`:
- 飞书 VC 参会人分页接口的确切路径（`list_participants`）
- 妙记 transcript/summary 路径（`get_transcript` / `get_summary`）
- 事件订阅的确切 event_type 名字（`main.py::_dispatch_event`）

部署前需要用 **Context7** 拉最新飞书 Open Platform 文档核对一次。这些是飞书侧经常改的地方。

## 许可证

内部项目，未公开发行。
