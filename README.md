# ADK Training Workshop

**3 時間ハンズオン**: **ADK 2.0** (Agent Development Kit) でグラフベース `Workflow` を構築し、MCP統合・Agent Engine デプロイ・Gemini Enterprise 呼び出しまでを一気通貫で体験。

> ワークショップの全手順と解説は **[tutorial.md](tutorial.md)** にまとまっています。本 README はリポジトリ構成のクイックリファレンスです。

## クイックスタート

Cloud Shell で:

```bash
git clone https://github.com/yuting0624/adk-training.git
cd adk-training
./setup.sh
./verify.sh      # 任意: 事前ヘルスチェック (API有効化 / モデル疎通 / Maps MCP 接続)
teachme tutorial.md
```

その後 [tutorial.md](tutorial.md) の Step 01 から進めてください。

## リポジトリ構成

```
adk-training/
├── tutorial.md            ← ワークショップ本体 (全手順 + 解説)
├── setup.sh               ← Cloud Shell ワンショットセットアップ
├── verify.sh              ← 事前ヘルスチェック (API / モデル / MCP 疎通)
├── pyproject.toml         ← 依存関係 (google-adk 2.x, uv 管理)
├── .env.example           ← 環境変数テンプレート
├── app/                   ← 受講者が育てるエージェント (Step 01 stub + evalset.json)
└── solutions/             ← 各 Step 完成形 (詰まったとき用)
    ├── 01_single_agent/   Step 01 完成形
    ├── 02_tools/          Step 03 完成形
    ├── 03_mcp/            Step 04 完成形
    ├── 04_multi_agent/    Step 05 完成形
    └── 05_safety_check/   Step 08 ストレッチ参考解
```

## ADK バージョン

`google-adk[mcp,gcp]>=2.1.0,<3` を使用。ADK 2.0 は 1.x から破壊的変更を含むため、古い記事や 1.x ベースの Codelab とは API が異なります (`Agent` + `Workflow` が中心)。

## ライセンス・注意

教育用デモです。題材として医療系を採用していますが、実際の医療診断行為ではありません。
