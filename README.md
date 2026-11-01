# 공지비서

제2회 SW중심대학 융합그룹 창업 해커톤 소노벨 7조 프로젝트입니다.

영남대 공지는 영대소식, 사업단, 학과 게시판에 나뉘어 올라옵니다. 대상이나 마감이 본문이 아니라 HWP, PDF 첨부에만 적혀 있는 경우도 많아서 일일이 열어봐야 내 얘기인지 알 수 있습니다. 공지비서는 이 공지들을 첨부까지 읽어서 내 학과, 학년에 해당되는 것만 골라 보여줍니다.

## 할 수 있는 것

- 구독한 게시판의 공지를 모아서 AI로 요약합니다.
- 학과, 학년, 관심사를 보고 나에게 해당되는 공지만 피드에 띄웁니다.
- 마감일을 일정에 넣고, 마감 전날과 당일에 앱 안에서 알려줍니다.
- 첨부파일을 앱 안에서 미리 보고 내려받을 수 있습니다.
- 신청서 초안을 내 정보로 채워줍니다. 제출은 학교 시스템에서 직접 해야 합니다.
- 행정실 담당자가 공문을 올리면 내용을 정리해 주고, 게시하면 대상 학생에게만 알림이 갑니다.

## 어떻게 판정하나

AI는 공지에서 대상, 마감, 혜택을 뽑는 일만 합니다. 내 공지가 맞는지는 뽑아낸 조건을 코드로 내 프로필과 비교해서 정합니다. AI가 판정까지 하면 왜 그렇게 나왔는지 설명하기 어렵고, 학생 정보를 외부로 보내야 하기 때문입니다. 이름, 학번 같은 프로필 정보는 AI로 보내지 않습니다.

흐름은 이렇습니다.

```text
게시판 수집 → 첨부 읽기 → AI로 조건 추출 → 프로필과 비교 → 피드, 일정, 알림
```

## 기술 스택

프론트는 Vue, 백엔드는 FastAPI, DB는 SQLite입니다. AI는 OpenAI 호환 API나 Claude를 쓸 수 있고, 지금은 Gemini 무료 키로 돌리고 있습니다. HWP, HWPX는 직접 파싱합니다.

## 실행 방법

Windows PowerShell 기준입니다. Python 3.12, Node 24에서 돌렸습니다.

**1. 백엔드 설치**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

**2. `backend/.env`에 AI 키 넣기**

Gemini 무료 키를 쓸 때는 아래처럼 적으면 됩니다. 키는 [Google AI Studio](https://aistudio.google.com/apikey)에서 받습니다. 변수 이름은 OPENAI로 시작하지만 Gemini 키를 넣는 자리가 맞습니다.

```text
OPENAI_API_KEY=여기에_키
OPENAI_MODEL=gemini-3.5-flash-lite
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
CRAWL_DELAY_SEC=5
ADMIN_USERNAMES=관리자로_쓸_아이디
```

키가 없어도 실행은 됩니다. 대신 정규식으로만 분석해서 요약 품질이 많이 떨어집니다.

**3. 프론트 빌드**

```powershell
cd ..\frontend
npm install
npm run build
```

**4. 서버 실행**

```powershell
cd ..\backend
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

브라우저로 [127.0.0.1:8000](http://127.0.0.1:8000)에 들어가서 회원가입합니다. `ADMIN_USERNAMES`에 적은 아이디로 가입하면 내 정보 탭에 행정실 메뉴가 나옵니다. 담당자 표시는 `STAFF_USERNAMES`에 적으면 됩니다.

**5. 공지 수집**

서버를 켜둔 채로 터미널을 하나 더 열어서 실행합니다. 처음에는 공지가 없으니 꼭 한 번 돌려야 합니다.

```powershell
cd backend
.venv\Scripts\python -m app.pipeline --limit 12
```

학과 게시판은 구독자가 있는 곳만 수집합니다. 그래서 회원가입을 먼저 하고 수집하는 게 좋습니다. 수집 간격이 5초라서 몇 분 걸립니다.

화면을 고칠 때는 `frontend`에서 `npm run dev`를 켜고 [localhost:5173](http://localhost:5173)에서 보면 바로 반영됩니다. 테스트는 `backend`에서 `.venv\Scripts\python -m pytest`로 돌립니다.

## 휴대폰으로 시연하기

서버를 따로 빌리지 않고 Cloudflare Tunnel로 공개 주소를 만들어서 시연합니다.

```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
```

터미널에 나오는 `trycloudflare.com` 주소로 접속하면 됩니다. 아이폰은 Safari 공유 버튼에서 홈 화면에 추가, 갤럭시는 Chrome 메뉴에서 앱 설치를 누르면 주소창 없이 앱처럼 열립니다.

PC가 꺼지면 접속도 끊기고, 터널을 다시 켜면 주소가 바뀌어서 홈 화면 아이콘도 다시 추가해야 합니다. 시연 때는 터널을 켠 채로 두세요.

## 서버에 올릴 때

Docker 설정은 넣어뒀지만 아직 실제로 빌드해 보지는 못했습니다.

```bash
docker compose up -d --build
docker compose exec app python -m app.pipeline --limit 15
```

HTTPS 뒤에 둘 때는 `COOKIE_SECURE=1`로 실행해야 합니다. SQLite를 쓰기 때문에 서버 한 대 기준입니다. 무료 호스팅처럼 재시작할 때 디스크가 지워지는 곳에 올리면 계정과 일정이 사라집니다.

## 폴더 구조

```text
backend/app/
  crawler.py       게시판 수집
  parsers.py       첨부파일 읽기
  analyzer.py      AI 분석
  matcher.py       내 공지인지 판정
  pipeline.py      수집부터 저장까지
  applications.py  신청서 초안
  admin.py         행정실 기능
  schedule.py      일정, 마감 알림
  main.py          API
backend/scripts/discover_boards.py  학과 게시판 주소 찾기
frontend/src/views/                 화면
```

## 아직 부족한 점

- 휴대폰 푸시 알림이 없습니다. 앱을 열어야 알림을 볼 수 있습니다.
- 구글 캘린더는 자동 연동이 아니라 일정마다 추가 링크를 누르거나 ICS 파일을 받는 방식입니다.
- 학과 게시판은 83곳을 연결했습니다. 국어국문학과, 건설시스템공학과, 신소재공학부 등 학부 공지 게시판을 찾지 못한 곳은 빠져 있습니다.
- 본문에 삽입된 이미지는 학교 `robots.txt`가 막고 있어서 읽지 않습니다. 첨부로 올라온 이미지는 읽습니다.
- GPT나 Gemini를 쓰면 PDF는 글자만 뽑아서 보내기 때문에 스캔본은 읽지 못합니다.
- 파일명에 명단, 합격자, 성적 같은 말이 있으면 AI로 보내지 않지만, 본문에 적힌 이름까지 걸러내지는 못합니다.
- 이메일을 받지 않아서 비밀번호 찾기가 없습니다.

## 실제로 서비스하려면

지금은 팀과 교수님 시연까지만 생각하고 만들었습니다. 학교 `robots.txt`가 AI 봇을 막고 있어서 실제로 운영하려면 학교 허락을 먼저 받아야 합니다. 무료 AI 키는 입력이 제품 개선에 쓰일 수 있어서 유료 요금제로 바꿔야 합니다. 개인정보 안내문도 담당자 검토가 필요합니다.
