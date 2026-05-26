# Facilitator Notes — ADK 2.0 ワークショップ

ワークショップを運営する **講師向けの非公開メモ**。tutorial.md は受講者向け、こちらは講師向け。

- [tutorial.md](../tutorial.md) — 受講者用ハンズオン本文
- 想定: 中級エンジニア 5 名 + 共有 GCP プロジェクト (全員 Editor)、所要 3 時間
- 重要前提: 過去のドライランで発覚したハマりどころは [トラブル集](#トラブル集--デモ崩壊時のリカバリ) に集約

---

## 講師の事前準備

### T-7 日

- [ ] 共有 GCP プロジェクト用意 (課金有効化、参加者全員に Editor 付与)
- [ ] **本リポジトリを fork or 自社オーガナイゼーションに clone** し、tutorial.md の `0-1` のリポジトリ URL を自社のものに置き換え
- [ ] 自分の個人 GCP プロジェクトで **end-to-end ドライラン** (Step 01〜07 全部、Step 08 もチェック)。実機で動かないと当日詰む
- [ ] **GE Agent Builder で事前にデモ用エージェント登録** (Step 07 のフォールバック用、当日デプロイが失敗してもデモ続行できる状態)
- [ ] GE デモ画面の **録画** を撮っておく (ライブデモ失敗時のフォールバック)

### T-1 日 (前日)

```bash
# 1. プロジェクトで必要 API 一括有効化 (mapstools.googleapis.com 必須)
gcloud services enable \
  aiplatform.googleapis.com \
  mapstools.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  maps-backend.googleapis.com \
  --project=<shared-project>

# 2. Maps API キー作成 (Maps Grounding Lite が allowlist に入った状態)
gcloud alpha services api-keys create \
  --display-name="adk-workshop-shared" \
  --project=<shared-project>
# 出力された keyString を控える。"Don't restrict key" を確認 (or restrict + Maps Grounding Lite を allow)

# 予備キー (Quota 枯渇に備え)
gcloud alpha services api-keys create \
  --display-name="adk-workshop-shared-backup" \
  --project=<shared-project>

# 3. Vertex AI Gemini クォータ確認 (5人同時 × 1 リクエスト 3-4 model call)
gcloud alpha services quota list \
  --service=aiplatform.googleapis.com \
  --consumer=projects/<shared-project> \
  --filter="quotaId:GenerateContent*" | head -20

# 4. GE workspace 確認 (Step 07 デモ用に access 可能か)
```

### T-10 分 (workshop 開始直前)

- [ ] スライド: ADK 全体像 / Workflow vs AgentTool vs Task API 比較 / アーキ図
- [ ] **画面投影**: Maps API キー (1〜2 分でいいので投影 → 受講者が手元 `.env` に貼り付け)
- [ ] **配布資料**: 症状サンプル文 (`動悸がして、たまに胸も痛む。東京駅周辺で病院を探したい` など 3〜4 例)
- [ ] Slack / Zoom チャットに以下を貼っておく:
  - リポジトリ URL
  - 共有 GCP プロジェクト ID
  - Maps API キー
  - 詰まったとき用 `solutions/0X_*` 参照

---

## 進行台本 (180 分)

| 時刻 | セクション | 講師が言う/やる |
|---|---|---|
| 0:00-0:05 | Intro スライド | ADK 全体像、本日のゴール (= reasoningEngine を GE から呼ぶ)、教育用デモの免責 |
| 0:05-0:25 | 事前準備 | 「Cloud Shell 開いて `git clone ... && cd adk-training && ./setup.sh`」「.env の MAPS_API_KEY に投影しているキーを貼る」 |
| 0:25-0:55 | Step 01 シングルエージェント | `app/agent.py` 読解 → 医療版に書き換え → `adk run app` で症状投入 |
| 0:55-1:15 | Step 02 開発ツール | `adk web app --allow_origins "*"` (`--allow_origins` 重要)、Cloud Shell Web Preview の手順実演 |
| 1:15-1:25 | ☕ 休憩 | 受講者は手を動かしすぎて疲れている。明示的に休憩を取る |
| 1:25-1:45 | Step 03 Tools | FunctionTool 追加。Trace タブで `lookup_specialty` 呼び出しを見る |
| 1:45-2:00 | Step 04 MCP | Maps Grounding Lite MCP 接続。「東京駅周辺の循環器内科」 |
| 2:00-2:50 | Step 05 Workflow | 設計判断スライド 10 分 → 実装 30 分 → end-to-end 確認 10 分。**ここが本日のヤマ場** |
| 2:50-2:55 | Step 06 Deploy 投入 | 全員に `adk deploy agent_engine ...` を打たせる。**講師の合図で 30 秒ずつズラして投入** (Cloud Build キュー対策) |
| 2:55-3:00 | Step 07 GE デモ | 講師の事前デプロイ済 reasoningEngine を GE Agent Builder に登録 → Chat で症状投入 → 回答表示 |
| 3:00+ | Step 08 [stretch] | 余裕あれば。なくても次に学ぶべきことリストで agents-cli 紹介で締め |

### 進行のコツ

- **Step 01-04 は手が早い人は先に進めても OK** にする (講師は質問対応に回る)
- **Step 05 だけは全員揃って始める** — 設計判断スライドが効くため
- **Step 06 の投入タイミングは絶対揃えない** — Cloud Build が直列気味なのでズラすほうが速い
- **Step 07 はデモのみ** — 受講者は自分で GE 登録しない方針 (workspace 散らかる)

---

## トラブル集 / デモ崩壊時のリカバリ

### よくある現象と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `./setup.sh` で `401 Unauthorized` on `us-python.pkg.dev/artifact-foundry-prod/` | Googler 個人マシン (Cloud Shell含む) で社内 Python registry が default index になっている | `pyproject.toml` に `[[tool.uv.index]] url = "https://pypi.org/simple/" default = true` が入っているのでこれで救済される。それでもダメなら `UV_INDEX_URL=https://pypi.org/simple/ ./setup.sh` |
| `adk web` で `ModuleNotFoundError: No module named 'cachetools'` | `~/.local/bin/adk` (壊れた system 版) が拾われた | **必ず `uv run adk ...`** で呼ぶ。`which adk` で確認 |
| `adk web` で「Failed to create session」/ 403 | Cloud Shell の strict CORS で ADK web 側が origin 弾いている | `--allow_origins "*"` を付ける (tutorial では既に標準化) |
| MCP ツール呼出で `403 Forbidden` (`mapstools.googleapis.com`) | プロジェクトで API 未有効化 or API キーの restrictions に Maps Grounding Lite 未許可 | `gcloud services enable mapstools.googleapis.com` + API キー restrictions 確認 |
| Agent Engine デプロイで Cloud Build キュー待ち | 5 人同時投入 | 30 秒ずつズラす |
| `app/.env` が知らない間に生成されている | 受講者が `adk create app` を実行してしまった | `rm app/.env` で root の `.env` のみに戻す。本ワークショップでは `adk create` 使わない方針 |
| Gemini 3.5 Flash がプロジェクトで使えない (403 / not found) | モデルアクセス未許諾 | フォールバック: `app/agent.py` の `model="gemini-3.5-flash"` を `gemini-2.5-flash` に書き換え |
| GE 登録時 reasoningEngine が見えない | リージョン違い / IAM 不足 | GE と Agent Engine が同じプロジェクト / リージョンか確認 |
| 受講者の Web Preview がうまく開かない | Cloud Shell の port forwarding | port `8000` 固定、Web Preview メニューから port を変えるだけ |

### デモ崩壊時のフォールバック優先順

1. **Step 07 GE デモが失敗** → 事前録画を流す (T-7 で撮影済み)
2. **Step 06 全員のデプロイが失敗** → 講師の事前デプロイ済 reasoningEngine を見せる
3. **Step 05 Workflow が動かない** → `solutions/04_multi_agent/agent.py` をそのままコピペさせる
4. **MCP がどうしても動かない** → Step 04 / Step 05 RecommendAgent の MCP コール部分を「ダミーで都内3病院を返す」関数ツールに置換する (講師が即興で実演 → 「本来は MCP でこう動く」と説明)

---

## 共有 GCP プロジェクトでの注意

5 人で 1 プロジェクトを使う今回のセットアップ特有の注意点。

### Maps API キーは 1 本で OK

個別発行は管理コストだけ増えて意味がない。**講師が事前に作って配布する 1 本のキー** を全員が `.env` に貼るだけで OK。

### Agent Engine `display_name` は個人識別子を入れる

tutorial.md Step 06 で `--display_name="Medical Triage - $(whoami)"` を案内済み。`$(whoami)` で衝突回避。

### 受講者間で「他人の reasoningEngine を消さない」

tutorial.md にも記載済みだが、口頭でも念押し。

### Cloud Build キューイング

5 人同時に `adk deploy agent_engine` を投入すると Cloud Build が直列気味になり、待ち時間が伸びる。講師が「右側の人から 30 秒ずつズラして投入してください」とアナウンス。

### Vertex AI Gemini クォータ

5 人 × Workflow 3-4 ノード × 数リクエスト = 瞬間的に数十 QPM。前日にクォータ確認 (上記 T-1 セクション参照)。

---

## ワークショップ後の後片付け

```bash
# 1. Agent Engine reasoningEngine 一括削除
for id in $(gcloud ai reasoning-engines list --region=us-central1 \
    --project=<shared-project> \
    --filter='displayName:Medical Triage*' \
    --format='value(name.basename())'); do
  echo "Deleting $id"
  gcloud ai reasoning-engines delete $id --region=us-central1 --quiet \
    --project=<shared-project>
done

# 2. (もし誰かが Cloud Run デプロイを試した場合) Cloud Run service 一括削除
for svc in $(gcloud run services list --region=us-central1 \
    --project=<shared-project> \
    --filter='metadata.name:medical-triage*' \
    --format='value(metadata.name)'); do
  gcloud run services delete $svc --region=us-central1 --quiet \
    --project=<shared-project>
done

# 3. Cloud Build / Artifact Registry の中間成果物
gcloud artifacts repositories list --project=<shared-project>
# 個別に gcloud artifacts repositories delete

# 4. API キー無効化 (workshop 専用キーだったため)
gcloud alpha services api-keys list --project=<shared-project>
# 個別に gcloud alpha services api-keys delete <KEY_ID>
```

参加者の Cloud Shell 環境はワークショップ後ほっといて OK (個人の home に clone した repo + `.venv` が残るだけで、課金には影響しない)。

---

## 想定 Q&A

> **Q: ADK 1.x で書いた既存コードはそのまま動きますか?**
> A: いいえ、ADK 2.0 は破壊的変更を含みます。`SequentialAgent` / `LoopAgent` / `ParallelAgent` は `legacy_workflows` 配下に移されました。代わりに graph-based の `Workflow` を使います。マイグレーションパスは [adk.dev](https://adk.dev) を参照。

> **Q: `gemini-3.5-flash` vs `gemini-3.5-pro` の使い分けは?**
> A: トリアージや要約のような軽量タスクは flash で十分高速・低コスト。複雑な推論 (例: 多段階の医学的判断、長文の解析) には pro。本ワークショップは flash で統一。

> **Q: MCP と FunctionTool の使い分けは?**
> A: 自社内のロジック / DB アクセスは FunctionTool で書くのが手っ取り早い。**他社・外部システムが提供する** ツール群 (Google Maps / Notion / Slack 等) は MCP で接続するのが今後のスタンダード。MCP は AI Agent Foundation (Linux Foundation, 2025-12〜) がガバナンスを管理しているオープン標準。

> **Q: Workflow の state を構造化したい (Pydantic で型安全に)。**
> A: `Agent(output_schema=MyPydanticModel)` で出力を Pydantic にできる。Workflow 内で `ctx.state["key"]` に書く / 関数ノードの型ヒント引数で自動注入される。本ワークショップでは時間の都合でテキスト受け渡しのみ。次に学ぶべき項目として案内。

> **Q: agents-cli と adk CLI、業務でどっち使えばいい?**
> A: 両方使う。`adk` CLI はフレームワークの素の操作 (run / web / deploy)。`agents-cli` は Claude Code / Gemini CLI 越しに `adk` の操作 + 評価 + GE 連携を自動化する Skills 層。Step 08 で体験した形が業務での使い方。

> **Q: Cloud Run と Agent Engine、本番ではどっち?**
> A: GE 連携・エージェント単体運用なら Agent Engine 一択 (リソース ID 貼るだけで GE 登録)。既存の Cloud Run 資産と統合したい / FastAPI でカスタムエンドポイント追加したい場合は Cloud Run。本ワークショップは Agent Engine で統一。

> **Q: A2A プロトコルとは?**
> A: `google-adk[a2a]` で導入される分散エージェント間通信プロトコル。複数の Agent Engine リソースを別々のチーム / システムで運用し、相互呼び出しするような分散シナリオ向け。本ワークショップでは触れず。

> **Q: ハンズオン中に間違えてコード壊した、戻したい。**
> A: `git checkout app/agent.py` で repo の最新版に戻る。それでもダメなら `solutions/0X_*/agent.py` を `app/agent.py` にコピー。

---

## 参考リンク

- [google/adk-python](https://github.com/google/adk-python)
- [adk.dev](https://adk.dev/)
- [Maps Grounding Lite docs](https://developers.google.com/maps/ai/grounding-lite)
- [Google-managed MCP servers (Cloud Blog)](https://cloud.google.com/blog/products/ai-machine-learning/google-managed-mcp-servers-are-available-for-everyone)
- [google/agents-cli](https://github.com/google/agents-cli)
- [Agent Engine ドキュメント](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)
