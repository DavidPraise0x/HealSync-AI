// HealSync Console Frontend Controller

document.addEventListener("DOMContentLoaded", () => {
    // API base URL
    const API_URL = "";

    // DOM Elements
    const incidentList = document.getElementById("incident-list");
    const incidentCount = document.getElementById("incident-count");
    
    // Stats Elements
    const statTotal = document.getElementById("stat-total");
    const statActive = document.getElementById("stat-active");
    const statResolved = document.getElementById("stat-resolved");
    const statRate = document.getElementById("stat-rate");
    
    // Console View Elements
    const defaultState = document.getElementById("console-default-state");
    const activeState = document.getElementById("console-active-state");
    const consoleTitle = document.getElementById("console-incident-title");
    const consoleDesc = document.getElementById("console-incident-desc");
    const consoleSeverity = document.getElementById("console-incident-severity");
    const consoleTime = document.getElementById("console-incident-time");
    const terminalOutput = document.getElementById("terminal-output");
    const selectedStatus = document.getElementById("selected-incident-status");

    // Modal Simulation Elements
    const triggerBtn = document.getElementById("trigger-incident-btn");
    const modalBackdrop = document.getElementById("incident-modal");
    const closeBtn = document.getElementById("modal-close-btn");
    const scenarioCards = document.querySelectorAll(".scenario-card");

    // Runbooks Elements
    const runbooksMenuBtn = document.getElementById("runbooks-menu-btn");
    const runbookModal = document.getElementById("runbook-modal");
    const runbookCloseBtn = document.getElementById("runbook-close-btn");
    const runbookGridContent = document.getElementById("runbook-grid-content");

    // State Variables
    let currentEventSource = null;
    let selectedIncidentId = null;

    // 1. Fetch Stats & Refresh Metrics
    async function fetchStats() {
        try {
            const res = await fetch(`${API_URL}/api/stats`);
            const stats = await res.json();
            
            statTotal.textContent = stats.total;
            statActive.textContent = stats.active;
            statResolved.textContent = stats.resolved;
            
            // Calculate success rate
            const totalResolvedOrFailed = stats.resolved + stats.failed;
            if (totalResolvedOrFailed > 0) {
                const rate = Math.round((stats.resolved / totalResolvedOrFailed) * 100);
                statRate.textContent = `${rate}%`;
            } else {
                statRate.textContent = "100%";
            }
        } catch (err) {
            console.error("Failed to fetch stats:", err);
        }
    }

    // 2. Fetch Incident Stream List
    async function fetchIncidents(autoSelectNewestId = null) {
        try {
            const res = await fetch(`${API_URL}/api/incidents`);
            const incidents = await res.json();
            
            incidentCount.textContent = `${incidents.length} Tickets`;
            
            if (incidents.length === 0) {
                incidentList.innerHTML = `
                    <div class="empty-state">
                        <p>No incidents recorded yet.</p>
                    </div>
                `;
                return;
            }

            incidentList.innerHTML = "";
            incidents.forEach(inc => {
                const card = document.createElement("div");
                card.className = `incident-card ${selectedIncidentId === inc.id ? 'active-selection' : ''}`;
                card.dataset.id = inc.id;
                
                // Formulate status badge
                const statusClass = `badge-status-${inc.status}`;
                const severityClass = `badge-severity-${inc.severity.toLowerCase()}`;
                
                card.innerHTML = `
                    <div class="card-top">
                        <h4>${inc.title}</h4>
                        <span class="badge ${severityClass}">${inc.severity}</span>
                    </div>
                    <div class="card-bottom">
                        <span class="badge ${statusClass}">${inc.status}</span>
                        <span>${formatDate(inc.created_at)}</span>
                    </div>
                `;
                
                card.addEventListener("click", () => {
                    selectIncident(inc.id);
                });
                
                incidentList.appendChild(card);
            });

            // Auto-select if requested
            if (autoSelectNewestId) {
                selectIncident(autoSelectNewestId);
            }
        } catch (err) {
            console.error("Failed to load incidents:", err);
        }
    }

    // 3. Select and Open Incident Console
    async function selectIncident(id) {
        selectedIncidentId = id;
        
        // Highlight active card
        document.querySelectorAll(".incident-card").forEach(card => {
            card.classList.toggle("active-selection", parseInt(card.dataset.id) === id);
        });

        // Close existing SSE stream
        if (currentEventSource) {
            currentEventSource.close();
        }

        try {
            const res = await fetch(`${API_URL}/api/incidents/${id}`);
            const incident = await res.json();
            
            // Toggle panels visibility
            defaultState.classList.add("hide");
            activeState.classList.remove("hide");
            
            // Populate fields
            consoleTitle.textContent = incident.title;
            consoleDesc.textContent = incident.description;
            consoleSeverity.textContent = incident.severity.toUpperCase();
            consoleSeverity.className = `severity-tag ${incident.severity.toLowerCase()}`;
            consoleTime.textContent = formatDate(incident.created_at);
            
            selectedStatus.textContent = incident.status;
            selectedStatus.className = `badge badge-status-${incident.status}`;

            // Reset terminal screen
            terminalOutput.innerHTML = "";
            appendTerminalLine("SYSTEM", "Connecting to agent event stream...", "cmd");

            // Open Server-Sent Events (SSE) Stream
            currentEventSource = new EventSource(`${API_URL}/api/stream/${id}`);
            
            currentEventSource.onmessage = (event) => {
                const logMsg = event.data;
                
                if (logMsg === "[COMPLETE]") {
                    appendTerminalLine("SYSTEM", "Connection closed. Healing procedure finalized.", "cmd");
                    currentEventSource.close();
                    currentEventSource = null;
                    
                    // Refresh status badges and metrics
                    fetchStats();
                    fetchIncidents();
                    
                    // Update status label
                    updateStatusLabel(id);
                    return;
                }
                
                // Color output based on prefix
                let lineClass = "stdout";
                if (logMsg.startsWith("Executing Step") || logMsg.startsWith("Running command") || logMsg.startsWith("Ingested new alert") || logMsg.startsWith("Querying CockroachDB")) {
                    lineClass = "cmd";
                } else if (logMsg.includes("CRITICAL") || logMsg.includes("failed")) {
                    lineClass = "error";
                }
                
                appendTerminalLine("AGENT", logMsg, lineClass);
            };

            currentEventSource.onerror = () => {
                appendTerminalLine("SYSTEM", "Stream connection interrupted. Agent is running in background.", "error");
                currentEventSource.close();
                currentEventSource = null;
            };

        } catch (err) {
            console.error("Failed to load incident detail:", err);
        }
    }

    async function updateStatusLabel(id) {
        try {
            const res = await fetch(`${API_URL}/api/incidents/${id}`);
            const incident = await res.json();
            selectedStatus.textContent = incident.status;
            selectedStatus.className = `badge badge-status-${incident.status}`;
        } catch (err) {
            console.color("Error updating status label:", err);
        }
    }

    function appendTerminalLine(source, text, lineClass) {
        const line = document.createElement("div");
        line.className = `terminal-line ${lineClass}`;
        
        // Strip out leading log prefixes if desired, or output directly
        line.textContent = text;
        terminalOutput.appendChild(line);
        
        // Auto scroll
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }

    // 4. Incident trigger simulation modal events
    triggerBtn.addEventListener("click", () => {
        modalBackdrop.classList.remove("hide");
    });

    closeBtn.addEventListener("click", () => {
        modalBackdrop.classList.add("hide");
    });

    modalBackdrop.addEventListener("click", (e) => {
        if (e.target === modalBackdrop) {
            modalBackdrop.classList.add("hide");
        }
    });

    // Handle scenario cards clicks
    scenarioCards.forEach(card => {
        card.addEventListener("click", async () => {
            const scenario = card.dataset.scenario;
            let payload = {};
            
            if (scenario === "cpu") {
                payload = {
                    title: "AWS ECS CPU Overload Spike",
                    description: "Average CPU utilization exceeded 95% on application tasks.",
                    symptoms: "High latency on payment requests, timeout errors in logs.",
                    severity: "critical"
                };
            } else if (scenario === "db") {
                payload = {
                    title: "CockroachDB Connection Timeout Outage",
                    description: "Client driver threw connection refused error on port 26257.",
                    symptoms: "API return code 500, db pool exhausted, retry failure.",
                    severity: "high"
                };
            } else if (scenario === "s3") {
                payload = {
                    title: "AWS S3 Upload Authorization Denied",
                    description: "IAM Role lacks putObject permission on target media bucket.",
                    symptoms: "AccessDenied exception on resource uploads, HTTP 403.",
                    severity: "medium"
                };
            } else if (scenario === "lambda") {
                payload = {
                    title: "AWS Lambda Out of Memory Core Outage",
                    description: "Lambda task terminated with code 137 memory limits exceeded.",
                    symptoms: "Transaction processing loop failed unexpectedly.",
                    severity: "high"
                };
            }

            try {
                // Post incident
                const res = await fetch(`${API_URL}/api/incidents`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();
                
                // Hide modal
                modalBackdrop.classList.add("hide");
                
                // Refresh list and select the newest one
                await fetchStats();
                await fetchIncidents(data.incident_id);
                
            } catch (err) {
                console.error("Failed to trigger incident:", err);
            }
        });
    });

    // 5. Runbook Library events
    runbooksMenuBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        runbookModal.classList.remove("hide");
        
        try {
            const res = await fetch(`${API_URL}/api/runbooks`);
            const runbooks = await res.json();
            
            runbookGridContent.innerHTML = "";
            runbooks.forEach(rb => {
                const card = document.createElement("div");
                card.className = "runbook-card";
                
                // Format steps
                const steps = JSON.parse(rb.remediation_steps);
                let stepsHTML = "";
                steps.forEach(st => {
                    stepsHTML += `
                        <div class="runbook-step-line">
                            <span>Step ${st.step}:</span> ${st.action}<br>
                            <code>$ ${st.command}</code>
                        </div>
                    `;
                });
                
                card.innerHTML = `
                    <h4>${rb.name}</h4>
                    <p>${rb.description}</p>
                    <div class="runbook-steps-list">
                        ${stepsHTML}
                    </div>
                `;
                
                runbookGridContent.appendChild(card);
            });
        } catch (err) {
            console.error("Failed to fetch runbooks:", err);
            runbookGridContent.innerHTML = `<p>Error loading runbooks: ${err.message}</p>`;
        }
    });

    runbookCloseBtn.addEventListener("click", () => {
        runbookModal.classList.add("hide");
    });

    runbookModal.addEventListener("click", (e) => {
        if (e.target === runbookModal) {
            runbookModal.classList.add("hide");
        }
    });

    // Helper: Format ISO timestamp to readable date
    function formatDate(isoStr) {
        if (!isoStr) return "";
        // SQLite output can be 'YYYY-MM-DD HH:MM:SS', javascript Date parses it.
        // Replace space with T to make it ISO compliant for safari/firefox
        const tStr = isoStr.replace(" ", "T");
        const date = new Date(tStr);
        if (isNaN(date.getTime())) return isoStr; // Fallback
        
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " | " + date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    // Init Page Load
    fetchStats();
    fetchIncidents();
});
