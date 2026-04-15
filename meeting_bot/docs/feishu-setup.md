# 飞书自建应用配置指南

本服务基于**飞书自建应用 + 事件订阅**工作。按以下步骤配置：

## 1. 创建自建应用

1. 打开 https://open.feishu.cn/app，登录你的飞书账号
2. 点击「创建应用」→ 选择「**自建应用**」
3. 填写应用名称「Meeting Bot」、描述、图标
4. 进入应用详情页，记下：
   - **App ID** (形如 `cli_xxxxxxxx`)
   - **App Secret** (点击"查看"获取，只显示一次！)
5. 把这两个值填入 `.env` 的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`

## 2. 启用能力

进入「应用功能」，开启以下：
- ✅ **机器人** — 能让 bot 被拉进群
- ✅ **网页** (可选) — 如果未来要做管理后台

## 3. 申请权限 scope

进入「权限管理」，搜索并开启以下 scope：

### 视频会议 (VC)
- `vc:meeting` — 读取会议信息
- `vc:meeting:readonly` — 读取参会人

### 妙记 (Minutes) ⚠️
- `minutes:minutes` — 读取妙记
- `minutes:minutes:readonly` — 只读（二选一）

> ⚠️ **如果搜不到 `minutes:*`** 说明你的飞书套餐**不支持**妙记 OpenAPI，整个方案走不通。
> 此时需要：
> 1. 去「飞书管理后台」→「套餐中心」升级到**专业版 / 旗舰版**
> 2. 或申请「飞书政务版」的妙记 API 单独授权
> 3. 或改用方案 B（妙记页面 + 手动上传文件触发）

### 云文档 (Docs)
- `docx:document` — 创建/编辑云文档
- `drive:drive` — 复制模板文件
- `drive:file` — 读取文件元信息

### 多维表格 (Bitable)
- `bitable:app` — 读写多维表格记录

### 任务 (Task v2)
- `task:task` — 创建/更新任务

### 通讯录 (Contact)
- `contact:user.base:readonly` — 根据 email 查 open_id
- `contact:user.email:readonly`

### 消息 (IM)
- `im:message` — 发送群消息
- `im:message:send_as_bot` — 以 bot 身份发送

权限申请后需要「**发布应用**」并由管理员审批。企业自用版可跳过审批。

## 4. 配置事件订阅

进入「事件订阅」：

### 4.1 配置请求地址

- **请求地址 URL**: `https://<你的公网域名>/webhook/feishu`
- **加密策略**:
  - 勾选「**Encrypt Key**」→ 生成一个 32 位随机字符串 → 填入 `.env` 的 `FEISHU_EVENT_ENCRYPT_KEY`
  - Verification Token 留空或忽略（V2 模式不需要）

### 4.2 验证地址有效性

点击「保存」，飞书会发送一次 `url_verification` 请求到你的端点。需要先把服务启动起来并公网可达（或用 ngrok/frp 内网穿透）：

```bash
# 本地启动
uvicorn meeting_bot.main:app --host 0.0.0.0 --port 8000

# 另开一个终端用 ngrok 暴露到公网
ngrok http 8000
# → 得到 https://xxxx.ngrok.io, 填入"请求地址"
```

### 4.3 订阅事件

搜索并订阅：
- `vc.meeting.meeting_ended_v1` — 会议结束
- `minutes.minute.created_v1`（如果能搜到）— 妙记生成完成

## 5. 准备飞书资源

### 5.1 会议索引多维表格

1. 新建一个飞书多维表格文档
2. 建表「会议记录」，字段（必须与 `pipeline.py:_write_bitable()` 对应）：
   | 字段名 | 类型 |
   |---|---|
   | 会议ID | 文本 |
   | 标题 | 文本 |
   | 开始时间 | 日期时间 |
   | 结束时间 | 日期时间 |
   | 参会人数 | 数字 |
   | 决议数 | 数字 |
   | 行动项数 | 数字 |
   | 摘要 | 多行文本 |
   | 妙记链接 | 超链接 |
3. 从 URL 拿到 `app_token` (`https://.../base/<app_token>`) 和 `table_id` (`?table=<table_id>`)
4. 填入 `.env` 的 `FEISHU_BITABLE_APP_TOKEN` 和 `FEISHU_BITABLE_TABLE_ID`

### 5.2 会议纪要模板文档

1. 新建一个云文档作为模板（包含"标题 / 摘要 / 决议 / 行动项"空框架）
2. 从 URL 拿 `doc_token`，填入 `FEISHU_DOC_TEMPLATE_TOKEN`
3. ⚠️ 确保 **bot 账号**（对应自建应用）在这个模板文档上**有读取权限**

### 5.3 通知群

1. 创建一个飞书群「会议总结通知」
2. 把 Meeting Bot 加入群聊
3. 从群设置拿 `chat_id` (可以通过 `/im/v1/chats` API 查询)
4. 填入 `FEISHU_SUMMARY_CHAT_ID`

## 6. 端到端测试

```bash
# 1. 起服务
cp .env.example .env   # 填完上面所有值
docker compose up -d

# 2. 手动跑一次 pipeline (需要一个已存在的会议 ID)
python -c "
import asyncio
from meeting_bot.config import get_settings
from meeting_bot.feishu.client import FeishuClient
from meeting_bot.pipeline import Pipeline

async def main():
    settings = get_settings()
    async with FeishuClient(settings) as client:
        pipeline = Pipeline(settings, client)
        result = await pipeline.process('<你的会议ID>', '<妙记token>')
        print(result.model_dump_json(indent=2))

asyncio.run(main())
"

# 3. 开真实会议, 会议结束后 1-2 分钟观察:
#    - 飞书群应出现总结卡片
#    - Bitable 多一行记录
#    - 参会人任务列表出现新任务
#    - 邮箱收到 HTML 邮件
```

## 常见坑

| 现象 | 原因 / 修复 |
|---|---|
| 99991672 权限不足 | scope 没申请/审批, 去权限管理再勾 |
| 99991663 应用未发布 | 开发版本权限变动后必须"创建版本并发布" |
| URL 验证失败 | 检查 ngrok 是否正常, 返回的 JSON 是否是 `{"challenge": "..."}` |
| 解密失败 | Encrypt Key 少一位、或没同步到 `.env` |
| 妙记 API 404 | 路径改过, 用 context7 拉最新 Feishu 文档 |
| 群消息发不出去 | bot 没加到群里、或 chat_id 错误 |
