import json, time, urllib.request, statistics, os, subprocess, signal
from pathlib import Path

ROOT = Path('/Users/sykim/workspace/boom-workspace/booml-mlx')
SRC = ROOT / 'server_v3_postgres_router.py'
TEST = ROOT / 'server_v3_postgres_router_bench.py'
LOG = ROOT / 'bench_server.log'
URL = 'http://127.0.0.1:8001/v1/chat/completions'
HEALTH = 'http://127.0.0.1:8001/health'

text = SRC.read_text()
text = text.replace('PORT = 8000', 'PORT = 8001')
TEST.write_text(text)

payloads = [
    {
        'model': 'qwen3-14b-mlx',
        'messages': [{'role': 'user', 'content': 'Reply with exactly: BENCH_OK'}],
        'temperature': 0.2,
        'max_tokens': 32,
    },
    {
        'model': 'qwen3-14b-mlx',
        'messages': [{'role': 'user', 'content': '한국어로 한 문장만 답해. 붐엘 벤치 테스트 중이라고 말해.'}],
        'temperature': 0.2,
        'max_tokens': 64,
    },
]

def wait_health(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(HEALTH, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False

env = os.environ.copy()
env['BOOML_DB_BACKEND'] = 'postgresql'
env['BOOML_POSTGRES_URL'] = 'postgresql://sykim@localhost:5432/booml'

logf = open(LOG, 'w')
proc = subprocess.Popen(['python3', str(TEST)], cwd=str(ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT)

try:
    if not wait_health():
        raise RuntimeError('server did not become healthy')

    results = []
    for idx, payload in enumerate(payloads, 1):
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(URL, data=data, headers={'Content-Type': 'application/json'})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read().decode('utf-8')
        dt = time.time() - t0
        obj = json.loads(body)
        text = obj['choices'][0]['message']['content']
        usage = obj.get('usage', {})
        results.append({'case': idx, 'seconds': dt, 'text': text, 'usage': usage})

    secs = [r['seconds'] for r in results]
    print(json.dumps({
        'ok': True,
        'avg_seconds': round(statistics.mean(secs), 2),
        'min_seconds': round(min(secs), 2),
        'max_seconds': round(max(secs), 2),
        'results': results,
    }, ensure_ascii=False, indent=2))
finally:
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    logf.close()
