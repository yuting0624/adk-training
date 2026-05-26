"""Section 2-2a: Agent + FunctionTool (specialty lookup).

1-1 のシングルエージェントに「症状キーワード→診療科候補」を返す Python 関数を
ツールとして装備する。

ADK 2.0 のポイント:
- 関数を直接 `tools=[...]` に渡すだけでツールになる (FunctionTool ラップ不要)
- docstring と型ヒントが LLM のツール選択判断に使われるため、丁寧に書く
"""

from google.adk import Agent

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
    """症状キーワードから対応する診療科候補と推奨緊急度を返す。

    Args:
        symptom_keyword: 患者の主訴を表すキーワード。
            例: "胸痛", "動悸", "発熱", "頭痛", "腹痛", "皮疹", "関節痛"。
            該当キーワードが DB にない場合は総合診療科を返す。

    Returns:
        以下のキーを持つ dict:
            - candidates (list[str]): 推奨診療科のリスト (1〜3 個)
            - urgency (str): 緊急度 "低" / "中" / "高"
            - matched_keyword (str): 実際にマッチしたキーワード
                (該当なしの場合は "default")
    """
    for keyword, info in _SPECIALTY_DB.items():
        if keyword in symptom_keyword:
            return {**info, "matched_keyword": keyword}
    return {
        "candidates": ["総合診療科"],
        "urgency": "低",
        "matched_keyword": "default",
    }


root_agent = Agent(
    name="triage_agent",
    model="gemini-2.5-flash",
    description=(
        "患者の症状から、診療科データベースを参照して候補診療科と緊急度を提示する"
        " 医療トリアージ補助エージェント。"
    ),
    instruction="""\
あなたは医療トリアージを補助する AI アシスタントです。
ユーザーが症状を入力したら、以下の手順で応答してください。

1. 症状文から主訴キーワードを抽出する
2. `lookup_specialty` ツールを必ず呼び出して、診療科候補と緊急度を取得する
3. 取得した結果を元に、以下のフォーマットで応答する

[出力フォーマット]
- 推奨診療科: <ツールが返した candidates を提示>
- 緊急度: <ツールが返した urgency を提示>
- 理由: <症状とツール結果を結びつける 1〜2 文>
- 注意事項: 「これは教育用の AI 応答であり、実際の診断ではありません。
  症状が続く場合は医療機関を受診してください。」

[ルール]
- 必ず `lookup_specialty` を呼んでから回答する (自己判断で診療科を答えない)
- 緊急度「高」の場合は救急受診を促す
""",
    tools=[lookup_specialty],
)
