#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual-Eye Investment Dashboard - データ取得スクリプト v1.2
6時間ごとに実行され、yfinanceからマーケットデータを取得し
ペロシ眼・清原眼の2ロジックでスコアリング＋START/GOAL進捗を計算してJSON出力する。

v1.2 新機能:
- 銘柄ごとの START/GOAL 価格自動算出（テクニカルベース）
- 現在値が START→GOAL のどこにいるか進捗％算出
- ステータス判定（STANDBY / RUNNING / GOAL達成）
"""

import json
import os
from datetime import datetime, timezone, timedelta
import yfinance as yf

# 日本時間
JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TIMESTAMP = NOW.isoformat()

# データディレクトリ
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ===== ペロシ眼：米国株ウォッチリスト =====
PELOSI_TICKERS = {
    'NVDA':  {'name': 'NVIDIA',              'tags': [{'label': 'AI', 'type': 'hot'}, {'label': 'CHIPS法', 'type': 'policy'}]},
    'MSFT':  {'name': 'Microsoft',           'tags': [{'label': 'AI', 'type': 'hot'}, {'label': 'クラウド', 'type': 'policy'}]},
    'GOOGL': {'name': 'Alphabet',            'tags': [{'label': 'AI', 'type': 'hot'}, {'label': 'クラウド', 'type': 'growth'}]},
    'AAPL':  {'name': 'Apple',               'tags': [{'label': 'AI', 'type': 'hot'}, {'label': 'ブランド', 'type': 'growth'}]},
    'TSLA':  {'name': 'Tesla',               'tags': [{'label': 'EV', 'type': 'hot'}, {'label': 'AI', 'type': 'growth'}]},
    'PANW':  {'name': 'Palo Alto Networks',  'tags': [{'label': 'サイバー', 'type': 'hot'}, {'label': '防衛予算', 'type': 'policy'}]},
    'CRWD':  {'name': 'CrowdStrike',         'tags': [{'label': 'サイバー', 'type': 'hot'}, {'label': '政府調達', 'type': 'policy'}]},
    'V':     {'name': 'Visa',                'tags': [{'label': '金融', 'type': 'policy'}, {'label': '安定', 'type': 'growth'}]},
    'AVGO':  {'name': 'Broadcom',            'tags': [{'label': '半導体', 'type': 'hot'}, {'label': 'AI', 'type': 'growth'}]},
    'AMZN':  {'name': 'Amazon',              'tags': [{'label': 'クラウド', 'type': 'hot'}, {'label': 'EC', 'type': 'growth'}]},
}

# ===== 清原眼：日本株ウォッチリスト =====
KIYOHARA_TICKERS = {
    '4011.T': {'name': 'ヘッドウォータース',  'tags': [{'label': 'AI', 'type': 'hot'}, {'label': '小型', 'type': 'policy'}]},
    '5132.T': {'name': 'pluszero',         'tags': [{'label': 'AI', 'type': 'hot'}, {'label': 'AEI', 'type': 'growth'}]},
    '5595.T': {'name': 'QPS研究所',        'tags': [{'label': '宇宙', 'type': 'hot'}, {'label': '防衛', 'type': 'policy'}]},
    '9158.T': {'name': 'シーユーシー',     'tags': [{'label': '医療', 'type': 'hot'}, {'label': 'M&A', 'type': 'growth'}]},
    '4180.T': {'name': 'Appier Group',     'tags': [{'label': 'AI', 'type': 'hot'}, {'label': '海外', 'type': 'growth'}]},
    '4592.T': {'name': 'サンバイオ',       'tags': [{'label': 'バイオ', 'type': 'hot'}, {'label': '承認', 'type': 'policy'}]},
    '6920.T': {'name': 'レーザーテック',   'tags': [{'label': '半導体', 'type': 'hot'}, {'label': '独占', 'type': 'growth'}]},
    '3681.T': {'name': 'ブイキューブ',     'tags': [{'label': 'DX', 'type': 'policy'}, {'label': '割安', 'type': 'growth'}]},
    '4375.T': {'name': 'セーフィー',       'tags': [{'label': 'SaaS', 'type': 'hot'}, {'label': '成長', 'type': 'growth'}]},
    '7380.T': {'name': '十六FG',           'tags': [{'label': '金融', 'type': 'policy'}, {'label': '割安', 'type': 'growth'}]},
}

def safe_info(ticker_symbol):
    """yfinanceから安全にデータ取得"""
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        hist = t.history(period='1y')  # v1.2: 1年分（START/GOAL用）
        return info, hist
    except Exception as e:
        print(f"[ERROR] {ticker_symbol}: {e}")
        return {}, None

def calc_start_goal(info, hist, current_price):
    """
    v1.2 新機能: START価格とGOAL価格を自動算出
    - START: 過去20日移動平均（買い検討ゾーン下限）
    - GOAL: 52週高値の90%（現実的な目標）
    - Progress: (current - start) / (goal - start) * 100
    """
    start_price = None
    goal_price = None
    try:
        if hist is not None and len(hist) >= 20:
            # START = 20日移動平均（近い買い水準）
            sma20 = hist['Close'].iloc[-20:].mean()
            start_price = round(float(sma20), 2)
        else:
            start_price = round(current_price * 0.92, 2) if current_price else None

        if hist is not None and len(hist) >= 50:
            # GOAL = 52週高値の90%（現実的目標）
            high52 = hist['High'].max()
            goal_raw = float(high52) * 0.95
            # 現在値より低い場合は、現在値の+20%
            if current_price and goal_raw <= current_price * 1.05:
                goal_raw = current_price * 1.20
            goal_price = round(goal_raw, 2)
        else:
            goal_price = round(current_price * 1.25, 2) if current_price else None

        # 進捗率計算
        if start_price and goal_price and goal_price > start_price and current_price:
            progress_raw = (current_price - start_price) / (goal_price - start_price) * 100
            progress = round(progress_raw)
            progress = max(-100, min(150, progress))
        else:
            progress = 0

        # ステータス判定
        if progress >= 100:
            status = "GOAL"
        elif progress >= 0:
            status = "RUNNING"
        else:
            status = "STANDBY"

        return start_price, goal_price, progress, status
    except Exception as e:
        print(f"[ERROR] calc_start_goal: {e}")
        return current_price, current_price, 0, "STANDBY"

def calc_pelosi_score(info, hist):
    """ペロシ眼スコア"""
    score = 0
    score += 20
    if hist is not None and len(hist) >= 20:
        try:
            recent = hist['Close'].iloc[-1]
            before = hist['Close'].iloc[-20]
            momentum = (recent - before) / before * 100
            if momentum > 10:    score += 40
            elif momentum > 5:   score += 30
            elif momentum > 0:   score += 20
            elif momentum > -5:  score += 10
        except Exception: score += 15
    else: score += 15
    if hist is not None and len(hist) >= 20:
        try:
            avg_vol = hist['Volume'].mean()
            recent_vol = hist['Volume'].iloc[-5:].mean()
            if recent_vol > avg_vol * 1.3:    score += 30
            elif recent_vol > avg_vol * 1.1:  score += 20
            elif recent_vol > avg_vol * 0.9:  score += 15
            else:                              score += 10
        except Exception: score += 15
    else: score += 15
    return min(100, score)

def calc_kiyohara_score(info, hist):
    """清原眼スコア"""
    score = 0
    try:
        pe = info.get('trailingPE') or info.get('forwardPE') or 99
        if pe < 10:   score += 40
        elif pe < 15: score += 30
        elif pe < 20: score += 20
        elif pe < 25: score += 10
    except Exception: score += 15
    try:
        growth = info.get('revenueGrowth') or 0
        if growth > 0.3:    score += 30
        elif growth > 0.15: score += 22
        elif growth > 0.05: score += 15
        elif growth > 0:    score += 8
    except Exception: score += 12
    try:
        roe = info.get('returnOnEquity') or 0
        if roe > 0.20:   score += 30
        elif roe > 0.15: score += 22
        elif roe > 0.10: score += 15
        elif roe > 0.05: score += 8
    except Exception: score += 12
    return min(100, score)

def get_price(info, hist):
    try:
        if hist is not None and len(hist) > 0:
            return round(float(hist['Close'].iloc[-1]), 2)
    except Exception: pass
    return info.get('currentPrice') or info.get('regularMarketPrice') or 0

def analyze_stocks(tickers_dict, scorer):
    """銘柄群を分析（v1.2: START/GOAL/Progress付き）"""
    results = []
    for symbol, meta in tickers_dict.items():
        print(f"[INFO] Analyzing {symbol}...")
        info, hist = safe_info(symbol)
        score = scorer(info, hist)
        price = get_price(info, hist)
        start_price, goal_price, progress, status = calc_start_goal(info, hist, price)
        results.append({
            'code': symbol,
            'name': meta['name'],
            'price': price,
            'start_price': start_price,
            'goal_price': goal_price,
            'progress': progress,
            'status': status,
            'score': score,
            'signal': '分析済',
            'tags': meta['tags']
        })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

def fetch_indices():
    """主要指数取得"""
    indices_map = [
        ('^GSPC', 'S&P500'),
        ('^IXIC', 'NASDAQ'),
        ('^N225', '日経平均'),
        ('^TOPX', 'TOPIX'),
        ('^VIX', 'VIX'),
        ('JPY=X', 'ドル円'),
    ]
    result = []
    for symbol, name in indices_map:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period='5d')
            if len(hist) >= 2:
                latest = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = (latest - prev) / prev * 100
                result.append({
                    'name': name,
                    'value': round(float(latest), 2),
                    'change': round(float(change), 2)
                })
        except Exception as e:
            print(f"[ERROR] Index {symbol}: {e}")
    return result

def calc_overall_score(indices, pelosi_top, kiyohara_top):
    """中立マーケット評価"""
    pelosi_avg = sum(s['score'] for s in pelosi_top[:3]) / 3 if pelosi_top else 50
    fundamental = round(pelosi_avg * 0.30)
    tech_score = 15
    for idx in indices[:3]:
        if idx['change'] > 1:    tech_score += 5
        elif idx['change'] > 0:  tech_score += 3
        elif idx['change'] > -1: tech_score += 1
    technical = min(30, tech_score)
    vix = next((i['value'] for i in indices if i['name'] == 'VIX'), 20)
    if vix < 15:    sentiment = 18
    elif vix < 20:  sentiment = 14
    elif vix < 25:  sentiment = 10
    elif vix < 30:  sentiment = 6
    else:            sentiment = 3
    kiyo_avg = sum(s['score'] for s in kiyohara_top[:3]) / 3 if kiyohara_top else 50
    macro = round(kiyo_avg * 0.20)
    overall = fundamental + technical + sentiment + macro
    return {
        'overall_score': overall,
        'fundamental': fundamental,
        'technical': technical,
        'sentiment': sentiment,
        'macro': macro
    }

def gen_actions(overall, pelosi, kiyohara):
    """アクションガイド生成（v1.2: GOAL到達銘柄もアラート）"""
    actions = []
    score = overall['overall_score']
    if score >= 80:
        actions.append({'priority': 'high', 'text': f"🔥 強い買いシグナル中（{score}点）。ペロシTOP3（{pelosi[0]['name']}等）に注目"})
    elif score >= 60:
        actions.append({'priority': 'high', 'text': f"🎯 買い検討環境（{score}点）。ペロシTOP5とQレシオ高い清原TOP3を優先チェック"})
    elif score >= 40:
        actions.append({'priority': 'mid', 'text': f"⚖️ 中立環境（{score}点）。ポジションは資金の5-10%に抑制"})
    else:
        actions.append({'priority': 'high', 'text': f"⚠️ 弱気相場（{score}点）。現金比率を高め、押し目を待つ"})

    # v1.2: GOAL到達銘柄をアラート
    goal_reached = [s for s in (pelosi or []) + (kiyohara or []) if s.get('status') == 'GOAL']
    for s in goal_reached[:3]:
        actions.append({'priority': 'high', 'text': f"🏁 {s['name']}（{s['code']}）がGOAL到達！利確検討"})

    # 加速中銘柄（進捗70%以上）
    accelerating = [s for s in (pelosi or []) + (kiyohara or []) if 70 <= s.get('progress', 0) < 100]
    if accelerating:
        top = max(accelerating, key=lambda x: x['progress'])
        actions.append({'priority': 'mid', 'text': f"⚡ {top['name']}がGOAL目前（進捗{top['progress']}%）"})

    if pelosi:
        actions.append({'priority': 'mid', 'text': f"🇺🇸 米国株TOP：{pelosi[0]['name']}（{pelosi[0]['code']}）スコア{pelosi[0]['score']}点"})
    if kiyohara:
        actions.append({'priority': 'mid', 'text': f"🇯🇵 日本株TOP：{kiyohara[0]['name']}（{kiyohara[0]['code']}）スコア{kiyohara[0]['score']}点"})
    return actions

def update_log(overall_score):
    """分析記録"""
    log_path = os.path.join(DATA_DIR, 'analysis_log.json')
    entries = []
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                entries = json.load(f).get('entries', [])
        except Exception:
            entries = []
    judge = '強い買い' if overall_score >= 80 else '買い検討' if overall_score >= 60 else '中立' if overall_score >= 40 else '売り検討'
    entries.insert(0, {
        'time': NOW.strftime('%-m/%-d %H:%M'),
        'score': overall_score,
        'judge': judge
    })
    entries = entries[:24]
    return {'updated': TIMESTAMP, 'entries': entries}

def main():
    print(f"[START] Dual-Eye v1.2 分析開始 @ {TIMESTAMP}")
    print("[STEP 1/4] ペロシ眼 米国株分析＋START/GOAL算出")
    pelosi_stocks = analyze_stocks(PELOSI_TICKERS, calc_pelosi_score)
    print("[STEP 2/4] 清原眼 日本株分析＋START/GOAL算出")
    kiyohara_stocks = analyze_stocks(KIYOHARA_TICKERS, calc_kiyohara_score)
    print("[STEP 3/4] 主要指数取得")
    indices = fetch_indices()
    print("[STEP 4/4] 中立マーケットスコア＋アクション生成")
    overall = calc_overall_score(indices, pelosi_stocks, kiyohara_stocks)
    actions = gen_actions(overall, pelosi_stocks, kiyohara_stocks)

    with open(os.path.join(DATA_DIR, 'pelosi_stocks.json'), 'w', encoding='utf-8') as f:
        json.dump({
            'updated': TIMESTAMP,
            'model': 'Pelosi Eye - Policy × Innovation',
            'stocks': pelosi_stocks
        }, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, 'kiyohara_stocks.json'), 'w', encoding='utf-8') as f:
        json.dump({
            'updated': TIMESTAMP,
            'model': 'Kiyohara Eye - Small Cap Growth × Q Ratio',
            'note': '時価総額500億円以下／ROE15%以上／Qレシオ1.0以上',
            'stocks': kiyohara_stocks
        }, f, ensure_ascii=False, indent=2)
    market_data = {
        'timestamp': TIMESTAMP,
        **overall,
        'indices': indices,
        'actions': actions
    }
    with open(os.path.join(DATA_DIR, 'market_status.json'), 'w', encoding='utf-8') as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)
    log_data = update_log(overall['overall_score'])
    with open(os.path.join(DATA_DIR, 'analysis_log.json'), 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 総合スコア: {overall['overall_score']}点")
    print(f"[DONE] ペロシTOP: {pelosi_stocks[0]['name']} 進捗{pelosi_stocks[0]['progress']}%（{pelosi_stocks[0]['status']}）")
    print(f"[DONE] 清原TOP: {kiyohara_stocks[0]['name']} 進捗{kiyohara_stocks[0]['progress']}%（{kiyohara_stocks[0]['status']}）")

if __name__ == '__main__':
    main()
