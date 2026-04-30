# DevOps Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `future-youth-ai/devops-template` GitHub Template Repository by extracting and generalizing the automation infrastructure from `devops-sandbox`.

**Architecture:** New repo with `config.yml` as single configuration entry point. All scripts read config via a shared `config_loader.py` module. Environment variables (from GitHub Secrets) override config.yml values. `archive_meeting.py` rewired to write Feishu cloud docs instead of git.

**Tech Stack:** Python 3.11, GitHub Actions, Feishu Open API, DeepSeek LLM, Ruff, TruffleHog, CodeRabbit

**Spec:** `docs/superpowers/specs/2026-04-30-devops-template-design.md`

---

### Task 1: Create the template repository and seed it with files from devops-sandbox

**Files:**
- Create: `future-youth-ai/devops-template` (new GitHub repo)
- Copy from devops-sandbox: `scripts/`, `.github/`, `.claude/`, `.coderabbit.yaml`, `.gitignore`

- [ ] **Step 1: Create the repository on GitHub**

```bash
gh repo create future-youth-ai/devops-template \
  --public \
  --description "GitHub DevOps automation template — CI / commit compliance / Feishu sync / meeting automation / AI code review" \
  --clone
```

- [ ] **Step 2: Copy infrastructure files from devops-sandbox**

```bash
cd devops-template

# Scripts (only non-test source files + tests, no __pycache__ or .venv)
cp -r ../devops-sandbox/scripts .
rm -rf scripts/__pycache__ scripts/.venv scripts/.pytest_cache scripts/.ruff_cache

# GitHub config
cp -r ../devops-sandbox/.github .

# Claude skills
mkdir -p .claude/skills
cp ../devops-sandbox/.claude/skills/commit-compliance.md .claude/skills/

# CodeRabbit config
cp ../devops-sandbox/.coderabbit.yaml .

# Gitignore
cp ../devops-sandbox/.gitignore .
```

- [ ] **Step 3: Remove project-specific files and references**

```bash
# Remove meeting_bot CI workflow (will be replaced by generic ci.yml)
rm .github/workflows/meeting-bot-ci.yml

# Remove meeting_bot references from labeler
# (will be rewritten in Task 7)
```

- [ ] **Step 4: Commit the seed**

```bash
git add -A
git commit -m "chore: seed template from devops-sandbox infrastructure"
git push -u origin main
```

---

### Task 2: Create config.yml and the shared config loader module

**Files:**
- Create: `config.yml`
- Create: `scripts/config_loader.py`
- Create: `scripts/test_config_loader.py`

- [ ] **Step 1: Write the test for config_loader**

```python
# scripts/test_config_loader.py
"""config_loader 单测."""
from __future__ import annotations

import json
import os

import config_loader


def test_load_config_from_file(tmp_path, monkeypatch):
    """config.yml 能正常加载."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        "project:\n  name: test-proj\nfeishu:\n  bitable_app_token: tok-123\n"
    )
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()
    cfg = config_loader.load_config()
    assert cfg["project"]["name"] == "test-proj"
    assert cfg["feishu"]["bitable_app_token"] == "tok-123"


def test_get_with_env_override(tmp_path, monkeypatch):
    """环境变量优先于 config.yml."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("feishu:\n  bitable_app_token: from-file\n")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()
    monkeypatch.setenv("FEISHU_BITABLE_APP_TOKEN", "from-env")
    val = config_loader.get("feishu", "bitable_app_token", env="FEISHU_BITABLE_APP_TOKEN")
    assert val == "from-env"


def test_get_falls_back_to_config(tmp_path, monkeypatch):
    """无环境变量时回退到 config.yml."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("feishu:\n  bitable_app_token: from-file\n")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()
    monkeypatch.delenv("FEISHU_BITABLE_APP_TOKEN", raising=False)
    val = config_loader.get("feishu", "bitable_app_token", env="FEISHU_BITABLE_APP_TOKEN")
    assert val == "from-file"


def test_get_returns_default_when_missing(tmp_path, monkeypatch):
    """section/key 不存在时返回 default."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("project:\n  name: x\n")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()
    val = config_loader.get("nonexistent", "key", default="fallback")
    assert val == "fallback"


def test_config_caches_after_first_load(tmp_path, monkeypatch):
    """config 只读一次文件."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("project:\n  name: v1\n")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()
    cfg1 = config_loader.load_config()
    cfg_file.write_text("project:\n  name: v2\n")
    cfg2 = config_loader.load_config()
    assert cfg1 is cfg2  # same object, cached
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd scripts
pip install pyyaml pytest
pytest test_config_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'config_loader'`

- [ ] **Step 3: Write config_loader.py**

```python
# scripts/config_loader.py
"""统一配置加载器.

读取优先级: 环境变量 > config.yml > 默认值.
config.yml 只读一次, 结果缓存在模块级变量中.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _REPO_ROOT / "config.yml"
_cache: dict[str, Any] = {}


def load_config() -> dict[str, Any]:
    """读取 config.yml, 结果缓存."""
    if "data" in _cache:
        return _cache["data"]
    if not CONFIG_PATH.exists():
        print(f"::warning::config.yml 不存在 ({CONFIG_PATH}), 使用空配置", file=sys.stderr)
        _cache["data"] = {}
        return _cache["data"]
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as e:
        print(f"::warning::config.yml 解析失败: {e}", file=sys.stderr)
        data = {}
    _cache["data"] = data
    return data


def get(section: str, key: str, *, env: str = "", default: Any = "") -> Any:
    """获取配置值. 环境变量 > config.yml > default."""
    if env:
        env_val = os.environ.get(env)
        if env_val:
            return env_val
    cfg = load_config()
    return cfg.get(section, {}).get(key, default)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_config_loader.py -v
```

Expected: 5 passed

- [ ] **Step 5: Create config.yml**

```yaml
# config.yml — 项目配置
# 使用模板后，填写以下字段即可启用全部自动化
# 密钥 (FEISHU_APP_ID/APP_SECRET 等) 从 org-level GitHub Secrets 继承，无需在此配置

project:
  name: "my-project"                    # 项目名称，用于飞书通知标题
  language: "python"                     # 主语言 (MVP 仅支持 python)

# 飞书集成
# 仓库级 Secrets 可覆盖组织默认值 (同名即覆盖)
feishu:
  bitable_app_token: ""                  # 多维表格 app token
  bitable_table_id: ""                   # 任务表 table ID
  summary_chat_id: ""                    # 通知群 chat ID
  doc_template_token: ""                 # 会议归档文档模板 token

# LLM (会议行动项提取)
llm:
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"

# commit 规范
commit:
  delivery_tracking: true                # 启用 [DEL-xx] / [PHASE-x] 交付物追踪
  task_sync: true                        # 启用 [TASK-xxx] 飞书任务状态同步
  extra_types: []                        # 额外允许的 conventional commit types
```

- [ ] **Step 6: Commit**

```bash
git add config.yml scripts/config_loader.py scripts/test_config_loader.py
git commit -m "feat: add config.yml and shared config loader module"
```

---

### Task 3: Refactor scripts to use config_loader

Each script currently reads configuration from hardcoded values or environment variables directly. Refactor them to use `config_loader.get()` with env var override. Only change the configuration reading — leave all business logic untouched.

**Files:**
- Modify: `scripts/feishu_content.py` (add config_loader for FEISHU_BASE)
- Modify: `scripts/sync_feishu.py` (config_loader for bitable/webhook config)
- Modify: `scripts/create_feishu_tasks.py` (config_loader for bitable config, remove .planning/tasks.json path)
- Modify: `scripts/update_feishu_task.py` (config_loader for bitable config, remove .planning/tasks.json path)
- Modify: `scripts/extract_action_items.py` (config_loader for LLM config)
- Modify: `scripts/sync_coderabbit_report.py` (config_loader for webhook config)
- Modify: `scripts/commit_lint.py` (config_loader for extra_types)

- [ ] **Step 1: Refactor feishu_content.py — add config_loader**

The `FEISHU_BASE` constant and `get_tenant_token` are used by multiple scripts. Keep them here but route credentials through config_loader.

```python
# In feishu_content.py, change the get_tenant_token function to accept
# app_id/app_secret as optional params that default to config_loader:
import config_loader

FEISHU_BASE = "https://open.feishu.cn/open-apis"
TIMEOUT = 30

def get_tenant_token(app_id: str = "", app_secret: str = "") -> str:
    app_id = app_id or config_loader.get("feishu", "app_id", env="FEISHU_APP_ID")
    app_secret = app_secret or config_loader.get("feishu", "app_secret", env="FEISHU_APP_SECRET")
    # ... rest unchanged
```

- [ ] **Step 2: Refactor sync_feishu.py**

Replace direct `os.environ.get()` calls for Feishu config with `config_loader.get()`:

```python
import config_loader

# In handle_push(), replace:
#   app_id = os.environ.get("FEISHU_APP_ID")
# with:
app_id = config_loader.get("feishu", "app_id", env="FEISHU_APP_ID")
app_secret = config_loader.get("feishu", "app_secret", env="FEISHU_APP_SECRET")
bitable_app = config_loader.get("feishu", "bitable_app_token", env="FEISHU_BITABLE_APP_TOKEN")
bitable_table = config_loader.get("feishu", "bitable_table_id", env="FEISHU_BITABLE_TABLE_ID")
webhook = config_loader.get("feishu", "webhook_url", env="FEISHU_WEBHOOK_URL")
```

Event/commit/PR env vars (`EVENT_NAME`, `COMMIT_SHA`, `REPO_NAME`, `ACTOR`, `COMMIT_MESSAGE`, `PR_*`) stay as `os.environ.get()` — these are injected by GitHub Actions at runtime, not user config.

- [ ] **Step 3: Refactor create_feishu_tasks.py**

Replace env var reads for Feishu config. Remove hardcoded `.planning/tasks.json` path — tasks.json is no longer used in the template (tasks go straight to Bitable). But keep the dedup mechanism using a simpler approach: query Bitable for existing records with the same title before creating.

For MVP, remove the tasks.json dependency entirely. The cross-issue dedup already happens at Bitable level.

```python
import config_loader

# In main(), replace:
#   app_id = os.environ.get("FEISHU_APP_ID", "")
# with:
app_id = config_loader.get("feishu", "app_id", env="FEISHU_APP_ID")
app_secret = config_loader.get("feishu", "app_secret", env="FEISHU_APP_SECRET")
app_token = config_loader.get("feishu", "bitable_app_token", env="FEISHU_BITABLE_APP_TOKEN")
table_id = config_loader.get("feishu", "bitable_table_id", env="FEISHU_BITABLE_TABLE_ID")
```

Remove `TASKS_JSON_PATH`, `load_tasks_map()`, `save_tasks_map()` — no longer writing to git.

- [ ] **Step 4: Refactor update_feishu_task.py**

Same pattern — config_loader for Feishu credentials and bitable config. Remove tasks.json dependency. The `find_record_id()` function needs to be reworked: instead of reading tasks.json, it should accept the record_id directly from the commit message tag (e.g. `[TASK-recXXX]`). The record_id is already in the tag.

```python
import config_loader

# In main():
app_id = config_loader.get("feishu", "app_id", env="FEISHU_APP_ID")
app_secret = config_loader.get("feishu", "app_secret", env="FEISHU_APP_SECRET")
app_token = config_loader.get("feishu", "bitable_app_token", env="FEISHU_BITABLE_APP_TOKEN")
table_id = config_loader.get("feishu", "bitable_table_id", env="FEISHU_BITABLE_TABLE_ID")
```

Simplify `find_record_id()` — the commit tag `[TASK-recXXX]` already contains the record_id. No need for tasks.json lookup.

- [ ] **Step 5: Refactor extract_action_items.py**

```python
import config_loader

# Replace hardcoded LLM defaults:
base_url = config_loader.get("llm", "base_url", env="LLM_BASE_URL", default="https://api.deepseek.com/v1")
model = config_loader.get("llm", "model", env="LLM_MODEL", default="deepseek-chat")
api_key = config_loader.get("llm", "api_key", env="LLM_API_KEY")
```

- [ ] **Step 6: Refactor sync_coderabbit_report.py**

```python
import config_loader

# Replace:
webhook = config_loader.get("feishu", "webhook_url", env="FEISHU_WEBHOOK_URL")
webhook_secret = config_loader.get("feishu", "webhook_secret", env="FEISHU_WEBHOOK_SECRET")
```

- [ ] **Step 7: Refactor commit_lint.py — support extra_types from config**

```python
import config_loader

# In main(), after loading base types, extend with config:
cfg = config_loader.load_config()
extra = cfg.get("commit", {}).get("extra_types", [])
all_types = CONVENTIONAL_TYPES + tuple(extra)
# Rebuild CONVENTIONAL_PATTERN with all_types
```

- [ ] **Step 8: Run all existing tests**

```bash
pytest scripts/ -v
```

Expected: All existing tests should still pass (they monkeypatch env vars, which still works since env vars take priority over config.yml).

- [ ] **Step 9: Commit**

```bash
git add scripts/
git commit -m "refactor: migrate scripts to config_loader, remove tasks.json dependency"
```

---

### Task 4: Rewrite archive_meeting.py for Feishu cloud docs

**Files:**
- Rewrite: `scripts/archive_meeting.py`
- Rewrite: `scripts/test_archive_meeting.py`

- [ ] **Step 1: Write the test**

```python
# scripts/test_archive_meeting.py
"""archive_meeting 单测 — 飞书云文档版."""
from __future__ import annotations

import json

import responses

import archive_meeting
import config_loader


@responses.activate
def test_archive_creates_feishu_doc(tmp_path, monkeypatch):
    """正常流程: 复制模板 → 写入内容 → 返回 URL."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        "feishu:\n  doc_template_token: tpl-abc\n"
    )
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("MEETING_TITLE", "测试会议")
    monkeypatch.setenv("MEETING_DATE", "2026-04-30")
    monkeypatch.setenv("ISSUE_NUMBER", "42")

    # Mock token
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    # Mock copy doc from template
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/drive/v1/files/copy",
        json={"code": 0, "data": {"file": {"token": "doc-new-123"}}},
    )

    rc = archive_meeting.main()
    assert rc == 0


def test_missing_template_token_returns_error(tmp_path, monkeypatch):
    """缺少 doc_template_token 时应报错."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("feishu:\n  doc_template_token: \"\"\n")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", cfg_file)
    config_loader._cache.clear()
    monkeypatch.setenv("MEETING_TITLE", "x")
    monkeypatch.setenv("MEETING_DATE", "2026-04-30")
    monkeypatch.setenv("ISSUE_NUMBER", "1")
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    assert archive_meeting.main() == 2
```

- [ ] **Step 2: Rewrite archive_meeting.py**

```python
# scripts/archive_meeting.py
"""归档会议记录到飞书云文档.

环境变量:
  MEETING_TITLE          会议标题
  MEETING_DATE           会议日期 (YYYY-MM-DD)
  ISSUE_NUMBER           GitHub issue 编号
  FEISHU_URL             飞书原始链接 (可选)
  ACTION_ITEMS_JSON      行动项 JSON (可选, 从 extract step 传)
  FEISHU_APP_ID/SECRET   飞书凭证 (env 或 config.yml)
  GITHUB_OUTPUT          输出文档 URL 给下游 step

行为:
  - 从 config.yml 读 feishu.doc_template_token
  - 调飞书 Drive API 从模板复制文档
  - 返回文档 URL
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime

import requests

import config_loader
from feishu_content import FEISHU_BASE, get_tenant_token

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISSUE_NUM_RE = re.compile(r"^\d+$")
TIMEOUT = 30


def copy_doc_from_template(token: str, template_token: str, title: str) -> str:
    """从模板复制文档, 返回新文档 token."""
    r = requests.post(
        f"{FEISHU_BASE}/drive/v1/files/copy",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": "docx",
            "token": template_token,
            "name": title,
        },
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise RuntimeError(f"copy doc HTTP {r.status_code}: {r.text}")
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"copy doc 失败: {data}")
    return data.get("data", {}).get("file", {}).get("token", "")


def main() -> int:
    title = os.environ.get("MEETING_TITLE", "").strip() or "未命名会议"
    date = os.environ.get("MEETING_DATE", "").strip()
    if not date:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
    issue_num = os.environ.get("ISSUE_NUMBER", "").strip()

    if not DATE_RE.fullmatch(date):
        print(f"::error::MEETING_DATE 格式必须是 YYYY-MM-DD (got {date!r})", file=sys.stderr)
        return 2
    if not issue_num or not ISSUE_NUM_RE.fullmatch(issue_num):
        print(f"::error::ISSUE_NUMBER 必须是纯数字 (got {issue_num!r})", file=sys.stderr)
        return 2

    template_token = config_loader.get("feishu", "doc_template_token", env="FEISHU_DOC_TEMPLATE_TOKEN")
    if not template_token:
        print("::error::缺少 feishu.doc_template_token 配置", file=sys.stderr)
        return 2

    app_id = config_loader.get("feishu", "app_id", env="FEISHU_APP_ID")
    app_secret = config_loader.get("feishu", "app_secret", env="FEISHU_APP_SECRET")
    if not (app_id and app_secret):
        print("::error::缺少 FEISHU_APP_ID / FEISHU_APP_SECRET", file=sys.stderr)
        return 2

    try:
        token = get_tenant_token(app_id, app_secret)
        doc_title = f"{date} {title} (issue #{issue_num})"
        doc_token = copy_doc_from_template(token, template_token, doc_title)
    except Exception as e:
        print(f"::error::创建飞书文档失败: {e}", file=sys.stderr)
        return 1

    doc_url = f"https://docs.feishu.cn/docx/{doc_token}"
    print(f"✅ 会议归档文档已创建: {doc_url}")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"archive_url={doc_url}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run tests**

```bash
pytest test_archive_meeting.py -v
```

- [ ] **Step 4: Commit**

```bash
git add scripts/archive_meeting.py scripts/test_archive_meeting.py
git commit -m "feat: rewrite archive_meeting to create Feishu cloud docs instead of git markdown"
```

---

### Task 5: Create generalized ci.yml workflow

**Files:**
- Create: `.github/workflows/ci.yml`
- Remove: `.github/workflows/meeting-bot-ci.yml` (already done in Task 1)

- [ ] **Step 1: Write ci.yml**

```yaml
name: CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

env:
  PYTHON_VERSION: "3.11"

jobs:
  scripts-lint:
    name: scripts / Lint (Ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install "ruff==0.6.9"
      - run: ruff check --output-format=github scripts
      - run: ruff format --check scripts

  ci-gate:
    name: CI Gate
    if: always()
    needs: [scripts-lint]
    runs-on: ubuntu-latest
    steps:
      - env:
          SCRIPTS_LINT: ${{ needs.scripts-lint.result }}
        run: |
          echo "scripts_lint=$SCRIPTS_LINT"
          if [ "$SCRIPTS_LINT" != "success" ]; then
            echo "::error::CI 未通过"
            exit 1
          fi
          echo "CI 全部通过 ✅"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add generalized ci.yml replacing meeting-bot-ci.yml"
```

---

### Task 6: Adapt remaining workflows for template use

**Files:**
- Modify: `.github/workflows/process-meeting.yml`
- Modify: `.github/workflows/feishu-sync.yml`
- Modify: `.github/workflows/coderabbit-report-sync.yml`
- Keep as-is: `.github/workflows/commit-lint.yml`, `.github/workflows/secret-scan.yml`, `.github/workflows/labeler.yml`

- [ ] **Step 1: Rewrite process-meeting.yml — remove git commit, use Feishu doc**

Key changes:
- Remove `contents: write` permission (no longer writing to git)
- Remove the entire "Commit archive to dev" step (git config, git add, rebase retry)
- Change archive step to call new `archive_meeting.py` (returns Feishu doc URL)
- Update comment step to show Feishu doc link instead of git file path
- Keep `github.actor != 'github-actions[bot]'` guard on closed events
- Keep `if: github.event.action != 'closed'` on LLM/task steps
- Add `pip install pyyaml` to deps (for config_loader)

```yaml
permissions:
  issues: write
  # contents: write is no longer needed

# In "Install Python deps" step:
- run: pip install requests openai pydantic pyyaml

# Replace "Archive meeting metadata" step:
- name: Archive to Feishu cloud doc
  id: archive
  working-directory: scripts
  env:
    MEETING_TITLE: ${{ steps.parse.outputs.meeting_title }}
    MEETING_DATE: ${{ steps.parse.outputs.meeting_date }}
    FEISHU_URL: ${{ steps.parse.outputs.feishu_url }}
    ACTION_ITEMS_JSON: ${{ steps.extract.outputs.action_items }}
  run: python archive_meeting.py

# Remove entire "Commit archive to dev" step

# Update "Comment on issue and close" to use archive_url:
- name: Comment on issue and close
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    TASK_COUNT: ${{ steps.tasks.outputs.task_count }}
    TASK_MD: ${{ steps.tasks.outputs.task_md }}
    ARCHIVE_URL: ${{ steps.archive.outputs.archive_url }}
  run: |
    comment_body="✅ 处理完成

    ## 创建了 ${TASK_COUNT:-0} 个飞书任务

    ${TASK_MD:-_(无)_}

    ## 归档

    [飞书文档](${ARCHIVE_URL:-#})

    ---
    _由 process-meeting workflow 自动生成_"
    gh issue comment "$ISSUE_NUMBER" --body "$comment_body"
    gh issue close "$ISSUE_NUMBER"
```

- [ ] **Step 2: Update feishu-sync.yml — add pyyaml**

Add `pyyaml` to pip install step so config_loader works:

```yaml
# Change:
- run: pip install requests
# To:
- run: pip install requests pyyaml
```

- [ ] **Step 3: Update coderabbit-report-sync.yml — add pyyaml**

Same change: add `pyyaml` to pip install.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "feat: adapt workflows for template — Feishu doc archive, remove git commit"
```

---

### Task 7: Generalize GitHub config files

**Files:**
- Modify: `.github/labeler.yml` (remove meeting_bot paths)
- Modify: `.github/CODEOWNERS` (remove meeting_bot, use placeholder)
- Modify: `.github/pull_request_template.md` (remove meeting_bot checkbox)
- Keep as-is: `.github/ISSUE_TEMPLATE/meeting.yml`

- [ ] **Step 1: Rewrite labeler.yml**

```yaml
# 按路径自动给 PR 打标签

"area/scripts":
  - changed-files:
      - any-glob-to-any-file:
          - "scripts/**"

"area/ci":
  - changed-files:
      - any-glob-to-any-file:
          - ".github/**"

"area/config":
  - changed-files:
      - any-glob-to-any-file:
          - "config.yml"
          - ".coderabbit.yaml"
          - ".gitignore"

"area/docs":
  - changed-files:
      - any-glob-to-any-file:
          - "**/*.md"
          - "**/docs/**"

"area/tests":
  - changed-files:
      - any-glob-to-any-file:
          - "**/test_*.py"
          - "**/tests/**"
```

- [ ] **Step 2: Rewrite CODEOWNERS**

```
# 默认兜底 — 改为你的 GitHub 用户名
*                                  @your-github-username

# 仓库基础设施
/.github/                          @your-github-username
/scripts/                          @your-github-username
/.coderabbit.yaml                  @your-github-username
/config.yml                        @your-github-username
```

- [ ] **Step 3: Rewrite pull_request_template.md**

```markdown
<!--
  Commit 消息规范:
    [DEL-xx] 描述               交付物
    [DEL-xx][MVP] 描述          里程碑
    [PHASE-x] 描述              阶段
    feat|fix|refactor: 描述     普通
-->

## 变更说明

<!-- 一句话描述本次 PR 做了什么 -->

## 影响范围

- [ ] `scripts/` — 自动化脚本
- [ ] `.github/` — CI / 仓库配置
- [ ] 文档 / 配置 / 其他

## 类型

- [ ] feat: 新功能
- [ ] fix: Bug 修复
- [ ] refactor: 重构
- [ ] docs: 文档
- [ ] chore: CI / 杂项
- [ ] [DEL-xx] 交付物
- [ ] [PHASE-x] 阶段交付

## 关联

- Issue: #
- 交付物编号: DEL-

## 自检清单

- [ ] `ruff check scripts && ruff format --check scripts` 通过
- [ ] 单元测试通过
- [ ] 未提交 `.env` / secrets / 真实凭证
```

- [ ] **Step 4: Commit**

```bash
git add .github/labeler.yml .github/CODEOWNERS .github/pull_request_template.md
git commit -m "chore: generalize GitHub configs for template use"
```

---

### Task 8: Clean up .coderabbit.yaml and .gitignore

**Files:**
- Modify: `.coderabbit.yaml` (remove meeting_bot-specific path_instructions)
- Modify: `.gitignore` (remove meeting_bot-specific entries)

- [ ] **Step 1: Simplify .coderabbit.yaml**

Remove all `meeting_bot/src/meeting_bot/` path instructions (feishu, main.py, pipeline.py, events.py). Keep only the generic sections:
- General security (`**/*.py`)
- General performance (`**/*.py`)
- Test quality (`**/tests/**`)

Update the tone instruction to be project-agnostic (remove "飞书开放平台" specifics from the top-level tone).

- [ ] **Step 2: Clean .gitignore**

Remove the `meeting_bot SQLite dedup` comment. Keep all generic Python/IDE/secrets entries.

- [ ] **Step 3: Commit**

```bash
git add .coderabbit.yaml .gitignore
git commit -m "chore: clean coderabbit and gitignore for template"
```

---

### Task 9: Write README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the full README**

Follow the structure from the spec (Section 7). Include:
- Feature list with one-line descriptions
- Quick start (5 steps)
- config.yml field-by-field documentation with instructions on where to find each value in Feishu
- Commit convention table with examples
- Each workflow explained (trigger + what it does)
- Example workflow for adding user project CI
- Org-level Secrets setup guide (admin, one-time)
- FAQ (how to override secrets, how to disable features, how to add CodeRabbit)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add template README with setup guide"
```

---

### Task 10: Add ruff config and final cleanup

**Files:**
- Create: `pyproject.toml` (root-level, for ruff config only)
- Remove any leftover meeting_bot references

- [ ] **Step 1: Create root pyproject.toml for ruff**

```toml
# Ruff configuration for scripts/
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["scripts"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM", "N", "S", "RUF", "ASYNC"]
ignore = ["E501", "S101", "B008"]

[tool.ruff.lint.per-file-ignores]
"scripts/test_*.py" = ["S", "N"]
"scripts/**/*.py" = ["S603", "S607", "S110", "RUF001", "RUF002", "RUF003", "N818", "SIM105", "B904"]

[tool.ruff.lint.isort]
known-first-party = ["config_loader", "feishu_content", "feishu_url"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

- [ ] **Step 2: Update ci.yml to use root pyproject.toml**

```yaml
# Change ruff commands to:
- run: ruff check --config pyproject.toml --output-format=github scripts
- run: ruff format --config pyproject.toml --check scripts
```

- [ ] **Step 3: Run ruff to verify**

```bash
ruff check --config pyproject.toml scripts
ruff format --config pyproject.toml --check scripts
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml
git commit -m "chore: add root pyproject.toml for ruff config"
```

---

### Task 11: Mark as Template Repository and push

- [ ] **Step 1: Push all commits**

```bash
git push origin main
```

- [ ] **Step 2: Mark as template**

```bash
gh repo edit future-youth-ai/devops-template --template
```

- [ ] **Step 3: Verify template status**

```bash
gh repo view future-youth-ai/devops-template --json isTemplate
```

Expected: `{"isTemplate": true}`

- [ ] **Step 4: Smoke test — create a test repo from template**

```bash
gh repo create future-youth-ai/template-test \
  --template future-youth-ai/devops-template \
  --public \
  --clone
cd template-test
cat config.yml  # should exist
ls scripts/     # should have all scripts
ls .github/workflows/  # should have all workflows
```

- [ ] **Step 5: Clean up test repo**

```bash
gh repo delete future-youth-ai/template-test --yes
```

- [ ] **Step 6: Final commit in devops-sandbox — link to template**

```bash
cd ../devops-sandbox
# Update README to reference the template
git commit -m "docs: link to devops-template from sandbox README"
```
