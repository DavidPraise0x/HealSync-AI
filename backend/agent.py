import json
import time
import asyncio
import numpy as np
from backend.db import db_manager, get_text_embedding

class RemediationAgent:
    def __init__(self):
        self.active_tasks = {}

    async def run_remediation(self, incident_id, log_callback=None):
        """
        Runs the full diagnostic and remediation loop for an incident.
        """
        async def log_and_save(msg):
            print(f"[Incident {incident_id}] {msg}")
            db_manager.update_incident_status(incident_id, 'remediating', log_message=msg)
            if log_callback:
                await log_callback(msg)
            await asyncio.sleep(1.0) # Realistic execution delay

        # Retrieve incident details
        incident = db_manager.get_incident(incident_id)
        if not incident:
            return

        await log_and_save(f"Ingested new alert: '{incident['title']}' with {incident['severity'].upper()} severity.")
        await log_and_save("Generating incident embedding vector...")
        
        # 1. Generate embedding and perform vector search
        symptoms_text = f"{incident['title']} {incident['description']} {incident['symptoms']}"
        vector = get_text_embedding(symptoms_text)
        
        await log_and_save("Querying CockroachDB Vector Index for similar historical incidents & runbooks...")
        match = db_manager.find_similar_runbook(vector)
        
        if not match:
            await log_and_save("CRITICAL: No matching runbook found in CockroachDB persistent memory.")
            await log_and_save("Escalating incident to Level 2 On-Call engineering. Remediation failed.")
            db_manager.update_incident_status(incident_id, 'failed', log_message="No runbook matched.")
            return

        await log_and_save(f"Found matching runbook: '{match['name']}' (Confidence: {match['similarity_score']:.2f})")
        await log_and_save(f"Description: {match['description']}")
        
        steps = match['remediation_steps']
        await log_and_save(f"Retrieved {len(steps)} remediation steps from database. Starting execution...")

        # 2. Run steps and simulate outputs
        for step in steps:
            step_num = step["step"]
            action = step["action"]
            cmd = step["command"]
            
            await log_and_save(f"Executing Step {step_num}/{len(steps)}: {action}")
            await log_and_save(f"Running command: `$ {cmd}`")
            
            # Simulate command output
            simulated_output = self._simulate_command_execution(cmd)
            for line in simulated_output:
                await log_and_save(f"  [stdout] {line}")
                
        await log_and_save("All remediation steps completed successfully. Running verification checks...")
        await log_and_save("SYSTEM STATUS: Active services returned 200 OK. CPU and memory in nominal bounds.")
        await log_and_save(f"Updating incident {incident_id} state to 'RESOLVED' in CockroachDB.")
        
        db_manager.update_incident_status(incident_id, 'resolved', resolved=True, log_message="Remediation completed successfully.")

    def _simulate_command_execution(self, command):
        """
        Returns realistic stdout responses based on the executed DevOps commands.
        """
        cmd_lower = command.lower()
        if "top" in cmd_lower or "ps" in cmd_lower:
            return [
                "PID   USER     %CPU  %MEM  COMMAND",
                "2304  root     94.2   8.4  node /app/server.js",
                "1102  postgres  2.1   4.2  postgres: walwriter",
                "45    root      0.5   0.2  sshd: connected"
            ]
        elif "aws ecs" in cmd_lower:
            return [
                "ServiceUpdate: 'app-service' update requested.",
                "Desired task count increased from 2 to 4.",
                "New ECS task ARN: arn:aws:ecs:us-east-1:1234567890:task/app-cluster/5f381",
                "Task provisioning initiated on Fargate instances..."
            ]
        elif "ccloud cluster" in cmd_lower:
            return [
                "ID         NAME              CLOUD   REGION          STATUS",
                "c5a31b2d   cockroach-prod    aws     us-east-1       AVAILABLE",
                "Capacity: 3 Nodes (Multi-AZ), Storage: 98.4 GB / 300.0 GB"
            ]
        elif "netstat" in cmd_lower or "pg_isready" in cmd_lower:
            return [
                "cockroach-prod.crdb.ccloud.io:26257 - accepting connections",
                "Active pool connections: 142 (Max: 500)",
                "HealthCheck status: OK (Response time: 4ms)"
            ]
        elif "iam" in cmd_lower:
            return [
                "AttachedPolicies:",
                "  - PolicyName: AmazonS3FullAccess (Arn: arn:aws:iam::aws:policy/AmazonS3FullAccess)",
                "  - PolicyName: AmazonECS_FullAccess (Arn: arn:aws:iam::aws:policy/AmazonECS_FullAccess)"
            ]
        elif "s3api" in cmd_lower:
            return [
                "BlockPublicAccessConfiguration:",
                "  BlockPublicAcls: true",
                "  IgnorePublicAcls: true",
                "  BlockPublicPolicy: false",
                "  RestrictPublicBuckets: false"
            ]
        elif "aws logs" in cmd_lower:
            return [
                "2026-06-30T14:20:01Z REPORT RequestId: 4f1a23b Memory Size: 512 MB Max Memory Used: 512 MB",
                "2026-06-30T14:20:01Z FATAL OutOfMemoryError: Container memory limit reached."
            ]
        elif "lambda update-function-configuration" in cmd_lower:
            return [
                "FunctionName: process-payment",
                "Runtime: python3.11",
                "MemorySize: 1024 MB",
                "LastModified: 2026-06-30T14:52:00Z",
                "State: Active"
            ]
        elif "lambda invoke" in cmd_lower:
            return [
                "Status: 200",
                "Payload: { 'success': true, 'transaction_id': 'tx_98a412b' }"
            ]
        else:
            return [
                "Command executed successfully.",
                "Return code: 0"
            ]

remediation_agent = RemediationAgent()
