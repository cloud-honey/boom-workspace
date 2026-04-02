import json, time, urllib.request, statistics, os, subprocess, signal
from pathlib import Path
ROOT = Path('/Users/sykim/.openclaw/workspace/booml-mlx')
TEST = ROOT / 'server_v3_postgres_router_bench.py'
LOG = ROOT / 'bench_server_extended.log'
URL = 'http://127.0.0.1:8003/v1/chat/completions'
HEALTH = 'http://127.0.0.1:8003/health'
SWITCH_URL = 'http://127.0.0.1:8003/v1/models/switch'
MODELS_URL = 'http://127.0.0.1:8003/v1/models'

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

def post(url, payload, timeout=240):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

env = os.environ.copy()
env['BOOML_DB_BACKEND'] = 'postgresql'
env['BOOML_POSTGRES_URL'] = 'postgresql://sykim@localhost:5432/booml'
logf = open(LOG, 'w')
proc = subprocess.Popen(['python3', str(TEST)], cwd=str(ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT)

try:
    if not wait_health():
        raise RuntimeError('server did not become healthy')

    cases = []

    # 1) long-form response on MLX
    payload = {
        'model': 'qwen3-14b-mlx',
        'messages': [{'role': 'user', 'content': '한국어로 5문장 이내로 PostgreSQL-first와 SQLite fallback 구조 차이를 쉽게 설명해줘.'}],
        'temperature': 0.2,
        'max_tokens': 180,
    }
    s=time.time(); out=post(URL, payload); dt=time.time()-s
    cases.append({'case':'long_korean_mlx','seconds':round(dt,2),'text':out['choices'][0]['message']['content'],'metadata':out.get('metadata',{})})

    # 2) search-including prompt on MLX (current architecture may include realtime helpers)
    payload = {
        'model': 'qwen3-14b-mlx',
        'messages': [{'role': 'user', 'content': '오늘 경제 뉴스 핵심만 한국어로 짧게 정리해줘.'}],
        'temperature': 0.2,
        'max_tokens': 220,
    }
    s=time.time(); out=post(URL, payload); dt=time.time()-s
    cases.append({'case':'news_prompt_mlx','seconds':round(dt,2),'text':out['choices'][0]['message']['content'],'metadata':out.get('metadata',{})})

    # 3) hot switch to dummy and compare
    switch = post(SWITCH_URL, {'model_name':'dummy'})
    payload = {
        'model': 'dummy',
        'messages': [{'role': 'user', 'content': 'Reply with exactly: DUMMY_OK'}],
        'temperature': 0.2,
        'max_tokens': 16,
    }
    s=time.time(); out=post(URL, payload); dt=time.time()-s
    cases.append({'case':'dummy_switch','seconds':round(dt,2),'text':out['choices'][0]['message']['content'],'metadata':out.get('metadata',{}),'switch':switch})

    # switch back to mlx
    switch_back = post(SWITCH_URL, {'model_name':'qwen3-14b-mlx'})
    models = get(MODELS_URL)

    print(json.dumps({
        'ok': True,
        'cases': cases,
        'switch_back': switch_back,
        'models': models
    }, ensure_ascii=False, indent=2))
finally:
    proc.send_signal(signal.SIGTERM)
    try: proc.wait(timeout=10)
    except Exception: proc.kill()
    logf.close()
