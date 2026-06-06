# 📊 퀀트 AI 종목 스크리너 점수 산출 공식 및 정의

본 문서는 주식 분석 및 리밸런싱 시스템의 핵심 엔진인 **종목 스크리너**에서 개별 종목을 평가하기 위해 사용하는 **진입 점수 (Entry Score)**와 **평가 점수 (Evaluation Score)**의 산출 공식 및 세부 정의를 설명합니다.

---

## 1. 진입 점수 (Entry Score)

진입 점수는 **기술적 지표(Technical Analysis)**를 기반으로 현재 주식이 매수 또는 진입하기에 적합한 추세인지 분석하는 지표입니다.

### 📌 정의 및 아키텍처적 위치
* **점수 범위**: 0점 ~ 100점
* **현재 구현 상태**: 현재 시스템의 `QuantScorer` 모듈에서는 `entry_score`를 `0`점(기본값)으로 설정해 둔 **플레이스홀더(Placeholder) 상태**입니다. 추후 정교한 기술적 지표 연동 엔진 확장을 위해 아키텍처적으로 자리가 예약되어 있습니다.
* **단기 이평선 상태 분석 (`entry_details`)**:
  점수와 별개로, 주가 데이터가 존재할 경우 단기 이동평균선(SMA 5일)과 중기 이동평균선(SMA 20일)의 관계를 분석하여 대시보드 및 상세 사유란에 노출합니다.
  * **단기 우상향**: $SMA_{5일} > SMA_{20일}$ 인 경우
  * **단기 조정세**: $SMA_{5일} \le SMA_{20일}$ 인 경우
  * **데이터 대기**: 차트 데이터가 부족할 경우 `"기술 지표 데이터 대기"`로 표시됩니다.

### 📈 추세 판정 공식 및 논리 (이유 작성기 기준)
실제 텍스트 기반 사유 산출 시에는 다음과 같은 기준으로 기술적 추세를 진단합니다:

| 점수 구간 | 기술적 추세 판정 설명 |
| :---: | :--- |
| **80점 이상** | 이평선 전반 정배열의 완벽한 우상향 추세 |
| **60점 ~ 79점** | 단기 골든크로스 및 추세 상승 전환국면 |
| **40점 ~ 59점** | 주요 지지선 지지 및 횡보 안정 흐름 |
| **40점 미만** | 추세 하락 및 역배열 조정 압력 |

> [!NOTE]
> **거래량 수급 진단**: 
> 당일 거래량이 최근 20일 평균 거래량의 1.3배를 초과할 경우, 위 판정 문구 뒤에 **" 및 거래량 수급 급증"**이라는 내용이 자동으로 결합합니다.

---

## 2. 평가 점수 (Evaluation Score)

평가 점수는 기업의 **기본적 재무 가치(Fundamental Analysis)**와 성장성, 시장 합의(Consensus), 그리고 CANSLIM 통과 여부를 종합하여 점수화한 복합 평가 지표입니다.

### 📌 정의 및 아키텍처적 위치
* **점수 범위**: 0점 ~ 100점 (최대 만점 100점)
* **산출 방식**: 5개의 핵심 재무 지표를 각각의 기준에 따라 점수화한 뒤 가중 합산(Weighted Sum)하여 산출합니다.

### 🧮 평가 점수 가중치 배분표

| 평가 항목 | 배정 만점 | 세부 지표 명칭 (yfinance API) | 핵심 평가 목적 |
| :--- | :---: | :--- | :--- |
| **① PER 평가** | **30점** | `trailingPE` (TTM 주가수익비율) | 밸류에이션 저평가 수준 측정 |
| **② PEG 평가** | **20점** | `pegRatio` (주가이익성장비율) | 이익 성장 대비 주가 저평가 측정 |
| **③ EPS 성장성** | **20점** | `trailingEps` / `forwardEps` | 향후 12개월간의 EPS 성장 모멘텀 |
| **④ 목표가 여력** | **15점** | `targetMeanPrice` (애널리스트 합의가) | 시장 컨센서스 대비 가격 상승 여력 |
| **⑤ CANSLIM 필터** | **15점** | `passed_screener` (CANSLIM 통과여부) | 모멘텀 투자 대가(윌리엄 오닐) 조건 부합 여부 |
| **합계** | **100점** | - | - |

---

## 📐 상세 산출 공식 및 코드 로직

### ① PER (Price-to-Earnings Ratio) 점수 (최대 30점)
* **공식**:
  $$PER \le 10 \implies 30\text{점}$$
  $$10 < PER < 30 \implies \text{int}\left(30 \times \frac{30 - PER}{20}\right)\text{점}$$
  $$PER \ge 30 \text{ 또는 적자}(PER < 0) \implies 0\text{점}$$
* **의미**: 업계 표준인 PER 10 이하를 최상의 저평가 구간으로 판정하고, 30을 초과하면 밸류에이션 매력이 없다고 판단하여 0점 처리합니다.

### ② PEG (Price-to-Earnings-to-Growth Ratio) 점수 (최대 20점)
* **공식**:
  $$PEG \le 1 \implies 20\text{점}$$
  $$1 < PEG < 2 \implies \text{int}\left(20 \times \frac{2 - PEG}{1}\right)\text{점}$$
  $$PEG \ge 2 \text{ 또는 데이터 없음} \implies 0\text{점}$$
* **의미**: 피터 린치의 성장주 평가 기법을 반영하여, 이익 성장률 대비 주가가 싼 구간(PEG 1 이하)에 만점을 부여하고 2를 초과하면 가산점을 배제합니다.

### ③ EPS 성장성 점수 (최대 20점)
* **성장률 계산식 ($G$ %)**:
  $$G = \left(\frac{\text{Forward EPS} - \text{Trailing EPS}}{|\text{Trailing EPS}|}\right) \times 100$$
* **공식**:
  $$G \ge 20\% \implies 20\text{점}$$
  $$0\% < G < 20\% \implies \text{int}\left(20 \times \frac{G}{20}\right)\text{점}$$
  $$G \le 0\% \text{ 또는 분모가 0} \implies 0\text{점}$$
* **의미**: 직전 12개월 실적 대비 향후 12개월 예측 실적의 성장 모멘텀이 20%를 넘는 고성장 기업에 만점을 부여합니다.

### ④ 애널리스트 목표가 대비 상승 여력 점수 (최대 15점)
* **상승 여력 계산식 ($U$ %)**:
  $$U = \left(\frac{\text{Target Mean Price} - \text{Current Price}}{\text{Current Price}}\right) \times 100$$
* **공식**:
  $$U \ge 20\% \implies 15\text{점}$$
  $$0\% < U < 20\% \implies \text{int}\left(15 \times \frac{U}{20}\right)\text{점}$$
  $$U \le 0\% \text{ 또는 정보 없음} \implies 0\text{점}$$
* **의미**: 다수 증권사 애널리스트가 평가한 평균 목표가 대비 현재 주가가 20% 이상 저평가되어 강한 상승 에너지를 지닌 종목에 점수를 차등 부여합니다.

### ⑤ CANSLIM 필터 점수 (최대 15점)
* **공식**:
  $$\text{CANSLIM 조건 전체 만족 (Passed)} \implies 15\text{점}$$
  $$\text{미충족 조건이 1개라도 있는 경우} \implies 0\text{점}$$
* **의미**: 모멘텀 및 성장주 선별의 글로벌 표준인 윌리엄 오닐의 CANSLIM 7대 조건을 완벽히 만족한 우량 모멘텀 주식에 15점의 가산점을 제공합니다.

---

## 🔍 부록: CANSLIM 7대 조건의 세부 통과 기준

평가 점수 중 **⑤ CANSLIM 필터**의 통과 판정(`passed_screener = True`)을 받기 위해서는 아래의 7가지 규칙을 모두 만족해야 합니다.

1. **C (Current Quarterly Earnings)**: 최근 분기 EPS YoY 성장률이 **20% 이상**일 것.
2. **A (Annual Earnings Increases)**: 최근 3개년 연속 연간 EPS 성장률이 각각 **20% 이상**이고, 최신 분기 자기자본이익률(ROE)이 **17% 이상**일 것.
3. **N (New Product, Service, or High)**: 현재 주가가 52주 신고가 가격 대비 **15% 이내(신고가 영역 인근)**에 위치해 있을 것.
4. **S (Supply and Demand)**: 당일 주가가 2% 이상 상승 시, 당일 거래량이 **50일 평균 거래량을 초과**하여 매수세 유입이 확인될 것.
5. **L (Leader or Laggard)**: 전종목 대비 상대강도 점수인 Relative Strength(RS) 백분위수 순위(Percentile Rank)가 **70 이상**일 것.
6. **I (Institutional Sponsorship)**: 기관 투자자 지분율이 **30% 이상**일 것 (yfinance `institutionalPercentHeld` 지표 기준).
7. **M (Market Direction)**: 시장의 추세 추종을 위해 주식 소속 시장(미국: S&P500, 한국: KOSPI)의 종합 지수가 50일 이평선 위에 있고, 50일 이평선이 200일 이평선 위에 위치하는 **정배열 상승 추세** 상태일 것.
