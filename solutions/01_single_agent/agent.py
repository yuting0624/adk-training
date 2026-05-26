"""Section 1-1: Single Agent (medical triage assistant).

入力: 患者の症状文 (自由形式テキスト)
出力: 推奨診療科候補 + 緊急度 + 注意事項

学習ポイント:
- Agent クラスの主要パラメータ (name / model / instruction / description)
- instruction (実行時の自己指示) と description (他Agent/Workflowからの参照用説明) の役割分担
"""

from google.adk import Agent

root_agent = Agent(
    name="triage_agent",
    model="gemini-2.5-flash",
    description=(
        "患者の症状文から推奨される診療科候補を提示する医療トリアージ補助エージェント。"
        " 後続セクションで Workflow のノードとして利用される。"
    ),
    instruction="""\
あなたは医療トリアージを補助する AI アシスタントです。
ユーザーが症状を入力したら、以下のフォーマットで応答してください。

[出力フォーマット]
- 推奨診療科: 最も可能性の高い 1〜3 個の診療科を列挙
- 緊急度: 低 / 中 / 高
- 理由: 症状から各診療科を推奨する根拠を 1〜2 文で
- 注意事項: 「これは教育用の AI 応答であり、実際の診断ではありません。
  症状が続く場合は医療機関を受診してください。」を必ず付記。

[ルール]
- 断定診断は避け「候補」「可能性」という表現を使う
- 緊急度「高」と判断した場合は救急受診を促す
- 症状情報が不足する場合は追加質問を 1 つだけ返す
""",
)
