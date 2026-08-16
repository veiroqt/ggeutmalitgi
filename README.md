# 끝말잇기 (Word Chain) — 실시간 멀티플레이 웹 게임

FastAPI + WebSocket 기반 실시간 끝말잇기 게임 (MVP).

## 실행 방법

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt

copy .env.example .env
# .env 파일을 열어 JWT_SECRET, KOREAN_DICT_API_KEY 값을 채워주세요.
# 사전 API 키는 https://opendict.korean.go.kr 오픈 API 신청에서 무료로 발급받을 수 있습니다.

uvicorn backend.main:app --reload
```

브라우저에서 http://localhost:8000 접속.

## 현재 구현된 기능 (MVP)

- 회원가입 / 로그인 (bcrypt 비밀번호 해싱 + JWT)
- 아이디 / 닉네임 중복 확인
- 방 생성 / 목록 조회 / 코드로 참가 / 비밀번호 방
- WebSocket 기반 실시간 끝말잇기 (턴 검증, 사전 API 검증, 끝말 연결 검증, 중복 단어 검증, 15초 제한시간)
- 게임 중 실시간 채팅 (간단한 비속어 필터링)
- 점수 / 연승 / 랭킹 시스템
- 마이페이지 (전적, 최근 게임 기록)

## 설계 참고사항

- 로비(방 목록/생성/대기실)와 게임 화면, 결과 화면은 하나의 WebSocket 연결을 유지해야 하므로
  `frontend/lobby.html` 한 페이지 안에서 화면 전환(view switching) 방식으로 구현했습니다.
  페이지를 이동(location.href)하면 WebSocket 연결이 끊어져 턴/타이머 상태가 끊기기 때문입니다.
- 모든 게임 판정(턴 확인, 단어 존재 여부, 끝말 연결, 중복 단어, 제한시간)은 `backend/game.py`에서
  서버 측으로만 이루어지며 클라이언트는 상태를 표시하는 역할만 합니다.
- 사전 API 키가 설정되지 않으면 단어 제출 시 "사전 API 키가 설정되지 않았습니다" 오류가 반환됩니다.
