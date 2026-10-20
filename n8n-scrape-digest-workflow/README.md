# n8n public page digest (lite)

Free subset. The dedupe helper and a one-page list. The weekday workflow, Google Sheet node, email node, and the full polite-fetch guide are in the full pack.

## English

### Deliverables

- `deliverables/dedupe.py` — classify a row as new, changed, or seen; check robots.txt; preview one public HTML file
- `examples/pages.json` — a single `https://example.com/status` row

Use it only on public pages you are allowed to read. Do not pass login, account, or profile URLs. Wait at least two seconds between live fetches, and read the host's robots.txt first. The helper refuses those private path segments even if you ask.

```bash
python3 deliverables/dedupe.py load-pages --file examples/pages.json
python3 deliverables/dedupe.py robots-check --robots-file examples/robots.txt --url https://example.com/changelog
```

Full version / 完整版: GUMROAD_URL

## 中文

免费子集。包含去重助手和只有一页的列表示例。工作日工作流、Google 表格节点、邮件节点和完整的礼貌抓取说明在完整版里。

### 交付物

- `deliverables/dedupe.py`：把一行标成 new、changed 或 seen；检查 robots.txt；对一份公开 HTML 做 preview
- `examples/pages.json`：只有 `https://example.com/status` 一行

只用于你有权阅读的公开页面。不要传入登录、账号或个人主页 URL。对真实站点至少间隔两秒，并先读对方的 robots.txt。即使你传入，助手也会拒绝那些私密路径段。

Full version / 完整版: GUMROAD_URL

## Delivery time / 交付时间

- Lite (this folder): free, available now. / 精简版（本目录）：免费，立即可用。
- Full version: instant download after purchase (GUMROAD_URL). / 完整版：购买后即时下载（GUMROAD_URL）。
