---
title: HealSync AI
emoji: 🪳
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# HealSync AI 🪳 - Autonomous DevOps & Infrastructure Self-Healing Agent


**HealSync AI** is an autonomous, self-healing DevOps and infrastructure agent designed for the **CockroachDB × AWS Hackathon: Build with Agentic Memory**. 

The application monitors infrastructure configurations and serverless executions, using **CockroachDB** as its persistent system of record. When an incident or outage is detected, the agent queries CockroachDB using **Distributed Vector Indexing (RAG)** to match the alert symptoms to historical incident runbooks, executes diagnostic commands, and runs automated self-healing procedures on AWS resources.

---

## 🏗️ Architecture & Component Design

HealSync AI is structured as a decoupled web application:
1. **Frontend Dashboard Console (`/frontend`)**: A premium dark-mode dashboard with live system metrics, incident history feeds, and an interactive real-time monospaced terminal displaying the agent's diagnostics outputs via Server-Sent Events (SSE).
2. **FastAPI Backend Server (`/backend/main.py`)**: Connects endpoints for metrics querying, stats dashboards, runbook listings, and real-time SSE log streaming.
3. **Database Manager (`/backend/db.py`)**: Persistent SQL table schemas for tracking incidents and runbooks. Incorporates automated seeding and vector cosine similarity matching.
4. **Remediation Agent Engine (`/backend/agent.py`)**: Embeds text queries, searches the vector index, executes CLI checks (`ccloud`, `aws`, `netstat`), and writes final statuses back to CockroachDB.

---

## ⚙️ How It Works

1. **Incident Triggered**: A mock outage alert is emitted (e.g. EC2 CPU Spike, Database Timeout, S3 Access Denied, Lambda Out of Memory).
2. **Vector Embedding RAG**: The agent generates a 384-dimensional symptom vector and queries the CockroachDB vector index.
3. **Remediation Plan Matched**: If a matching runbook is found above the similarity threshold, the agent retrieves the step-by-step remediation path.
4. **Autonomous Execution**: The agent executes each check sequentially, simulating diagnostics output, and updating the database state in real-time.
5. **Resolution Persisted**: Once verified healed, the incident is updated to `status: resolved` with complete action logs written to CockroachDB.

---

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
Ensure you have **Python 3.11+** installed.

### 2. Setup Project
Clone the repository and set up a virtual environment:
```bash
git clone https://github.com/DavidPraise0x/HealSync-AI.git
cd HealSync-AI
python -m venv venv
```

Activate the virtual environment:
* **Windows**:
  ```powershell
  .\venv\Scripts\activate
  ```
* **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Launch Backend Server
Run the backend FastAPI server:
```bash
python -u -m backend.main
```
The server will start listening at **`http://localhost:8000`**.

### 4. Access the Dashboard
Open your web browser and navigate to **`http://localhost:8000`** to access the control room cockpit. Click **"Simulate System Incident"** to watch the self-healing loops run!
