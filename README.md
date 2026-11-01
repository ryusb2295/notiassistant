# 공지비서

영남대 학교·사업단·학과 공지를 첨부까지 읽고, 나에게 해당되는 것만 알려주는 서비스입니다.
제2회 SW중심대학 융합그룹 창업 해커톤 소노벨 7조 프로토타입입니다.

공지 수집 → 첨부 분석 → 맞춤 피드 → 일정·마감 알림의 4단계와 신청서 초안, 행정실 공지 게시가 동작합니다.

행정실 화면은 `backend/.env`의 `ADMIN_USERNAMES`에 적은 아이디로 로그인하면 내 정보 탭에 나타납니다. 쉼표로 여러 개를 적을 수 있습니다.

## 실행

Windows 기준입니다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env   # OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 입력
.venv\Scripts\python -m app.pipeline --limit 15
```

```powershell
cd frontend
npm install
npm run build
```

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

브라우저에서 http://127.0.0.1:8000 을 엽니다. 화면을 고칠 때는 `frontend`에서 `npm run dev`를 쓰고 http://localhost:5173 을 엽니다.

테스트는 `backend`에서 `.venv\Scripts\python -m pytest`로 실행합니다.

## 배포

Docker로 프론트 빌드와 서버를 한 컨테이너에 묶습니다. 데이터는 `noti-data` 볼륨에 남습니다.

```bash
docker compose up -d --build
```

- HTTPS 프록시 뒤에 둘 때는 `COOKIE_SECURE=1`로 실행합니다. HTTP에서는 로그인이 유지되지 않습니다.
- 공지는 60분마다 수집합니다. 처음 실행 직후에는 `docker compose exec app python -m app.pipeline --limit 15`로 채웁니다.
- 상태는 `/api/health`에서 확인합니다.
- 서버 1대, 프로세스 1개 기준입니다. SQLite를 쓰므로 여러 대로 늘리려면 DB 교체가 필요합니다.
- `requirements.lock`은 `pip freeze`로 고정한 버전입니다. 의존성을 바꾸면 다시 생성합니다.

## 구조

| 경로 | 역할 |
|---|---|
| `backend/app/crawler.py` | 게시판 목록·본문 파싱, robots.txt 확인 |
| `backend/app/parsers.py` | HWP, HWPX, PDF, XLSX 텍스트 추출 |
| `backend/app/analyzer.py` | GPT·Claude 구조화 추출, 실패 시 규칙 분석 |
| `backend/app/matcher.py` | 추출 조건과 학생 프로필 비교 |
| `backend/app/pipeline.py` | 수집부터 저장까지의 흐름 |
| `backend/app/applications.py` | 신청서 초안. 학생 정보는 LLM으로 보내지 않음 |
| `backend/app/admin.py` | 공문 분석, 게시, 대상 학생 알림 |
| `backend/app/schedule.py` | 구글 캘린더 링크, ICS, 마감 알림 |
| `backend/app/main.py` | API, 빌드된 프론트 서빙 |
| `frontend/src/views` | 가입, 추천, 피드, 상세, 일정, 게시판, 내 정보 화면 |

분석은 AI가, 해당 여부 판정은 코드가 맡습니다. LLM은 공지에서 대상과 마감을 뽑고, `matcher.py`가 학과·학년과 비교합니다.

## 알아둘 제약

- **API 키:** 키가 없으면 규칙 분석으로 동작합니다. 키를 넣고 다시 수집하면 규칙 분석으로 남은 공지만 AI로 다시 분석하고, 저장한 일정은 유지됩니다.
- **호출 한도:** 무료 키 한도에 걸린 공지는 규칙 분석으로 저장됩니다. 한도가 풀린 뒤 다시 수집하면 이어서 분석합니다.
- **GPT·호환 서비스의 PDF:** 추출한 텍스트만 보내므로 글자가 없는 스캔 PDF는 읽지 못합니다. Claude는 PDF 원본을 읽습니다.
- **개인정보:** 파일명에 명단, 합격자 등이 있는 첨부는 내려받지 않고 LLM으로 보내지 않습니다. 파일명 기준이라 본문이나 다른 첨부에 적힌 이름까지 막지는 못합니다.
- **본문 이미지:** `/_attach` 경로는 학교 `robots.txt`가 모든 봇에 금지하므로 읽지 않습니다. 첨부로 올라온 이미지는 읽습니다. 상세 화면에 읽지 않은 이미지 수를 표시합니다.
- **AI 봇 차단:** 학교 `robots.txt`는 ClaudeBot, GPTBot 등을 전면 금지합니다. 이 크롤러는 별도 User-Agent로 `*` 규칙을 따르지만, 수집한 내용을 LLM으로 보내므로 실서비스 전에 학교 측 허락을 받아야 합니다.
- **구글 캘린더:** OAuth 연동 대신 일정별 추가 링크와 ICS 파일을 제공합니다.
- **알림:** 앱 안의 알림함입니다. 휴대폰 푸시는 없습니다.
- **로그인:** 아이디·비밀번호 방식이고 세션은 30일 유지됩니다. 비밀번호는 scrypt 해시로만 저장하고, 5회 실패하면 15분 잠깁니다. 이메일을 받지 않아 비밀번호 찾기는 없습니다.
- **SW중심대학 참여 학과:** `config.py`의 목록은 2026년도 하반기 마일리지 신청 공지 기준입니다.
