#!/usr/bin/env python3
"""GROWTH ATLAS — 実株価バンドル生成パイプライン.

yfinance で日足データを取得し、フロントエンド (index.html) が読む
dist/atlas_bundle.json を生成する。

series タプルの列順 (index.html の COL と同期):
  [price, daily_return, deviation, vol20, cum_return, trend_slope,
   stage, volume_norm, state_code]

state_code: 0=healthy, 1=excited, 2=sick, 3=sleeping, 4=evolving
"""
import json
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "..", "dist", "atlas_bundle.json")

LOOKBACK = "2y"          # 取得期間
TREND_WINDOW = 40        # トレンド回帰の窓
VOL_WINDOW = 20          # ボラティリティ窓
MA_WINDOW = 20           # 乖離率の基準移動平均

COMPANIES = [
    dict(id="voc", ticker="VOC", yf=None, name="Dutch East India Company",
         name_ja="オランダ東インド会社", hq_lat=52.3702, hq_lng=4.8952,
         founded_year=1602, ipo_year=1602, defunct_year=1799, sector="Trade",
         history_events=[
             {"year": 1602, "type": "founded", "title": "世界初の株式会社として設立・株式公開", "effect": "birth"},
             {"year": 1799, "type": "bankruptcy", "title": "解散", "effect": "death"}]),
    dict(id="aapl", ticker="AAPL", yf="AAPL", name="Apple Inc.", name_ja="アップル",
         hq_lat=37.3230, hq_lng=-122.0322, founded_year=1976, ipo_year=1980,
         defunct_year=None, sector="Technology",
         history_events=[
             {"year": 1976, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 1980, "type": "ipo", "title": "NASDAQ上場", "effect": "evolve"},
             {"year": 1997, "type": "milestone", "title": "倒産危機・ジョブズ復帰", "effect": "damage"},
             {"year": 2007, "type": "milestone", "title": "iPhone発表", "effect": "evolve"},
             {"year": 2018, "type": "milestone", "title": "時価総額1兆ドル到達", "effect": "evolve"}]),
    dict(id="7203", ticker="7203", yf="7203.T", name="Toyota Motor", name_ja="トヨタ自動車",
         hq_lat=35.0833, hq_lng=137.1561, founded_year=1937, ipo_year=1949,
         defunct_year=None, sector="Automotive",
         history_events=[
             {"year": 1937, "type": "founded", "title": "豊田自動織機から独立し設立", "effect": "birth"},
             {"year": 1949, "type": "ipo", "title": "東証上場", "effect": "evolve"},
             {"year": 1997, "type": "milestone", "title": "プリウス発売（世界初量産HV）", "effect": "evolve"},
             {"year": 2008, "type": "milestone", "title": "世界販売台数首位に", "effect": "evolve"}]),
    dict(id="tsla", ticker="TSLA", yf="TSLA", name="Tesla, Inc.", name_ja="テスラ",
         hq_lat=30.2419, hq_lng=-97.6202, founded_year=2003, ipo_year=2010,
         defunct_year=None, sector="Automotive",
         history_events=[
             {"year": 2003, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 2010, "type": "ipo", "title": "NASDAQ上場", "effect": "evolve"},
             {"year": 2020, "type": "milestone", "title": "S&P500採用・時価総額急拡大", "effect": "evolve"}]),
    dict(id="005930", ticker="005930", yf="005930.KS", name="Samsung Electronics",
         name_ja="サムスン電子", hq_lat=37.2636, hq_lng=127.0286, founded_year=1969,
         ipo_year=1975, defunct_year=None, sector="Technology",
         history_events=[
             {"year": 1969, "type": "founded", "title": "設立", "effect": "birth"},
             {"year": 1975, "type": "ipo", "title": "韓国取引所上場", "effect": "evolve"},
             {"year": 1993, "type": "milestone", "title": "新経営宣言・グローバル化", "effect": "evolve"}]),
    dict(id="sap", ticker="SAP", yf="SAP.DE", name="SAP SE", name_ja="SAP",
         hq_lat=49.2933, hq_lng=8.6428, founded_year=1972, ipo_year=1988,
         defunct_year=None, sector="Software",
         history_events=[
             {"year": 1972, "type": "founded", "title": "IBM出身の5人が創業", "effect": "birth"},
             {"year": 1988, "type": "ipo", "title": "フランクフルト上場", "effect": "evolve"}]),
    dict(id="msft", ticker="MSFT", yf="MSFT", name="Microsoft", name_ja="マイクロソフト",
         hq_lat=47.6396, hq_lng=-122.1283, founded_year=1975, ipo_year=1986,
         defunct_year=None, sector="Technology",
         history_events=[
             {"year": 1975, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 1986, "type": "ipo", "title": "NASDAQ上場", "effect": "evolve"},
             {"year": 1995, "type": "milestone", "title": "Windows 95発売", "effect": "evolve"}]),
    dict(id="6758", ticker="6758", yf="6758.T", name="Sony Group", name_ja="ソニーグループ",
         hq_lat=35.6304, hq_lng=139.7401, founded_year=1946, ipo_year=1958,
         defunct_year=None, sector="Electronics",
         history_events=[
             {"year": 1946, "type": "founded", "title": "東京通信工業として創業", "effect": "birth"},
             {"year": 1958, "type": "renamed", "title": "ソニーに社名変更・東証上場", "effect": "transform"},
             {"year": 1979, "type": "milestone", "title": "ウォークマン発売", "effect": "evolve"},
             {"year": 1994, "type": "milestone", "title": "PlayStation発売", "effect": "evolve"}]),
    dict(id="nvda", ticker="NVDA", yf="NVDA", name="NVIDIA", name_ja="エヌビディア",
         hq_lat=37.3705, hq_lng=-121.9645, founded_year=1993, ipo_year=1999,
         defunct_year=None, sector="Semiconductors",
         history_events=[
             {"year": 1993, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 1999, "type": "ipo", "title": "NASDAQ上場・GPUの発明", "effect": "evolve"},
             {"year": 2023, "type": "milestone", "title": "AIブームで時価総額1兆ドル到達", "effect": "evolve"}]),
    dict(id="lehman", ticker="LEH", yf=None, name="Lehman Brothers", name_ja="リーマン・ブラザーズ",
         hq_lat=40.7648, hq_lng=-73.9808, founded_year=1850, ipo_year=1994,
         defunct_year=2008, sector="Finance",
         history_events=[
             {"year": 1850, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 1994, "type": "ipo", "title": "アメックスから独立し再上場", "effect": "transform"},
             {"year": 2008, "type": "bankruptcy", "title": "経営破綻（史上最大級の倒産）", "effect": "death"}]),
    dict(id="kodak", ticker="KODK", yf="KODK", name="Eastman Kodak", name_ja="コダック",
         hq_lat=43.1566, hq_lng=-77.6088, founded_year=1892, ipo_year=1905,
         defunct_year=None, sector="Imaging",
         history_events=[
             {"year": 1892, "type": "founded", "title": "設立", "effect": "birth"},
             {"year": 2012, "type": "bankruptcy", "title": "連邦破産法11条申請", "effect": "damage"},
             {"year": 2013, "type": "milestone", "title": "再建・再上場", "effect": "transform"}]),
    dict(id="9984", ticker="9984", yf="9984.T", name="SoftBank Group",
         name_ja="ソフトバンクグループ", hq_lat=35.6478, hq_lng=139.7461,
         founded_year=1981, ipo_year=1994, defunct_year=None, sector="Holding",
         history_events=[
             {"year": 1981, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 1994, "type": "ipo", "title": "株式公開", "effect": "evolve"},
             {"year": 2000, "type": "milestone", "title": "ITバブル崩壊で株価急落", "effect": "damage"},
             {"year": 2016, "type": "acquisition", "title": "ARM買収", "effect": "evolve"}]),
    dict(id="asml", ticker="ASML", yf="ASML", name="ASML Holding", name_ja="ASML",
         hq_lat=51.4231, hq_lng=5.4623, founded_year=1984, ipo_year=1995,
         defunct_year=None, sector="Semiconductors",
         history_events=[
             {"year": 1984, "type": "founded", "title": "フィリップスとASMIの合弁として設立", "effect": "birth"},
             {"year": 1995, "type": "ipo", "title": "上場", "effect": "evolve"},
             {"year": 2017, "type": "milestone", "title": "EUV露光装置の量産開始", "effect": "evolve"}]),
    dict(id="tcehy", ticker="0700", yf="0700.HK", name="Tencent Holdings", name_ja="テンセント",
         hq_lat=22.5333, hq_lng=113.9333, founded_year=1998, ipo_year=2004,
         defunct_year=None, sector="Technology",
         history_events=[
             {"year": 1998, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 2004, "type": "ipo", "title": "香港上場", "effect": "evolve"},
             {"year": 2011, "type": "milestone", "title": "WeChat公開", "effect": "evolve"}]),
    dict(id="nestle", ticker="NESN", yf="NESN.SW", name="Nestlé", name_ja="ネスレ",
         hq_lat=46.4628, hq_lng=6.8419, founded_year=1866, ipo_year=1873,
         defunct_year=None, sector="Food",
         history_events=[
             {"year": 1866, "type": "founded", "title": "創業", "effect": "birth"},
             {"year": 1905, "type": "merger", "title": "Anglo-Swissと合併", "effect": "transform"}]),
]


def fetch_prices():
    tickers = [c["yf"] for c in COMPANIES if c["yf"]]
    raw = yf.download(tickers, period=LOOKBACK, interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")
    closes, volumes = {}, {}

    def extract(frame, t):
        try:
            df = frame[t][["Close", "Volume"]].dropna(subset=["Close"])
        except KeyError:
            return False
        if len(df) < TREND_WINDOW + 10:
            return False
        closes[t] = df["Close"]
        volumes[t] = df["Volume"]
        return True

    missing = [t for t in tickers if not extract(raw, t)]
    for attempt in range(3):
        if not missing:
            break
        time.sleep(3)
        print(f"retry {attempt + 1} for {missing}")
        raw2 = yf.download(missing, period=LOOKBACK, interval="1d",
                           auto_adjust=True, progress=False, group_by="ticker")
        if len(missing) == 1:  # 単一銘柄は列が平坦になる
            raw2 = pd.concat({missing[0]: raw2}, axis=1)
        missing = [t for t in missing if not extract(raw2, t)]
    for t in missing:
        print(f"WARN: no data for {t}")
    close_df = pd.DataFrame(closes).sort_index()
    vol_df = pd.DataFrame(volumes).reindex(close_df.index)
    # 市場ごとの休場日は前日値で補完
    close_df = close_df.ffill()
    vol_df = vol_df.fillna(0.0)
    # 全銘柄が揃う日から開始
    close_df = close_df.dropna()
    vol_df = vol_df.loc[close_df.index]
    return close_df, vol_df


def trend_slope(logp: pd.Series) -> pd.Series:
    x = np.arange(TREND_WINDOW)
    x = x - x.mean()
    denom = (x ** 2).sum()

    def slope(w):
        return float(np.dot(x, w - w.mean()) / denom)

    return logp.rolling(TREND_WINDOW).apply(slope, raw=True)


def build_series(close: pd.Series, volume: pd.Series):
    price = close / close.iloc[0] * 100.0
    ret = price.pct_change().fillna(0.0)
    ma = price.rolling(MA_WINDOW, min_periods=1).mean()
    deviation = (price / ma - 1.0).fillna(0.0)
    vol20 = ret.rolling(VOL_WINDOW, min_periods=2).std().fillna(0.0)
    cum = price / 100.0 - 1.0
    slope = trend_slope(np.log(price)).fillna(0.0)

    # 進化段階: トレンドの強さで 1〜3
    stage = pd.Series(1, index=price.index)
    stage[slope > 0.0008] = 2
    stage[slope > 0.0020] = 3

    # 出来高の正規化 (0〜0.69): 過去120日内での分位
    vrank = volume.rolling(120, min_periods=10).apply(
        lambda w: (w < w[-1]).mean(), raw=True).fillna(0.5) * 0.69

    rows = []
    prev_stage = None
    for i in range(len(price)):
        st = int(stage.iloc[i])
        if prev_stage is not None and st > prev_stage:
            state = 4                      # evolving
        elif vrank.iloc[i] < 0.08:
            state = 3                      # sleeping
        elif deviation.iloc[i] < -0.05:
            state = 2                      # sick
        elif abs(ret.iloc[i]) > 0.045 or vol20.iloc[i] > 0.035:
            state = 1                      # excited
        else:
            state = 0                      # healthy
        prev_stage = st
        rows.append([
            round(float(price.iloc[i]), 4),
            round(float(ret.iloc[i]), 6),
            round(float(deviation.iloc[i]), 5),
            round(float(vol20.iloc[i]), 5),
            round(float(cum.iloc[i]), 5),
            round(float(slope.iloc[i]), 7),
            st,
            round(float(vrank.iloc[i]), 4),
            state,
        ])
    return rows


def main():
    close_df, vol_df = fetch_prices()
    dates = [d.strftime("%Y-%m-%d") for d in close_df.index]
    companies = []
    for c in COMPANIES:
        meta = {k: v for k, v in c.items() if k != "yf"}
        if c["yf"] and c["yf"] in close_df.columns:
            meta["series"] = build_series(close_df[c["yf"]], vol_df[c["yf"]])
            meta["real_price_base"] = round(float(close_df[c["yf"]].iloc[0]), 4)
        else:
            meta["series"] = None
        companies.append(meta)

    bundle = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "thresholds_version": 2,
        "source": "yfinance (daily, auto-adjusted)",
        "dates": dates,
        "companies": companies,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUT_PATH) / 1024
    alive = sum(1 for c in companies if c["series"])
    print(f"OK: {len(dates)} days × {alive} live companies -> {OUT_PATH} ({size:.0f} KB)")


if __name__ == "__main__":
    main()
