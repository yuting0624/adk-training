"""Step 08 (ストレッチ) 参考解: 04_multi_agent に SafetyCheckAgent を追加。

最終応答に医療免責事項 3 点が含まれているかをチェックし、不足を補完する
4 ノード目を Workflow 末尾に追加する。

> このファイルは agents-cli + Gemini CLI で参加者自身が AI に書かせるのが
> 本筋。詰まったときの比較対象として参照してください。
"""

import os

from dotenv import load_dotenv
from google.adk import Agent, Workflow
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

load_dotenv()

# ---------- 共有: Maps MCP ----------
_MAPS_API_KEY = os.environ.get("MAPS_API_KEY")
if not _MAPS_API_KEY or _MAPS_API_KEY.startswith("YOUR_"):
    raise RuntimeError(
        "MAPS_API_KEY is not set. ワークショップ配布キーを .env に追加してください。"
    )

_maps_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mapstools.googleapis.com/mcp",
        headers={"X-Goog-Api-Key": _MAPS_API_KEY},
        timeout=30.0,
        sse_read_timeout=300.0,
    ),
)

# ---------- 共有: 診療科 DB ----------
_SPECIALTY_DB: dict[str, dict] = {
    "胸痛": {"candidates": ["循環器内科", "呼吸器内科"], "urgency": "高"},
    "動悸": {"candidates": ["循環器内科", "心療内科"], "urgency": "中"},
    "息切れ": {"candidates": ["循環器内科", "呼吸器内科"], "urgency": "中"},
    "発熱": {"candidates": ["内科", "感染症内科"], "urgency": "中"},
    "頭痛": {"candidates": ["脳神経内科", "内科"], "urgency": "中"},
    "腹痛": {"candidates": ["消化器内科", "外科"], "urgency": "中"},
    "皮疹": {"candidates": ["皮膚科", "アレルギー科"], "urgency": "低"},
    "関節痛": {"candidates": ["整形外科", "リウマチ科"], "urgency": "低"},
}


def lookup_specialty(symptom_keyword: str) -> dict:
    """症状キーワードから推奨診療科候補と緊急度を返す。"""
    for kw, info in _SPECIALTY_DB.items():
        if kw in symptom_keyword:
            return {**info, "matched_keyword": kw}
    return {"candidates": ["総合診療科"], "urgency": "低", "matched_keyword": "default"}


# ---------- Node 1: 問診 ----------
intake_agent = Agent(
    name="intake_agent",
    model="gemini-2.5-flash",
    description="患者の自由記述から主訴キーワードと希望エリアを抽出する。",
    instruction="""\
ユーザーが症状やエリアを述べたら、以下のフォーマット (1 行) で出力してください。
他の説明は一切付けません。

主訴: <最も顕著な症状を表す 1 単語>; エリア: <希望エリア または 「指定なし」>

例:
入力: 「最近よく胸が痛むんだ。東京駅周辺で病院を探したい」
出力: 主訴: 胸痛; エリア: 東京駅周辺
""",
)

# ---------- Node 2: トリアージ ----------
triage_agent = Agent(
    name="triage_agent",
    model="gemini-2.5-flash",
    description="主訴キーワードから lookup_specialty ツールで診療科を推定する。",
    instruction="""\
入力にある「主訴: ...」の値を取り出し、必ず `lookup_specialty` ツールを呼んで結果を取得してください。
取得後、以下のフォーマット (1 行) で出力します。

診療科: <candidates の先頭>; 緊急度: <urgency>; エリア: <入力から引き継ぐ>
""",
    tools=[lookup_specialty],
)

# ---------- Node 3: 病院レコメンド ----------
recommend_agent = Agent(
    name="recommend_agent",
    model="gemini-2.5-flash",
    description="診療科とエリアから Maps MCP で近隣医療機関を検索・提示する。",
    instruction="""\
入力にある診療科とエリアを使って、必ず Maps MCP のツールで近隣の医療機関を 3〜5 件検索し、
以下の形式で回答してください。

- 推奨診療科: <診療科>
- 緊急度: <緊急度> (高の場合は救急受診を強く促す)
- 近隣の候補医療機関:
  1. <施設名> (住所、距離)
  2. ...
""",
    tools=[_maps_mcp],
)

# ---------- Node 4: 安全チェック (Step 08 で追加) ----------
safety_check_agent = Agent(
    name="safety_check_agent",
    model="gemini-2.5-flash",
    description=(
        "最終応答に医療免責事項 (教育用 AI / 診断ではない / 医療機関受診促進) が"
        "含まれているかチェックし、不足があれば補完する安全網ノード。"
    ),
    instruction="""\
入力テキストを確認し、以下の 3 点がすべて含まれているかチェックしてください。
1. 「教育用 AI 応答」または同等の免責表現
2. 「実際の診断ではない」旨
3. 「医療機関を受診」を促す文言

[ルール]
- 不足しているものがあれば、入力末尾に「## 注意事項」セクションを追加して補う
- 3 点すべて揃っていれば、入力をそのまま返す
- 医療判断・推奨内容自体は絶対に変更しない (診療科名・緊急度・病院リストには触らない)
- 入力にある書式・改行は維持する
""",
)

# ---------- Workflow: 4 ノードに拡張 ----------
root_agent = Workflow(
    name="medical_triage_workflow_with_safety",
    edges=[
        ("START", intake_agent, triage_agent, recommend_agent, safety_check_agent),
    ],
)
