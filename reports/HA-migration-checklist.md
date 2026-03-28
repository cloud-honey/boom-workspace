# Home Assistant 맥미니 이전 체크리스트

> 작성: 붐 | 2026-03-28
> 현재: XPS Docker → 목표: 맥미니 Docker (OrbStack)

---

## 현재 XPS 구성

| 항목 | 내용 |
|------|------|
| 실행 방식 | Docker (ghcr.io/home-assistant/home-assistant:stable) |
| 설정 경로 | /home/sykim/homeassistant/ |
| 포트 | 8123 (외부 미노출, 로컬 전용) |
| dbus 마운트 | /run/dbus → /run/dbus |
| 주요 설정 | configuration.yaml, automations.yaml, secrets.yaml |
| 부가 서비스 | TeslaMate + Grafana + Postgres + Mosquitto (별도 유지) |

---

## 이전 단계

### ✅ STEP 1 — XPS HA 백업
- [ ] XPS에서 HA 설정 전체 백업
  ```bash
  ssh sykim@100.116.65.86
  cd /home/sykim
  tar czf ha-backup-$(date +%Y%m%d).tar.gz homeassistant/
  # 맥미니로 복사
  scp ha-backup-*.tar.gz sykim@kim-macmini.tail89d37c.ts.net:~/
  ```
- [ ] 백업 파일 내용 확인 (configuration.yaml, automations.yaml, secrets.yaml 포함 여부)

### ✅ STEP 2 — 맥미니 Docker 준비
- [ ] OrbStack 정상 구동 확인: `docker ps`
- [ ] HA 설정 폴더 생성
  ```bash
  mkdir -p /Users/sykim/homeassistant
  cd ~
  tar xzf ha-backup-*.tar.gz
  # 또는 복사 후 압축 해제
  ```

### ✅ STEP 3 — 맥미니 HA 컨테이너 실행
```bash
docker run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  -e TZ=Asia/Seoul \
  -v /Users/sykim/homeassistant:/config \
  -v /run/dbus:/run/dbus:ro \
  --network=host \
  ghcr.io/home-assistant/home-assistant:stable
```
- [ ] 컨테이너 정상 실행 확인: `docker ps | grep homeassistant`
- [ ] http://localhost:8123 접속 확인
- [ ] 기존 설정/자동화/기기 정상 로드 확인

### ✅ STEP 4 — 기기 재연결 확인
- [ ] HomeKit 기기 재발견 (macOS Bonjour 자동)
- [ ] 자동화 정상 동작 확인
- [ ] 알림/스크립트 정상 동작 확인

### ✅ STEP 5 — OrbStack 자동 시작 설정
- [ ] OrbStack 로그인 시 자동 시작 설정 확인
- [ ] Docker 컨테이너 restart=unless-stopped 확인 (이미 설정됨)

### ✅ STEP 6 — XPS HA 서비스 종료
이전 완료 후 XPS에서 실행:
```bash
ssh sykim@100.116.65.86
docker stop homeassistant
docker rm homeassistant
# 설정 폴더 백업 보관 (삭제 금지)
# rm -rf /home/sykim/homeassistant  ← 당분간 보관
```
- [ ] XPS homeassistant 컨테이너 stop + rm 완료
- [ ] 맥미니 HA 최종 정상 동작 재확인

---

## 주의사항
- TeslaMate는 XPS에 별도 구성 — HA 이전과 무관, 현재 상태 유지
- secrets.yaml에 API 키/토큰 포함 — 백업 파일 외부 유출 금지
- macOS에서 --network=host 옵션은 제한적으로 동작할 수 있음
  → 문제 시 `-p 8123:8123` 포트 바인딩 방식으로 전환

---

## 마이그레이션 대시보드 체크리스트 업데이트
완료 후 Phase 6에 추가:
- `Home Assistant 맥미니 이전 완료` → done: true
- `XPS homeassistant 컨테이너 종료` → done: true
