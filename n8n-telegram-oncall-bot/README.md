# n8n Telegram on-call bot (lite)

Free subset. A smaller agent that returns uptime, load, and disk, plus a workflow that answers `/status` and `/help`. `/disk`, `/ack`, service checks, the setup guide, and the systemd unit are in the full pack.

## English

### Deliverables

- `deliverables/status_agent.py` — `GET /health` and `GET /v1/status` with bearer auth
- `deliverables/workflows/telegram-status-help.json` — import into n8n. Credential id `PLACEHOLDER_TELEGRAM`. The bearer is the n8n environment variable `STATUS_AGENT_TOKEN`.

```bash
python3 deliverables/status_agent.py --disk /tmp --host-label app-01.example.com
```

Set `STATUS_AGENT_TOKEN` before that command. The process listens on `127.0.0.1:8765`.

Full version / 完整版: GUMROAD_URL

## 中文

免费子集。精简代理只返回开机时间、负载和磁盘。工作流只回答 `/status` 和 `/help`。`/disk`、`/ack`、服务检查、安装说明和 systemd 单元在完整版里。

### 交付物

- `deliverables/status_agent.py`：带 bearer 认证的 `GET /health` 和 `GET /v1/status`
- `deliverables/workflows/telegram-status-help.json`：导入 n8n。凭据 id 是 `PLACEHOLDER_TELEGRAM`。口令来自 n8n 环境变量 `STATUS_AGENT_TOKEN`。

先设置 `STATUS_AGENT_TOKEN`，再运行上面的命令。进程监听 `127.0.0.1:8765`。

Full version / 完整版: GUMROAD_URL

## Delivery time / 交付时间

- Lite (this folder): free, available now. / 精简版（本目录）：免费，立即可用。
- Full version: instant download after purchase (GUMROAD_URL). / 完整版：购买后即时下载（GUMROAD_URL）。
