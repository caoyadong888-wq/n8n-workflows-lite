# n8n ops alert workflows (lite)

Free subset. One hourly disk workflow and a disk-only probe. Telegram and email nodes are included, with credential placeholders and no bot token.

## English

### Deliverables

- `deliverables/workflows/disk-usage-alert.json` — import into n8n. Warn at 80% used, critical at 90%, on `/` and `/var`.
- `deliverables/probe.py` — `python3 deliverables/probe.py --path / --warn 80 --crit 90`

Copy the probe to `/opt/ops-alerts/probe.py` before you activate the workflow. Create n8n credentials named `Telegram account` and `SMTP account`, re-select them on the send nodes, and replace `PLACEHOLDER_CHAT_ID`. From `alerts@example.com`, to `ops@example.com`.

The full pack adds the TLS expiry workflow, the HTTP down workflow, the daily summary, the host list, and the setup guide.

Full version: GUMROAD_URL

## 中文

免费子集：只有磁盘告警工作流和只检查磁盘的探测脚本。Telegram 和邮件节点已接好，凭据是占位符，不含 bot token。

### 交付物

- `deliverables/workflows/disk-usage-alert.json`：导入 n8n。`/` 和 `/var`，80% 警告，90% 严重。
- `deliverables/probe.py`：`python3 deliverables/probe.py --path / --warn 80 --crit 90`

激活前把脚本放到 `/opt/ops-alerts/probe.py`。在 n8n 里创建 `Telegram account` 和 `SMTP account`，在发送节点上重新选择，并替换 `PLACEHOLDER_CHAT_ID`。

完整版另外包含证书到期、HTTP 宕机、每日汇总、主机列表示例和安装说明。

Full version: GUMROAD_URL
