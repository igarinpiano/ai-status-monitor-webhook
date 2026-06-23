# AI Status Monitor

各社 AI サービスの稼働状況を監視し、異常があれば Discord に通知するツールです。

## 対応サービス (自由に追加・削除が可能)

| サービス | ステータスページ |
|---|---|
| 🟣 Anthropic (Claude) | <https://status.anthropic.com> |
| ⚫ OpenAI (ChatGPT / GPT-4) | <https://status.openai.com> |
| 🟠 Mistral AI | <https://mistralstatus.com> |
| 🔵 Cohere | <https://status.cohere.com> |
| 🟡 Together AI | <https://status.together.ai> |

## セットアップ (GitHub Actions)

### 1. このリポジトリをフォーク or 新規リポジトリに配置

```
your-repo/
├── monitor.py
└── .github/
    └── workflows/
        └── ai-status-monitor.yml
```

### 2. Discord Webhook URL を Secrets に登録

GitHub リポジトリ → Settings → Secrets and variables → Actions → **New repository secret**

- Name: `DISCORD_WEBHOOK_URL`
- Value: `https://discord.com/api/webhooks/...`

### 3. Actions を有効化

リポジトリの **Actions** タブ → ワークフローを有効化

以上で 5 分ごとに自動監視が始まります。

## ローカルで実行する場合

```bash
pip install requests
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python monitor.py
```

cron に登録する場合 (5 分ごと):

```cron
*/5 * * * * cd /path/to/ai-status-monitor && python monitor.py
```

## カスタマイズ

### サービスを追加する

`monitor.py` の `AI_SERVICES` に追記するだけです。
Statuspage.io を使っているサービスなら URL パターンは同じです。

```python
"新しいサービス": {
    "api":   "https://status.example.com/api/v2/summary.json",
    "page":  "https://status.example.com",
    "emoji": "🔴",
},
```

### 通知条件を変える

- **障害中は毎回通知したい**: `main()` の `if changed:` を `if changed or indicator != "none":` に変更
- **特定の重大度のみ通知**: `if changed and indicator in ("major", "critical"):` のようにフィルタ

## 通知メッセージの例

```
🟣 Anthropic (Claude)
API Degraded Performance
📊 ステータス変化: ✅ 正常稼働 → 🔶 重大な障害
🚨 API Errors: We are investigating increased error rates on the API.
⚙️ 影響コンポーネント: • Claude API — degraded_performance
```
