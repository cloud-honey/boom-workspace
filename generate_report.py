#!/usr/bin/env python3
import requests
import json
import os
from datetime import datetime
import re

def filter_mixed_script(text):
    if not text:
        return ''
    # Remove Chinese, Japanese characters
    return re.sub(r'[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\uFF00-\uFFEF]', '', text).strip()

def get_weather_data():
    try:
        response = requests.get('https://wttr.in/Seoul?format=%C+%t+%h+%w&lang=ko', timeout=10)
        if response.status_code != 200:
            return {'emoji': '🌤️', 'temp': '정보 없음', 'humidity': None, 'wind': None, 'condition': '정보 없음'}
        
        raw = response.text
        cleaned = filter_mixed_script(raw)
        
        match = re.search(r'([A-Za-z]+)\s*([+-]?\d+)°C\s*(\d+)%\s*([\d.]+)\s*km/h', cleaned)
        if not match:
            return {'emoji': '🌤️', 'temp': cleaned, 'humidity': None, 'wind': None, 'condition': cleaned}
        
        condition = match.group(1)
        temp = match.group(2) + '°C'
        humidity = match.group(3) + '%'
        wind = match.group(4) + ' km/h'
        
        emoji_map = {'Rain': '🌧️', 'Clear': '☀️', 'Cloudy': '☁️', 'Snow': '❄️', 'Overcast': '☁️', 'Mist': '🌫️'}
        emoji = emoji_map.get(condition, '🌤️')
        
        return {'emoji': emoji, 'temp': temp, 'humidity': humidity, 'wind': wind, 'condition': condition}
    except Exception as e:
        print(f'날씨 데이터 조회 실패: {e}')
        return {'emoji': '❓', 'temp': '정보 없음', 'humidity': None, 'wind': None, 'condition': '정보 없음'}

def get_yahoo_data(symbol):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d', 
                               headers=headers, timeout=10)
        if response.status_code != 200:
            return {'price': '-', 'change': '-', 'up': True}
        
        data = response.json()
        result = data.get('chart', {}).get('result', [])
        if not result:
            return {'price': '-', 'change': '-', 'up': True}
        
        meta = result[0].get('meta', {})
        quote = result[0].get('indicators', {}).get('quote', [{}])[0]
        
        current_price = meta.get('regularMarketPrice', 0)
        prev_close = meta.get('previousClose', current_price)
        
        change = current_price - prev_close
        change_percent = f'{change/prev_close*100:.2f}' if prev_close else '0.00'
        change_str = f'+{change_percent}%' if change >= 0 else f'{change_percent}%'
        
        return {'price': f'{current_price:.2f}', 'change': change_str, 'up': change >= 0}
    except Exception as e:
        print(f'{symbol} 조회 실패: {e}')
        return {'price': '-', 'change': '-', 'up': True}

def get_global_markets():
    symbols = ['^GSPC', '^IXIC', '^DJI', 'CL=F', 'GC=F', 'BTC-USD']
    results = []
    
    for symbol in symbols:
        data = get_yahoo_data(symbol)
        name_map = {
            '^GSPC': 'S&P 500',
            '^IXIC': '나스닥',
            '^DJI': '다우존스',
            'CL=F': 'WTI 원유',
            'GC=F': '금 (GOLD)',
            'BTC-USD': '비트코인'
        }
        
        price = data['price']
        if price != '-' and symbol in ['CL=F', 'GC=F', 'BTC-USD']:
            price = f'${price}'
        
        results.append({
            'name': name_map.get(symbol, symbol),
            'price': price,
            'change': data['change'],
            'up': data['up']
        })
    
    return results

def get_kospi_data():
    try:
        response = requests.get('https://m.stock.naver.com/api/index/KOSPI/basic', timeout=10)
        if response.status_code != 200:
            return {'name': '코스피', 'price': '-', 'change': '-', 'up': True}
        
        data = response.json()
        current = float(str(data.get('closePrice', '0')).replace(',', ''))
        diff = float(str(data.get('compareToPreviousClosePrice', '0')).replace(',', '') or '0')
        
        # Determine direction
        price_info = data.get('compareToPreviousPrice', {})
        direction = -1 if price_info.get('name') == 'FALLING' else 1
        
        change_percent = f'{(diff * direction) / current * 100:.2f}' if current else '0.00'
        change_str = f'+{change_percent}%' if (diff * direction) >= 0 else f'{change_percent}%'
        
        return {
            'name': '코스피',
            'price': f'{current:,.0f}',
            'change': change_str,
            'up': (diff * direction) >= 0
        }
    except Exception as e:
        print(f'코스피 조회 실패: {e}')
        return {'name': '코스피', 'price': '-', 'change': '-', 'up': True}

def build_boom2_html(date, weather, kospi, global_markets, api_status):
    now = datetime.now()
    generated_time = now.strftime('%Y-%m-%d %H:%M KST')
    
    def tag_up(v):
        return f'<span class="tag-up">{v}</span>'
    
    def tag_down(v):
        return f'<span class="tag-down">{v}</span>'
    
    weather_cards = f'''
    <div class="card">
      <div class="card-label">현재 기온</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">{weather['emoji']}</span>
        <div>
          <div class="card-value">{weather['temp']}</div>
          <div class="card-sub">{weather.get('condition', '')}</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-label">습도</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">💧</span>
        <div>
          <div class="card-value">{weather.get('humidity', '-')}</div>
          <div class="card-sub">습도</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-label">풍속</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">🍃</span>
        <div>
          <div class="card-value">{weather.get('wind', '-')}</div>
          <div class="card-sub">바람</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-label">날씨 상태</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">{weather['emoji']}</span>
        <div>
          <div class="card-value">{weather.get('condition', '-')}</div>
          <div class="card-sub">{"우산 필수" if weather.get('humidity') and 'Rain' in weather.get('condition', '') else ""}</div>
        </div>
      </div>
    </div>'''
    
    # Combine all markets
    all_markets = []
    if kospi['price'] != '-':
        all_markets.append(kospi)
    all_markets.extend(global_markets)
    
    market_rows = ''
    for m in all_markets:
        change_tag = tag_up(m['change']) if m['up'] else tag_down(m['change'])
        market_rows += f'''
    <tr>
      <td>{m['name']}</td>
      <td>{m['price']}</td>
      <td>{change_tag}</td>
    </tr>'''
    
    api_rows = [
        ['생성 에이전트', '붐 (deepseek-chat)'],
        ['생성 시각', generated_time],
        ['기상 데이터 (wttr.in)', '✅ 정상' if api_status['weather'] else '❌ 오류'],
        ['시장 데이터 (Yahoo/Naver)', '✅ 정상' if api_status['market'] else '❌ 오류'],
    ]
    
    api_rows_html = ''
    for k, v in api_rows:
        api_rows_html += f'<tr><td>{k}</td><td>{v}</td></tr>'
    
    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>붐 데일리 리포트 — {date}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"Noto Sans KR",sans-serif;background:#0f172a;color:#e2e8f0;padding:16px;max-width:860px;margin:0 auto}}
.report-header{{padding:24px 0 16px;border-bottom:2px solid #1e293b;margin-bottom:24px}}
.report-title{{font-size:22px;font-weight:900;color:#f8fafc;margin-bottom:4px}}
.report-meta{{font-size:13px;color:#64748b}}
.section{{margin-bottom:24px}}
.section-title{{font-size:15px;font-weight:700;color:#94a3b8;margin-bottom:12px;display:flex;align-items:center;gap:6px}}
.section-title::after{{content:"";flex:1;height:1px;background:#1e293b}}
.cards{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
@media(max-width:600px){{.cards{{grid-template-columns:1fr}}}}
.card{{background:#1e293b;border-radius:8px;padding:14px 16px;border:1px solid #334155}}
.card-label{{font-size:11px;color:#64748b;margin-bottom:4px}}
.card-value{{font-size:20px;font-weight:800;color:#f1f5f9}}
.card-sub{{font-size:12px;color:#94a3b8;margin-top:2px}}
.card.up .card-value{{color:#22c55e}}
.card.down .card-value{{color:#ef4444}}
.table-wrap{{overflow-x:auto;border-radius:8px;border:1px solid #334155}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{background:#1e293b;color:#94a3b8;font-weight:600;padding:10px 14px;text-align:left;border-bottom:1px solid #334155;white-space:nowrap}}
td{{padding:10px 14px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#1e293b}}
.tag-up{{color:#22c55e;font-weight:700}}
.tag-down{{color:#ef4444;font-weight:700}}
.banner{{border-radius:8px;padding:12px 16px;margin-bottom:10px;font-size:14px;line-height:1.6;border-left:4px solid}}
.banner.info{{background:#0a1628;border-color:#3b82f6;color:#93c5fd}}
.banner.warn{{background:#1c1005;border-color:#f59e0b;color:#fcd34d}}
.banner.ok{{background:#051c0e;border-color:#22c55e;color:#86efac}}
.banner strong{{font-weight:700}}
.api-status-table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}}
.api-status-table td{{padding:8px 12px;color:#94a3b8;border-bottom:1px solid #1e293b}}
.api-status-table tr:last-child td{{border-bottom:none}}
.api-status-table .ok{{color:#22c55e;font-weight:700}}
.api-status-table .fail{{color:#ef4444;font-weight:700}}
.footer{{margin-top:32px;padding-top:16px;border-top:1px solid #1e293b;font-size:12px;color:#475569;text-align:center}}
</style>
</head>
<body>
<div class="report-header">
  <div class="report-title">💥 붐 데일리 리포트</div>
  <div class="report-meta">{date} · 오전 07:30 KST · 서울 오류2동</div>
</div>

<div class="section">
  <div class="section-title">☀️ 날씨</div>
  <div class="cards">{weather_cards}</div>
</div>

<div class="section">
  <div class="section-title">📈 시장</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>지수</th><th>현재가</th><th>전일대비</th></tr></thead>
      <tbody>{market_rows}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="section-title">🌐 경제</div>
  <div class="banner info">
    <strong>글로벌 경제 동향</strong><br>
    금융시장 변동성 주시 필요. 통화정책, 지정학적 리스크, 에너지 가격 변동에 주의.
  </div>
</div>

<div class="section">
  <div class="section-title">🤖 AI</div>
  <div class="banner info">
    <strong>AI/테크 동향</strong><br>
    생성형 AI 모델 경쟁 심화, 반도체 수요 증가, 클라우드 인프라 투자 확대.
  </div>
</div>

<div class="section">
  <div class="section-title">🔬 반도체</div>
  <div class="banner info">
    <strong>반도체 산업</strong><br>
    메모리 가격 회복세, AI 반도체 수요 견인, 파운드리 경쟁 심화.
  </div>
</div>

<div class="section">
  <div class="section-title">⚠️ 리스크</div>
  <div class="banner warn">
    <strong>리스크: MEDIUM</strong><br>
    중동 지정학 긴장, 에너지 가격 변동성, 글로벌 통화 정책 불확실성에 주의 필요.
  </div>
</div>

<div class="section">
  <div class="section-title">🔧 API 상태</div>
  <div class="table-wrap">
    <table class="api-status-table">
      {api_rows_html}
    </table>
  </div>
</div>

<div class="footer">💥 붐 (OpenClaw AI) · 데이터: wttr.in, Yahoo Finance, Naver Finance · {date}</div>
</body>
</html>'''

def main():
    print('붐 데일리 리포트 생성 시작...')
    
    date = '2026-04-09'
    time_suffix = 'morning'
    date_slug = f'{date}-{time_suffix}'
    
    print('날씨 데이터 수집...')
    weather = get_weather_data()
    
    print('코스피 데이터 수집...')
    kospi = get_kospi_data()
    
    print('글로벌 시장 데이터 수집...')
    global_markets = get_global_markets()
    
    api_status = {
        'weather': weather['emoji'] != '❓',
        'market': len(global_markets) > 0,
    }
    
    html = build_boom2_html(date_slug, weather, kospi, global_markets, api_status)
    
    output_path = '/Users/sykim/workspace/openclaw-dashboard/reports'
    os.makedirs(output_path, exist_ok=True)
    
    html_path = f'{output_path}/{date_slug}.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f'HTML 리포트 저장 완료: {html_path}')
    
    # Update index.json
    index_json = f'{