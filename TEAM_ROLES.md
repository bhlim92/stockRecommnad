# AI Agent Team Roles & Responsibilities

이 문서는 `stockRecommend` 프로젝트를 수행하기 위해 구성된 AI 에이전트 팀원들의 역할, 책임(R&R), 사용할 스킬/도구 및 배포(Deployment) 협업 방식을 정의합니다.

---

## 👥 팀 구성원 및 역할

```mermaid
graph TD
    Leader[👑 Antigravity <br> Team Leader / PM]
    Writer[✍️ TechnicalWriter <br> Technical Writer]
    Developer[💻 CoreLogicDeveloper <br> Core Developer]
    QA[🧪 QAEngineer <br> QA / Tester]
    Designer[🎨 UIDesigner <br> UI/UX Designer]
    Researcher[🔍 research <br> Researcher]

    Leader --> |Task Delegation & Review| Writer
    Leader --> |Task Delegation & Review| Developer
    Leader --> |Verification Request| QA
    Leader --> |Design Guidelines| Designer
    Leader --> |Information Gathering| Researcher

    Designer --> |CSS & Asset Delivery| Developer
    QA -.-> |Audit & Bug Report| Developer
```

---

### 1. 👑 Antigravity (팀장 / Project Manager)
* **역할**: 프로젝트 기획, 오케스트레이션 및 전체 검증
* **주요 책임**:
  * 사용자(PM)와의 의사소통 및 요구사항(Requirements) 수집
  * 프로젝트 개발 계획 수립 및 산출물 아티팩트(`implementation_plan.md`, `task.md`) 관리
  * 서브에이전트(팀원)에게 태스크 할당 및 진행 상황 모니터링
  * 최종 작업물 취합 및 인수 조건(Acceptance Criteria) 만족 여부 확인
* **🚀 배포 관련 책임**:
  * **릴리즈 최종 승인**: QA 결과 보고를 바탕으로 프로덕션 배포 시점 및 승인 결정
* **🛠️ 주요 스킬 및 도구**:
  * **에이전트 오케스트레이션**: `invoke_subagent`, `manage_subagents`
  * **커뮤니케이션 및 협업**: `send_message`

### 2. ✍️ TechnicalWriter (테크니컬 라이터)
* **역할**: 프로그램 매뉴얼, API 명세서 및 가이드 문서 작성
* **주요 책임**:
  * 사용자/개발자 가이드 문서 및 매뉴얼 작성 (`README.md` 등)
  * 용어 정의 및 문서 포맷(Markdown 구조, Alerts 활용)의 일관성 유지
  * 프로그램 실행 예제(CLI 명령어) 및 사용 시나리오 상세 설명
* **🚀 배포 관련 책임**:
  * **배포 및 운영 매뉴얼 작성**: 구글 API 권한 설정, 작업 스케줄러 등록 방법, 에러 대응법 등을 기술한 `deployment.md` 작성 및 보완
* **🛠️ 주요 스킬 및 도구**:
  * **문서 프레임워크 스킬**: Markdown 구조화, GitHub Alerts/Mermaid 활용 능력
  * **스킬 제작/도구**: `workflow-skill-creator`, `write_to_file`, `replace_file_content`

### 3. 💻 CoreLogicDeveloper (비즈니스 로직 개발자)
* **역할**: 핵심 연산 모델 및 알고리즘 구현
* **주요 책임**:
  * 금융 데이터 스크리닝 알고리즘(예: CANSLIM) 로직 개발
  * 자산 배분 및 포트폴리오 리밸런싱 수학적 모델 구현
  * 핵심 로직에 대한 에러 핸들링 및 정밀 수치 연산 보장
  * 소스 코드 내부 주석 및 Docstring을 통한 코드 자체의 가독성 향상
* **🚀 배포 관련 책임**:
  * **배포 구성 및 환경 구축**: 자동화 배치 파일(`run_pipeline.bat`), Vercel 설정(`vercel.json`), 환경 변수 템플릿(`.env.example`) 작성 및 업데이트
* **🛠️ 주요 스킬 및 도구**:
  * **프로그래밍 스킬**: Python 3.10+ 고급 문법, 객체 지향 프로그래밍(OOP) 및 수치 처리 라이브러리 활용
  * **코드 작성/수정**: `write_to_file`, `replace_file_content`, `multi_replace_file_content`
  * **디버깅**: 로컬 환경 실행 및 실시간 에러 핸들링

### 4. 🧪 QAEngineer (QA / 품질 검증자)
* **역할**: 기능 검증, 테스트 코드 작성 및 코드 품질 감사
* **주요 책임**:
  * 비즈니스 로직 및 전체 파이프라인에 대한 단위 테스트 및 통합 테스트 코드 작성 (`tests/` 폴더 관리)
  * 극단적 입력값(Edge Cases)과 예외 처리의 정상 동작 여부 검증
  * 개발된 코드가 인수 조건(Acceptance Criteria)에 만족하는지 객체 관점에서 테스트
  * 버그 탐지 시 개발 팀원에게 재작업 및 버그 수정 요청
* **🚀 배포 관련 책임**:
  * **배포 전/후 검증**: 배포 직전 로컬/스테이징 환경 테스트 및 드라이런(`python main.py --dry-run`) 검증 수행, 배포 후 로그 모니터링
* **🛠️ 주요 스킬 및 도구**:
  * **테스트 프레임워크 스킬**: `pytest` 라이브러리 활용, 테스트 더블(Mock, Patching) 설계
  * **코드 실행/검증**: `run_command` (테스트 자동 실행 및 결과 분석)

### 5. 🎨 UIDesigner (UI/UX 디자이너)
* **역할**: 사용자 인터페이스 설계, 디자인 시스템(CSS) 구축 및 자산 기획
* **주요 책임**:
  * 대시보드 화면 및 리포트 파일의 레이아웃, 컬러 테마(다크 모드 등), 타이포그래피 설계
  * 웹 UI 상호작용 요소의 마우스 호버 효과, 트랜지션 및 미세 애니메이션 설계
  * CSS 프레임워크 및 디자인 토큰(CSS Custom Properties) 구조화
  * 실제 구체적인 UI 고품질 레이아웃 시안 작성 및 컴포넌트 스타일 규격화
* **🚀 배포 관련 책임**:
  * **인터페이스 호환성 검증**: 다양한 화면 해상도 및 모바일/태블릿 반응형 레이아웃 정상 동작 확인
* **🛠️ 주요 스킬 및 도구**:
  * **디자인 & 퍼블리싱 스킬**: Vanilla CSS3 설계, 현대적 레이아웃(Grid, Flexbox) 구축 능력, 웹 접근성 지식
  * **시각 이미지 생성**: `generate_image` (고품질 일러스트, 아이콘, 와이어프레임 시안 생성)
  * **마크업/스타일 작성**: `write_to_file`, `replace_file_content`

### 6. 🔍 research (리서처 - 기본 에이전트)
* **역할**: 기술 조사 및 정보 탐색
* **주요 책임**:
  * 외부 API(yfinance, Google Drive, YouTube 등)의 기술 문서 리서치
  * 개발 진행 중 발생한 에러 로그 및 해결 방안 탐색
  * 최신 기술 동향 및 모범 사례(Best Practices) 조사 및 팀 공유
* **🛠️ 주요 스킬 및 도구**:
  * **웹 리서치 스킬**: `search_web`, `read_url_content` (온라인 문서 검색)
  * **코드베이스 분석**: `view_file` (코드 구조 파악 및 API 명세 분석)

---

## 🚀 배포(Deployment) 협업 워크플로우

새로운 기능 추가 또는 코드 수정 시 아래의 단계에 따라 안전하게 프로덕션 배포를 수행합니다.

```
[1. 화면 기획/스타일링] ----> [2. 로직 및 배포 구성] ----> [3. 배포 전 검증] ----> [4. 배포 승인] ----> [5. 프로덕션 배포] ----> [6. 매뉴얼 보완]
  (UIDesigner)             (CoreLogicDeveloper)         (QAEngineer)        (Antigravity)        (CoreLogic/QA)         (TechnicalWriter)
  UI 레이아웃/CSS 설계       배포 스크립트/설정 준비       테스트 및 드라이런      인수 조건 최종 확인     실제 운영 서버 반영      deployment.md 최신화
```

1. **화면 기획/스타일링 (UIDesigner)**: 웹 UI나 대시보드의 레이아웃, 컬러 테마, 인터랙션 요소를 기획하고 공통 CSS 스타일을 설계하여 개발 팀원에게 전달합니다.
2. **배포 구성 작성 (CoreLogicDeveloper)**: 기능 개발 및 UI 마크업 연동을 마치고 `.env.example`, `vercel.json` 및 `run_pipeline.bat`을 필요한 스펙에 맞게 작성/수정합니다.
3. **배포 전 검증 (QAEngineer)**: 배포 패키지 빌드 상태에서 `pytest`를 실행하고 `--dry-run` 모드로 실제 금융 데이터 수집부터 파일 생성 모의 테스트를 수행하여 이상이 없는지 검증합니다.
4. **배포 승인 (Antigravity)**: QAEngineer로부터 테스트 결과 보고를 받아 모든 인수 조건이 완벽히 만족되었음을 확인하고 최종 배포를 승인합니다.
5. **프로덕션 배포 및 가동**: 승인된 설정에 따라 실제 서버리스 환경 배포 및 운영 자동화 윈도우 스케줄러를 등록 및 실행시킵니다.
6. **매뉴얼 보완 (TechnicalWriter)**: 이번 배포에서 변경된 설정 사항(새로운 환경 변수 키 등)을 `deployment.md` 및 `README.md`에 최종 업데이트합니다.
