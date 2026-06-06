# 프론트엔드-백엔드 연동 분석 및 QA 리포트

본 문서는 백엔드 단독 테스트(pytest 및 로컬 Python 클라이언트) 환경에서는 스크리너가 정상 동작함에도 불구하고, 프론트엔드(Vercel 등)와 연동하여 실서비스 배포 시 오동작하거나 연동에 실패하는 원인을 QA 관점에서 분석하고 기록한 보고서입니다.

---

## 🔍 핵심 원인 분석 요약

분석 결과, 백엔드 단독 실행 환경과 프론트엔드 배포 환경의 **아키텍처적 차이** 및 **보안 쿠키 정책**, 그리고 **백엔드 API 중복 정의 버그**가 결합하여 문제가 발생한 것으로 진단되었습니다.

| 번호 | 문제 유형 | 현상 | 원인 |
| :---: | :--- | :--- | :--- |
| **1** | **서버리스 아키텍처 제약 (Vercel)** | 백엔드 테스트에서는 스크리닝이 잘 수행되나, Vercel 웹 페이지에서 가동 시 진행률이 `0%`에서 멈추거나 갱신되지 않음 | Vercel은 **서버리스(Serverless) 함수**로 구동되므로 지속적인 **백그라운드 스레드(Persistent Background Thread)**를 지원하지 않음. 응답 반환 후 컨테이너가 즉시 동결(Freeze)됨 |
| **2** | **교차 출처 쿠키 누락 (CORS / SameSite)** | 로컬 웹 서버에서는 API 호출이 성공하나, 배포된 Vercel 웹에서 Cafe24 API를 호출하면 `401 Unauthorized` 발생 | 세션 쿠키인 `auth_token`이 `samesite="lax"`, `secure=False`로 설정되어 있어 브라우저가 다른 도메인(Vercel -> Cafe24)으로 요청을 보낼 때 쿠키 전송을 차단함 |
| **3** | **API 엔드포인트 중복 정의 버그** | `api_key` 유무 체크 로직이 동작하지 않거나 테스트 클라이언트와 실환경의 응답 규격이 충돌함 | `app/web_server.py` 내에 `/api/screener/start` 라우트가 두 번 중복 정의되어 있어 첫 번째 정의가 두 번째 정의를 가려버리는 데드 코드(Dead Code) 발생 |

---

## 🛠️ 상세 진단 내용

### 1. Vercel 서버리스 환경의 백그라운드 스레드 유실 문제
* **진단**: 
  백엔드 코드 `app/screener.py`는 `threading.Thread`를 활용하여 백그라운드에서 전체 종목의 가격 데이터를 수집하고 연산합니다.
  ```python
  # app/screener.py
  self._thread = threading.Thread(target=self._run_screener_worker, args=(market,))
  self._thread.daemon = True
  self._thread.start()
  return True # 즉시 HTTP 200 응답 반환
  ```
* **오동작 이유**:
  - **로컬/Cafe24**: 상주형(Persistent) 프로세스(Uvicorn/Gunicorn)가 구동 중이므로 스레드가 메인 프로세스 위에서 지속 작동하며 500개 종목을 끝까지 연산합니다.
  - **Vercel**: 서버리스 아키텍처는 요청이 올 때만 컨테이너가 깨어납니다. 프론트엔드가 `/api/screener/start`를 호출하여 백그라운드 스레드가 뜨고 곧바로 "스캔 시작됨" 응답을 리턴하면, Vercel 인프라는 **해당 요청이 종료된 것으로 간주하고 컨테이너의 CPU 리소스를 차단(Freeze/Destroy)**합니다.
  - 이로 인해 스레드가 시세 데이터를 채 다운로드하기도 전에 중단되며, 이후 프론트엔드가 `/api/screener/status`로 폴링하더라도 계속 `0%` 상태이거나 새 인스턴스로 부팅되어 `idle`로 리셋됩니다.

### 2. 세션 쿠키 SameSite 및 Secure 설정에 의한 401 차단
* **진단**: 
  로그인 성공 시 백엔드는 브라우저에 `auth_token` 쿠키를 심어 다음 API 요청들의 권한을 확인합니다.
  ```python
  # app/web_server.py
  response.set_cookie(
      key="auth_token",
      value=session_token,
      httponly=True,
      samesite="lax",
      secure=False
  )
  ```
* **오동작 이유**:
  - 프론트엔드(`https://stock-recommnad.vercel.app`)와 백엔드 API(`https://bhlim123.cafe24.com`)가 서로 다른 도메인으로 분리되어 서비스될 때, 브라우저는 이를 **Cross-Site 요청**으로 취급합니다.
  - `samesite="lax"` 정책 상 서드파티 컨텍스트에서의 API 요청에는 쿠키가 포함되지 않으며, HTTPS 환경이 아닐 경우 `secure=False` 설정도 쿠키 유실의 원인이 됩니다.
  - 결국 프론트엔드 연동 상태에서 `/api/screener/start` 호출 시 쿠키가 전송되지 않아 권한 부족(`401 Unauthorized`) 에러가 발생합니다.

### 3. FastAPI 엔드포인트 중복(Duplicate) 선언 버그
* **진단**:
  `app/web_server.py` 파일 내에 동일한 경로의 라우터가 중복 정의되어 있습니다.
  - **첫 번째 선언 (563라인)**:
    ```python
    @app.post("/api/screener/start")
    def screener_start(req: dict) -> JSONResponse:
        # req.get("market") 만 활용하여 가동
    ```
  - **두 번째 선언 (1115라인)**:
    ```python
    @app.post("/api/screener/start")
    def start_screener(req: ScreenerRequest) -> JSONResponse:
        # Pydantic 모델 검증 및 api_key 체크
    ```
* **오동작 이유**:
  - FastAPI(Starlette)의 라우팅 테이블은 등록 순서대로 매칭을 수행합니다. 563라인이 먼저 정의되어 있으므로 모든 `/api/screener/start` POST 요청은 첫 번째 함수로 전달됩니다.
  - 따라서 프론트엔드나 테스트 코드가 `ScreenerRequest` 포맷으로 API Key 등을 전달하더라도 백엔드에서는 그냥 일반 딕셔너리로 받아 처리하며, 두 번째에 정의된 필수 검증 로직은 완전히 우회됩니다.

---

## 📝 해결 및 개선 방향 제안

1. **상주형 서버 기반의 API 고정 (Recommended)**
   * 스크리너처럼 시간이 수십 초 이상 소요되는 장기 실행(Long-running) 백그라운드 작업은 Vercel Serverless가 아닌 **Cafe24(VPS) 등 상주형 서버의 백엔드 주소로 통일**하여 프론트엔드가 해당 API 주소를 바라보도록 설정해야 합니다.
2. **세션 쿠키 SameSite/Secure 규격 수정**
   * 교차 도메인 간의 인증을 위해 쿠키의 SameSite 속성을 `None`으로 변경하고 `secure=True`로 설정하거나, 쿠키 대신 HTTP Header의 `Authorization: Bearer <Token>` 방식을 채택하는 것이 안전합니다.
3. **백엔드 데드 코드 정리**
   * `app/web_server.py`에서 중복 등록된 `/api/screener/start` 및 `/api/screener/status`, `/api/screener/stop` 엔드포인트를 하나로 통합하고 사용하지 않는 중복 코드는 삭제해야 합니다.
