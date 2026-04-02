import json, time, urllib.request, statistics, os, subprocess, signal
from pathlib import Path
ROOT = Path('/Users/sykim/.openclaw/workspace/booml-mlx')
TEST = ROOT / 'server_v3_postgres_router_bench.py'
LOG = ROOT / 'bench_server_real.log'
URL = 'http://127.0.0.1:8003/v1/chat/completions'
HEALTH = 'http://127.0.0.1:8003/health'

def wait_health(timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(HEALTH, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False

payloads = [
    {
        'model': 'qwen3-14b-mlx',
        'messages': [{'role': 'user', 'content': 'Reply with exactly: BENCH_OK'}],
        'temperature': 0.2,
        'max_tokens': 16,
    },
    {
        'model': 'qwen3-14b-mlx',
        'messages': [{'role': 'user', 'content': '한국어로 한 문장만 답해. 붐엘 실벤치 테스트 중이라고 말해.'}],
        'temperature': 0.2,
        'max_tokens': 48,
    },
]

env = os.environ.copy()
env['BOOML_DB_BACKEND'] = 'postgresql'
env['BOOML_POSTGRES_URL'] = 'postgresql://sykim@localhost:5432/booml'
logf = open(LOG, 'w')
proc = subprocess.Popen(['python3', str(TEST)], cwd=str(ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT)

try:
    t0=time.time()
    if not wait_health():
        raise RuntimeError('server did not become healthy')
    boot=time.time()-t0
    results=[]
    for idx,payload in enumerate(payloads,1):
        data=json.dumps(payload).encode('utf-8')
        req=urllib.request.Request(URL,data=data,headers={'Content-Type':'application/json'})
        s=time.time()
        with urllib.request.urlopen(req, timeout=240) as r:
            body=r.read().decode('utf-8')
        dt=time.time()-s
        obj=json.loads(body)
        text=obj['choices'][0]['message']['content']
        meta=obj.get('metadata',{})
        results.append({'case':idx,'seconds':round(dt,2),'text':text,'metadata':meta})
    secs=[r['seconds'] for r in results]
    print(json.dumps({'ok':True,'boot_seconds':round(boot,2),'avg_seconds':round(statistics.mean(secs),2),'min_seconds':round(min(secs),2),'max_seconds':round(max(secs),2),'results':results}, ensure_ascii=False, indent=2))
finally:
    proc.send_signal(signal.SIGTERM)
    try: proc.wait(timeout=10)
    except Exception: proc.kill()
    logf.close()
