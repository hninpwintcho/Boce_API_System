const API_KEY_KEY = "boce_proxy_api_key";

async function fetchWithAuth(url, options = {}) {
    let apiKey = localStorage.getItem(API_KEY_KEY);
    if (!apiKey) {
        apiKey = prompt("Please enter your X-API-KEY for access:");
        if (apiKey) localStorage.setItem(API_KEY_KEY, apiKey);
    }
    
    options.headers = options.headers || {};
    options.headers["X-API-KEY"] = apiKey;
    
    const response = await fetch(url, options);
    if (response.status === 403 || response.status === 401) {
        localStorage.removeItem(API_KEY_KEY);
        alert("Invalid API Key. Please refresh and try again.");
    }
    return response;
}

async function refreshData() {
    try {
        // 1. Fetch Balance
        const balanceResp = await fetchWithAuth("/api/balance");
        const balanceData = await balanceResp.json();
        const bal = balanceData.data || {};
        document.getElementById("balance-value").innerText = 
            `${bal.balance || 0} CNY (${bal.point || 0} pts)`;

        // 2. Fetch History
        const historyResp = await fetchWithAuth("/api/history?limit=100");
        const historyData = await historyResp.json();
        const items = historyData.items || [];
        
        const body = document.getElementById("history-body");
        body.innerHTML = "";
        
        let totalAvail = 0;
        let completedCount = 0;
        let processingCount = 0;

        items.forEach(item => {
            if (item.status === "completed") completedCount++;
            if (item.status === "processing" || item.status === "pending") processingCount++;

            const row = document.createElement("tr");
            row.innerHTML = `
                <td><small>${item.id}</small></td>
                <td>${item.url}</td>
                <td><span class="badge">${item.provider}</span></td>
                <td><span class="status-${item.status}">${item.status}</span></td>
                <td>${item.availability || 'N/A'}%</td>
                <td><small>${new Date(item.timestamp).toLocaleString()}</small></td>
            `;
            body.appendChild(row);
        });

        document.getElementById("active-tasks").innerText = processingCount;
        document.getElementById("total-audited").innerText = items.length;
        
    } catch (err) {
        console.error("Failed to refresh dashboard:", err);
    }
}

// Initial load
refreshData();
// Auto-refresh every 30s
setInterval(refreshData, 30000);
