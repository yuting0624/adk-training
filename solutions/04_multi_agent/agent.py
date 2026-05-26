"""Section 2-1: Multi-Agent Workflow (Intake -> Triage -> Recommend).

ADK 2.0 の `Workflow` (graph-based execution engine) で 3 つの専門エージェントを
直列合成する。各ノードの出力テキストが次ノードの入力になる。

学習ポイント:
- `from google.adk import Workflow` と `edges=[("START", a, b, c)]` の意味
- ノード間の暗黙的な入出力受け渡し (構造化共有 state は別パターン)
- FunctionTool (2-2a) と McpToolset (2-2b) を持つ複数 Agent を組み合わせられる
"""

import os

from dotenv import load_dotenv
from google.adk import Agent, Workflow
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

load_dotenv()

# ---------- 共有: Maps MCP (Section 2-2b と同じ) ----------
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

# ---------- 共有: 診療科 DB FunctionTool (Section 2-2a と同じ) ----------
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
    """症状キーワードから推奨診療科候補と緊急度を返す。

    Args:
        symptom_keyword: 患者の主訴を表すキーワード (例: "胸痛", "発熱")。

    Returns:
        candidates (list[str]), urgency (str), matched_keyword (str) を含む dict。
    """
    for kw, info in _SPECIALTY_DB.items():
        if kw in symptom_keyword:
            return {**info, "matched_keyword": kw}
    return {"candidates": ["総合診療科"], "urgency": "低", "matched_keyword": "default"}


# ---------- Node 1: 問診 (Intake) ----------
intake_agent = Agent(
    name="intake_agent",
    model="gemini-3.5-flash",
    description="患者の自由記述から主訴キーワードと希望エリアを抽出する問診エージェント。",
    instruction="""\
ユーザーが症状やエリアを述べたら、以下のフォーマット (1 行) で出力してください。
他の説明は一切付けません。

主訴: <最も顕著な症状を表す 1 単語>; エリア: <希望エリア または 「指定なし」>

例:
入力: 「最近よく胸が痛むんだ。東京駅周辺で病院を探したい」
出力: 主訴: 胸痛; エリア: 東京駅周辺
""",
)

# ---------- Node 2: トリアージ (Triage) ----------
triage_agent = Agent(
    name="triage_agent",
    model="gemini-3.5-flash",
    description="主訴キーワードから lookup_specialty ツールを使って診療科を推定する。",
    instruction="""\
入力にある「主訴: ...」の値を取り出し、必ず `lookup_specialty` ツールを呼んで結果を取得してください。
取得後、以下のフォーマット (1 行) で出力します。

診療科: <candidates の先頭>; 緊急度: <urgency>; エリア: <入力から引き継ぐ>

例:
入力: 主訴: 胸痛; エリア: 東京駅周辺
ツール結果: {"candidates": ["循環器内科", "呼吸器内科"], "urgency": "高", "matched_keyword": "胸痛"}
出力: 診療科: 循環器内科; 緊急度: 高; エリア: 東京駅周辺
""",
    tools=[lookup_specialty],
)

# ---------- Node 3: 病院レコメンド (Recommend) ----------
recommend_agent = Agent(
    name="recommend_agent",
    model="gemini-3.5-flash",
    description="診療科とエリアから Maps MCP で近隣医療機関を検索・提示する。",
    instruction="""\
入力にある診療科とエリアを使って、必ず Maps MCP のツールで近隣の医療機関を 3〜5 件検索し、
以下の形式で最終回答してください (これがユーザーへの最終返答になります)。

[最終回答フォーマット]
- 推奨診療科: <診療科>
- 緊急度: <緊急度> (高の場合は救急受診を強く促す)
- 近隣の候補医療機関:
  1. <施設名> (住所、距離)
  2. ...
- 注意事項:
  - これは教育用 AI 応答であり、実際の診断ではありません。
  - 症状が続く場合や緊急時は必ず医療機関を受診してください。
  - 最新情報は各施設の公式サイトで確認してください。
""",
    tools=[_maps_mcp],
)

# ---------- Workflow: 3 ノードを直列に合成 ----------
root_agent = Workflow(
    name="medical_triage_workflow",
    edges=[("START", intake_agent, triage_agent, recommend_agent)],
)
