# Antigravity 2.0 Telegram Bot 가이드 (Telegram Control Guide)

이 가이드는 모바일 텔레그램을 통해 **Antigravity 2.0 AI 코딩 에이전트**에게 명령을 내리고 로컬 시스템 상태를 모니터링할 수 있도록 텔레그램 봇을 생성하고 연동하는 절차를 설명합니다.

---

## 1. 텔레그램 봇 생성 및 설정 (Prerequisites)

### 1단계: Bot Token 발급받기
1. 텔레그램 앱에서 **@BotFather**를 검색하여 대화를 시작합니다.
2. `/newbot` 명령어를 전송합니다.
3. 봇의 이름(Name)과 사용자명(Username, 반드시 `_bot`으로 끝나야 함)을 입력합니다.
4. 생성이 완료되면 제공되는 **HTTP API Token** (예: `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`)을 복사합니다.

### 2단계: 본인의 Chat ID 확인하기
안전한 전용 채널을 만들기 위해 본인의 텔레그램 계정 ID(Chat ID)를 조회하여 등록해야 합니다. (타인 접근 불가)
1. 텔레그램 앱에서 **@userinfobot** 또는 **@GetIDBot**을 검색하여 대화를 시작합니다.
2. `/start`를 전송하면 본인의 **ID 숫자가 출력**됩니다. (예: `987654321`)
3. 이 숫자를 복사해 둡니다.

---

## 2. 환경 변수 구성 (`.env` 파일 수정)

프로젝트 루트 디렉토리의 [`.env`](file:///c:/Users/samsung/proj/stockRecommnad/.env) 파일을 열고, 맨 아래에 복사해 둔 값을 입력합니다:

```env
# --- TELEGRAM BOT CONFIGURATION ---
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321
```

---

## 3. 텔레그램 봇 실행 및 테스트

### 로컬 PC에서 봇 구동하기
터미널을 열고 가상환경 파이썬 인터프리터를 이용해 봇 데몬을 실행합니다:

```bash
# Windows PowerShell 기준
c:\Users\samsung\proj\stockRecommnad\venv\Scripts\python.exe c:\Users\samsung\proj\antigravity_bot.py
```

실행 시 봇이 가동되며 등록된 텔레그램으로 아래와 같은 알림이 전송됩니다.
> 🤖 **Antigravity 2.0 Agent Bot**이 가동되었습니다!
> /help 명령어로 지원되는 명령어를 확인해 보세요.

---

## 4. 텔레그램 명령어 사용법

봇 프로필에 진입하여 대화창에 명령어를 입력해 모바일로 제어합니다.

* **`/system`** : 로컬 PC의 CPU 사용량, 사용 중인 메모리 리소스, 디스크 여유 공간을 실시간 조회합니다.
* **`/cmd <명령어>`** : 로컬 터미널의 cmd 명령을 직접 실행합니다.
  - 예: `/cmd git status` (git 상태 확인)
  - 예: `/cmd venv\Scripts\python.exe -m pytest tests/` (로컬 테스트 강제 실행)
* **`/chat <작업지시>`** : **AI 코딩 에이전트(Antigravity 2.0)**에게 자연어로 작업을 지시합니다.
  - 에이전트는 파일 읽기(`read_file`), 쓰기(`write_file`), 폴더 내용 보기(`list_dir`), 터미널 실행(`run_command`) 도구를 자유자재로 사용하여 로컬 코드를 고치거나 테스트를 실행합니다.
  - 예: `/chat tests/test_scoring.py 파일 읽어줘`
  - 예: `/chat scoring.py에 주석을 한글로 보완하고 테스트 돌려서 결과 알려줘`
* **자연어 대화** : `/chat` 없이 텍스트를 바로 입력하면, 일반적인 AI 대화 및 태스크 연산을 수행합니다.
