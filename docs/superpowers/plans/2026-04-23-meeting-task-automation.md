# Meeting → AI → Feishu Task 自动化 实施计划 (2026-04-23)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 devops-sandbox 改造成 future-youth-ai 组织的 **CI/CD + 项目管理自动化模板**，实现两条核心闭环：
- **A**: 用户开 GitHub Issue 贴飞书云文档/妙记链接 → workflow 拉内容 → LLM 抽 action items → 飞书 Task v2 创建并派遣
- **B**: 团队 commit (含 `[TASK-xxx]` 标签) push 到 main → workflow 反查映射 → PATCH 飞书任务状态

**Architecture:**
- 全链路跑在 GitHub Actions 上，无需自建服务器（meeting_bot/ 保留备用）
- Org-level Secrets 管理凭证，所有 repo 复制 `.github/` + `scripts/` 即获得能力
- `.planning/tasks.json` 当 commit-tag↔task-guid 映射存储
- `.planning/meetings/<日期>-issue<n>.md` 归档（策略 B：链接 + 提取结果，不存原文）

**Tech Stack:** GitHub Actions, GitHub CLI (`gh`), Python 3.11, OpenAI SDK (DeepSeek-compatible), 飞书 OpenAPI v1/v2, pydantic。

**本计划替代 `2026-04-23-devops-sandbox-finish-line.md`**：那份计划基于"DevOps 收尾"的误解写的；本计划是真实业务目标。两者在"分支保护 + stale 分支清理 + dev→main release"上有重叠，本计划的 Phase 6 已覆盖。

---

## 🧑‍💻 标记说明

每个 Task 起始位置标注：

- 🤖 **[CLAUDE]**: 我可以直接执行（写代码/跑命令）
- 🧑 **[USER ACTION]**: 需要你在浏览器/外部工具操作，我无法代劳
- 🤝 **[MIXED]**: 你触发，我观察/收尾

---

## Phase 0：落地 PR #7（ai_review 回滚）

**前置条件:** PR #7 已开（https://github.com/future-youth-ai/devops-sandbox/pull/7），当前分支 `chore/rollback-ai-review-to-smoke-test`。

### Task 0.1：等 CI + CodeRabbit 复审 🤖 [CLAUDE]

- [ ] **Step 1：等所有 status check 通过**

Run:
```bash
until gh pr checks 7 2>&1 | grep -qv 'pending'; do sleep 30; done
gh pr checks 7
```

Expected: 全部 `pass`。

- [ ] **Step 2：触发 CodeRabbit 复审**

Run:
```bash
gh pr comment 7 --body "@coderabbitai review"
```

Expected: 评论 URL 输出。

- [ ] **Step 3：等 review 提交**

Run:
```bash
until gh api repos/future-youth-ai/devops-sandbox/pulls/7/reviews \
  -q '.[-1].state' 2>/dev/null | grep -qE '^(APPROVED|CHANGES_REQUESTED)$'; do
  sleep 30
done
gh api repos/future-youth-ai/devops-sandbox/pulls/7/reviews -q '.[-1].state'
```

Expected: `APPROVED`。

**Exit criteria:** PR #7 CI 全绿 + CodeRabbit APPROVED。

---

### Task 0.2：合并 PR #7 → dev 🤖 [CLAUDE]

- [ ] **Step 1：squash merge**

Run:
```bash
gh pr merge 7 --squash --delete-branch \
  --subject "chore(ai_review): 回滚业务骨架, 恢复为 CI smoke test 占位"
```

Expected: `✓ Squashed and merged pull request #7`。

- [ ] **Step 2：同步本地**

Run:
```bash
git checkout dev
git pull --ff-only origin dev
git log --oneline -5
```

Expected: dev 含 PR #7 squash commit。

**Exit criteria:** dev 已含回滚，本地切回 dev。

---

## Phase 1：飞书 + LLM + Org Secrets 准备

> ⚠️ **本 Phase 几乎全部需要你在浏览器操作**。我只能给精确步骤 + 验证命令。
> Phase 1 完成前 Phase 5 测试无法跑（但 Phase 2/3/4 写代码不依赖）。

### Task 1.1：飞书自建应用准备 🧑 [USER ACTION]

- [ ] **Step 1：登 https://open.feishu.cn/app**

打开网页，使用 future-youth-ai 组织管理员账号登录。

- [ ] **Step 2：检查是否已有 App，没有就创建**

如果之前 meeting_bot 已经创建过自建应用，直接复用，跳到 Step 3。否则：
- 点 "创建企业自建应用"
- 名称：`future-youth-ai-meeting-bot`（或任意）
- 描述：`会议记录 → 飞书任务自动化`
- 创建后会自动跳到应用配置页

- [ ] **Step 3：拿 App ID 和 App Secret**

应用配置页 → "凭证与基础信息"：
- 把 **App ID** 复制保存（形如 `cli_a1b2c3d4`）
- 把 **App Secret** 点 "查看/重置" 后复制保存

- [ ] **Step 4：开通事件订阅 + 拿 Encrypt Key**

应用配置页 → "事件订阅" → "加密策略":
- 生成或填一个 32 字符的 **Encrypt Key**（base64，飞书有自动生成按钮）
- 复制保存

> 这个 Key 是 meeting_bot webhook 用的；本次主流程没用，但保留备用 (Phase 0 决定 meeting_bot 保留)。

- [ ] **Step 5：申请权限 scopes**

应用配置页 → "权限管理" → "权限申请", 勾选并点"申请"：

| 权限 scope | 用途 |
|---|---|
| `vc:meeting` | 读取视频会议信息（备用） |
| `docs:doc.readonly` | 读云文档 docx 内容 |
| `docs:document:readonly` | （旧版同义，有些应用必须勾） |
| `wiki:wiki.readonly` | 读 Wiki 节点 |
| `minutes:minutes.readonly` | 读妙记 transcript |
| `task:task` | 创建/更新任务 |
| `contact:user.id.readonly` | 姓名 → open_id 解析 |
| `im:message:send_as_bot` | 群消息（发任务通知卡片用，可选） |

> 如果某权限提示"需管理员审批"，找你们 future-youth-ai 飞书管理员批一下。

- [ ] **Step 6：发布应用版本**

应用配置页 → "版本管理与发布" → 创建版本 → 填变更说明 → "提交审核"。
组织管理员后台审批通过后才生效（一般几分钟）。

- [ ] **Step 7：本地验证 token 拿得到**

把 App ID 和 Secret 临时写到本地 shell：
```bash
export TEST_APP_ID="cli_xxx"
export TEST_APP_SECRET="xxx"
curl -sS -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H 'Content-Type: application/json' \
  -d "{\"app_id\":\"$TEST_APP_ID\",\"app_secret\":\"$TEST_APP_SECRET\"}" | python3 -m json.tool
```

Expected: 输出 JSON 含 `"code": 0` 和 `"tenant_access_token": "t-..."`。

如果返回 `{"code":99991663,"msg":"app ticket invalid"}` → Step 6 还没审过，等。

**Exit criteria:** App ID + Secret + Encrypt Key 都已拿到；token 测试调用返回 `code=0`。

---

### Task 1.2：建"会议纪要" Wiki 空间 + 加应用 🧑 [USER ACTION]

- [ ] **Step 1：在飞书里创建 Wiki 空间**

飞书 App → 知识库 → 新建知识库 → 名称：`会议纪要`。

- [ ] **Step 2：把应用加为空间成员**

进知识库 → 右上角"成员"按钮 → 添加成员 → 搜索你的应用名（如 `future-youth-ai-meeting-bot`） → 角色选 **管理员** → 确定。

> 这一步让应用对该空间下**所有**会议文档/妙记/Docx 都有读权限，不用每次手动分享。

- [ ] **Step 3：放一个测试文档进去**

进知识库 → "新建" → "新建妙记"（如果已有妙记，用 "添加" 把妙记移入此空间）。
或：
- 录一个 30 秒的飞书会议（自己跟自己），妙记会自动生成
- 把妙记从 "我的妙记" 移到 "会议纪要" 知识库

- [ ] **Step 4：复制测试妙记的 URL**

打开妙记 → 浏览器地址栏复制，形如：
```
https://meetings.feishu.cn/minutes/<token>
```

保存这个 URL，后面 Phase 5 测试用。

- [ ] **Step 5：用 API 验证应用能读到 transcript**

```bash
TOKEN=$(curl -sS -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H 'Content-Type: application/json' \
  -d "{\"app_id\":\"$TEST_APP_ID\",\"app_secret\":\"$TEST_APP_SECRET\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['tenant_access_token'])")

MINUTES_TOKEN="<从 URL 复制的 token>"

curl -sS https://open.feishu.cn/open-apis/minutes/v1/minutes/$MINUTES_TOKEN/transcript \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -30
```

Expected: 返回 JSON 含 `"code": 0` 和 `data.transcripts: [...]`。

**Exit criteria:** 测试妙记 URL + transcript API 调用成功（拿到至少 1 条 transcript 段落）。

---

### Task 1.3：注册 DeepSeek 并拿 API Key 🧑 [USER ACTION]

- [ ] **Step 1：注册账号**

打开 https://platform.deepseek.com/ → 注册（手机号或邮箱）。

- [ ] **Step 2：充值**

控制台 → "充值" → 推荐 ¥10（够小团队跑半年以上）。

- [ ] **Step 3：创建 API Key**

控制台 → "API keys" → "Create new API key" → 命名如 `github-actions-future-youth-ai` → 复制。

> 重要：key 只显示一次，丢了只能重新建。

- [ ] **Step 4：本地验证 key 能用**

```bash
export TEST_LLM_KEY="sk-xxxxxxxxxxxx"
curl -sS https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $TEST_LLM_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}' \
  | python3 -m json.tool | head -20
```

Expected: 返回 JSON 含 `choices[0].message.content`。

**Exit criteria:** DeepSeek API Key 可用。

---

### Task 1.4：配置 GitHub Org Secrets 🧑 [USER ACTION]

- [ ] **Step 1：进入 Org secrets 页**

打开 https://github.com/organizations/future-youth-ai/settings/secrets/actions

- [ ] **Step 2：添加 4 个 Org secret**

依次点 "New organization secret"，填以下 4 个：

| Secret 名 | 值 | Repository access |
|---|---|---|
| `FEISHU_APP_ID` | Task 1.1 拿到的 App ID | Selected → 勾 `devops-sandbox`（以后多了再加） |
| `FEISHU_APP_SECRET` | Task 1.1 拿到的 App Secret | 同上 |
| `DEEPSEEK_API_KEY` | Task 1.3 拿到的 sk-xxx | 同上 |
| `FEISHU_BOT_WEBHOOK_URL` | （可选，Phase 4 通知群用，没有可后补） | 同上 |

> 注：现有 `FEISHU_WEBHOOK_URL`（CodeRabbit 同步用的）建议**保留**，不要混用。新 secret 用 `FEISHU_BOT_WEBHOOK_URL` 名字区分用途。

- [ ] **Step 3：在 devops-sandbox repo 验证可见**

打开 https://github.com/future-youth-ai/devops-sandbox/settings/secrets/actions
应能在 "Organization secrets" 区看到刚加的 4 个（值显示为 `***`）。

**Exit criteria:** 4 个 org secret 都已创建，devops-sandbox 在 access list 里。

---

## Phase 2：实现 5 个核心脚本

> 🤖 全部 Claude 主导。每个脚本独立可测试。

### Task 2.1：飞书 URL 解析器 🤖 [CLAUDE]

**Files:**
- Create: `scripts/feishu_url.py`
- Test: `scripts/test_feishu_url.py`

- [ ] **Step 1：写 feishu_url.py**

```python
"""飞书资源 URL 解析: URL → (kind, token).

支持的 URL 形态:
  https://meetings.feishu.cn/minutes/<token>          -> ("minutes", token)
  https://*.feishu.cn/docx/<doc_id>                   -> ("docx", doc_id)
  https://*.feishu.cn/docs/<doc_id>                   -> ("docs", doc_id)
  https://*.feishu.cn/wiki/<wiki_token>               -> ("wiki", wiki_token)
"""
from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_KINDS = {"minutes", "docx", "docs", "wiki"}


class InvalidFeishuURL(ValueError):
    pass


def parse_feishu_url(url: str) -> tuple[str, str]:
    """返回 (kind, token). 不合法抛 InvalidFeishuURL."""
    if not url or not isinstance(url, str):
        raise InvalidFeishuURL("URL 为空")
    p = urlparse(url.strip())
    if p.scheme not in {"http", "https"}:
        raise InvalidFeishuURL(f"协议必须为 https: {url}")
    if not (
        p.netloc.endswith("feishu.cn")
        or p.netloc.endswith("larksuite.com")
        or p.netloc == "meetings.feishu.cn"
    ):
        raise InvalidFeishuURL(f"非飞书域名: {p.netloc}")
    parts = [seg for seg in p.path.split("/") if seg]
    if len(parts) < 2:
        raise InvalidFeishuURL(f"路径段不足: {p.path}")
    kind, token = parts[0], parts[1]
    if kind not in ALLOWED_KINDS:
        raise InvalidFeishuURL(f"未支持的资源类型 {kind!r}, 仅支持 {ALLOWED_KINDS}")
    if not token or len(token) < 8:
        raise InvalidFeishuURL(f"token 长度异常: {token}")
    return kind, token
```

- [ ] **Step 2：写 test_feishu_url.py**

```python
"""URL 解析单测."""
from __future__ import annotations

import pytest
from feishu_url import parse_feishu_url, InvalidFeishuURL


@pytest.mark.parametrize("url, expected", [
    ("https://meetings.feishu.cn/minutes/abc12345xyz",
     ("minutes", "abc12345xyz")),
    ("https://example.feishu.cn/docx/doxcnxxxxxxxxxxxx",
     ("docx", "doxcnxxxxxxxxxxxx")),
    ("https://example.feishu.cn/docs/doccnxxxxxxxxxxxx",
     ("docs", "doccnxxxxxxxxxxxx")),
    ("https://example.feishu.cn/wiki/wikcnxxxxxxxxxxxxxxxx",
     ("wiki", "wikcnxxxxxxxxxxxxxxxx")),
    ("https://example.larksuite.com/docx/doxxxxxxxxx",
     ("docx", "doxxxxxxxxx")),
])
def test_valid_urls(url, expected):
    assert parse_feishu_url(url) == expected


@pytest.mark.parametrize("url, match", [
    ("", "为空"),
    ("ftp://example.feishu.cn/docx/abc12345", "https"),
    ("https://evil.com/docx/abc12345", "非飞书域名"),
    ("https://example.feishu.cn/", "路径段不足"),
    ("https://example.feishu.cn/unknown/abc12345", "未支持"),
    ("https://example.feishu.cn/docx/x", "token 长度"),
])
def test_invalid_urls(url, match):
    with pytest.raises(InvalidFeishuURL, match=match):
        parse_feishu_url(url)
```

- [ ] **Step 3：运行 test 验证**

Run:
```bash
cd scripts
python3 -m pytest test_feishu_url.py -v
```

Expected: 11 个 test 全 pass。

- [ ] **Step 4：commit**

Run:
```bash
git add scripts/feishu_url.py scripts/test_feishu_url.py
git commit -m "feat(scripts): 飞书 URL 解析器 + 单测"
```

**Exit criteria:** test 全 pass，代码 commit。

---

### Task 2.2：飞书内容下载器 🤖 [CLAUDE]

**Files:**
- Create: `scripts/feishu_content.py`
- Test: `scripts/test_feishu_content.py`

按 kind 调对应 API 拿纯文本。

- [ ] **Step 1：写 feishu_content.py**

```python
"""按 (kind, token) 调飞书 API 拿文本内容.

输入: kind ∈ {minutes, docx, docs, wiki}, token, tenant_access_token
输出: 纯文本 str (transcript 多段拼接 / 文档 blocks 拼接)
"""
from __future__ import annotations

import requests

FEISHU_BASE = "https://open.feishu.cn/open-apis"
TIMEOUT = 30


class FeishuFetchError(RuntimeError):
    pass


def _get(path: str, token: str, params: dict | None = None) -> dict:
    r = requests.get(
        f"{FEISHU_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise FeishuFetchError(
            f"飞书 API 失败: code={data.get('code')} msg={data.get('msg')} path={path}"
        )
    return data


def get_tenant_token(app_id: str, app_secret: str) -> str:
    r = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise FeishuFetchError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def fetch_minutes(token: str, minute_token: str) -> str:
    """拼接妙记 transcript 各段为一个长字符串."""
    data = _get(f"/minutes/v1/minutes/{minute_token}/transcript", token)
    segs = data.get("data", {}).get("transcripts", [])
    lines = []
    for s in segs:
        speaker = s.get("speaker_name") or s.get("user_id") or "未知"
        text = s.get("text") or s.get("sentence") or ""
        if text.strip():
            lines.append(f"[{speaker}] {text.strip()}")
    return "\n".join(lines)


def fetch_docx(token: str, doc_id: str) -> str:
    """拉 docx 全部 blocks, 拼成 markdown-ish 文本."""
    all_blocks: list[dict] = []
    page_token: str | None = None
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        data = _get(f"/docx/v1/documents/{doc_id}/blocks", token, params)
        body = data.get("data", {})
        all_blocks.extend(body.get("items", []))
        if not body.get("has_more"):
            break
        page_token = body.get("page_token")
        if not page_token:
            break

    return _blocks_to_text(all_blocks)


def _blocks_to_text(blocks: list[dict]) -> str:
    """把 docx blocks 简化提取文本 (text/heading 类型, 忽略其他)."""
    out: list[str] = []
    for b in blocks:
        t = b.get("block_type")
        if t == 2:  # text
            text = "".join(
                e.get("text_run", {}).get("content", "")
                for e in b.get("text", {}).get("elements", [])
            )
            if text.strip():
                out.append(text.strip())
        elif t in (3, 4, 5, 6, 7, 8, 9, 10, 11):  # headings 1-9
            text = "".join(
                e.get("text_run", {}).get("content", "")
                for e in b.get(f"heading{t-2}", {}).get("elements", [])
            )
            if text.strip():
                out.append(f"## {text.strip()}")
    return "\n\n".join(out)


def fetch_docs_legacy(token: str, doc_id: str) -> str:
    """老版 docs API (返回 raw_content 文本)."""
    data = _get(f"/doc/v2/{doc_id}/raw_content", token)
    return data.get("data", {}).get("content", "") or ""


def fetch_wiki(token: str, wiki_token: str) -> str:
    """Wiki: 先解析到底层 obj_token, 再按 obj_type 派发."""
    data = _get("/wiki/v2/spaces/get_node", token, {"token": wiki_token})
    node = data.get("data", {}).get("node", {})
    obj_type = node.get("obj_type")
    obj_token = node.get("obj_token")
    if not obj_token:
        raise FeishuFetchError(f"wiki 节点无 obj_token: {node}")
    if obj_type == "docx":
        return fetch_docx(token, obj_token)
    if obj_type == "doc":
        return fetch_docs_legacy(token, obj_token)
    raise FeishuFetchError(f"wiki 节点未支持的 obj_type: {obj_type}")


def fetch_content(kind: str, token: str, tenant_token: str) -> str:
    """统一入口: 按 kind 派发."""
    if kind == "minutes":
        return fetch_minutes(tenant_token, token)
    if kind == "docx":
        return fetch_docx(tenant_token, token)
    if kind == "docs":
        return fetch_docs_legacy(tenant_token, token)
    if kind == "wiki":
        return fetch_wiki(tenant_token, token)
    raise FeishuFetchError(f"未知 kind: {kind}")
```

- [ ] **Step 2：写 test_feishu_content.py（用 responses 库 mock HTTP）**

```python
"""feishu_content 单测 - mock 飞书 HTTP 响应."""
from __future__ import annotations

import pytest
import responses

from feishu_content import fetch_content, get_tenant_token, FeishuFetchError


@responses.activate
def test_get_tenant_token_ok():
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    assert get_tenant_token("app", "secret") == "t-abc"


@responses.activate
def test_fetch_minutes_concat_segments():
    responses.add(
        responses.GET,
        "https://open.feishu.cn/open-apis/minutes/v1/minutes/mtk/transcript",
        json={
            "code": 0,
            "data": {
                "transcripts": [
                    {"speaker_name": "Alice", "text": "Hello"},
                    {"speaker_name": "Bob", "text": "World"},
                ]
            },
        },
    )
    text = fetch_content("minutes", "mtk", "t-abc")
    assert "[Alice] Hello" in text
    assert "[Bob] World" in text


@responses.activate
def test_fetch_docx_text_blocks():
    responses.add(
        responses.GET,
        "https://open.feishu.cn/open-apis/docx/v1/documents/doc1/blocks",
        json={
            "code": 0,
            "data": {
                "items": [
                    {
                        "block_type": 2,
                        "text": {"elements": [{"text_run": {"content": "段落一"}}]},
                    },
                    {
                        "block_type": 2,
                        "text": {"elements": [{"text_run": {"content": "段落二"}}]},
                    },
                ],
                "has_more": False,
            },
        },
    )
    text = fetch_content("docx", "doc1", "t-abc")
    assert "段落一" in text and "段落二" in text


@responses.activate
def test_unknown_kind_raises():
    with pytest.raises(FeishuFetchError, match="未知 kind"):
        fetch_content("xxx", "tok", "t-abc")


@responses.activate
def test_api_code_nonzero_raises():
    responses.add(
        responses.GET,
        "https://open.feishu.cn/open-apis/minutes/v1/minutes/mtk/transcript",
        json={"code": 99991672, "msg": "permission denied"},
    )
    with pytest.raises(FeishuFetchError, match="permission denied"):
        fetch_content("minutes", "mtk", "t-abc")
```

- [ ] **Step 3：装依赖 + 跑 test**

Run:
```bash
cd scripts
python3 -m pip install --quiet --user responses pytest requests
python3 -m pytest test_feishu_content.py -v
```

Expected: 5 个 test 全 pass。

- [ ] **Step 4：commit**

Run:
```bash
git add scripts/feishu_content.py scripts/test_feishu_content.py
git commit -m "feat(scripts): 飞书内容下载器 (minutes/docx/docs/wiki) + 单测"
```

**Exit criteria:** test 全 pass。

---

### Task 2.3：LLM 抽取脚本 🤖 [CLAUDE]

**Files:**
- Create: `scripts/extract_action_items.py`
- Test: `scripts/test_extract_action_items.py`

- [ ] **Step 1：写 extract_action_items.py**

```python
"""调 OpenAI-compatible API (DeepSeek) 从 transcript 抽取 action items.

入口: 通过环境变量传入 transcript + LLM 配置.
输出: JSON 数组到 GITHUB_OUTPUT 的 action_items key, 也打印到 stdout.
"""
from __future__ import annotations

import json
import os
import sys

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

SYSTEM_PROMPT = "你是会议秘书。你只输出 JSON，不输出任何解释或 markdown 标记。"

USER_PROMPT_TEMPLATE = """从以下会议记录中提取所有"行动项 / 待办 / Action Item"。

要求:
1. 只提取**明确派遣给某人**的具体任务, 不要泛泛之谈或讨论性发言。
2. 输出严格的 JSON 对象, 形如 {{"items": [...]}}。
3. items 数组每个元素含字段:
   - title:        任务标题, 动词开头, ≤30 字
   - description:  补充背景, ≤200 字, 可空
   - assignee_name: 负责人姓名 (从原文找), 没明确指派写空字符串
   - due_date:     截止日期 YYYY-MM-DD, 没说写 null
4. 如果会议没有任何 action item, 返回 {{"items": []}}.

会议记录:
---
{transcript}
---
"""


class ActionItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    assignee_name: str = ""
    due_date: str | None = None


def extract(
    transcript: str,
    api_key: str,
    base_url: str,
    model: str,
) -> list[dict]:
    if not transcript or not transcript.strip():
        print("⚠️ transcript 为空, 跳过 LLM", file=sys.stderr)
        return []

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(transcript=transcript)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2000,
    )
    raw = resp.choices[0].message.content or '{"items": []}'
    obj = json.loads(raw)
    raw_items = obj.get("items", []) if isinstance(obj, dict) else []
    if not isinstance(raw_items, list):
        return []

    validated: list[dict] = []
    for ri in raw_items:
        try:
            validated.append(ActionItem(**ri).model_dump())
        except ValidationError as e:
            print(f"⚠️ 跳过格式不对的 item: {ri} ({e})", file=sys.stderr)
    return validated


def main() -> int:
    transcript = os.environ.get("TRANSCRIPT", "")
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")

    if not api_key:
        print("::error::LLM_API_KEY 未设置", file=sys.stderr)
        return 2

    items = extract(transcript, api_key, base_url, model)
    print(f"提取到 {len(items)} 个 action items")
    print(json.dumps(items, ensure_ascii=False, indent=2))

    # 写 GITHUB_OUTPUT (multi-line)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        out_str = json.dumps(items, ensure_ascii=False)
        with open(gh_out, "a") as f:
            f.write(f"action_items<<EOF\n{out_str}\nEOF\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2：写 test_extract_action_items.py**

```python
"""extract_action_items 单测 - mock OpenAI 客户端."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from extract_action_items import extract


def _mock_client(json_response: str):
    """构造 mock client.chat.completions.create 返回."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = json_response
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    client.chat.completions.create.return_value = resp
    return client


@patch("extract_action_items.OpenAI")
def test_extract_normal_response(mock_openai_class):
    mock_openai_class.return_value = _mock_client(json.dumps({
        "items": [
            {"title": "实现登录", "assignee_name": "张三", "due_date": "2026-04-30"},
            {"title": "写文档", "description": "API 文档", "assignee_name": "李四"},
        ]
    }))
    items = extract("会议内容", "k", "u", "m")
    assert len(items) == 2
    assert items[0]["title"] == "实现登录"
    assert items[0]["due_date"] == "2026-04-30"
    assert items[1]["due_date"] is None


@patch("extract_action_items.OpenAI")
def test_extract_empty_transcript_skips(mock_openai_class):
    items = extract("", "k", "u", "m")
    assert items == []
    mock_openai_class.assert_not_called()


@patch("extract_action_items.OpenAI")
def test_extract_filters_invalid_items(mock_openai_class):
    mock_openai_class.return_value = _mock_client(json.dumps({
        "items": [
            {"title": "正常", "assignee_name": "x"},
            {"title": "", "assignee_name": "y"},  # title 太短, 应被过滤
            {"description": "no title"},  # 缺必填
        ]
    }))
    items = extract("xxx", "k", "u", "m")
    assert len(items) == 1
    assert items[0]["title"] == "正常"


@patch("extract_action_items.OpenAI")
def test_extract_no_items_key_returns_empty(mock_openai_class):
    mock_openai_class.return_value = _mock_client('{"foo": "bar"}')
    assert extract("xxx", "k", "u", "m") == []
```

- [ ] **Step 3：装依赖 + 跑 test**

Run:
```bash
cd scripts
python3 -m pip install --quiet --user openai pydantic
python3 -m pytest test_extract_action_items.py -v
```

Expected: 4 个 test 全 pass。

- [ ] **Step 4：commit**

Run:
```bash
git add scripts/extract_action_items.py scripts/test_extract_action_items.py
git commit -m "feat(scripts): LLM action items 抽取脚本 (DeepSeek 兼容)"
```

**Exit criteria:** test 全 pass。

---

### Task 2.4：飞书任务创建脚本 + tasks.json 维护 🤖 [CLAUDE]

**Files:**
- Create: `scripts/create_feishu_tasks.py`
- Test: `scripts/test_create_feishu_tasks.py`

- [ ] **Step 1：写 create_feishu_tasks.py**

```python
"""读 ACTION_ITEMS_JSON, 调飞书 Task v2 批量建任务, 维护 .planning/tasks.json 映射.

环境变量:
  FEISHU_APP_ID / FEISHU_APP_SECRET   必需
  ACTION_ITEMS_JSON                    必需 (extract step 的输出)
  ISSUE_NUMBER                         必需 (用于 tasks.json 索引)
  GITHUB_OUTPUT                        可选 (写 guids 给下游 step)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from feishu_content import get_tenant_token, FEISHU_BASE

TASKS_JSON_PATH = ".planning/tasks.json"


def create_task(
    tenant_token: str,
    title: str,
    description: str,
    due_date: str | None,
    assignee_open_ids: list[str],
) -> str:
    body: dict = {"summary": title, "description": description}
    if due_date:
        try:
            ts_ms = int(datetime.fromisoformat(due_date).replace(
                tzinfo=timezone.utc
            ).timestamp() * 1000)
            body["due"] = {"timestamp": str(ts_ms), "is_all_day": True}
        except ValueError:
            pass
    if assignee_open_ids:
        body["members"] = [
            {"id": oid, "type": "user", "role": "assignee"}
            for oid in assignee_open_ids
        ]
    r = requests.post(
        f"{FEISHU_BASE}/task/v2/tasks",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"create task 失败: {data}")
    return data.get("data", {}).get("task", {}).get("guid", "")


def load_tasks_map() -> dict:
    p = Path(TASKS_JSON_PATH)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_tasks_map(mapping: dict) -> None:
    p = Path(TASKS_JSON_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    items_raw = os.environ.get("ACTION_ITEMS_JSON", "[]")
    items = json.loads(items_raw)
    if not items:
        print("ℹ️ 没有 action items, 跳过任务创建")
        return 0

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    if not (app_id and app_secret and issue_num):
        print("::error::缺 FEISHU_APP_ID / FEISHU_APP_SECRET / ISSUE_NUMBER", file=sys.stderr)
        return 2

    tenant_token = get_tenant_token(app_id, app_secret)

    created: list[dict] = []  # {guid, title, assignee_name, due_date}
    for item in items:
        # TODO: assignee_name -> open_id 解析 (Phase 5 改进, 当前直接空列表)
        guid = create_task(
            tenant_token,
            title=item.get("title", "未命名"),
            description=item.get("description", ""),
            due_date=item.get("due_date"),
            assignee_open_ids=[],
        )
        if guid:
            created.append({
                "guid": guid,
                "title": item.get("title", ""),
                "assignee_name": item.get("assignee_name", ""),
                "due_date": item.get("due_date"),
            })
            print(f"  ✅ {item.get('title')} -> {guid}")

    # 维护 tasks.json
    mapping = load_tasks_map()
    key = f"issue#{issue_num}"
    mapping.setdefault(key, []).extend(created)
    save_tasks_map(mapping)
    print(f"已写 {TASKS_JSON_PATH}, key={key}")

    # 输出给 workflow
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        guids = " ".join(c["guid"] for c in created)
        with open(gh_out, "a") as f:
            f.write(f"task_count={len(created)}\n")
            f.write(f"guids={guids}\n")
            md_lines = "\\n".join(
                f"- {c['title']} ({c['assignee_name'] or '未指派'}): {c['guid']}"
                for c in created
            )
            f.write(f"task_md<<EOF\n{md_lines}\nEOF\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2：写 test_create_feishu_tasks.py**

```python
"""create_feishu_tasks 单测."""
from __future__ import annotations

import json
import os
import responses
from unittest.mock import patch

import create_feishu_tasks


@responses.activate
def test_create_tasks_writes_mapping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # mock token
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    # mock create_task (调 2 次)
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 0, "data": {"task": {"guid": "g-1"}}},
    )
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 0, "data": {"task": {"guid": "g-2"}}},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("ISSUE_NUMBER", "42")
    monkeypatch.setenv("ACTION_ITEMS_JSON", json.dumps([
        {"title": "实现登录", "description": "", "assignee_name": "张三", "due_date": "2026-04-30"},
        {"title": "写文档", "description": "API 文档", "assignee_name": "李四", "due_date": None},
    ]))

    rc = create_feishu_tasks.main()
    assert rc == 0

    # tasks.json 存在 + 内容正确
    mapping = json.loads((tmp_path / ".planning/tasks.json").read_text())
    assert "issue#42" in mapping
    assert len(mapping["issue#42"]) == 2
    assert mapping["issue#42"][0]["guid"] == "g-1"


def test_no_items_returns_zero(monkeypatch):
    monkeypatch.setenv("ACTION_ITEMS_JSON", "[]")
    monkeypatch.setenv("FEISHU_APP_ID", "x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "y")
    monkeypatch.setenv("ISSUE_NUMBER", "1")
    assert create_feishu_tasks.main() == 0
```

- [ ] **Step 3：跑 test**

Run:
```bash
cd scripts
python3 -m pytest test_create_feishu_tasks.py -v
```

Expected: 2 个 test 全 pass。

- [ ] **Step 4：commit**

Run:
```bash
git add scripts/create_feishu_tasks.py scripts/test_create_feishu_tasks.py
git commit -m "feat(scripts): 飞书任务批量创建 + tasks.json 映射维护 + 单测"
```

**Exit criteria:** test 全 pass。

---

### Task 2.5：会议归档脚本 🤖 [CLAUDE]

**Files:** Create: `scripts/archive_meeting.py`

- [ ] **Step 1：写 archive_meeting.py**

```python
"""把会议元信息 + 提取结果归档为 markdown 到 .planning/meetings/.

归档策略 B: 不存原文 transcript, 只存元信息 + action items + task GUIDs.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


TEMPLATE = """# {title}

- **日期**: {date}
- **入口 issue**: #{issue_number}
- **原始链接**: {feishu_url}
- **生成时间 (UTC)**: {generated_at}

## AI 提取的 Action Items

{table}

> 归档策略 B: transcript 原文留在飞书, 此处仅留元信息和 AI 抽取结果.
"""


def build_table(items: list[dict]) -> str:
    if not items:
        return "_(本次会议未提取到 action items)_"
    lines = ["| # | 任务 | 负责人 | 截止 | 飞书 Task GUID |", "|---|---|---|---|---|"]
    for i, it in enumerate(items, 1):
        title = (it.get("title") or "").replace("|", "\\|")
        assignee = (it.get("assignee_name") or "未指派").replace("|", "\\|")
        due = it.get("due_date") or "—"
        guid = it.get("guid") or "(创建失败)"
        lines.append(f"| {i} | {title} | {assignee} | {due} | `{guid}` |")
    return "\n".join(lines)


def main() -> int:
    title = os.environ.get("MEETING_TITLE", "未命名会议")
    date = os.environ.get("MEETING_DATE") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    issue_num = os.environ.get("ISSUE_NUMBER", "?")
    feishu_url = os.environ.get("FEISHU_URL", "")

    # 从 tasks.json 取本次的 created 条目
    tasks_path = Path(".planning/tasks.json")
    items: list[dict] = []
    if tasks_path.exists():
        mapping = json.loads(tasks_path.read_text(encoding="utf-8"))
        items = mapping.get(f"issue#{issue_num}", [])

    md = TEMPLATE.format(
        title=title,
        date=date,
        issue_number=issue_num,
        feishu_url=feishu_url or "(未提供)",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        table=build_table(items),
    )

    out_path = Path(f".planning/meetings/{date}-issue{issue_num}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(str(out_path))  # 输出文件路径供 workflow 用
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2：手动 smoke test**

Run:
```bash
cd /Users/jimmy/Documents/Projects/devops-sandbox
mkdir -p /tmp/archive-test/.planning
echo '{"issue#99": [{"guid":"g-1","title":"测试任务","assignee_name":"张三","due_date":"2026-05-01"}]}' \
  > /tmp/archive-test/.planning/tasks.json
cd /tmp/archive-test
MEETING_TITLE="测试会议" MEETING_DATE="2026-04-23" ISSUE_NUMBER="99" \
  FEISHU_URL="https://meetings.feishu.cn/minutes/xxx" \
  python3 /Users/jimmy/Documents/Projects/devops-sandbox/scripts/archive_meeting.py
cat .planning/meetings/2026-04-23-issue99.md
cd /Users/jimmy/Documents/Projects/devops-sandbox
rm -rf /tmp/archive-test
```

Expected: 输出 markdown，含表格行 `| 1 | 测试任务 | 张三 | 2026-05-01 | \`g-1\` |`。

- [ ] **Step 3：commit**

Run:
```bash
git add scripts/archive_meeting.py
git commit -m "feat(scripts): 会议归档脚本 (策略 B - 链接 + 提取结果)"
```

**Exit criteria:** smoke test 输出正确 markdown。

---

## Phase 3：Issue Form + workflow

### Task 3.1：Issue Form 模板 🤖 [CLAUDE]

**Files:** Create: `.github/ISSUE_TEMPLATE/meeting.yml`

- [ ] **Step 1：写 ISSUE_TEMPLATE/meeting.yml**

```yaml
name: 📝 处理会议记录
description: 上传飞书会议链接, AI 自动抽取 action items 并在飞书创建任务
title: "[Meeting] "
labels: ["meeting"]
body:
  - type: markdown
    attributes:
      value: |
        ## 使用说明
        - 把要处理的会议**飞书链接**（妙记 / 云文档 / Wiki）粘贴下来
        - 应用必须有访问权限（已加入「会议纪要」知识库的资源默认可读）
        - 提交后 GitHub Actions 自动运行, 1-2 分钟出结果

  - type: input
    id: meeting_title
    attributes:
      label: 会议标题
      placeholder: 4月23日 项目立项会
    validations:
      required: true

  - type: input
    id: meeting_date
    attributes:
      label: 会议日期 (YYYY-MM-DD)
      placeholder: "2026-04-23"
    validations:
      required: true

  - type: input
    id: feishu_url
    attributes:
      label: 飞书链接 (妙记/Docx/Wiki)
      description: |
        支持以下形态:
        - https://meetings.feishu.cn/minutes/xxx (妙记, 推荐)
        - https://*.feishu.cn/docx/xxx
        - https://*.feishu.cn/wiki/xxx
      placeholder: https://meetings.feishu.cn/minutes/abc123xyz
    validations:
      required: true

  - type: textarea
    id: notes
    attributes:
      label: 备注 (可选)
      description: 任何想给 AI 的额外说明 (例如"重点关注前 30 分钟")
```

- [ ] **Step 2：commit**

Run:
```bash
git add .github/ISSUE_TEMPLATE/meeting.yml
git commit -m "feat(issues): 会议记录处理 Issue Form 模板"
```

**Exit criteria:** 模板已 commit。

---

### Task 3.2：process-meeting workflow 🤖 [CLAUDE]

**Files:** Create: `.github/workflows/process-meeting.yml`

- [ ] **Step 1：写 workflow**

```yaml
name: Process Meeting Record

on:
  issues:
    types: [opened, labeled]

permissions:
  contents: write
  issues: write

jobs:
  process:
    if: contains(github.event.issue.labels.*.name, 'meeting')
    runs-on: ubuntu-latest
    env:
      ISSUE_NUMBER: ${{ github.event.issue.number }}
      ISSUE_BODY: ${{ github.event.issue.body }}
      ISSUE_TITLE: ${{ github.event.issue.title }}
      FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
      FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
      LLM_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
      LLM_BASE_URL: https://api.deepseek.com/v1
      LLM_MODEL: deepseek-chat
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - run: pip install requests openai pydantic

      - name: Parse issue form fields
        id: parse
        run: python scripts/parse_meeting_issue.py

      - name: Fetch transcript from Feishu
        id: fetch
        env:
          FEISHU_URL: ${{ steps.parse.outputs.feishu_url }}
        run: python scripts/fetch_transcript_for_workflow.py

      - name: Extract action items via LLM
        id: extract
        env:
          TRANSCRIPT: ${{ steps.fetch.outputs.transcript }}
        run: python scripts/extract_action_items.py

      - name: Create Feishu tasks
        id: tasks
        env:
          ACTION_ITEMS_JSON: ${{ steps.extract.outputs.action_items }}
        run: python scripts/create_feishu_tasks.py

      - name: Archive meeting
        env:
          MEETING_TITLE: ${{ steps.parse.outputs.meeting_title }}
          MEETING_DATE: ${{ steps.parse.outputs.meeting_date }}
          FEISHU_URL: ${{ steps.parse.outputs.feishu_url }}
        run: |
          path=$(python scripts/archive_meeting.py)
          echo "archive_path=$path" >> "$GITHUB_OUTPUT"
        id: archive

      - name: Commit archive
        run: |
          git config user.name "meeting-bot"
          git config user.email "meeting-bot@users.noreply.github.com"
          git add .planning/
          git diff --cached --quiet || git commit -m "docs(meeting): 归档 #${ISSUE_NUMBER}"
          git push origin HEAD:dev || echo "::warning::push 失败 (可能权限不足或冲突)"

      - name: Comment on issue and close
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TASK_COUNT: ${{ steps.tasks.outputs.task_count }}
          TASK_MD: ${{ steps.tasks.outputs.task_md }}
          ARCHIVE_PATH: ${{ steps.archive.outputs.archive_path }}
        run: |
          gh issue comment "$ISSUE_NUMBER" --body "✅ 已处理完成

          ## 创建了 ${TASK_COUNT:-0} 个飞书任务

          ${TASK_MD:-(无)}

          ## 归档
          [\`${ARCHIVE_PATH}\`](../tree/dev/${ARCHIVE_PATH})
          "
          gh issue close "$ISSUE_NUMBER"
```

- [ ] **Step 2：写两个辅助脚本 (parse_meeting_issue.py + fetch_transcript_for_workflow.py)**

Create `scripts/parse_meeting_issue.py`:
```python
"""从 GitHub Issue Form 生成的 body 解析字段, 输出到 GITHUB_OUTPUT."""
from __future__ import annotations

import os
import re
import sys


def extract_field(body: str, label: str) -> str:
    """Issue Form 在 body 里以 `### <Label>\n\n<value>\n\n###` 形式排版."""
    pattern = rf"###\s*{re.escape(label)}\s*\n+(.*?)(?=\n###|\Z)"
    m = re.search(pattern, body, re.S)
    return m.group(1).strip() if m else ""


def main() -> int:
    body = os.environ.get("ISSUE_BODY", "")
    title = extract_field(body, "会议标题") or os.environ.get("ISSUE_TITLE", "未命名").replace("[Meeting]", "").strip()
    date = extract_field(body, "会议日期 (YYYY-MM-DD)")
    url = extract_field(body, "飞书链接 (妙记/Docx/Wiki)")

    if not url:
        print("::error::issue body 里没找到飞书链接字段", file=sys.stderr)
        return 2

    gh_out = os.environ["GITHUB_OUTPUT"]
    with open(gh_out, "a") as f:
        f.write(f"meeting_title={title}\n")
        f.write(f"meeting_date={date}\n")
        f.write(f"feishu_url={url}\n")
    print(f"meeting_title={title}\nmeeting_date={date}\nfeishu_url={url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Create `scripts/fetch_transcript_for_workflow.py`:
```python
"""调 feishu_url 解析 + feishu_content 拉文本, 写到 GITHUB_OUTPUT.

也存到一个临时文件中, 长 transcript 通过文件传更可靠 (env var 有大小限制).
"""
from __future__ import annotations

import os
import sys

from feishu_url import parse_feishu_url, InvalidFeishuURL
from feishu_content import fetch_content, get_tenant_token


def main() -> int:
    url = os.environ.get("FEISHU_URL", "")
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")

    try:
        kind, token = parse_feishu_url(url)
    except InvalidFeishuURL as e:
        print(f"::error::飞书 URL 无效: {e}", file=sys.stderr)
        return 2

    print(f"📥 拉取 kind={kind}, token={token[:8]}...")
    tenant_token = get_tenant_token(app_id, app_secret)
    text = fetch_content(kind, token, tenant_token)
    print(f"✅ 拿到 {len(text)} 字符")

    gh_out = os.environ["GITHUB_OUTPUT"]
    with open(gh_out, "a") as f:
        f.write(f"transcript<<TRANSCRIPT_EOF\n{text}\nTRANSCRIPT_EOF\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3：本地 lint + import 检查**

Run:
```bash
cd scripts
python3 -c "import parse_meeting_issue, fetch_transcript_for_workflow; print('ok')"
```

Expected: 输出 `ok`。

- [ ] **Step 4：commit**

Run:
```bash
git add .github/workflows/process-meeting.yml \
  scripts/parse_meeting_issue.py scripts/fetch_transcript_for_workflow.py
git commit -m "feat(workflow): process-meeting 全链路 + 辅助解析脚本"
```

**Exit criteria:** 文件已 commit。

---

### Task 3.3：保护 process-meeting workflow 不被恶意 issue 触发 🤖 [CLAUDE]

> Issue body 由用户输入, FEISHU_URL 是不可信输入。已在 fetch 阶段 `parse_feishu_url` 校验，再补一道 commit 时的安全说明。

- [ ] **Step 1：在 process-meeting.yml 头部加注释**

直接在文件头加：
```yaml
# 安全设计:
#   - 所有不可信 issue body 字段通过 env: 块注入, 不在 run: 里直接展开
#   - feishu_url 必须通过 scripts/feishu_url.py 白名单校验 (kind ∈ {minutes,docx,docs,wiki})
#   - LLM 调用对 transcript 不做内容过滤, 但 prompt 里 system 强制只输出 JSON
#   - 所有 secret 通过 GitHub Actions secret 注入, 不进 issue / 归档
```

- [ ] **Step 2：commit (作为前一个 commit 的 amend 或新 commit)**

```bash
git add .github/workflows/process-meeting.yml
git commit -m "docs(workflow): process-meeting 安全设计说明"
```

**Exit criteria:** 注释已加。

---

## Phase 4：扩展 commit → task PATCH 链路

### Task 4.1：扩展 commit_lint.py 支持 [TASK-xxx] 标签 🤖 [CLAUDE]

**Files:** Modify: `scripts/commit_lint.py`

- [ ] **Step 1：在 `validate_subject` 里允许尾缀 `[TASK-xxx]` 或 `[DONE-TASK-xxx]`**

读源码 (Read):
```bash
cat scripts/commit_lint.py | head -100
```

修改：把每个 pattern 末尾的 `\S.*$` 改为允许可选 task 标签。

具体做法：在文件顶部加新 regex：

```python
TASK_TAG_RE = re.compile(r"\s*\[(?:DONE-)?TASK-[A-Za-z0-9_-]+\]\s*$")
```

修改 `validate_subject`：
```python
def validate_subject(subject: str) -> tuple[bool, str]:
    # 把尾部的 [TASK-xxx] / [DONE-TASK-xxx] 暂时剥掉, 只看主体格式
    bare = TASK_TAG_RE.sub("", subject).strip()

    if MERGE_PATTERN.match(bare):
        return True, "merge"
    if DELIVERABLE_PATTERN.match(bare):
        return True, "deliverable"
    if PHASE_PATTERN.match(bare):
        return True, "phase"
    if CONVENTIONAL_PATTERN.match(bare):
        return True, "conventional"
    return False, "..."
```

- [ ] **Step 2：加单测**

Create `scripts/test_commit_lint.py`:
```python
"""commit_lint 单测."""
from commit_lint import validate_subject


def test_conventional_with_task_tag():
    ok, kind = validate_subject("feat(api): 实现登录 [TASK-abc123]")
    assert ok and kind == "conventional"


def test_conventional_with_done_task_tag():
    ok, kind = validate_subject("fix: 修登录 bug [DONE-TASK-abc123]")
    assert ok and kind == "conventional"


def test_deliverable_with_task_tag():
    ok, kind = validate_subject("[DEL-04] 文档解析器完成 [TASK-xyz]")
    assert ok and kind == "deliverable"


def test_plain_conventional_still_works():
    ok, kind = validate_subject("feat: 加一个功能")
    assert ok and kind == "conventional"


def test_invalid_format_rejected():
    ok, _ = validate_subject("just random text")
    assert not ok


def test_invalid_task_tag_format_rejected():
    # task tag 单独不能作为主体
    ok, _ = validate_subject("[TASK-abc] xxx")
    assert not ok
```

- [ ] **Step 3：跑 test**

Run:
```bash
cd scripts
python3 -m pytest test_commit_lint.py -v
```

Expected: 6 个 test 全 pass。

- [ ] **Step 4：commit**

Run:
```bash
git add scripts/commit_lint.py scripts/test_commit_lint.py
git commit -m "feat(commit-lint): 支持 [TASK-xxx] / [DONE-TASK-xxx] 尾标签"
```

**Exit criteria:** test 全 pass，commit 完成。

---

### Task 4.2：写 update_feishu_task.py 🤖 [CLAUDE]

**Files:** Create: `scripts/update_feishu_task.py`

- [ ] **Step 1：写 update_feishu_task.py**

```python
"""调飞书 Task v2 PATCH 接口更新任务状态.

环境变量:
  FEISHU_APP_ID / FEISHU_APP_SECRET    必需
  COMMIT_MESSAGE                        必需 (从 sync_feishu workflow 传)
  COMMIT_SHA / REPO_NAME / ACTOR        可选 (审计信息)

行为:
  - 解析 commit subject 里的 [TASK-xxx] / [DONE-TASK-xxx]
  - 反查 .planning/tasks.json 拿 task guid
  - DONE 标签 -> PATCH complete=true
  - 普通 TASK 标签 -> 当前实现仅打 log (in_progress 推进留给后续扩展)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

from feishu_content import get_tenant_token, FEISHU_BASE

TASK_RE = re.compile(r"\[(DONE-)?TASK-([A-Za-z0-9_-]+)\]")
TASKS_JSON = Path(".planning/tasks.json")


def find_task_guid(short_or_full: str) -> str | None:
    """从 tasks.json 找匹配的 guid (前缀匹配, 因为 commit 标签里只放短 id)."""
    if not TASKS_JSON.exists():
        return None
    mapping = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    for entries in mapping.values():
        for e in entries:
            guid = e.get("guid", "")
            if guid == short_or_full or guid.startswith(short_or_full):
                return guid
    return None


def patch_task_complete(token: str, guid: str) -> None:
    r = requests.patch(
        f"{FEISHU_BASE}/task/v2/tasks/{guid}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "task": {"completed_at": str(int(__import__('time').time() * 1000))},
            "update_fields": ["completed_at"],
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"PATCH 任务失败: {data}")
    print(f"  ✅ task {guid} 标记完成")


def main() -> int:
    msg = os.environ.get("COMMIT_MESSAGE", "")
    if not msg:
        print("ℹ️ COMMIT_MESSAGE 为空, 跳过")
        return 0

    matches = list(TASK_RE.finditer(msg))
    if not matches:
        print("ℹ️ commit 不含 [TASK-xxx] / [DONE-TASK-xxx], 跳过")
        return 0

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not (app_id and app_secret):
        print("::warning::缺 FEISHU_APP_ID/SECRET, 跳过", file=sys.stderr)
        return 0

    token = get_tenant_token(app_id, app_secret)

    for m in matches:
        is_done = bool(m.group(1))
        short_id = m.group(2)
        guid = find_task_guid(short_id)
        if not guid:
            print(f"::warning::未在 tasks.json 找到 TASK-{short_id}", file=sys.stderr)
            continue
        if is_done:
            patch_task_complete(token, guid)
        else:
            # 留给后续: in_progress 状态推进
            print(f"  ℹ️ 引用 task {guid} (非 DONE, 暂不改状态)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2：写单测**

Create `scripts/test_update_feishu_task.py`:
```python
"""update_feishu_task 单测."""
import json
import responses
import update_feishu_task


def test_no_task_tag_in_message_skips(monkeypatch):
    monkeypatch.setenv("COMMIT_MESSAGE", "feat: 普通提交")
    assert update_feishu_task.main() == 0


def test_no_message_skips(monkeypatch):
    monkeypatch.delenv("COMMIT_MESSAGE", raising=False)
    assert update_feishu_task.main() == 0


@responses.activate
def test_done_tag_calls_patch(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".planning").mkdir()
    (tmp_path / ".planning/tasks.json").write_text(
        json.dumps({"issue#1": [{"guid": "g-abc123", "title": "x"}]})
    )

    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    responses.add(
        responses.PATCH,
        "https://open.feishu.cn/open-apis/task/v2/tasks/g-abc123",
        json={"code": 0, "data": {}},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("COMMIT_MESSAGE", "fix: 修 bug [DONE-TASK-g-abc123]")

    assert update_feishu_task.main() == 0
```

- [ ] **Step 3：跑 test**

Run:
```bash
cd scripts
python3 -m pytest test_update_feishu_task.py -v
```

Expected: 3 个 test pass。

- [ ] **Step 4：commit**

Run:
```bash
git add scripts/update_feishu_task.py scripts/test_update_feishu_task.py
git commit -m "feat(scripts): commit -> 飞书任务状态推进 (PATCH /task/v2/tasks/:guid)"
```

**Exit criteria:** test 全 pass。

---

### Task 4.3：扩展 feishu-sync.yml 调 update_feishu_task 🤖 [CLAUDE]

**Files:** Modify: `.github/workflows/feishu-sync.yml`

- [ ] **Step 1：在 sync job 后追加新 step**

现有 workflow 的 `python scripts/sync_feishu.py` 之后追加：

```yaml
      - name: Update Feishu task status (推进 [TASK-xxx])
        if: github.event_name == 'push'
        env:
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          COMMIT_MESSAGE: ${{ github.event.head_commit.message }}
          COMMIT_SHA: ${{ github.sha }}
          REPO_NAME: ${{ github.repository }}
          ACTOR: ${{ github.actor }}
        run: python scripts/update_feishu_task.py
```

注意：`if: github.event_name == 'push'` 是因为 PR 事件没 head_commit。

- [ ] **Step 2：commit**

Run:
```bash
git add .github/workflows/feishu-sync.yml
git commit -m "feat(workflow): feishu-sync 加 commit -> task 状态推进 step"
```

**Exit criteria:** workflow 已更新并 commit。

---

## Phase 5：E2E 测试

### Task 5.1：开 PR 把所有改动合到 dev 🤖 [CLAUDE]

- [ ] **Step 1：从 dev 切新分支汇总 Phase 2-4 commits**

Run:
```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/meeting-task-automation

# 把 Phase 2-4 的 commits cherry-pick 过来 (假设我们一直在某分支提交)
# 或者直接在这条分支重做 Phase 2-4 的 commits
```

> 实际操作中, Phase 2-4 的 commits 都直接做在这条分支上即可, 不需要 cherry-pick.

- [ ] **Step 2：push + 开 PR**

Run:
```bash
git push -u origin feat/meeting-task-automation
gh pr create --base dev --head feat/meeting-task-automation \
  --title "feat: meeting → AI → 飞书任务自动化主链路" \
  --body "本 PR 实现两条核心闭环:
  1. Issue (飞书链接) → process-meeting workflow → 飞书任务创建
  2. commit ([TASK-xxx]) → feishu-sync workflow → 飞书任务状态 PATCH

  详见 docs/superpowers/plans/2026-04-23-meeting-task-automation.md
  "
```

- [ ] **Step 3：等 CI + CodeRabbit 通过**

Run:
```bash
PR_NUM=$(gh pr list --state open --head feat/meeting-task-automation --json number -q '.[0].number')
until gh pr checks "$PR_NUM" 2>&1 | grep -qv 'pending'; do sleep 30; done
gh pr checks "$PR_NUM"
```

Expected: 全 pass.

- [ ] **Step 4：merge**

Run:
```bash
gh pr merge "$PR_NUM" --squash --delete-branch \
  --subject "feat: meeting → AI → 飞书任务自动化主链路"
git checkout dev
git pull --ff-only origin dev
```

**Exit criteria:** dev 已含整套自动化代码。

---

### Task 5.2：开 dev → main release PR 🤖 [CLAUDE]

> 必须 main 上有 process-meeting workflow + 4 个 secrets 已生效, Issue 才能正确触发.

- [ ] **Step 1：开 release PR**

Run:
```bash
gh pr create --base main --head dev \
  --title "release: meeting → AI → 飞书任务自动化 + ai_review 回滚" \
  --body "Release 内容:
  1. ai_review 回滚到 smoke test 占位 (PR #7)
  2. meeting-task-automation 全链路 (本计划 Phase 2-4 全部 commit)

  必须先在 Org Settings 配齐 4 个 secrets (DEEPSEEK_API_KEY, FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BOT_WEBHOOK_URL) 才能正常运行 process-meeting."
```

- [ ] **Step 2：等绿后合**

Run:
```bash
RELEASE_PR=$(gh pr list --state open --base main --head dev --json number -q '.[0].number')
until gh pr checks "$RELEASE_PR" 2>&1 | grep -qv 'pending'; do sleep 30; done
gh pr merge "$RELEASE_PR" --merge --subject "Merge dev into main: meeting-task-automation release"
git checkout main && git pull --ff-only origin main
```

**Exit criteria:** main 已含全部代码。

---

### Task 5.3：用真飞书会议链接做 E2E 测试 🤝 [MIXED]

**前置:** Phase 1 全部完成（4 个 org secrets + 应用权限 + Wiki 测试妙记）。

- [ ] **Step 1：你打开 GitHub Issues 页 🧑**

打开 https://github.com/future-youth-ai/devops-sandbox/issues
点 "New issue" → 选 "📝 处理会议记录"。

- [ ] **Step 2：填表单 🧑**

| 字段 | 值 |
|---|---|
| 会议标题 | E2E 测试-XX |
| 会议日期 (YYYY-MM-DD) | 今天 |
| 飞书链接 | 你 Task 1.2 拿到的测试妙记 URL |
| 备注 | （留空） |

点 "Submit new issue"。

- [ ] **Step 3：观察 workflow 触发 🤖**

Run:
```bash
sleep 30
gh run list --workflow="process-meeting.yml" --limit 3
RUN_ID=$(gh run list --workflow="process-meeting.yml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID"
```

Expected: workflow 跑完, conclusion=success.

- [ ] **Step 4：你看 issue + 飞书 🧑**

- 在 issue 里应看到 bot 评论 "✅ 已处理完成", 列出创建的任务
- issue 状态变成 closed
- 打开飞书任务面板 → "我的任务" → 应能看到本次创建的任务们

- [ ] **Step 5：失败排查（如果上面任一步出问题）🤝**

| 症状 | 排查 |
|---|---|
| workflow 没触发 | 看 issue 是否有 `meeting` label (Issue Form 自动加, 没有手动加) |
| feishu_url 解析失败 | 看 run log 里 `parse_feishu_url` 错误 |
| 拉不到 transcript | `code=99991672` → 应用没权限, 检查会议是否在"会议纪要"知识库下 |
| LLM 报错 | `LLM_API_KEY` 未配 / 余额不足 |
| 任务创建失败 | `task:task` 权限没申请 |

**Exit criteria:** issue 评论看到任务列表, 飞书任务面板看到任务真的存在.

---

### Task 5.4：测 commit → task PATCH 推进 🤝 [MIXED]

- [ ] **Step 1：从飞书任务里挑一个, 复制其 GUID 🧑**

(GUID 通常显示在飞书任务详情 URL 里, 或在 Task 5.3 的 issue comment 里有列出)

- [ ] **Step 2：在 dev 分支造一条带 [DONE-TASK-xxx] 的 commit 🤖**

Run:
```bash
git checkout dev && git pull
echo "" >> README.md
git add README.md
git commit -m "test: E2E 推进任务 [DONE-TASK-<贴你的 guid>]"
git push origin dev
```

> ⚠️ 这个 commit 走 commit-lint, 因为 dev 分支不是 PR target 所以不被强制. 但 push 到 main 才触发 feishu-sync. 走 dev → main PR 比较干净.

- [ ] **Step 3：开 dev → main PR + merge 🤖**

```bash
gh pr create --base main --head dev --title "test: E2E 任务推进 demo"
PR_NUM=$(gh pr list --state open --base main --head dev --json number -q '.[0].number')
until gh pr checks "$PR_NUM" 2>&1 | grep -qv 'pending'; do sleep 30; done
gh pr merge "$PR_NUM" --merge
```

- [ ] **Step 4：观察 feishu-sync workflow 🤖**

```bash
gh run list --workflow="feishu-sync.yml" --limit 3
RUN_ID=$(gh run list --workflow="feishu-sync.yml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run view "$RUN_ID" --log | grep -E "(task|TASK|完成)"
```

Expected: 看到 `✅ task g-xxx 标记完成`.

- [ ] **Step 5：你确认飞书任务状态变了 🧑**

打开飞书任务, 应看到任务已勾选完成.

**Exit criteria:** 飞书任务从待办变成完成.

---

## Phase 6：收尾

### Task 6.1：清 stale 分支 🤖 [CLAUDE]

- [ ] **Step 1：删远端 stale**

```bash
for b in feat/coderabbit-auto-sync fix/meeting-bot-api-paths feat/ai-review-skeleton chore/remove-placeholder; do
  git push origin --delete "$b" 2>/dev/null || true
done
git fetch --prune
git branch -r
```

Expected: 仅剩 main + dev.

- [ ] **Step 2：删本地 stale**

```bash
for b in feat/coderabbit-auto-sync fix/meeting-bot-api-paths feat/ai-review-skeleton chore/remove-placeholder chore/rollback-ai-review-to-smoke-test feat/meeting-task-automation; do
  git branch -D "$b" 2>/dev/null || true
done
git branch
```

Expected: dev + main.

**Exit criteria:** 分支干净。

---

### Task 6.2：写 ONBOARDING.md 让别的 repo 复用 🤖 [CLAUDE]

**Files:** Create: `ONBOARDING.md`

- [ ] **Step 1：写新 repo 接入指南**

```markdown
# 接入 Meeting → 飞书任务自动化

## 1. 复制资产到你的新 repo

\`\`\`bash
# 在新 repo 根目录:
cp -r /path/to/devops-sandbox/.github/ISSUE_TEMPLATE/meeting.yml \
      ./.github/ISSUE_TEMPLATE/
cp -r /path/to/devops-sandbox/.github/workflows/{process-meeting,feishu-sync,commit-lint}.yml \
      ./.github/workflows/
cp -r /path/to/devops-sandbox/scripts/ ./scripts/
\`\`\`

## 2. 把新 repo 加到 Org Secrets 的 access list

打开 https://github.com/organizations/future-youth-ai/settings/secrets/actions
对每个 secret 点 "Update", 在 "Repository access" 勾上你的新 repo.

## 3. 验证

开个测试 issue, 走一遍流程.

## 涉及的 secrets

- DEEPSEEK_API_KEY
- FEISHU_APP_ID
- FEISHU_APP_SECRET
- FEISHU_BOT_WEBHOOK_URL (可选)
```

- [ ] **Step 2：commit + 走 PR 入 main (因为 main 有 branch protection)**

```bash
git checkout dev && git pull
git checkout -b docs/onboarding
git add ONBOARDING.md
git commit -m "docs: 添加新 repo 接入指南"
git push -u origin docs/onboarding
gh pr create --base dev --head docs/onboarding --title "docs: 添加新 repo 接入指南"
# 等绿合并
```

**Exit criteria:** ONBOARDING.md 已合到 dev (将随下次 release 入 main)。

---

### Task 6.3：配 main 分支保护 🤖 [CLAUDE]

> 跟 finish-line plan 的 Phase 5 一样, 此处简化版.

- [ ] **Step 1：拿当前 check 名字**

```bash
LATEST=$(git rev-parse main)
gh api "repos/future-youth-ai/devops-sandbox/commits/$LATEST/check-runs" \
  -q '.check_runs[].name' | sort -u
```

- [ ] **Step 2：应用 protection**

```bash
cat > /tmp/main-protection.json <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Commit Lint",
      "TruffleHog (repo-wide)",
      "ai_review / CI Gate",
      "meeting_bot / CI Gate"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
gh api -X PUT repos/future-youth-ai/devops-sandbox/branches/main/protection \
  --input /tmp/main-protection.json | head -10
```

- [ ] **Step 3：反向验证 (尝试 push 应被拒)**

```bash
git checkout main && echo "" >> README.md && git add README.md
git commit -m "test: should be rejected"
git push origin main 2>&1 || echo "✅ rejected as expected"
git reset --hard HEAD~1
```

**Exit criteria:** main 上锁, 直接 push 被拒.

---

## Definition of Done

- [ ] Phase 0: PR #7 已合并到 dev
- [ ] Phase 1: 飞书 App + Wiki 空间 + DeepSeek + 4 个 Org Secrets 全部配好
- [ ] Phase 2: 5 个核心脚本全部实现 + 单测全 pass
- [ ] Phase 3: Issue Form + process-meeting workflow 已落地
- [ ] Phase 4: commit → task PATCH 链路 + commit_lint 扩展
- [ ] Phase 5.3: E2E 真实测试: 开 Issue → 飞书任务列表里看到任务
- [ ] Phase 5.4: E2E commit 推进: commit `[DONE-TASK-xxx]` → 飞书任务变完成
- [ ] Phase 6: stale 分支清理, ONBOARDING.md 写好, main 上锁

---

## 全局风险表

| 风险 | 缓解 |
|---|---|
| 飞书应用权限审批拖延 | Phase 1 提早开始, 别等到最后 |
| transcript 太长超 LLM 上下文 | extract 脚本里加分段处理 (留给后续) |
| LLM 抽取的 assignee 名字对不上飞书 open_id | 当前实现是空 assignee, Phase 5.3 跑一遍后再优化 |
| GitHub Actions runner 超时 | 当前所有任务 < 1 分钟, 远低于 6 小时上限 |
| Org secrets 误配漏 repo | Phase 1.4 Step 3 验证可见性 |
| Issue body 注入恶意内容 | Phase 3.3 注释 + parse_meeting_issue 仅按白名单字段提取 |

---

## 时间估算

| Phase | 你 (USER) | 我 (CLAUDE) |
|---|---|---|
| 0 | 0 | 10-15 min |
| 1 | **30-60 min**（飞书审批可能拖到次日）| 0 |
| 2 | 0 | 30-45 min |
| 3 | 0 | 15-20 min |
| 4 | 0 | 15-20 min |
| 5.1+5.2 | 0 | 15-20 min |
| 5.3+5.4 | **15 min**（开 issue + 看飞书）| 5 min |
| 6 | 0 | 15-20 min |
| **合计** | **45-75 min** | **~2 小时** |

---

## 执行模式选择

按 superpowers:writing-plans 规范, 你选一种:

**1. Subagent-Driven (推荐)** — 我每完成一个 Task 派一个 fresh subagent, 你 review 后我再派下一个. 上下文清爽, 但需要你审 N 次.

**2. Inline Execution** — 在当前会话顺序执行. 连续, 但日志多.

回我 `1` 或 `2`, 以及 **从哪个 Phase 开始** (默认 Phase 0).

注意 Phase 1 是阻塞 Phase 5 测试的, 但不阻塞 Phase 2-4 写代码. 推荐节奏:

- 我**立刻**开始 Phase 0 + Phase 2-4 (代码部分, ~2 小时)
- 你**并行**做 Phase 1 (你的 USER ACTION, 30-60 min)
- 我做完代码, 等你 Phase 1 ready, 一起做 Phase 5 E2E
- 最后 Phase 6 收尾

要这个并行节奏吗？
