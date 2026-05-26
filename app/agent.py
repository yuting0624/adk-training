"""Step 01 のスタート地点 — 最小限の Agent。

このファイルが Step 01〜08 を通して育てていくエージェントの種です。
- Step 01 (b): 医療トリアージ用に書き換える
- Step 03: lookup_specialty 関数ツールを追加
- Step 04: Google Maps Grounding Lite MCP を追加
- Step 05: Workflow で 3 つのエージェントを直列合成
- Step 08 [stretch]: SafetyCheckAgent を Workflow 末尾に追加

詰まったら solutions/0X_xxx/agent.py を参照。
"""

from google.adk import Agent

root_agent = Agent(
    name="my_agent",
    model="gemini-3.5-flash",
    instruction="あなたは親切なアシスタントです。日本語で質問に答えてください。",
)
