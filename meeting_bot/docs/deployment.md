# 部署指南

## 1. 最小要求

- Python 3.11+
- 公网可达的域名 + HTTPS 证书（飞书 webhook 强制 HTTPS）
- SMTP 出口（发邮件）
- 2 核 2G 内存（单实例够用，每小时处理 ~100 场会议）

## 2. 推荐部署方式

### 方式 A：Docker Compose（最简单）

```bash
git clone <repo> meeting-bot && cd meeting-bot
cp .env.example .env
vim .env                 # 填入所有 FEISHU_* / SMTP_* 值
docker compose up -d --build
docker compose logs -f
```

前面需要加一层 Nginx 反向代理做 HTTPS：

```nginx
server {
    listen 443 ssl http2;
    server_name bot.example.com;

    ssl_certificate /etc/letsencrypt/live/bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.example.com/privkey.pem;

    location /webhook/feishu {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Lark-Request-Timestamp $http_x_lark_request_timestamp;
        proxy_set_header X-Lark-Request-Nonce $http_x_lark_request_nonce;
        proxy_set_header X-Lark-Signature $http_x_lark_signature;
        proxy_read_timeout 60s;
    }

    location /healthz {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### 方式 B：Systemd + venv（轻量）

```bash
python -m venv /opt/meeting-bot/.venv
/opt/meeting-bot/.venv/bin/pip install -e .

# /etc/systemd/system/meeting-bot.service
[Unit]
Description=Meeting Bot
After=network.target

[Service]
User=meetingbot
WorkingDirectory=/opt/meeting-bot
EnvironmentFile=/opt/meeting-bot/.env
ExecStart=/opt/meeting-bot/.venv/bin/uvicorn meeting_bot.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 方式 C：Kubernetes（生产推荐）

- Deployment（2 replicas）+ Service + Ingress
- HPA 按 CPU 70% 扩
- SQLite 换成 Redis 做幂等（否则多副本去重会失效）
- Secrets 从 K8s Secret 挂载到 `.env`

## 3. 关键运维点

### 3.1 飞书 webhook 重试

飞书在收到非 200 响应时会重试最多 ~10 次，间隔递增。一旦你的服务返回 500，飞书会持续重推。
- **必须**：webhook 端点立即 200，重活进 BackgroundTasks
- **必须**：event_id 幂等，避免重试时重复创建任务

### 3.2 观测

- **日志**：结构化 JSON（structlog 已配），接入 Loki / ELK
- **指标**：建议加 `prometheus-fastapi-instrumentator`
- **追踪**：OpenTelemetry + Jaeger

### 3.3 幂等存储

当前用 SQLite（单实例）。生产多实例必须换：
- Redis SETNX + TTL 24h
- 或 PostgreSQL 唯一索引

### 3.4 SMTP 失败降级

邮件失败不应影响其他步骤。pipeline 已用 `asyncio.gather(return_exceptions=True)`，
但要监控 `PipelineResult.errors` 中 `email:*` 的比例，超过 1% 需要告警。

### 3.5 妙记 API 限频

飞书 API 默认 100 QPS per tenant。高峰期可能触顶：
- 并发数控制在 `FeishuClient.__init__` 的 `max_connections=20`
- 如果仍超限，引入本地令牌桶 (aiolimiter)

## 4. 灾备

- **配置丢失**：`.env` 必须加密备份（Bitwarden / 1Password / Vault）
- **SQLite 数据**：`./data/` 目录定期 rsync
- **密钥泄露**：立即去 https://open.feishu.cn/app 重置 App Secret + Encrypt Key
