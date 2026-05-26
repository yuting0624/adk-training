"""Section 2-2b: Agent + Google Maps Grounding Lite MCP.

Google公式の Maps Grounding Lite MCP server (Streamable HTTP transport) を使用。
旧 `@modelcontextprotocol/server-google-maps` (npm) は 2025 年に deprecated /
archived となったため、本ワークショップでは使わない。
"""

import os

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

load_dotenv()

_MAPS_API_KEY = os.environ.get("MAPS_API_KEY")
if not _MAPS_API_KEY or _MAPS_API_KEY.startswith("YOUR_"):
    raise RuntimeError(
        "MAPS_API_KEY is not set. ワークショップで配布されたキーを .env に追加してください。"
    )

_maps_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mapstools.googleapis.com/mcp",
        headers={"X-Goog-Api-Key": _MAPS_API_KEY},
        timeout=30.0,
        sse_read_timeout=300.0,
    ),
)

root_agent = Agent(
    name="hospital_recommender_agent",
    model="gemini-2.5-flash",
    description=(
        "指定された診療科とエリアから、Google Maps Grounding Lite MCP 経由で"
        "近隣の医療機関を検索・提示するエージェント。"
    ),
    instruction="""\
あなたは病院検索アシスタントです。
ユーザーから「診療科 + エリア (例: 東京駅周辺の循環器内科)」が示されたら、
Google Maps MCP のツールを使って近隣の医療機関を 3〜5 件検索し、以下の形式で提示してください。

[出力フォーマット]
1. <施設名>
   - 住所: <住所>
   - 距離・方角: <概算>
   - 備考: <評価や営業時間など分かれば>
2. ...

[ルール]
- 必ず Maps MCP のツールを呼び出す (記憶や推測で病院名を出さない)
- 結果が 0 件の場合は検索エリアを広げて再検索することを提案
- 注意事項として「最新情報は各施設の公式サイトで確認してください」を付記
""",
    tools=[_maps_mcp],
)
