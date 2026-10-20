# n8n ops tickets and backup workflows (lite)

Free subset. Webhook ticket intake and a validator that appends JSONL. Nightly backup freshness, git backup, and the Monday report are in the full pack. This is not a disk, certificate, or HTTP-down alert.

## English

### Deliverables

- `deliverables/workflows/webhook-ticket-intake.json` — POST `/ops-ticket`, store a valid ticket, append a sheet, notify Telegram
- `deliverables/ticket_check.py` — validate severity, service slug, title, and detail
- `examples/ticket-body.json` — a filled-in body for `app.example.com` and `oncall@example.com`

```bash
python3 deliverables/ticket_check.py remember --store /tmp/tickets.jsonl --record-b64 "$(python3 -c 'import base64,pathlib; print(base64.b64encode(pathlib.Path("examples/ticket-body.json").read_bytes()).decode())')"
```

Import the workflow, re-select the header, sheet, and Telegram credentials, and replace `PLACEHOLDER_CHAT_ID` and `PLACEHOLDER_SHEET_ID`. The workflow command expects the script at `/opt/ops-tickets/ticket_check.py`.

Full version / 完整版: GUMROAD_URL

## 中文

免费子集。Webhook 收工单，以及一个校验后追加 JSONL 的脚本。每晚备份新鲜度、git 备份和周一汇总在完整版里。这不是磁盘、证书或 HTTP 宕机告警。

### 交付物

- `deliverables/workflows/webhook-ticket-intake.json`：POST `/ops-ticket`，合格工单入库，追加表格，通知 Telegram
- `deliverables/ticket_check.py`：校验严重级别、服务短名、标题和详情
- `examples/ticket-body.json`：填好的示例，主机是 `app.example.com`，邮箱是 `oncall@example.com`

导入工作流后，重新选择头凭据、表格凭据和 Telegram 凭据，并替换 `PLACEHOLDER_CHAT_ID` 和 `PLACEHOLDER_SHEET_ID`。工作流里的命令默认脚本在 `/opt/ops-tickets/ticket_check.py`。

Full version / 完整版: GUMROAD_URL

## Delivery time / 交付时间

- Lite (this folder): free, available now. / 精简版（本目录）：免费，立即可用。
- Full version: instant download after purchase (GUMROAD_URL). / 完整版：购买后即时下载（GUMROAD_URL）。
