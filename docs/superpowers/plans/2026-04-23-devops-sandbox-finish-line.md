# devops-sandbox 收尾执行计划 (2026-04-23)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 devops-sandbox 从 "PR #7 开着 + dev 领先 main 多个 commit" 推到 "main 已同步 / branch protection 上锁 / CodeRabbit→飞书 E2E 在 main 上跑通"。

**Architecture:** 6 个串行 Phase。每个 Phase 有明确的依赖前置条件、可验证的退出标准、独立的回滚策略。Phase 之间不可乱序，但 Phase 内部 Task 可串行执行。本计划假设执行者熟悉 git/gh CLI 但不熟悉本仓库的工作流约定。

**Tech Stack:** GitHub CLI (`gh`), Git, GitHub Actions, GitHub Branch Protection REST API, CodeRabbit GitHub App, 飞书自定义机器人 webhook。

---

## Phase 1：落地 PR #7（ai_review 回滚）

**前置条件:** PR #7 已开（https://github.com/future-youth-ai/devops-sandbox/pull/7），当前在 `chore/rollback-ai-review-to-smoke-test` 分支。

### Task 1.1：等 CI 全绿

**Files:** 无（运行时验证）

- [ ] **Step 1：检查 PR #7 的所有 status check**

Run:
```bash
gh pr checks 7 2>&1 | tee /tmp/pr7-checks.log
```

Expected: 看到 `ai_review CI / Commit Lint / Secret Scan / Auto Label PR` 等都 `pass`，没有 `fail` 或长时间 `pending`。

- [ ] **Step 2：如果有 pending，轮询直到完成**

Run:
```bash
until gh pr checks 7 2>&1 | grep -qv 'pending'; do sleep 30; done
echo "all checks completed"
```

Expected: 命令退出后再跑一次 `gh pr checks 7`，应不再有 `pending` 状态。

**Exit criteria:** `gh pr checks 7` 输出全部为 `pass`，无 `fail`。

---

### Task 1.2：让 CodeRabbit 复审

**Files:** 无

- [ ] **Step 1：触发 CodeRabbit review**

Run:
```bash
gh pr comment 7 --body "@coderabbitai review"
```

Expected: 输出 PR 评论 URL（形如 `https://github.com/.../pull/7#issuecomment-...`）。

- [ ] **Step 2：等 review 提交**

Run:
```bash
until gh api repos/future-youth-ai/devops-sandbox/pulls/7/reviews -q '.[-1].state' 2>/dev/null | grep -qE '^(APPROVED|CHANGES_REQUESTED)$'; do
  sleep 30
done
gh api repos/future-youth-ai/devops-sandbox/pulls/7/reviews -q '.[-1].state'
```

Expected: 输出 `APPROVED` 或 `CHANGES_REQUESTED`。

- [ ] **Step 3：若 CHANGES_REQUESTED，处理意见**

Run:
```bash
gh api repos/future-youth-ai/devops-sandbox/pulls/7/comments -q '.[] | "FILE: \(.path)\n\(.body[0:300])\n---"' | head -60
```

Expected: 输出 CodeRabbit 各条 inline 意见。逐条评估：
- 若是合理改动 → 修代码 → commit（conventional 格式：`fix(...)：xxx`）→ push
- 若是 nit 可忽略 → 在 PR 上回复 `@coderabbitai resolve` 或人工 dismiss

**Exit criteria:** CodeRabbit 最新 review state = `APPROVED`，或剩余意见已被人工评估并标记为可接受。

---

### Task 1.3：合并 PR #7 → dev

- [ ] **Step 1：squash merge 到 dev**

Run:
```bash
gh pr merge 7 --squash --delete-branch \
  --subject "chore(ai_review): 回滚业务骨架, 恢复为 CI smoke test 占位"
```

Expected: 输出 `✓ Squashed and merged pull request #7`。

- [ ] **Step 2：同步本地 dev**

Run:
```bash
git checkout dev
git pull --ff-only origin dev
```

Expected: 输出 `Fast-forward`，dev 含 PR #7 的 squash commit。

- [ ] **Step 3：验证 ai_review/ 回到 smoke test 形态**

Run:
```bash
find ai_review -type f \( -name '*.py' -o -name '*.toml' -o -name '*.md' -o -name '*.yaml' \) -not -path '*/__pycache__/*' | sort
```

Expected: 恰好 7 行：
```
ai_review/.pre-commit-config.yaml
ai_review/CONTRIBUTING.md
ai_review/README.md
ai_review/docs/git-workflow.md
ai_review/pyproject.toml
ai_review/src/__init__.py
ai_review/tests/test_smoke.py
```

**Exit criteria:** dev 已 fast-forward 到含 PR #7 squash 的 SHA，`ai_review/src/` 和 `ai_review/tests/` 总文件数 ≤ 4。

**Risks & Rollback:**
- ❗ squash 后发现 ai_review 仍有业务代码残留 → 在 dev 上加 fix commit 删除残留，**不要** revert squash commit（避免历史扭曲）
- ❗ ai-review-ci 在 dev push 上崩 → 看 Actions 日志；通常是 mypy/test 命令在 src 为空时没正确 skip，修 workflow 后单独提 PR

---

## Phase 2：清理 stale 分支

**前置条件:** Phase 1 完成。

### Task 2.1：盘点 stale 分支

- [ ] **Step 1：拉远端最新引用 + prune**

Run:
```bash
git fetch --prune origin
```

Expected: 删掉本地缓存中已被远端删除的远端引用。

- [ ] **Step 2：列出待清分支**

Run:
```bash
echo "=== local ===" && git branch
echo "=== remote ===" && git branch -r
```

Expected: 待清的远端分支名（如未被 Phase 1 的 `--delete-branch` 自动清掉）：
- `origin/feat/coderabbit-auto-sync`
- `origin/fix/meeting-bot-api-paths`
- `origin/feat/ai-review-skeleton`
- `origin/chore/remove-placeholder`

本地同名分支也是 stale。

**Exit criteria:** 已确认上述 4 个 stale 分支的存在状态，记录哪些还存在。

---

### Task 2.2：删远端 stale 分支

- [ ] **Step 1：批量删除**

Run:
```bash
for b in feat/coderabbit-auto-sync fix/meeting-bot-api-paths feat/ai-review-skeleton chore/remove-placeholder; do
  echo "deleting origin/$b"
  git push origin --delete "$b" 2>&1 || echo "  (already gone)"
done
```

Expected: 每个分支输出 `- [deleted]` 或 `(already gone)`。

- [ ] **Step 2：验证**

Run:
```bash
git fetch --prune origin
git branch -r | grep -E "(coderabbit-auto-sync|meeting-bot-api-paths|ai-review-skeleton|remove-placeholder)" || echo "✅ all clean"
```

Expected: 输出 `✅ all clean`。

**Exit criteria:** 远端没有上述 4 个 stale 分支。

---

### Task 2.3：删本地 stale 分支

- [ ] **Step 1：批量删除（含本次回滚分支自身）**

Run:
```bash
for b in feat/coderabbit-auto-sync fix/meeting-bot-api-paths feat/ai-review-skeleton chore/remove-placeholder chore/rollback-ai-review-to-smoke-test; do
  git branch -D "$b" 2>/dev/null && echo "deleted local $b" || echo "(no local $b)"
done
```

Expected: 已存在的本地分支被删掉。

- [ ] **Step 2：验证**

Run:
```bash
git branch
```

Expected: 只剩 `dev`、`main`（其他全清干净）。

**Exit criteria:** `git branch` 输出只有 `dev` + `main`（带星号标当前分支）。

**Risks & Rollback:**
- ❗ 误删本地分支但里面有未合并 commit → SHA 仍在 reflog，用 `git reflog | head -30` 找回，再 `git branch <name> <sha>` 重建
- ❗ 误删远端分支 → 从对应已合并的 PR 的 head SHA 重建（`gh pr view <num> --json headRefOid -q '.headRefOid'` 拿 SHA）

---

## Phase 3：dev → main release PR

**前置条件:** Phase 1 + 2 完成，dev 已含 PR #7 的 squash。

### Task 3.1：分析 dev 与 main 的 diff

- [ ] **Step 1：看 dev 比 main 多多少 commit**

Run:
```bash
git fetch origin
git log --oneline origin/main..origin/dev
```

Expected: 输出多行 commit subject，覆盖 PR #2 / #3 / #4 / #5 / #7 的 squash + 中间的 fix commit。

- [ ] **Step 2：看 diff 文件总览**

Run:
```bash
git diff --stat origin/main..origin/dev | tail -5
```

Expected: 总改动行数和文件数（用于 release PR 描述）。

**Exit criteria:** 已掌握 dev 比 main 多哪些改动。

---

### Task 3.2：创建 release PR

- [ ] **Step 1：切到 dev**

Run:
```bash
git checkout dev
git pull --ff-only origin dev
```

Expected: 本地 dev = origin/dev。

- [ ] **Step 2：创建 dev → main PR**

Run:
```bash
gh pr create --base main --head dev \
  --title "release: 合并 dev 到 main (CI 沙箱基础设施 + meeting_bot API 修复 + ai_review 回滚)" \
  --body "$(cat <<'EOF'
## Summary

将 dev 上累积的 commit 合并到主干 main。本次 release 涵盖：

### CI / DevOps 基础设施
- feat(ci): CodeRabbit 自动 review + 飞书报告同步 workflow (PR #2)
- fix(ci): 5 个 workflow 分支统一为 [main, dev]
- 安全加固: lark_md 注入转义 / 字节截断 / 输入白名单校验 / 飞书签名

### meeting_bot 业务修复
- fix(meeting_bot): 按飞书官方 SDK (lark-oapi) 对齐 VC + Minutes API 路径 (PR #3)
  - list_participants 改用 /vc/v1/participant_list (废弃 /meetings/{id}/participants)
  - get_summary → get_statistics, 路径 /minutes/v1/minutes/{token}/statistics

### ai_review 回滚
- chore(ai_review): 回滚 PR #5 的业务骨架, 恢复 CI smoke test 占位 (PR #7)

## Test plan
- [x] 所有子项目 CI 全绿 (ai_review / meeting_bot / Commit Lint / Secret Scan)
- [x] CodeRabbit 在每个子 PR 上都已 APPROVED
- [ ] 合并到 main 后, coderabbit-report-sync workflow 进入 main 默认分支生效
- [ ] 后续 demo PR 验证 E2E 飞书同步

## Rollback
本 release 是多个已 review 的 PR 的累积。如出现问题:
1. 立即 `gh pr revert <release-pr-number>` 创建反向 PR
2. 或单独 revert 引发问题的子 commit
EOF
)"
```

Expected: 输出 PR URL。

- [ ] **Step 3：记录 release PR 号到环境变量**

Run:
```bash
RELEASE_PR=$(gh pr list --state open --base main --head dev --json number -q '.[0].number')
echo "release PR: #$RELEASE_PR"
```

Expected: 输出 `release PR: #N`（具体数字记录下来供后续步骤用）。

**Exit criteria:** dev → main 的 release PR 已存在，PR 号已记录。

---

### Task 3.3：等 CI + CodeRabbit 复审通过

- [ ] **Step 1：等所有 status check 跑完**

Run:
```bash
until gh pr checks "$RELEASE_PR" 2>&1 | grep -qv 'pending'; do sleep 30; done
gh pr checks "$RELEASE_PR"
```

Expected: 全 `pass`。

- [ ] **Step 2：等 CodeRabbit review**

Run:
```bash
until gh api repos/future-youth-ai/devops-sandbox/pulls/"$RELEASE_PR"/reviews \
  -q '.[-1].state' 2>/dev/null | grep -qE '^(APPROVED|CHANGES_REQUESTED)$'; do
  sleep 30
done
gh api repos/future-youth-ai/devops-sandbox/pulls/"$RELEASE_PR"/reviews -q '.[-1].state'
```

Expected: 输出 `APPROVED`（理想情况，因为子 PR 都已被 review 过）。

- [ ] **Step 3：若 CHANGES_REQUESTED，评估**

按需修代码 + push，重新跑 review。

**Exit criteria:** release PR 全绿 + CodeRabbit `APPROVED`。

---

### Task 3.4：合并 release PR

- [ ] **Step 1：merge commit 合入（保留子 PR 的 commit history）**

Run:
```bash
gh pr merge "$RELEASE_PR" --merge \
  --subject "Merge dev into main: release 2026-04-23"
```

Expected: 输出 `✓ Merged pull request #N`。

> 注：用 `--merge` 而非 `--squash`，是因为 dev 上的子 commit 都已经过 review，保留 history 更清晰。

- [ ] **Step 2：同步本地 main**

Run:
```bash
git checkout main
git pull --ff-only origin main
git log --oneline -10
```

Expected: 看到 release merge commit + 之前 dev 上的所有 commit。

- [ ] **Step 3：验证 main 上有 coderabbit-report-sync 资产**

Run:
```bash
test -f .github/workflows/coderabbit-report-sync.yml && echo "✅ workflow on main"
test -f scripts/sync_coderabbit_report.py && echo "✅ script on main"
```

Expected: 两行都输出 `✅`。

**Exit criteria:** main 已包含 dev 全部内容，coderabbit-report-sync 进入默认分支。

**Risks & Rollback:**
- ❗ 合并后某 commit 引入 main 破坏 → `gh pr revert <release-pr-num>` 创建 revert PR
- ❗ release PR 触发的 main push 让 secret-scan 报错 → 看 Actions 日志，false positive 就开 fix PR；真问题就 revert release

---

## Phase 4：E2E demo 验证 CodeRabbit → 飞书同步

**前置条件:** Phase 3 完成，main 上有 coderabbit-report-sync 资产。

### Task 4.1：准备最小 demo 改动

- [ ] **Step 1：从 main 拉新分支**

Run:
```bash
git checkout main
git pull --ff-only origin main
git checkout -b chore/e2e-demo-coderabbit-feishu
```

Expected: 在新分支上，干净工作区。

- [ ] **Step 2：在 README 加无害注释**

Run:
```bash
printf '\n<!-- E2E demo: 验证 CodeRabbit → Feishu 同步链路, %s -->\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> README.md
git diff README.md | tail -5
```

Expected: 看到 README.md 末尾多了一行 HTML 注释。

- [ ] **Step 3：commit + push**

Run:
```bash
git add README.md
git commit -m "chore: E2E demo for CodeRabbit Feishu sync verification"
git push -u origin chore/e2e-demo-coderabbit-feishu
```

Expected: 分支推到远端。

**Exit criteria:** demo 分支已 push，工作区干净。

---

### Task 4.2：开 demo PR 并触发 review

- [ ] **Step 1：创建 PR 到 main**

Run:
```bash
gh pr create --base main --head chore/e2e-demo-coderabbit-feishu \
  --title "chore: E2E demo for CodeRabbit Feishu sync" \
  --body "Tiny README touch to verify the full pipeline:

1. CodeRabbit auto-reviews (because base=main, in .coderabbit.yaml base_branches)
2. CodeRabbit posts Summary comment
3. coderabbit-report-sync workflow fires on issue_comment
4. Filter (sender=coderabbitai[bot] + Summary pattern) passes
5. Feishu group receives blue Summary card

Then when CodeRabbit submits its review:
- review state in {approved, changes_requested}
- coderabbit-report-sync fires on pull_request_review
- Feishu group receives green/red verdict card

Will close after verification."

DEMO_PR=$(gh pr list --state open --base main --head chore/e2e-demo-coderabbit-feishu --json number -q '.[0].number')
echo "demo PR: #$DEMO_PR"
```

Expected: 输出 demo PR 号。

- [ ] **Step 2：等 CodeRabbit Summary 评论出现**

Run:
```bash
until gh api repos/future-youth-ai/devops-sandbox/issues/"$DEMO_PR"/comments \
  -q '[.[] | select(.user.login == "coderabbitai[bot]") | select(.body | contains("Summary by CodeRabbit"))] | length' \
  2>/dev/null | grep -qE '^[1-9]'; do
  sleep 20
done
echo "✅ CodeRabbit Summary comment posted"
```

Expected: 输出 `✅ CodeRabbit Summary comment posted`。

**Exit criteria:** demo PR 已开，CodeRabbit 已发 Summary 评论。

---

### Task 4.3：验证 coderabbit-report-sync workflow run 成功

- [ ] **Step 1：等 workflow 启动 + 找到 run**

Run:
```bash
sleep 30
gh run list --workflow="coderabbit-report-sync.yml" --limit 5
```

Expected: 至少一个 run，event 为 `issue_comment`，conclusion 为 `success`。

- [ ] **Step 2：查 Summary 触发的那次 run 的日志**

Run:
```bash
for rid in $(gh run list --workflow="coderabbit-report-sync.yml" --limit 10 --json databaseId -q '.[].databaseId'); do
  echo "--- run $rid ---"
  gh run view "$rid" --log 2>&1 | grep -E "(已推送到飞书|跳过)" || true
done
```

Expected: 至少有一行 `✅ 已推送到飞书: kind=summary, PR #<DEMO_PR>`。

**Exit criteria:** workflow run 列表中至少一次 run 日志输出 `已推送到飞书`，无 `error::`。

---

### Task 4.4：飞书群人肉验收

- [ ] **Step 1：打开飞书 App，进 CodeRabbit 通知群**

无命令。预期看到：
- 📝 蓝色 Summary 卡片，标题：`📝 CodeRabbit 审查摘要 · future-youth-ai/devops-sandbox#<DEMO_PR>`
- 卡片正文是 CodeRabbit 的 Summary 文字（已截断到 3000 字节）
- 卡片末尾有 "查看 PR" 按钮跳到 demo PR

- [ ] **Step 2：等 CodeRabbit 提交 review，看到第二张卡片**

Run（等 review）:
```bash
until gh api repos/future-youth-ai/devops-sandbox/pulls/"$DEMO_PR"/reviews \
  -q '.[-1].state' 2>/dev/null | grep -qE '^(APPROVED|CHANGES_REQUESTED)$'; do
  sleep 30
done
gh api repos/future-youth-ai/devops-sandbox/pulls/"$DEMO_PR"/reviews -q '.[-1].state'
```

Expected: 输出 `APPROVED`（README 加注释，CodeRabbit 通常 approve）。

预期飞书第二张卡片：
- ✅ 绿色 "CodeRabbit 审查通过" 卡（state=APPROVED）
- 或 ❌ 红色 "CodeRabbit 要求修改" 卡（state=CHANGES_REQUESTED）

- [ ] **Step 3：截图存证**

把卡片截图保存到本地。建议路径：
```
docs/superpowers/evidence/2026-04-23-coderabbit-feishu-summary-card.png
docs/superpowers/evidence/2026-04-23-coderabbit-feishu-verdict-card.png
```

**Exit criteria:** 飞书群里至少看到 1 张 Summary 卡 + 1 张 review 结论卡，截图已存档。

---

### Task 4.5：关闭 demo PR

- [ ] **Step 1：close 不合并（README 那行注释没意义）**

Run:
```bash
gh pr close "$DEMO_PR" --delete-branch \
  --comment "E2E demo verified: Feishu received Summary card + review verdict card. Closing without merge — the README comment is intentionally throwaway."
```

Expected: PR closed，远端分支自动删除。

- [ ] **Step 2：删本地 demo 分支**

Run:
```bash
git checkout main
git branch -D chore/e2e-demo-coderabbit-feishu
git branch
```

Expected: 本地只剩 `dev`、`main`。

**Exit criteria:** demo PR closed，本地 + 远端 demo 分支已清理。

**Risks & Rollback:**

| 症状 | 排查 | 处理 |
|---|---|---|
| 飞书没收到任何卡片 | `gh run view <rid> --log` 看 sender 过滤是否过 / Summary 模式是否匹配 | 调 `coderabbit-report-sync.yml` if 条件或 Python 正则 |
| webhook POST 失败 | 看脚本日志 `飞书群消息发送失败` | 检查 secret `FEISHU_WEBHOOK_URL` 是否还在 main scope（org/repo secret 都看一下） |
| Summary 收到但 review 没收到 | `gh api .../reviews` 看 state | 如果 state=`commented`，说明走 `pull_request_review` 但被 PUSH_REVIEW_STATES 过滤了，这是预期行为 |

---

## Phase 5：配置 GitHub Branch Protection

**前置条件:** Phase 3 完成，main 已含所有应有的 workflow（status check 名字必须匹配实际 job 名）。

### Task 5.1：列出 main 上当前的 status check 名字

- [ ] **Step 1：查 main 最近一次 commit 的 check-runs**

Run:
```bash
LATEST_MAIN_SHA=$(git rev-parse main)
gh api "repos/future-youth-ai/devops-sandbox/commits/$LATEST_MAIN_SHA/check-runs" \
  -q '.check_runs[].name' | sort -u
```

Expected: 一组 check 名字，例如：
```
ai_review / CI Gate
ai_review / Dependency Audit (pip-audit)
ai_review / Lint (Ruff)
ai_review / SAST (Bandit)
ai_review / Test (pytest)
ai_review / Type Check (mypy)
Commit Lint
meeting_bot / CI Gate
meeting_bot / Dependency Audit (pip-audit)
meeting_bot / Docker Build Smoke
meeting_bot / Lint (Ruff)
meeting_bot / SAST (Bandit)
meeting_bot / Test (pytest)
meeting_bot / Type Check (mypy)
TruffleHog (repo-wide)
```

- [ ] **Step 2：决定 required check 清单**

建议 required（聚合 gate + 通用安全 + commit 规范）：
- `Commit Lint`
- `TruffleHog (repo-wide)`
- `ai_review / CI Gate`
- `meeting_bot / CI Gate`

不放 required 的（事件驱动，不一定每次跑）：
- `Auto Label PR`
- `CodeRabbit Report Sync`
- `Feishu Sync`

**Exit criteria:** required check 清单已确定（4 项）。

---

### Task 5.2：用 GitHub API 配置 main 的 branch protection

- [ ] **Step 1：写 protection 配置 JSON**

Run:
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
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
cat /tmp/main-protection.json
```

Expected: 输出该 JSON。

- [ ] **Step 2：应用到 main**

Run:
```bash
gh api -X PUT repos/future-youth-ai/devops-sandbox/branches/main/protection \
  --input /tmp/main-protection.json | head -20
```

Expected: 输出 protection 当前配置（API 返回 200），无 error。

- [ ] **Step 3：回读校验**

Run:
```bash
gh api repos/future-youth-ai/devops-sandbox/branches/main/protection \
  -q '{
    checks: .required_status_checks.contexts,
    strict: .required_status_checks.strict,
    reviews: .required_pull_request_reviews.required_approving_review_count,
    dismiss_stale: .required_pull_request_reviews.dismiss_stale_reviews,
    require_last: .required_pull_request_reviews.require_last_push_approval,
    force_push: .allow_force_pushes.enabled,
    deletions: .allow_deletions.enabled,
    conversations: .required_conversation_resolution.enabled
  }'
```

Expected:
```json
{
  "checks": ["Commit Lint", "TruffleHog (repo-wide)", "ai_review / CI Gate", "meeting_bot / CI Gate"],
  "strict": true,
  "reviews": 1,
  "dismiss_stale": true,
  "require_last": true,
  "force_push": false,
  "deletions": false,
  "conversations": true
}
```

**Exit criteria:** main 已上 protection，回读完全匹配预期。

---

### Task 5.3：反向验证（直接 push 应被拒）

- [ ] **Step 1：故意做无意义 main commit**

Run:
```bash
git checkout main
git pull --ff-only origin main
echo "" >> README.md
git add README.md
git commit -m "test: should be rejected by branch protection"
```

Expected: 本地 commit 成功（本地无保护）。

- [ ] **Step 2：试推到 origin/main**

Run:
```bash
git push origin main 2>&1 || echo "✅ push rejected as expected"
```

Expected: GitHub 返回 `protected branch hook declined`，最终输出 `✅ push rejected as expected`。

- [ ] **Step 3：撤掉本地试探 commit**

Run:
```bash
git reset --hard HEAD~1
git status
```

Expected: 本地 main 回到推送前 SHA，工作区干净。

**Exit criteria:** 直接 push 被拒；本地状态已清理。

**Risks & Rollback:**

| 症状 | 处理 |
|---|---|
| Protection 把 admin 也锁外面 | `enforce_admins` 留 `false` 即可避免；已发生则 `gh api -X DELETE repos/.../branches/main/protection` 一键移除 |
| Required check 名字写错 | PR 永远卡 `expected check missing` → 用 Task 5.1 的 GET 查实际 check 名 → 重新 PUT contexts 数组 |
| `strict: true` 让 PR 老需要 rebase | 可改为 `strict: false`，但失去"分支必须最新"的保证 |

---

## Phase 6：验收 + 计划归档

**前置条件:** Phase 1-5 全部完成。

### Task 6.1：总检查清单

- [ ] **Step 1：所有 PR 状态盘点**

Run:
```bash
echo "=== open PRs ===" && gh pr list --state open
echo "=== closed today ===" && gh pr list --state closed \
  --search "closed:>=$(date -u +%Y-%m-%d)" --limit 10
```

Expected:
- `open PRs:`：0 或仅剩 Phase 6.2 的计划归档 PR
- `closed today:`：PR #7、release PR、demo PR

- [ ] **Step 2：main / dev 同步状态**

Run:
```bash
git fetch origin
echo "main = $(git rev-parse origin/main)"
echo "dev  = $(git rev-parse origin/dev)"
git log --oneline origin/main..origin/dev || true
```

Expected: dev 不再领先 main（最理想）；或仅领先 0-2 个不重要的 commit。

- [ ] **Step 3：stale 分支已清**

Run:
```bash
git branch -r | grep -vE "(origin/main|origin/dev|origin/HEAD)" \
  || echo "✅ only main + dev remain"
```

Expected: 输出 `✅ only main + dev remain`。

- [ ] **Step 4：branch protection 生效**

Run:
```bash
gh api repos/future-youth-ai/devops-sandbox/branches/main/protection \
  -q '.required_pull_request_reviews.required_approving_review_count'
```

Expected: 输出 `1`。

**Exit criteria:** 上述 4 步全部预期匹配。

---

### Task 6.2：归档本计划文档

- [ ] **Step 1：从 main 开新分支**

Run:
```bash
git checkout main
git pull --ff-only origin main
git checkout -b docs/finish-line-plan
```

Expected: 在 docs/finish-line-plan 分支，工作区干净。

- [ ] **Step 2：commit 计划文档**

Run:
```bash
git add docs/superpowers/plans/2026-04-23-devops-sandbox-finish-line.md
git commit -m "docs: 归档 2026-04-23 收尾执行计划"
git push -u origin docs/finish-line-plan
```

Expected: 推送成功。

- [ ] **Step 3：开 PR + 走完整 review/merge 流程**

Run:
```bash
gh pr create --base main --head docs/finish-line-plan \
  --title "docs: 归档 2026-04-23 收尾执行计划" \
  --body "把本次收尾执行计划留档, 后续可作 runbook 参考."
```

Expected: PR URL。

按 Phase 1 模式：等 CI + CodeRabbit → squash merge → 同步 main → 删本地分支。

**Exit criteria:** 计划文档已通过 branch protection 流程合入 main。

---

### Task 6.3：TodoWrite 全部 completed

- [ ] **Step 1：调用 TodoWrite 把所有 todo 标 completed**

通过 TodoWrite 工具把当前 todo 列表里所有项都置为 `completed`，或删掉过时项。

**Exit criteria:** TodoWrite 没有 in_progress / pending 项，与本计划交付一致。

---

## 全局风险 & 通用回滚指引

### 风险 1：新 PR 触发不到 CodeRabbit auto-review

**症状:** PR 开了，没人 @ 也没 bot 评论

**排查:**
```bash
# 1. 看 main 上的 .coderabbit.yaml 是否真的合入
gh api repos/future-youth-ai/devops-sandbox/contents/.coderabbit.yaml \
  -q '.content' | base64 -d | grep base_branches

# 2. 看 CodeRabbit App 是否仍安装
gh api orgs/future-youth-ai/installations \
  -q '.installations[] | select(.app_slug == "coderabbitai") | {selection: .repository_selection}'
```

**临时绕过:** 在 PR 里评论 `@coderabbitai review` 强制触发。

---

### 风险 2：Feishu webhook 调用失败

**症状:** workflow run 日志输出 `飞书群消息发送失败`

**排查:**
```bash
# 看脚本 main 上版本
gh api repos/future-youth-ai/devops-sandbox/contents/scripts/sync_coderabbit_report.py \
  -q '.content' | base64 -d | head -30

# 看 secret 是否设置
gh secret list -R future-youth-ai/devops-sandbox | grep FEISHU
```

**回滚:** 重新生成 webhook URL，更新 secret；或临时把 workflow `if` 加 `&& false` 关掉 sync。

---

### 风险 3：Branch protection 锁死所有人

**症状:** 谁也合不进 main，包括 admin

**排查:**
```bash
gh api repos/future-youth-ai/devops-sandbox/branches/main/protection
```

**回滚（核选项）:**
```bash
gh api -X DELETE repos/future-youth-ai/devops-sandbox/branches/main/protection
```

然后重新 PUT 调整后的配置。

---

## Definition of Done

✅ 全部完成的判断（按 Phase 编号）：

1. **Phase 1**：PR #7 已 squash merge 到 dev，本地 dev 含 squash commit，ai_review/ 文件总数 ≤ 7
2. **Phase 2**：4 个 stale 远端分支 + 5 个本地分支均已清理；`git branch` 只剩 dev/main
3. **Phase 3**：dev → main 的 release PR 已 merge commit 合并；main 含 coderabbit-report-sync 资产
4. **Phase 4**：demo PR 在 main 上跑过完整链路；飞书群截图已存档
5. **Phase 5**：main 已上 branch protection；直接 push 被拒
6. **Phase 6**：本计划文档已归档到 main；TodoWrite 清空

---

## 时间估算 (单人执行)

| Phase | 主动操作 | 等待 (CI + CodeRabbit) | 合计 |
|---|---|---|---|
| 1 | 5 min | 5-10 min | 10-15 min |
| 2 | 3 min | 0 | 3 min |
| 3 | 5 min | 5-10 min | 10-15 min |
| 4 | 8 min | 5-10 min | 13-18 min |
| 5 | 5 min | 1-2 min | 6-7 min |
| 6 | 5 min | 5-10 min | 10-15 min |
| **总计** | **31 min** | **21-42 min** | **52-73 min** |

预计 1-1.5 小时完成。
