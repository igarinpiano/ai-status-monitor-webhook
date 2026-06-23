#!/usr/bin/env python3
"""
AI Status Monitor
各社 AI サービスの稼働状況を監視し、変化があれば Discord に通知します。

対応サービス (Statuspage.io 互換 API):
  - Anthropic (Claude)
  - OpenAI (ChatGPT / GPT-4)
  - Mistral AI
  - Cohere
  - Together AI
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 監視するサービス
# api  : Statuspage.io の summary エンドポイント
# page : ステータスページの URL (embed リンク用)
AI_SERVICES: dict[str, dict] = {
    "Anthropic (Claude)": {
        "api":   "https://status.anthropic.com/api/v2/summary.json",
        "page":  "https://status.anthropic.com",
        "emoji": "🟣",
    },
    "OpenAI (GPT / DALL-E)": {
        "api":   "https://status.openai.com/api/v2/summary.json",
        "page":  "https://status.openai.com",
        "emoji": "⚫",
    },
    "Mistral AI": {
        "api":   "https://mistralstatus.com/api/v2/summary.json",
        "page":  "https://mistralstatus.com",
        "emoji": "🟠",
    },
    "Cohere": {
        "api":   "https://status.cohere.com/api/v2/summary.json",
        "page":  "https://status.cohere.com",
        "emoji": "🔵",
    },
    "Together AI": {
        "api":   "https://status.together.ai/api/v2/summary.json",
        "page":  "https://status.together.ai",
        "emoji": "🟡",
    },
}

# 前回ステータスを保存するファイル
STATE_FILE = "ai_status_state.json"

# Discord embed カラー (整数値)
STATUS_COLORS = {
    "none":     0x00D26A,  # 緑  ─ 正常
    "minor":    0xFFCC00,  # 黄  ─ 軽微な障害
    "major":    0xFF7600,  # 橙  ─ 重大な障害
    "critical": 0xFF0000,  # 赤  ─ 致命的障害
}

STATUS_JP = {
    "none":     "✅ 正常稼働",
    "minor":    "⚠️ 軽微な障害",
    "major":    "🔶 重大な障害",
    "critical": "🔴 致命的障害",
}


# ─────────────────────────────────────────
# ステータス取得
# ─────────────────────────────────────────

def load_state() -> dict:
    """前回チェック時のステータスを JSON ファイルから読み込む"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    """今回のステータスを JSON ファイルに書き込む"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_status(url: str) -> dict | None:
    """Statuspage.io の summary API を叩いてレスポンスを返す"""
    try:
        r = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "AI-Status-Monitor/1.0"},
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    ⚠  取得エラー: {e}")
        return None


# ─────────────────────────────────────────
# Discord Embed 構築
# ─────────────────────────────────────────

def build_embed(
    name: str,
    info: dict,
    old_indicator: str,
    data: dict,
) -> dict:
    """Discord の Embed オブジェクトを構築して返す"""

    indicator   = data["status"]["indicator"]
    description = data["status"]["description"]
    incidents   = data.get("incidents", [])
    components  = data.get("components", [])

    color     = STATUS_COLORS.get(indicator, 0x95A5A6)
    old_label = STATUS_JP.get(old_indicator, old_indicator)
    new_label = STATUS_JP.get(indicator, indicator)
    fields    = []

    # ── ステータス変化フィールド ──────────────────
    if old_indicator and old_indicator != indicator:
        fields.append({
            "name":   "📊 ステータス変化",
            "value":  f"{old_label}  →  **{new_label}**",
            "inline": False,
        })
    else:
        fields.append({
            "name":   "📊 ステータス",
            "value":  new_label,
            "inline": True,
        })

    # ── 進行中のインシデント ──────────────────────
    if incidents:
        inc   = incidents[0]
        title = inc.get("name", "インシデント")
        upds  = inc.get("incident_updates", [])
        body  = upds[0].get("body", "詳細なし") if upds else "詳細なし"
        if len(body) > 250:
            body = body[:247] + "…"
        fields.append({
            "name":   f"🚨 {title}",
            "value":  body,
            "inline": False,
        })

    # ── 影響を受けているコンポーネント ────────────
    degraded = [
        c for c in components
        if c.get("status", "operational") != "operational"
    ]
    if degraded:
        lines = "\n".join(
            f"• **{c['name']}** — {c.get('status', '?')}"
            for c in degraded[:6]
        )
        fields.append({
            "name":   "⚙️ 影響コンポーネント",
            "value":  lines,
            "inline": False,
        })

    ts = datetime.now(timezone.utc)
    return {
        "title":       f"{info['emoji']} {name}",
        "description": description,
        "color":       color,
        "fields":      fields,
        "url":         info["page"],
        "timestamp":   ts.isoformat(),
        "footer": {
            "text": f"AI Status Monitor  •  {ts.strftime('%Y-%m-%d %H:%M UTC')}",
        },
    }


# ─────────────────────────────────────────
# Discord 送信
# ─────────────────────────────────────────

def send_discord(embeds: list[dict]) -> None:
    """Discord Webhook に Embed を送信する (最大 10 個ずつ)"""
    if not DISCORD_WEBHOOK_URL:
        print("⚠  DISCORD_WEBHOOK_URL が未設定のため通知をスキップします")
        return

    for chunk in [embeds[i : i + 10] for i in range(0, len(embeds), 10)]:
        payload = {
            "username": "AI Status Monitor",
            "embeds":   chunk,
        }
        try:
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            r.raise_for_status()
            print(f"  📨 Discord に {len(chunk)} 件送信しました")
        except Exception as e:
            print(f"  ❌ Discord 送信エラー: {e}")
        time.sleep(0.5)


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────

def main() -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*52}")
    print(f"  AI Status Monitor  {now_str}")
    print(f"{'='*52}")

    state     = load_state()
    new_state: dict = {}
    embeds:    list  = []

    for name, info in AI_SERVICES.items():
        print(f"\n{info['emoji']}  {name}")
        data = fetch_status(info["api"])

        if data is None:
            # 取得失敗時は前回の状態を引き継ぐ
            if name in state:
                new_state[name] = state[name]
            continue

        indicator     = data["status"]["indicator"]
        old           = state.get(name, {})
        old_indicator = old.get("indicator", "")

        is_first_check = old_indicator == ""
        status_changed = not is_first_check and old_indicator != indicator
        already_broken = is_first_check and indicator != "none"

        label  = STATUS_JP.get(indicator, indicator)
        reason = ""
        if status_changed:
            reason = "  ★ 変化あり！"
        elif already_broken:
            reason = "  ★ 初回チェック時すでに障害中"

        print(f"    → {label}{reason}")

        # 通知条件:
        #   - 通常時: 前回からステータスが変化した
        #   - 初回時: すでに障害中 (none 以外)
        if status_changed or already_broken:
            embeds.append(build_embed(name, info, old_indicator, data))

        new_state[name] = {
            "indicator":   indicator,
            "description": data["status"]["description"],
            "checked_at":  datetime.now(timezone.utc).isoformat(),
        }
        time.sleep(0.3)

    print()
    if embeds:
        send_discord(embeds)
    else:
        print("  ℹ  変化なし — 通知は送りませんでした")

    save_state(new_state)
    print("\n完了\n")


if __name__ == "__main__":
    main()
