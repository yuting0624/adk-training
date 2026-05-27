"""Step 05 [オプション拡張]: EvidenceAgent を Workflow に追加する参考解。

04_multi_agent の 3 ノード Workflow (Intake → Triage → Recommend) の末尾に、
**ADK 2.x の組み込み `google_search` ツール** を装備した EvidenceAgent を 1 つ
追加し、最終回答に「診療科の代表的な症状・受診の目安」をエビデンスとして
添える 4 ノード Workflow を構成する。

学習ポイント:
- `from google.adk.tools import google_search` で Gemini ネイティブの
  Google 検索 grounding を任意の Agent に装備できる
- `google_search` は **モデル内蔵ツール** なので、Function Tool / MCP と
  同居させたいときは `GoogleSearchTool(bypass_multi_tools_limit=True)` を使う
- 本ノードは単独 Agent なので bypass は不要 (シンプル構成)
- Workflow の `edges` 末尾にノードを 1 つ足すだけで拡張できる柔軟性

詰まったら本ファイルを参照、もしくは 04_multi_agent との `diff` を見るのが早い。
"""

import os

from dotenv import load_dotenv
from google.adk import Agent, Workflow
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

load_dotenv()

# ---------- 共有: Maps MCP (Step 04 と同じ) ----------
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

# ---------- 共有: 診療科 DB FunctionTool (Step 03 と同じ) ----------
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

# ---------- Node 2: トリアージ (Triage) ----------
triage_agent = Agent(
    name="triage_agent",
    model="gemini-3.5-flash",
    description="主訴キーワードから lookup_specialty ツールで診療科を推定する。",
    instruction="""\
入力にある「主訴: ...」の値を取り出し、必ず `lookup_specialty` ツールを呼んで結果を取得してください。
取得後、以下のフォーマット (1 行) で出力します。

診療科: <candidates の先頭>; 緊急度: <urgency>; エリア: <入力から引き継ぐ>
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
以下の形式で回答してください。

- 推奨診療科: <診療科>
- 緊急度: <緊急度> (高の場合は救急受診を強く促す)
- 近隣の候補医療機関:
  1. <施設名> (住所、距離)
  2. ...
""",
    tools=[_maps_mcp],
)

# ---------- Node 4: エビデンス補強 (Evidence) — このセクションの主役 ----------
# google_search は Gemini ネイティブの内蔵ツール (`types.GoogleSearch()`)。
# モデル内部で実行されるため、Trace 上では `tool_call` イベントではなく
# model_call の grounding metadata として現れる点に注意。
evidence_agent = Agent(
    name="evidence_agent",
    model="gemini-3.5-flash",
    description=(
        "前ノードが提示した推奨診療科について、Google 検索でエビデンスを補強し、"
        "代表的な症状・受診の目安を最終回答に追記する補強ノード。"
    ),
    # ──────────────────────────────────────────────────────────
    # 注意: google_search は Gemini の **内蔵ツール** で、呼ぶかどうかは
    # モデル判断に委ねられる。「検索して」程度の指示だと自分の知識で済ませて
    # 出典を捏造することがあるため、以下のように
    #   (a) 検索が必須であることを最初に宣言
    #   (b) 検索結果のみを根拠にすると明示
    #   (c) 検索結果が薄い場合の代替動作を指定
    #   (d) 捏造禁止を明示
    # の 4 点を強めに書く。これでも flash で取りこぼす場合は gemini-3.5-pro へ。
    # ──────────────────────────────────────────────────────────
    instruction="""\
あなたの仕事は、入力に含まれる推奨診療科について
**Google 検索の結果のみを根拠として** 参考情報を追記することです。

## 必須手順 (順守すること)
1. 入力テキストから推奨診療科名を 1 つ取り出す (例: 「循環器内科」)。
2. **応答を書き始める前に必ず** Google 検索ツールを以下のクエリで呼び出す:
   - 「<診療科名> 代表的な症状」
   - 「<診療科名> 受診の目安」
3. 検索結果に **明示的に書かれている内容のみ** を引用して、下記セクションを構成する。

## 出力形式
入力テキストをそのまま冒頭に保持し、末尾に以下を追記:

```
## 診療科について (参考情報)
- 代表的な症状: <検索結果に書かれた症状を 2〜4 個>
- 受診の目安: <検索結果から 1〜2 文で引用>
- 出典: <検索結果に実在した URL またはドメインを 1〜2 個>

これは教育用 AI 応答であり、実際の診断ではありません。
症状が続く場合や緊急時は医療機関を受診してください。
```

## 絶対ルール (違反したら出力は不正)
- 検索結果に出ていない情報は書かない。記憶や推測で書かない。
- 出典 URL を捏造しない (`example.com` などの架空ドメインも禁止)。
- 検索結果が薄い、または該当が無い場合は「## 診療科について (参考情報)」セクション全体を
  **「参考情報を取得できませんでした。」** の 1 行に置き換える。
- 既存の応答 (病院リスト・推奨診療科・緊急度) は変更しない。追記のみ。
""",
    tools=[google_search],
)

# ---------- Workflow: 4 ノードに拡張 ----------
root_agent = Workflow(
    name="medical_triage_workflow_with_evidence",
    edges=[
        ("START", intake_agent, triage_agent, recommend_agent, evidence_agent),
    ],
)
