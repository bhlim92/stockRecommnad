# 🎨 UI/UX 디자인 설계 문서 (UI/UX Design Specification)

이 문서는 `stockRecommend` 프로젝트의 웹 UI/UX를 개발자 중심에서 사용자 중심으로 전면 재정의하여 설계한 명세서와 그 개정 이력(Revision History)을 담고 있습니다.

---

## 📅 개정 이력 (Revision History)

| 버전 (Version) | 개정 일자 (Date) | 개정 내용 (Description) | 작업자 (Author) | 승인자 (Approver) |
| :--- | :--- | :--- | :--- | :--- |
| **v1.0** | 2026-06-06 | - 1차 사용자 관점 UI 레이아웃 설계 수립<br>- 로그 터미널 및 설정 창 모달화 레이아웃 분리<br>- Chart.js 시각화 차트(도넛, 바) 연동 기획<br>- 리밸런싱 지시서 카드 뷰 1차 설계 및 시안 도출 | `UIDesigner` | `Antigravity (팀장)` |
| **v1.1** | 2026-06-06 | - 팀원 피드백 수렴 반영 2차 개선안 수립 및 최종 승인<br>- Chart.js 네온 그라디언트(Neon Gradient) 적용<br>- 리밸런싱 카드 액션별 정렬 및 네온 테두리 글로우 효과 추가<br>- 비동기 통신 시각 개선용 스켈레톤 로더(Skeleton Loader) 설계<br>- API Cooldown 대기 중 카운트다운 타이머 게이지 바 신설<br>- 모달 닫기 편의성 개선(배경 클릭 및 Esc 키 바인딩)<br>- 프리미엄 인앱 경고 배너 및 가이드라인 가이드 추가 | `Antigravity` | `Antigravity (팀장)` |

---

## 👥 디자인 협업 R&R (Roles & Responsibilities)

* **Antigravity (팀장/PM):** 사용자 요구사항 조율, UI/UX 최종 개선 설계 및 변경안 승인, 검증 지시.
* **UIDesigner (UI/UX 디자이너):** HSL 네온 테마 스타일 토큰 설계, 마크업 레이아웃, 모바일 반응형 뷰 설계 및 퍼블리싱.
* **CoreLogicDeveloper (개발자):** 모달 동작 바인딩, Chart.js 라이브러리 연동 및 그라디언트 렌더링 스크립트 작성, 실시간 Cooldown 타이머 제어.
* **QAEngineer (품질 검증):** 모달 닫기 편의성 테스트, 멀티 해상도 브라우저 호환성 검사, 단위/통합 테스트 코드 확인.
* **TechnicalWriter (라이터):** 화면 가이드라인 및 설명문 인라인 마크업 작성, `README.md` 가이드 최신화.

---

## 🎨 UI/UX 디자인 시스템 및 사양 (Design Token & Specs)

### 1. 프리미엄 컬러 테마 (Sleek Dark Mode)
- **배경색 (Background):** Sleek Dark HSL 테마 (`#0a0d14` ~ `#0c0f24` 리니어 그라디언트 적용)
- **카드 및 모달 (Glassmorphism):** 반투명 카드 (`rgba(18, 22, 33, 0.75)`), 블러 처리 (`backdrop-filter: blur(16px);`) 및 미세 흰색 테두리 (`rgba(255, 255, 255, 0.07)`) 적용.
- **포인트 네온 액센트:**
  - `var(--accent-cyan)`: `#00d2ff` (메인 가이드 및 수치 강조)
  - `var(--accent-blue)`: `#0066ff` (보조 블루 및 진행률 바)
  - `var(--accent-green)`: `#00ff66` (매수/수익률 양수 신호)
  - `var(--accent-red)`: `#ff0055` (매도/손실률 음수 신호)

### 2. 시각 차트 컴포넌트 (Chart.js Visualization)
포트폴리오 비중 비교 및 드리프트 판단을 위해 **Chart.js** 2D Canvas를 연동하며, 단조로운 단색 대신 세련된 **Canvas Linear Gradient**를 주입합니다.
- **자산 비중 도넛 차트:** 현금(Slate), 주식(Neon Blue), 채권(Purple-Blue), 원자재(Amber) 그라디언트.
- **현재 vs 목표 비교 바 차트:** 현재 비중(Cyan Gradient), 목표 비중(Glassy Grey Gradient)을 대조하여 가독성 강화.

### 3. 리밸런싱 카드 뷰 (Rebalancing Action Cards)
- 마크다운 규격 테이블을 실시간 파싱하여 반응형 카드로 동적 변환합니다.
- **정렬 우선순위:** 사용자가 즉시 체득할 수 있도록 **BUY(매수) ➡️ SELL(매도) ➡️ HOLD(유지)** 정렬 순서 적용.
- **그림자(Glow):** BUY 카드는 네온 그린 글로우(`rgba(0, 255, 102, 0.25)`), SELL 카드는 네온 레드 글로우(`rgba(255, 0, 85, 0.25)`) 스타일이 미세하게 호버 시 발산됩니다.

### 4. API Cooldown 타이머 UI
- yfinance / Gemini API의 Rate Limit 방지를 위해 13초간 대기하는 시점에 컨트롤 패널 내부에 실시간 카운트다운 타이머 및 주황색 수평 게이지가 나타납니다.
- 게이지 너비가 100%에서 0%로 매초 linear 애니메이션 처리되어 대기 상태를 피드백합니다.

### 5. 스켈레톤 로더 (Skeleton Loading)
- 비동기 구글 드라이브/yfinance 로딩 시 투박한 로딩 글씨 대신 깜빡이는 펄스 애니메이션(`.skeleton-placeholder`) 행과 카드들을 그려 레이아웃 흔들림(Layout Shift)을 방지합니다.

---

## 📂 관련 리소스 및 디자인 시안

- **최종 완성 화면 디자인 시안:** [dashboard_ui_mockup_1780732605334.png](file:///C:/Users/samsung/.gemini/antigravity/brain/a1fcc791-5aaa-493e-aefa-0b3c8e8d1237/dashboard_ui_mockup_1780732605334.png)
- **디자인 스타일시트:** [style.css](file:///c:/Users/samsung/proj/stockRecommnad/app/static/style.css)
- **웹 대시보드 마크업:** [index.html](file:///c:/Users/samsung/proj/stockRecommnad/app/static/index.html)
- **프론트엔드 연동 스크립트:** [app.js](file:///c:/Users/samsung/proj/stockRecommnad/app/static/app.js)
