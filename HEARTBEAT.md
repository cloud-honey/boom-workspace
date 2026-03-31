# Heartbeat 체크리스트

## DevTeam 에스컬레이션 감지 (최우선)
매 heartbeat마다 아래 파일 확인:
`/home/sykim/.openclaw/workspace/reports/devteam-escalation.md`

파일에 `상태: PENDING` 항목이 있으면:
1. 해당 에스컬레이션 내용 분석
2. 해결책 수립 (다른 에이전트 투입, 접근법 변경 등)
3. 마스터에게 텔레그램으로 보고:
   ```
   🔧 [붐] DevTeam 에스컬레이션 처리
   - 문제: (내용)
   - 해결책: (방안)
   - 조치: (붐이 직접 처리 또는 마스터 컨펌 필요)
   ```
4. 에스컬레이션 파일의 해당 항목 `상태: RESOLVED`로 업데이트
- PENDING 없으면 이 항목 무시



## 진행 중인 작업이 있으면
- 현재 진행 상태, 몇 % 완료됐는지, 예상 완료 시간을 보고할 것

## 진행 중인 작업이 없으면
- HEARTBEAT_OK 로만 응답할 것 (메시지 전송 안 됨)

## 작업 중 오류가 발생했으면
- 시간대 관계없이 즉시 보고할 것
- 오류 내용과 해결 방법 또는 내가 해야 할 조치를 함께 알려줄 것
- 절대 조용히 멈추지 말 것

## 게이트웨이 재시작 감지 시
- "게이트웨이가 재시작됐습니다. 다시 작동 중입니다." 라고 텔레그램으로 보고할 것
- 재시작 전에 진행 중이던 작업이 있었으면 작업 목록을 알려줄 것

## 모델 상태 모니터링
- 매 heartbeat마다 현재 모델이 `claude-sonnet-4-6`인지 확인할 것.
- 만약 현재 모델이 `claude-sonnet-4-6`이 아닐 경우, 즉시 텔레그램으로 아래 형식에 맞춰 보고할 것:
  `⚠️ 현재 모델: [모델명], Claude 쿨타임 남은 시간: [시간]`
  (쿨타임 확인이 불가능할 경우 '확인 불가'로 보고)

## XPS 노드 상태 모니터링
- 매 heartbeat마다 XPS 노드 상태 확인:
  ```
  exec: openclaw nodes invoke --node "XPS Node" --command system.run --params '{"command":["/home/sykim/xps-status.sh"]}'
  ```
- 응답에서 `gateway` 값이 `active`가 아니면 즉시 텔레그램 보고:
  `⚠️ XPS 게이트웨이 다운: [상태값] — 붐스 응답 불가 상태`
- XPS 노드 자체가 연결 안 되면 (invoke 실패):
  `⚠️ XPS 노드 연결 끊김 — XPS 전원 꺼짐 또는 네트워크 문제`
- 이상 없으면 보고 안 해도 됨 (HEARTBEAT_OK)

## 하트비트 로그 기록 (필수)
매 heartbeat 실행 시 반드시 아래 파일에 1줄 로그를 append할 것:
`/Users/sykim/.openclaw/workspace/logs/heartbeat.log`

형식 (한 줄):
```
YYYY-MM-DD HH:MM:SS KST | STATUS | model=모델명 | xps=active/down/disconnected | escalation=none/PENDING | notes=비고
```

- STATUS: `OK` (이상 없음) 또는 `ALERT` (문제 감지)
- 파일이 없으면 생성
- 100줄 이상이면 최근 50줄만 남기고 나머지 삭제
