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

## Render로 배포하기

이 프로젝트는 WebSocket 연결과 방 상태를 메모리에 들고 있는 상시 구동 서버라, GitHub Pages나 Vercel 같은
정적/서버리스 플랫폼에는 올릴 수 없습니다. 대신 [Render](https://render.com)처럼 프로세스를 계속 띄워주는
곳을 사용합니다. 저장소에 있는 `render.yaml`을 그대로 인식하는 Blueprint 배포 방식입니다.

1. https://render.com 에서 GitHub 계정으로 가입/로그인
2. 대시보드에서 **New +** → **Blueprint** 선택
3. 이 저장소(`veiroqt/ggeutmalitgi`)를 연결 (처음이면 Render가 리포지토리 접근 권한을 요청함 — 승인)
4. Render가 `render.yaml`을 읽어 서비스 설정을 자동으로 채움. **Apply** 클릭
5. 배포 후 서비스의 **Environment** 탭에서 아래 두 값을 채워넣기 (`render.yaml`에는 값이 비어 있음, 직접 입력해야 함)
   - `JWT_SECRET`: 아무 긴 임의 문자열
   - `KOREAN_DICT_API_KEY`: opendict.korean.go.kr에서 발급받은 키
6. 저장하면 자동 재배포되고, Render가 준 `https://ggeutmalitgi.onrender.com` 같은 주소로 접속

**무료 플랜 제한사항 (알아두어야 할 것)**
- 15분간 요청이 없으면 서비스가 슬립 상태로 들어가고, 다음 접속 시 다시 깨어나는 데 30초~1분 정도 걸릴 수 있습니다.
- 무료 플랜은 영구 디스크를 지원하지 않아서, 재배포하거나 서비스가 재시작되면 SQLite DB(`database/database.db`)가
  초기화될 수 있습니다. 가입자/랭킹 데이터를 계속 보존하려면 유료 디스크를 추가하거나 외부 DB(Render Postgres 등)로
  옮겨야 합니다.

## 설계 참고사항

- 로비(방 목록/생성/대기실)와 게임 화면, 결과 화면은 하나의 WebSocket 연결을 유지해야 하므로
  `frontend/lobby.html` 한 페이지 안에서 화면 전환(view switching) 방식으로 구현했습니다.
  페이지를 이동(location.href)하면 WebSocket 연결이 끊어져 턴/타이머 상태가 끊기기 때문입니다.
- 모든 게임 판정(턴 확인, 단어 존재 여부, 끝말 연결, 중복 단어, 제한시간)은 `backend/game.py`에서
  서버 측으로만 이루어지며 클라이언트는 상태를 표시하는 역할만 합니다.
- 사전 API 키가 설정되지 않으면 단어 제출 시 "사전 API 키가 설정되지 않았습니다" 오류가 반환됩니다.
