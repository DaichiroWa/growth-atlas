# GROWTH ATLAS 🌍🌱

株価を「生き物」として育てて眺めるウェブアプリ。実際の株価（yfinance 日足）で動く。

**デモ構成**: 静的 HTML + 毎日自動更新される `dist/atlas_bundle.json`

## 仕組み

```
yfinance ──(毎日 JST 7:30, GitHub Actions)──▶ pipeline/build_bundle.py
        ──▶ dist/atlas_bundle.json ──▶ GitHub Pages で index.html と一緒に配信
```

- 13銘柄（AAPL / トヨタ / テスラ / サムスン / SAP / MSFT / ソニー / NVIDIA /
  コダック / ソフトバンクG / ASML / テンセント / ネスレ）+ 墓2社（VOC・リーマン）
- 株価は期首=100 の指数に正規化。日次リターン・20日ボラ・移動平均乖離・
  トレンド回帰から「元気/興奮/不調/睡眠/進化中」の状態を判定
- 「庭に迎える」は localStorage に保存

## ローカル実行

```bash
pip install -r pipeline/requirements.txt
python pipeline/build_bundle.py     # dist/atlas_bundle.json を生成
python3 -m http.server 8123         # http://localhost:8123 を開く
```

## 公開手順（GitHub Pages）

1. GitHub に新規リポジトリを作成し push
2. リポジトリ Settings → Pages → Source を **GitHub Actions** に設定
3. Actions タブから `Update stock bundle & deploy` を手動実行（以後は平日毎朝自動）

## 注意

- yfinance は Yahoo Finance の非公式 API。個人利用・デモ用途向け。
  商用公開する場合は正規のデータライセンスが必要。
- データは日足・調整後終値。リアルタイムではない。
