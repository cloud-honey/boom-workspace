const fetch = require('node-fetch').default;
const fs = require('fs');

// Filter mixed script function
function filterMixedScript(text) {
    if (!text) return '';
    return text.replace(
        /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\uFF00-\uFFEF]/g,
        ''
    ).trim();
}

// Get weather data
async function getWeatherData() {
    try {
        const response = await fetch('https://wttr.in/Seoul?format=%C+%t+%h+%w&lang=ko', { timeout: 10000 });
        if (!response.ok) throw new Error('wttr.in 응답 실패');
        const raw = await response.text();
        const cleaned = filterMixedScript(raw);

        const match = cleaned.match(/([A-Za-z]+)\s*([+-]?\d+)°C\s*(\d+)%\s*([\d.]+)\s*km\/h/);
        if (!match) return { emoji: '🌤️', temp: cleaned, humidity: null, wind: null, condition: cleaned };

        const condition = match[1];
        const temp = match[2] + '°C';
        const humidity = match[3] + '%';
        const wind = match[4] + ' km/h';

        const emojiMap = { Rain: '🌧️', Clear: '☀️', Cloudy: '☁️', Snow: '❄️', Overcast: '☁️', Mist: '🌫️' };
        return { emoji: emojiMap[condition] || '🌤️', temp, humidity, wind, condition };
    } catch (error) {
        console.error('날씨 데이터 조회 실패:', error);
        return { emoji: '❓', temp: '정보 없음', humidity: null, wind: null, condition: '정보 없음' };
    }
}

// Get Yahoo Finance data
async function getYahooData(symbol) {
    try {
        const response = await fetch(
            `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=2d`,
            { timeout: 10000, headers: { 'User-Agent': 'Mozilla/5.0' } }
        );
        if (!response.ok) throw new Error(`Yahoo ${symbol} 응답 실패`);
        const data = await response.json();
        const result = data?.chart?.result?.[0];
        if (!result) throw new Error(`${symbol} 데이터 없음`);

        const meta = result.meta;
        const quote = result.indicators?.quote?.[0];
        const currentPrice = meta.regularMarketPrice ?? quote?.close?.[quote.close.length - 1] ?? 0;
        const prevClose = meta.previousClose ?? quote?.close?.[quote.close.length - 2] ?? currentPrice;
        const change = currentPrice - prevClose;
        const changePercent = prevClose ? ((change / prevClose) * 100).toFixed(2) : '0.00';
        const changeStr = change >= 0 ? `+${changePercent}%` : `${changePercent}%`;

        return { price: currentPrice.toFixed(2), change: changeStr, up: change >= 0 };
    } catch (error) {
        console.error(`${symbol} 조회 실패:`, error.message);
        return { price: '-', change: '-', up: true };
    }
}

async function getGlobalMarkets() {
    const [sp500, nasdaq, dow, wti, gold, btc] = await Promise.all([
        getYahooData('^GSPC'),
        getYahooData('^IXIC'),
        getYahooData('^DJI'),
        getYahooData('CL=F'),
        getYahooData('GC=F'),
        getYahooData('BTC-USD'),
    ]);

    return [
        { name: 'S&P 500', price: sp500.price, change: sp500.change, up: sp500.up },
        { name: '나스닥', price: nasdaq.price, change: nasdaq.change, up: nasdaq.up },
        { name: '다우존스', price: dow.price, change: dow.change, up: dow.up },
        { name: 'WTI 원유', price: wti.price !== '-' ? '$' + wti.price : '-', change: wti.change, up: wti.up },
        { name: '금 (GOLD)', price: gold.price !== '-' ? '$' + gold.price : '-', change: gold.change, up: gold.up },
        { name: '비트코인', price: btc.price !== '-' ? '$' + btc.price : '-', change: btc.change, up: btc.up },
    ];
}

// Get KOSPI data
async function getKospiData() {
    try {
        const response = await fetch('https://m.stock.naver.com/api/index/KOSPI/basic', { timeout: 10000 });
        if (!response.ok) throw new Error('Naver 응답 실패');
        const data = await response.json();
        const current = parseFloat(String(data.closePrice).replace(/,/g, ''));
        const diff = parseFloat(String(data.compareToPreviousClosePrice).replace(/,/g, '') || '0');
        const ratio = parseFloat(data.fluctuationsRatio || '0');
        const direction = data.compareToPreviousPrice?.name === 'FALLING' ? -1 : 1;
        const changeStr = (diff * direction) >= 0
            ? `+${((diff * direction) / current * 100).toFixed(2)}%`
            : `${((diff * direction) / current * 100).toFixed(2)}%`;

        return { name: '코스피', price: current.toLocaleString(), change: changeStr, up: diff * direction >= 0 };
    } catch (error) {
        console.error('코스피 조회 실패:', error);
        return { name: '코스피', price: '-', change: '-', up: true };
    }
}

// Build HTML
function buildBoom2Html({ date, weather, kospi, globalMarkets, apiStatus }) {
    const now = new Date();
    const generatedTime = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')} KST`;

    const tagUp = (v) => `<span class="tag-up">${v}</span>`;
    const tagDown = (v) => `<span class="tag-down">${v}</span>`;

    const weatherCards = `
    <div class="card">
      <div class="card-label">현재 기온</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">${weather.emoji}</span>
        <div>
          <div class="card-value">${weather.temp}</div>
          <div class="card-sub">${weather.condition || ''}</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-label">습도</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">💧</span>
        <div>
          <div class="card-value">${weather.humidity || '-'}</div>
          <div class="card-sub">습도</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-label">풍속</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">🍃</span>
        <div>
          <div class="card-value">${weather.wind || '-'}</div>
          <div class="card-sub">바람</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-label">날씨 상태</div>
      <div style="display:flex;align-items:center;gap:10px">
        <span style="font-size:38px">${weather.emoji}</span>
        <div>
          <div class="card-value">${weather.condition || '-'}</div>
          <div class="card-sub">${weather.humidity ? '우산 필수' : ''}</div>
        </div>
      </div>
    </div>`;

    // Add KOSPI to markets
    const allMarkets = [];
    if (kospi.price !== '-') {
        allMarkets.push(kospi);
    }
    allMarkets.push(...globalMarkets);

    const marketRows = allMarkets.map(m => `
    <tr>
      <td>${m.name}</td>
      <td>${m.price}</td>
      <td>${m.up ? tagUp(m.change) : tagDown(m.change)}</td>
    </tr>`).join('');

    const apiRows = [
        ['생성 에이전트', '붐 (deepseek-chat)'],
        ['생성 시각', generatedTime],
        ['기상 데이터 (wttr.in)', apiStatus.weather ? '✅ 정상' : '❌ 오류'],
        ['시장 데이터 (Yahoo/Naver)', apiStatus.market ? '✅ 정상' : '❌ 오류'],
    ].map(([k,v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');

    return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>붐 데일리 리포트 — ${date}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"Noto Sans KR",sans-serif;background:#0f172a;color:#e2e8f0;padding:16px;max-width:860px;margin:0 auto}
.report-header{padding:24px 0 16px;border-bottom:2px solid #1e293b;margin-bottom:24px}
.report-title{font-size:22px;font-weight:900;color:#f8fafc;margin-bottom:4px}
.report-meta{font-size:13px;color:#64748b}
.section{margin-bottom:24px}
.section-title{font-size:15px;font-weight:700;color:#94a3b8;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.section-title::after{content:"";flex:1;height:1px;background:#1e293b}
.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(max-width:600px){.cards{grid-template-columns:1fr}}
.card{background:#1e293b;border-radius:8px;padding:14px 16px;border:1px solid #334155}
.card-label{font-size:11px;color:#64748b;margin-bottom:4px}
.card-value{font-size:20px;font-weight:800;color:#f1f5f9}
.card-sub{font-size:12px;color:#94a3b8;margin-top:2px}
.card.up .card-value{color:#22c55e}
.card.down .card-value{color:#ef4444}
.table-wrap{overflow-x:auto;border-radius:8px;border:1px solid #334155}
table{width:100%;border-collapse:collapse;font-size:14px}
th{background:#1e293b;color:#94a3b8;font-weight:600;padding:10px 14px;text-align:left;border-bottom:1px solid #334155;white-space:nowrap}
td{padding:10px 14px;border-bottom:1px solid #1e293b;color:#cbd5e1}
tr:last-child td{border-bottom:none}
tr:hover td{background:#1e293b}
.tag-up{color:#22c55e;font-weight:700}
.tag-down{color:#ef4444;font-weight:700}
.banner{border-radius:8px;padding:12px 16px;margin-bottom:10px;font-size:14px;line-height:1.6;border-left:4px solid}
.banner.info{background:#0a1628;border-color:#3b82f6;color:#93c5fd}
.banner.warn{background:#1c1005;border-color:#f59e0b;color:#fcd34d}
.banner.ok{background:#051c0e;border-color:#22c55e;color:#86efac}
.banner strong{font-weight:700}
.api-status-table{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}
.api-status-table td{padding:8px 12px;color:#94a3b8;border-bottom:1px solid #1e293b}
.api-status-table tr:last-child td{border-bottom:none}
.api-status-table .ok{color:#22c55e;font-weight:700}
.api-status-table .fail{color:#ef4444;font-weight:700}
.footer{margin-top:32px;padding-top:16px;border-top:1px solid #1e293b;font-size:12px;color:#475569;text-align:center}
</style>
</head>
<body>
<div class="report-header">
  <div class="report-title">💥 붐 데일리 리포트</div>
  <div class="report-meta">${date} · 오전 07:30 KST · 서울 오류2동</div>
</div>

<div class="section">
  <div class="section-title">☀️ 날씨</div>
  <div class="cards">${weatherCards}</div>
</div>

<div class="section">
  <div class="section-title">📈 시장</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>지수</th><th>현재가</th><th>전일대비</th></tr></thead>
      <tbody>${marketRows}</tbody>
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
      ${apiRows}
    </table>
  </div>
</div>

<div class="footer">💥 붐 (OpenClaw AI) · 데이터: wttr.in, Yahoo Finance, Naver Finance · ${date}</div>
</body>
</html>`;
}

async function main() {
    console.log('붐 데일리 리포트 생성 시작...');
    
    const date = '2026-04-09';
    const timeSuffix = 'morning';
    const dateSlug = `${date}-${timeSuffix}`;
    
    console.log('날씨 데이터 수집...');
    const weather = await getWeatherData();
    
    console.log('코스피 데이터 수집...');
    const kospi = await getKospiData();
    
    console.log('글로벌 시장 데이터 수집...');
    const globalMarkets = await getGlobalMarkets();
    
    const apiStatus = {
        weather: weather.emoji !== '❓',
        market: globalMarkets.length > 0,
    };
    
    const html = buildBoom2Html({
        date: dateSlug,
        weather,
        kospi,
        globalMarkets,
        apiStatus,
    });
    
    const outputPath = '/Users/sykim/workspace/openclaw-dashboard/reports';
    if (!fs.existsSync(outputPath)) {
        fs.mkdirSync(outputPath, { recursive: true });
    }
    
    const htmlPath = `${outputPath}/${dateSlug}.html`;
    fs.writeFileSync(htmlPath, html);
    console.log(`HTML 리포트