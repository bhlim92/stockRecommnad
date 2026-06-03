/* ==============================================================================
   Quantum Dashboard Core JavaScript - Stock Recommendation System
   ============================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // API Endpoints
    const API_STATUS = "/api/status";
    const API_RUN = "/api/run";
    const API_PORTFOLIO = "/api/portfolio";
    const API_REPORTS = "/api/reports";
    const API_PIPELINE_INGEST = "/api/pipeline/ingest";
    const API_PIPELINE_NEWS = "/api/pipeline/news";
    const API_PIPELINE_YOUTUBE = "/api/pipeline/youtube";
    const API_PIPELINE_RECOMMENDING = "/api/pipeline/recommending";
    const API_PIPELINE_UPLOAD = "/api/pipeline/upload";
    const API_PORTFOLIO_GSPREAD = "/api/portfolio/gspread";
    const API_PORTFOLIO_REBALANCE = "/api/portfolio/rebalance";

    // DOM Elements
    const serverStatusBadge = document.getElementById("server-status-badge");
    const btnRunPipeline = document.getElementById("btn-run-pipeline");
    const btnLoader = btnRunPipeline.querySelector(".btn-loader");
    const btnText = btnRunPipeline.querySelector(".btn-text");
    
    const currentStepText = document.getElementById("current-step-text");
    const progressPercentText = document.getElementById("progress-percent-text");
    const progressBarFill = document.getElementById("progress-bar-fill");
    const logTerminal = document.getElementById("log-terminal");
    
    // Gemini settings inputs
    const selectGeminiModel = document.getElementById("select-gemini-model");
    const inputGeminiApiKey = document.getElementById("input-gemini-api-key");
    const portfolioForm = document.getElementById("portfolio-form");

    // Reports list and viewer
    const reportsList = document.getElementById("reports-list");
    const reportViewerSection = document.getElementById("report-viewer-section");
    const viewingReportTitle = document.getElementById("viewing-report-title");
    const reportMdDisplay = document.getElementById("report-md-display");
    const btnCloseViewer = document.getElementById("btn-close-viewer");
    const holdingsList = document.getElementById("holdings-list");
    const btnGenerateRebalance = document.getElementById("btn-generate-rebalance");
    const rebalanceStrategyDisplay = document.getElementById("rebalance-strategy-display");

    // Step items map
    const stepItems = {
        "ingesting": document.getElementById("step-ingesting"),
        "news": document.getElementById("step-news"),
        "youtube": document.getElementById("step-youtube"),
        "recommending": document.getElementById("step-recommending"),
        "uploading": document.getElementById("step-uploading")
    };

    // DOM Elements for Caveats
    const caveatsPanel = document.getElementById("caveats-panel");
    const caveatsText = document.getElementById("caveats-text");

    // Caveats text for each phase
    const stepCaveats = {
        "idle": "자동 분석이 대기 중입니다. '지금 분석 시작하기' 버튼을 눌러 실시간 분석을 진행하십시오.",
        "ingesting": "<strong>[금융 데이터 수집]</strong> 한국은행 기준금리 및 한국 CPI는 FRED 프록시 ID를 통해 간접 조회하므로 실제 발표 시간과 수 시간의 오차가 존재할 수 있습니다.",
        "news": "<strong>[마켓 뉴스 분석]</strong> Yahoo Finance 및 Google News RSS 검색 결과를 4건씩 중복 필터링하여 주요 키워드로 요약합니다. 세부 원문 내용의 맥락이 일부 요약 과정에서 생략될 수 있으니 헤드라인 분석에 신중을 기하십시오.",
        "youtube": "<strong>[유튜브 전문가 요약]</strong> 최근 48시간 내의 영상만 분석하며 한글/영어 자막을 추출하여 핵심 키포인트를 LLM으로 정리합니다. 자막이 비공개인 경우 영상 설명글(Description)로 대체하므로 정보가 제한될 수 있습니다.",
        "screening": "<strong>[CANSLIM 조건 스크리닝]</strong><br>• C (QoQ EPS성장 > 20%)<br>• A (3년 EPS성장 > 20% & ROE > 17%)<br>• N (52주 최고가 대비 15% 이내)<br>• S (거래량 돌파 여부)<br>• L (상대강도 RS Rank > 70)<br>• M (시장 정배열 정합)",
        "rebalancing": "<strong>[포트폴리오 리밸런싱]</strong> 자산 배분 비중 괴리율(Drift)이 5% 이상 벌어졌을 때만 거래 제안(Rebalance Action)이 활성화됩니다. 미국 주식 자산은 현재 고시 환율을 연동해 원화(KRW)로 정밀 환산 처리됩니다.",
        "recommending": "<strong>[AI 추천 보고서 생성]</strong> 수집된 데이터셋(FRED 거시 지표, RSS 뉴스, 유튜브 요약, CANSLIM 점수)을 바탕으로 Google Gemini가 종합 리포트를 합성합니다. 최종 투자의 결정과 책임은 본인에게 있습니다.",
        "uploading": "<strong>[구글 드라이브 업로드]</strong> 생성된 마크다운 리포트는 Google Docs 문서로 변환되어 클라우드에 자동 업로드됩니다. 클라우드 권한 및 이메일 공유 상태를 확인하십시오.",
        "done": "<strong>[분석 완료]</strong> 일일 분석 파이프라인이 안전하게 완료되었습니다. 하단 보관소에서 보고서 내용을 조회하거나 구글 드라이브에서 문서를 확인하실 수 있습니다.",
        "failed": "<strong>[오류 발생]</strong> 분석 수행 중 예외가 발생했습니다. 실시간 터미널 로그 창을 확인하여 오류 메시지를 확인하고 조치를 취하십시오."
    };

    // Tracking states
    let isPipelineRunning = false;
    let statusInterval = null;
    let lastRenderedLogsCount = 0;
    let portfolioData = null;

    // Initialize UI
    if (inputGeminiApiKey) {
        inputGeminiApiKey.value = localStorage.getItem("gemini_api_key") || "";
    }
    loadPortfolio();
    loadReportsList();
    loadGspreadPortfolio();
    loadRebalanceStrategy();
    startPollingStatus();

    // Logout DOM element
    const btnLogout = document.getElementById("btn-logout");

    // Event Listeners
    btnRunPipeline.addEventListener("click", triggerPipelineRun);
    portfolioForm.addEventListener("submit", savePortfolio);
    btnCloseViewer.addEventListener("click", () => {
        reportViewerSection.classList.add("hidden");
    });
    if (btnGenerateRebalance) {
        btnGenerateRebalance.addEventListener("click", generateRebalanceStrategy);
    }
    if (btnLogout) {
        btnLogout.addEventListener("click", () => {
            fetch("/api/auth/logout", { method: "POST" })
                .then(() => {
                    window.location.href = "/login.html";
                })
                .catch(err => {
                    console.error("Logout failed:", err);
                    window.location.href = "/login.html";
                });
        });
    }

    // ==========================================================================
    // Core Functions
    // ==========================================================================

    function startPollingStatus() {
        if (statusInterval) clearInterval(statusInterval);
        
        // Initial fetch
        fetchStatus();
        
        // Set interval to poll every 1.5 seconds
        statusInterval = setInterval(fetchStatus, 1500);
    }

    async function fetchStatus() {
        if (isPipelineRunning) return; // Skip polling if client-side pipeline is running
        try {
            const response = await fetch(API_STATUS);
            if (isPipelineRunning) return; // Discard if pipeline was started in-between
            if (!response.ok) throw new Error("Status query failed");
            
            const data = await response.json();
            if (isPipelineRunning) return; // Discard if pipeline was started in-between
            updatePipelineUI(data);
        } catch (error) {
            if (isPipelineRunning) return;
            console.error("Error polling system status:", error);
        }
    }

    function updatePipelineUI(data) {
        const { status, progress, current_step, logs, error } = data;
        
        // 1. Update status badge
        serverStatusBadge.className = "status-badge";
        if (status === "idle") {
            serverStatusBadge.classList.add("status-idle");
            serverStatusBadge.innerText = "대기중 (IDLE)";
            isPipelineRunning = false;
        } else if (status === "done") {
            serverStatusBadge.classList.add("status-done");
            serverStatusBadge.innerText = "완료 (SUCCESS)";
            isPipelineRunning = false;
        } else if (status === "failed") {
            serverStatusBadge.classList.add("status-failed");
            serverStatusBadge.innerText = "실패 (FAILED)";
            isPipelineRunning = false;
        } else {
            serverStatusBadge.classList.add("status-running");
            serverStatusBadge.innerText = `진행중 (${status.toUpperCase()})`;
            isPipelineRunning = true;
        }

        // 2. Enable/disable button based on run state
        if (isPipelineRunning) {
            btnRunPipeline.disabled = true;
            btnLoader.classList.remove("hidden");
            btnText.innerText = "분석 진행 중...";
        } else {
            btnRunPipeline.disabled = false;
            btnLoader.classList.add("hidden");
            btnText.innerText = "지금 분석 시작하기 (ON-DEMAND)";
        }

        // 3. Update Progress Bar
        currentStepText.innerText = current_step;
        progressPercentText.innerText = `${progress}%`;
        progressBarFill.style.width = `${progress}%`;

        // 4. Highlight steps
        Object.keys(stepItems).forEach(key => {
            const item = stepItems[key];
            if (!item) return;

            item.className = "step-item";
            
            if (status === key) {
                item.classList.add("active");
            } else {
                const stepsSeq = ["ingesting", "news", "youtube", "recommending", "uploading", "done"];
                const currentIdx = stepsSeq.indexOf(status);
                const stepIdx = stepsSeq.indexOf(key);
                
                if (status === "done" || (currentIdx > stepIdx && currentIdx !== -1)) {
                    item.classList.add("completed");
                }
            }
        });

        // 4.5 Update Dynamic Caveats Display
        if (caveatsText && caveatsPanel) {
            const caveatContent = stepCaveats[status] || stepCaveats["idle"];
            caveatsText.innerHTML = caveatContent;
            
            if (status !== "idle" && status !== "done" && status !== "failed") {
                caveatsPanel.classList.add("highlight");
            } else {
                caveatsPanel.classList.remove("highlight");
            }
        }

        // 5. Append logs to terminal
        if (logs.length > lastRenderedLogsCount) {
            for (let i = lastRenderedLogsCount; i < logs.length; i++) {
                const line = logs[i];
                let type = "";
                if (line.includes("WARNING")) type = "warning-line";
                else if (line.includes("ERROR")) type = "error-line";
                else if (line.includes("SUCCESS") || line.includes("successfully")) type = "success-line";
                
                addTerminalLine(line, type);
            }
            lastRenderedLogsCount = logs.length;
        }

        if (status === "ingesting" && progress <= 5) {
            logTerminal.innerHTML = "";
            lastRenderedLogsCount = 0;
            addTerminalLine("[SYSTEM] 새로운 분석 파이프라인이 시작되었습니다.");
        }

        if (status === "done" && progress === 100 && lastRenderedLogsCount > 0) {
            loadReportsList();
            lastRenderedLogsCount = 0;
        }
    }

    function addTerminalLine(text, className = "") {
        const lineDiv = document.createElement("div");
        lineDiv.className = "terminal-line";
        if (className) lineDiv.classList.add(className);
        lineDiv.innerText = text;
        logTerminal.appendChild(lineDiv);
        logTerminal.scrollTop = logTerminal.scrollHeight;
    }

    // Client-side step UI updater
    function updateClientStepUI(status, progress, currentStepName) {
        serverStatusBadge.className = "status-badge status-running";
        serverStatusBadge.innerText = `진행중 (${status.toUpperCase()})`;
        
        btnRunPipeline.disabled = true;
        btnLoader.classList.remove("hidden");
        btnText.innerText = "분석 진행 중...";
        
        currentStepText.innerText = currentStepName;
        progressPercentText.innerText = `${progress}%`;
        progressBarFill.style.width = `${progress}%`;
        
        Object.keys(stepItems).forEach(key => {
            const item = stepItems[key];
            if (!item) return;
            item.className = "step-item";
            
            const stepsSeq = ["ingesting", "news", "youtube", "recommending", "uploading", "done"];
            const currentIdx = stepsSeq.indexOf(status);
            const stepIdx = stepsSeq.indexOf(key);
            
            if (status === key) {
                item.classList.add("active");
            } else if (currentIdx > stepIdx && currentIdx !== -1) {
                item.classList.add("completed");
            }
        });
        
        if (caveatsText && caveatsPanel) {
            caveatsText.innerHTML = stepCaveats[status] || stepCaveats["idle"];
            caveatsPanel.classList.add("highlight");
        }
    }

    function markPipelineDone() {
        serverStatusBadge.className = "status-badge status-done";
        serverStatusBadge.innerText = "완료 (SUCCESS)";
        btnRunPipeline.disabled = false;
        btnLoader.classList.add("hidden");
        btnText.innerText = "지금 분석 시작하기 (ON-DEMAND)";
        
        currentStepText.innerText = "분석 완료";
        progressPercentText.innerText = "100%";
        progressBarFill.style.width = "100%";
        
        Object.keys(stepItems).forEach(key => {
            const item = stepItems[key];
            if (item) {
                item.className = "step-item completed";
            }
        });
        
        if (caveatsText && caveatsPanel) {
            caveatsText.innerHTML = stepCaveats["done"];
            caveatsPanel.classList.remove("highlight");
        }
        
        isPipelineRunning = false;
        startPollingStatus();
    }

    function markPipelineFailed(errorMsg) {
        serverStatusBadge.className = "status-badge status-failed";
        serverStatusBadge.innerText = "실패 (FAILED)";
        btnRunPipeline.disabled = false;
        btnLoader.classList.add("hidden");
        btnText.innerText = "지금 분석 시작하기 (ON-DEMAND)";
        
        currentStepText.innerText = "오류 발생";
        
        if (caveatsText && caveatsPanel) {
            caveatsText.innerHTML = stepCaveats["failed"];
            caveatsPanel.classList.remove("highlight");
        }
        
        addTerminalLine(`[SYSTEM ERROR] 파이프라인 수행 실패: ${errorMsg}`, "error-line");
        isPipelineRunning = false;
        startPollingStatus();
    }

    function appendStepLogs(logs) {
        if (logs && Array.isArray(logs)) {
            logs.forEach(line => {
                let type = "";
                if (line.includes("WARNING")) type = "warning-line";
                else if (line.includes("ERROR")) type = "error-line";
                else if (line.includes("SUCCESS") || line.includes("successfully")) type = "success-line";
                addTerminalLine(line, type);
            });
        }
    }

    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function startCooldown(seconds, reason) {
        for (let i = seconds; i > 0; i--) {
            addTerminalLine(`[SYSTEM] ${reason}을 위해 대기 중... (${i}초 남음)`);
            await delay(1000);
        }
    }

    function saveReportToLocalStorage(filename, markdown) {
        let archive = [];
        try {
            archive = JSON.parse(localStorage.getItem("reports_archive")) || [];
        } catch (e) {
            archive = [];
        }
        archive = archive.filter(item => item.filename !== filename);
        archive.unshift({ filename, content: markdown });
        localStorage.setItem("reports_archive", JSON.stringify(archive));
    }

    async function triggerPipelineRun() {
        if (isPipelineRunning) return;
        
        const apiKey = inputGeminiApiKey ? inputGeminiApiKey.value.trim() : "";
        if (!apiKey) {
            alert("Gemini API Key를 입력해 주십시오! (설정 메뉴에서 입력 후 '설정 저장 및 반영' 클릭)");
            addTerminalLine("[SYSTEM ERROR] Gemini API Key가 제공되지 않아 분석을 시작할 수 없습니다.", "error-line");
            return;
        }

        localStorage.setItem("gemini_api_key", apiKey);

        isPipelineRunning = true;
        if (statusInterval) clearInterval(statusInterval);
        logTerminal.innerHTML = "";
        lastRenderedLogsCount = 0;
        
        Object.keys(stepItems).forEach(key => {
            if (stepItems[key]) stepItems[key].className = "step-item";
        });
        
        addTerminalLine("[SYSTEM] 클라이언트 사이드 순차 분석 파이프라인을 기동합니다...");
        
        let marketData = null;
        let newsData = null;
        let youtubeSummaries = null;
        let reportMarkdown = null;
        let gdocLink = "";

        const selectedModel = selectGeminiModel ? selectGeminiModel.value : "gemini-3.5-flash";

        try {
            // Step 1: Ingest
            updateClientStepUI("ingesting", 10, "금융 데이터 수집 중...");
            addTerminalLine("[SYSTEM] 1단계: 금융 데이터 수집 요청 중...");
            let res = await fetch(API_PIPELINE_INGEST, { method: "POST" });
            if (!res.ok) throw new Error(`1단계 수집 실패 (HTTP ${res.status})`);
            let data = await res.json();
            marketData = data.market_data;
            appendStepLogs(data.logs);
            
            // Step 2: News
            updateClientStepUI("news", 30, "마켓 뉴스 분석 중...");
            addTerminalLine("[SYSTEM] 2단계: 마켓 주요 뉴스 분석 요청 중...");
            res = await fetch(API_PIPELINE_NEWS, { method: "POST" });
            if (!res.ok) throw new Error(`2단계 뉴스 분석 실패 (HTTP ${res.status})`);
            data = await res.json();
            newsData = data.news;
            appendStepLogs(data.logs);
            
            // Wait 13 seconds (Gemini API Cooldown)
            updateClientStepUI("news", 45, "대기 지연 실행 중...");
            await startCooldown(13, "유튜브 분석 전 API 호출 속도 제한(Rate Limit)");

            // Step 3: YouTube Summarizer
            updateClientStepUI("youtube", 60, "유튜브 전문가 요약 중...");
            addTerminalLine("[SYSTEM] 3단계: 유튜브 전문가 요약 요청 중...");
            res = await fetch(API_PIPELINE_YOUTUBE, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ api_key: apiKey, model: selectedModel })
            });
            if (!res.ok) throw new Error(`3단계 유튜브 분석 실패 (HTTP ${res.status})`);
            data = await res.json();
            youtubeSummaries = data.youtube_summaries;
            appendStepLogs(data.logs);

            // Wait 13 seconds (Gemini API Cooldown)
            updateClientStepUI("youtube", 75, "대기 지연 실행 중...");
            await startCooldown(13, "보고서 합성 전 API 호출 속도 제한(Rate Limit)");

            // Step 4: Recommending
            updateClientStepUI("recommending", 85, "최종 추천 보고서 작성 중...");
            addTerminalLine("[SYSTEM] 4단계: AI 추천 보고서 생성 요청 중...");
            res = await fetch(API_PIPELINE_RECOMMENDING, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    api_key: apiKey,
                    model: selectedModel,
                    market_data: marketData,
                    news: newsData,
                    youtube_summaries: youtubeSummaries
                })
            });
            if (!res.ok) throw new Error(`4단계 보고서 생성 실패 (HTTP ${res.status})`);
            data = await res.json();
            reportMarkdown = data.report_markdown;
            appendStepLogs(data.logs);

            // Step 5: Upload
            updateClientStepUI("uploading", 95, "드라이브 업로드 및 저장 중...");
            addTerminalLine("[SYSTEM] 5단계: 아카이빙 및 업로드 요청 중...");
            res = await fetch(API_PIPELINE_UPLOAD, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ report_markdown: reportMarkdown })
            });
            if (!res.ok) throw new Error(`5단계 저장/업로드 실패 (HTTP ${res.status})`);
            data = await res.json();
            gdocLink = data.gdoc_link;
            appendStepLogs(data.logs);

            // Save report locally in browser
            const timestamp = new Date().toISOString().split('T')[0];
            const reportFilename = `${timestamp}_report.md`;
            saveReportToLocalStorage(reportFilename, reportMarkdown);

            // Mark completed
            markPipelineDone();
            addTerminalLine(`[SUCCESS] 전체 파이프라인 분석이 성공적으로 종료되었습니다!`, "success-line");
            if (gdocLink) {
                addTerminalLine(`[SUCCESS] 구글 드라이브 업로드 주소: ${gdocLink}`, "success-line");
            }
            
            // Reload reports list
            loadReportsList();
            
            // Render the newly generated report
            renderReportInViewer(reportFilename, reportMarkdown);

        } catch (error) {
            console.error("Pipeline run failed:", error);
            markPipelineFailed(error.message);
        }
    }

    // ==========================================================================
    // Portfolio Functions
    // ==========================================================================

    async function loadPortfolio() {
        const savedSettings = localStorage.getItem("portfolio_settings");
        if (savedSettings) {
            try {
                portfolioData = JSON.parse(savedSettings);
                populatePortfolioUI(portfolioData);
                addTerminalLine("[SYSTEM] 브라우저 로컬 저장소에서 설정을 불러왔습니다.");
                return;
            } catch (e) {
                console.error("Failed to parse local portfolio settings:", e);
            }
        }

        try {
            const response = await fetch(API_PORTFOLIO);
            if (!response.ok) throw new Error("Portfolio load failed");
            
            portfolioData = await response.json();
            localStorage.setItem("portfolio_settings", JSON.stringify(portfolioData));
            populatePortfolioUI(portfolioData);
        } catch (error) {
            console.error("Failed to load settings database:", error);
            addTerminalLine(`[SYSTEM ERROR] 설정을 불러오지 못했습니다: ${error.message}`, "error-line");
        }
    }

    function populatePortfolioUI(data) {
        if (selectGeminiModel && data) {
            selectGeminiModel.value = data.gemini_model || "gemini-3.5-flash";
        }
    }

    async function savePortfolio(e) {
        e.preventDefault();

        if (inputGeminiApiKey) {
            localStorage.setItem("gemini_api_key", inputGeminiApiKey.value.trim());
        }

        const selectedModel = selectGeminiModel ? selectGeminiModel.value : "gemini-3.5-flash";

        const updatedData = {
            ...(portfolioData || {}),
            gemini_model: selectedModel
        };

        portfolioData = updatedData;
        localStorage.setItem("portfolio_settings", JSON.stringify(updatedData));

        try {
            const response = await fetch(API_PORTFOLIO, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedData)
            });
            if (response.ok) {
                addTerminalLine("[SYSTEM] 모델 및 설정이 서버에도 저장되었습니다.", "success-line");
            }
        } catch (error) {
            console.warn("Backend settings save failed (normal for serverless/read-only fs):", error);
        }

        alert("Gemini AI 모델 및 API Key 설정이 브라우저 로컬 저장소에 저장되었습니다!");
        addTerminalLine("[SYSTEM] 설정이 브라우저에 저장되었습니다.", "success-line");
        loadPortfolio();
    }

    // ==========================================================================
    // Google Spreadsheet Portfolio holdings Functions
    // ==========================================================================

    async function loadGspreadPortfolio() {
        if (!holdingsList) return;
        
        try {
            const response = await fetch(API_PORTFOLIO_GSPREAD);
            if (!response.ok) throw new Error("API response not OK");
            
            const data = await response.json();
            await renderGspreadPortfolio(data);
        } catch (error) {
            console.error("Failed to load Google Sheet holdings:", error);
            holdingsList.innerHTML = `<tr><td colspan="11" class="loading-holdings" style="color: var(--accent-red);">구글 스프레드시트 보유 종목 데이터를 불러오지 못했습니다. 연동 설정을 확인하십시오.</td></tr>`;
        }
    }

    async function renderGspreadPortfolio(holdings) {
        if (!holdingsList) return;
        
        if (!holdings || holdings.length === 0) {
            holdingsList.innerHTML = `<tr><td colspan="11" class="loading-holdings">보유 중인 종목이 없습니다. (보유량 > 0 필터링)</td></tr>`;
            return;
        }

        // Fetch exchange rate asynchronously
        let exchangeRate = 1380.0;
        try {
            const erResp = await fetch("https://open.er-api.com/v6/latest/USD");
            if (erResp.ok) {
                const erData = await erResp.json();
                if (erData && erData.rates && erData.rates.KRW) {
                    exchangeRate = erData.rates.KRW;
                }
            }
        } catch (e) {
            console.warn("Failed to fetch exchange rate, using fallback 1380:", e);
        }

        // Calculate aggregates
        let totalInvested = 0.0;
        let totalEvaluation = 0.0;

        holdings.forEach(item => {
            const isKRW = item.ticker.toLowerCase().includes(".ks");
            const rate = isKRW ? 1.0 : exchangeRate;
            
            totalInvested += (item.total_purchase || 0.0) * rate;
            totalEvaluation += (item.total_evaluation || 0.0) * rate;
        });

        const totalProfit = totalEvaluation - totalInvested;
        const totalROI = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : 0.0;

        // Render summary bar
        const summaryBar = document.getElementById("portfolio-summary-bar");
        if (summaryBar) {
            const profitClass = totalProfit > 0 ? "pos-return" : (totalProfit < 0 ? "neg-return" : "");
            const profitSign = totalProfit > 0 ? "+" : "";
            const roiSign = totalROI > 0 ? "+" : "";
            
            summaryBar.innerHTML = `
                <div class="summary-card">
                    <span class="summary-label">총 투자금액</span>
                    <span class="summary-value">${Math.round(totalInvested).toLocaleString('ko-KR')}원</span>
                </div>
                <div class="summary-card profit-card ${profitClass}">
                    <span class="summary-label">총 평가손익</span>
                    <span class="summary-value">${profitSign}${Math.round(totalProfit).toLocaleString('ko-KR')}원</span>
                </div>
                <div class="summary-card profit-card ${profitClass}">
                    <span class="summary-label">총 수익률</span>
                    <span class="summary-value">${roiSign}${totalROI.toFixed(2)}%</span>
                </div>
            `;
        }

        holdingsList.innerHTML = "";
        
        // Helper to format currency
        function formatCurrency(val, isKRW) {
            if (isKRW) {
                return Math.round(val).toLocaleString('ko-KR') + "원";
            } else {
                return "$" + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            }
        }

        holdings.forEach(item => {
            const tr = document.createElement("tr");
            
            const isKRW = item.ticker.toLowerCase().includes(".ks");
            const rate = isKRW ? 1.0 : exchangeRate;
            const profitVal = parseFloat(item.profit) || 0.0;
            const isPositive = profitVal > 0;
            const isNegative = profitVal < 0;
            
            let returnClass = "";
            if (isPositive) returnClass = "pos-return";
            else if (isNegative) returnClass = "neg-return";
            
            // Calculate evaluation weight
            const stockEvalKRW = (item.total_evaluation || 0.0) * rate;
            const evalWeightPct = totalEvaluation > 0 ? (stockEvalKRW / totalEvaluation) * 100 : 0.0;
            const formattedEvalWeight = evalWeightPct.toFixed(2) + "%";
            
            // Format values
            const formattedQty = item.quantity.toLocaleString('en-US', { maximumFractionDigits: 4 });
            const formattedPrice = formatCurrency(item.current_price, isKRW);
            const formattedPurchase = formatCurrency(item.purchase_price, isKRW);
            const formattedTotalPurchase = formatCurrency(item.total_purchase, isKRW);
            const formattedTotalEval = formatCurrency(item.total_evaluation, isKRW);
            
            let formattedProfit = formatCurrency(Math.abs(profitVal), isKRW);
            if (isPositive) formattedProfit = "+" + formattedProfit;
            else if (isNegative) formattedProfit = "-" + formattedProfit;
            
            // Create cells
            tr.innerHTML = `
                <td class="ticker-cell">${item.ticker.toUpperCase()}</td>
                <td>${item.name}</td>
                <td class="number-cell">${formattedQty}</td>
                <td class="number-cell">${formattedPrice}</td>
                <td class="number-cell">${formattedPurchase}</td>
                <td class="number-cell">${formattedTotalPurchase}</td>
                <td class="number-cell">${formattedTotalEval}</td>
                <td class="number-cell ${returnClass}">${formattedProfit}</td>
                <td class="number-cell ${returnClass}">${item.roi}</td>
                <td class="number-cell" style="font-family: 'Orbitron', monospace;">${item.weight}</td>
                <td class="number-cell" style="font-family: 'Orbitron', monospace; color: var(--accent-cyan);">${formattedEvalWeight}</td>
            `;
            
            holdingsList.appendChild(tr);
        });
    }

    // ==========================================================================
    // Rebalance Strategy Functions
    // ==========================================================================

    async function loadRebalanceStrategy() {
        if (!rebalanceStrategyDisplay) return;
        try {
            const response = await fetch(API_PORTFOLIO_REBALANCE);
            if (response.ok) {
                const data = await response.json();
                if (data && data.content) {
                    rebalanceStrategyDisplay.innerHTML = parseMarkdown(data.content);
                }
            }
        } catch (error) {
            console.warn("Failed to load cached rebalance strategy:", error);
        }
    }

    async function generateRebalanceStrategy() {
        const apiKey = inputGeminiApiKey ? inputGeminiApiKey.value.trim() : "";
        if (!apiKey) {
            alert("Gemini API Key를 입력해 주십시오! (설정 메뉴에서 입력 후 '설정 저장 및 반영' 클릭)");
            return;
        }
        
        const selectedModel = selectGeminiModel ? selectGeminiModel.value : "gemini-3.5-flash";
        
        const btnTextEl = btnGenerateRebalance.querySelector(".btn-text");
        const btnLoaderEl = btnGenerateRebalance.querySelector(".btn-loader");
        
        btnGenerateRebalance.disabled = true;
        if (btnLoaderEl) btnLoaderEl.classList.remove("hidden");
        if (btnTextEl) btnTextEl.innerText = "리밸런싱 전략 생성 중...";
        rebalanceStrategyDisplay.innerHTML = `<div class="loading-holdings" style="text-align: center; padding: 30px 0;">
            <span class="btn-loader" style="display: inline-block; margin-bottom: 10px;"></span><br>
            구글 스프레드시트 포트폴리오와 추천 종목을 기반으로 AI 리밸런싱 전략을 분석 및 합성하고 있습니다. 잠시만 기다려 주십시오... (약 15-20초 소요)
        </div>`;
        
        try {
            const response = await fetch(API_PORTFOLIO_REBALANCE, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ api_key: apiKey, model: selectedModel })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || errorData.error || "API call failed");
            }
            
            const data = await response.json();
            rebalanceStrategyDisplay.innerHTML = parseMarkdown(data.content);
            addTerminalLine("[SUCCESS] AI 포트폴리오 리밸런싱 전략이 성공적으로 생성되었습니다.", "success-line");
            if (data.gdoc_link) {
                addTerminalLine(`[SUCCESS] 리밸런싱 구글 드라이브 업로드 주소: ${data.gdoc_link}`, "success-line");
            }
            loadReportsList();
        } catch (error) {
            console.error("Failed to generate rebalance strategy:", error);
            rebalanceStrategyDisplay.innerHTML = `<div class="loading-holdings" style="color: var(--accent-red); text-align: center; padding: 30px 0;">
                리밸런싱 전략을 생성하지 못했습니다: ${error.message}
            </div>`;
            addTerminalLine(`[SYSTEM ERROR] 리밸런싱 전략 생성 실패: ${error.message}`, "error-line");
        } finally {
            btnGenerateRebalance.disabled = false;
            if (btnLoaderEl) btnLoaderEl.classList.add("hidden");
            if (btnTextEl) btnTextEl.innerText = "AI 리밸런싱 전략 생성 및 업데이트";
        }
    }

    // ==========================================================================
    // Report Archiver Functions
    // ==========================================================================

    async function loadReportsList() {
        let serverReports = [];
        try {
            const response = await fetch(API_REPORTS);
            if (response.ok) {
                serverReports = await response.json();
            }
        } catch (error) {
            console.warn("Could not load reports from server:", error);
        }
        
        let localReports = [];
        try {
            localReports = JSON.parse(localStorage.getItem("reports_archive")) || [];
        } catch (e) {
            localReports = [];
        }
        
        const allReportsMap = new Map();
        
        serverReports.forEach(filename => {
            allReportsMap.set(filename, { filename, isLocalOnly: false });
        });
        
        localReports.forEach(item => {
            allReportsMap.set(item.filename, { filename: item.filename, isLocalOnly: true, content: item.content });
        });
        
        const sortedReports = Array.from(allReportsMap.values()).sort((a, b) => b.filename.localeCompare(a.filename));
        renderReportsList(sortedReports);
    }

    function getReportDisplayName(filename) {
        // 1. Check for rebalance strategy
        const rebalanceMatch = filename.match(/^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})_rebalance/i);
        if (rebalanceMatch) {
            return `⚖️ 리밸런싱 전략 (${rebalanceMatch[1]} ${rebalanceMatch[2]}:${rebalanceMatch[3]}:${rebalanceMatch[4]})`;
        }
        
        // 2. Check for general report
        const reportMatch = filename.match(/^(\d{4}-\d{2}-\d{2})_report/i);
        if (reportMatch) {
            return `📈 추천 보고서 (${reportMatch[1]})`;
        }
        
        // Fallback
        if (filename.toLowerCase().includes("rebalance") || filename.toLowerCase().includes("strategy")) {
            return `⚖️ 리밸런싱 전략 (${filename.replace(".md", "")})`;
        }
        return `📈 보고서 (${filename.replace(".md", "")})`;
    }

    function renderReportsList(reports) {
        reportsList.innerHTML = "";
        
        if (reports.length === 0) {
            reportsList.innerHTML = '<li class="empty-item">보관된 보고서가 없습니다.</li>';
            return;
        }

        reports.forEach(item => {
            const li = document.createElement("li");
            
            const nameSpan = document.createElement("span");
            nameSpan.className = "report-file-name";
            nameSpan.innerText = getReportDisplayName(item.filename);
            
            const btnView = document.createElement("button");
            btnView.className = "btn-report-view";
            btnView.innerText = "보기";
            btnView.addEventListener("click", (e) => {
                e.stopPropagation();
                viewReport(item);
            });

            li.appendChild(nameSpan);
            li.appendChild(btnView);
            li.addEventListener("click", () => viewReport(item));
            
            reportsList.appendChild(li);
        });
    }

    async function viewReport(item) {
        if (item.isLocalOnly && item.content) {
            renderReportInViewer(item.filename, item.content);
        } else {
            try {
                const response = await fetch(`${API_REPORTS}/${item.filename}`);
                if (!response.ok) throw new Error("Failed to retrieve report content");
                
                const data = await response.json();
                renderReportInViewer(data.filename, data.content);
            } catch (error) {
                console.error("Failed to view report:", error);
                alert(`보고서를 로드하지 못했습니다: ${error.message}`);
            }
        }
    }

    function renderReportInViewer(filename, content) {
        viewingReportTitle.innerText = `${filename.replace(".md", "")} 투자 종목 추천 리포트`;
        reportMdDisplay.innerHTML = parseMarkdown(content);
        reportViewerSection.classList.remove("hidden");
        reportViewerSection.scrollIntoView({ behavior: "smooth" });
    }

    // A lightweight, offline-ready Regex Markdown Parser
    function parseMarkdown(md) {
        let html = md;
        
        // Escape HTML
        html = html
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Headers
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
        
        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Bullets
        html = html.replace(/^\* (.*$)/gim, '<li>$1</li>');
        html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
        
        // Wrap lists (greedy check)
        html = html.replace(/((?:<li>.*<\/li>\s*)+)/g, '<ul>$1</ul>');
        
        // Tables
        let lines = html.split('\n');
        let inTable = false;
        let tableHtml = "";
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].trim();
            if (line.startsWith('|') && line.endsWith('|')) {
                if (!inTable) {
                    inTable = true;
                    tableHtml = "<table>";
                }
                
                // Skip separator lines like |---|---|
                if (line.includes('---')) {
                    lines[i] = "";
                    continue;
                }
                
                let cells = line.split('|').slice(1, -1);
                let tag = (tableHtml === "<table>") ? "th" : "td";
                tableHtml += "<tr>" + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + "</tr>";
                lines[i] = "";
            } else {
                if (inTable) {
                    inTable = false;
                    tableHtml += "</table>";
                    lines[i-1] += "\n" + tableHtml;
                    tableHtml = "";
                }
            }
        }
        
        html = lines.filter(l => l !== "").join('\n');
        
        // Convert double returns to paragraph breaks, single returns to line breaks
        html = html.replace(/\n\n/g, '<p></p>');
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }
});
