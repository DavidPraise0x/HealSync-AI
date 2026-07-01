import os
import sqlite3
import json
import numpy as np

# In a real environment, we would connect to CockroachDB using psycopg:
# import psycopg
# conn = psycopg.connect("postgresql://username:password@host:port/database?sslmode=verify-full")

# Try to load SentenceTransformer for real embeddings
try:
    from sentence_transformers import SentenceTransformer
    print("Loading SentenceTransformer model 'all-MiniLM-L6-v2'...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    HAS_TRANSFORMERS = True
except Exception as e:
    print(f"Transformers not available: {e}. Using resilient keyword embedding fallback.")
    HAS_TRANSFORMERS = False
    model = None

def get_text_embedding(text):
    """
    Returns a 384-dimensional normalized vector for a given text query.
    If SentenceTransformer is available, it uses it.
    Otherwise, falls back to a deterministic TF-IDF style vector generator.
    """
    if HAS_TRANSFORMERS and model:
        try:
            emb = model.encode(text)
            return (emb / np.linalg.norm(emb)).tolist()
        except Exception as e:
            print(f"Embedding generation failed, using fallback: {e}")
            
    # Deterministic vector fallback
    # Create a simple bag-of-words hash vector of size 384
    words = text.lower().replace(".", "").replace(",", "").replace("-", " ").split()
    vector = np.zeros(384)
    for word in words:
        # Simple hash function to map word to index
        idx = sum(ord(c) for c in word) % 384
        vector[idx] += 1.0
        
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
        
    return vector.tolist()

class DatabaseManager:
    def __init__(self):
        self.db_url = os.environ.get("COCKROACH_DB_URL")
        self.use_cockroach = False
        self.conn = None
        
        # Initialize database
        self.init_db()

    def init_db(self):
        # We will use SQLite locally for simulation, but write it in a way that matches Postgres/CockroachDB schemas.
        # This makes it fully runnable out of the box.
        self.conn = sqlite3.connect("heal_sync.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        # Create incidents table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            symptoms TEXT,
            status TEXT NOT NULL, -- 'active', 'remediating', 'resolved', 'failed'
            severity TEXT NOT NULL, -- 'low', 'medium', 'high', 'critical'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            remediation_logs TEXT
        )
        """)
        
        # Create runbooks table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            symptoms TEXT NOT NULL,
            symptoms_vector TEXT, -- Stored as JSON array string for SQLite fallback
            remediation_steps TEXT NOT NULL
        )
        """)
        
        self.conn.commit()
        
        # Seed initial runbooks if empty
        cursor.execute("SELECT COUNT(*) FROM runbooks")
        if cursor.fetchone()[0] == 0:
            self.seed_runbooks()

    def seed_runbooks(self):
        # We will seed some standard runbooks with dummy vectors (simulated embeddings)
        runbooks_data = [
            {
                "name": "EC2/ECS CPU Spike Remediation",
                "description": "Triggered when CPU utilization exceeds 90% on ECS tasks or EC2 instances.",
                "symptoms": "High CPU utilization, service latency degradation, timeout errors.",
                "symptoms_vector": get_text_embedding("High CPU utilization, service latency degradation, timeout errors."),
                "remediation_steps": json.dumps([
                    {"step": 1, "action": "Collect top processes via ssh/agent", "command": "top -b -n 1 | head -n 20"},
                    {"step": 2, "action": "Identify resource hogging process", "command": "ps -eo pid,ppid,%mem,%cpu,cmd --sort=-%cpu | head"},
                    {"step": 3, "action": "Scale task count to distribute load", "command": "aws ecs update-service --service-name app-service --desired-count 4"}
                ])
            },
            {
                "name": "Database Connection Timeout Outage",
                "description": "Triggered when backend cannot reach the CockroachDB cluster.",
                "symptoms": "Database connection pool timeout, connection refused, 500 error on api.",
                "symptoms_vector": get_text_embedding("Database connection pool timeout, connection refused, 500 error on api."),
                "remediation_steps": json.dumps([
                    {"step": 1, "action": "Verify database cluster status using ccloud CLI", "command": "ccloud cluster list"},
                    {"step": 2, "action": "Check connection pool health and check open files", "command": "netstat -an | grep 26257 | wc -l"},
                    {"step": 3, "action": "Perform database client reconnect check", "command": "pg_isready -h cockroach-cluster -p 26257"}
                ])
            },
            {
                "name": "Amazon S3 Access Denied Error",
                "description": "Triggered when files fail to upload to S3 due to credential or permission issues.",
                "symptoms": "S3 Access Denied 403, permissions error, upload failure.",
                "symptoms_vector": get_text_embedding("S3 Access Denied 403, permissions error, upload failure."),
                "remediation_steps": json.dumps([
                    {"step": 1, "action": "Validate current IAM Role policy attachment", "command": "aws iam list-attached-role-policies --role-name ecsTaskRole"},
                    {"step": 2, "action": "Verify S3 bucket policy public blocking config", "command": "aws s3api get-public-access-block --bucket heal-sync-assets"},
                    {"step": 3, "action": "Refresh temporary AWS credentials", "command": "aws sts get-caller-identity"}
                ])
            },
            {
                "name": "AWS Lambda Out of Memory Outage",
                "description": "Triggered when a serverless Lambda function runs out of allocated memory.",
                "symptoms": "Lambda process exited, Process exited unexpectedly, memory limit exceeded.",
                "symptoms_vector": get_text_embedding("Lambda process exited, Process exited unexpectedly, memory limit exceeded."),
                "remediation_steps": json.dumps([
                    {"step": 1, "action": "Check CloudWatch logs for maximum memory used", "command": "aws logs filter-log-events --log-group-name /aws/lambda/process-payment --filter-pattern 'Memory Size'"},
                    {"step": 2, "action": "Increase Lambda function memory limits by 512MB", "command": "aws lambda update-function-configuration --function-name process-payment --memory-size 1024"},
                    {"step": 3, "action": "Re-run test payload to verify execution success", "command": "aws lambda invoke --function-name process-payment output.json"}
                ])
            }
        ]
        
        cursor = self.conn.cursor()
        for rb in runbooks_data:
            cursor.execute(
                "INSERT INTO runbooks (name, description, symptoms, symptoms_vector, remediation_steps) VALUES (?, ?, ?, ?, ?)",
                (rb["name"], rb["description"], rb["symptoms"], json.dumps(rb["symptoms_vector"]), rb["remediation_steps"])
            )
        self.conn.commit()

    # Incidents API
    def create_incident(self, title, description, symptoms, severity):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO incidents (title, description, symptoms, status, severity, remediation_logs) VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, symptoms, 'active', severity, json.dumps([]))
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_incident_status(self, incident_id, status, resolved=False, log_message=None):
        cursor = self.conn.cursor()
        
        # Retrieve existing logs
        cursor.execute("SELECT remediation_logs FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        logs = json.loads(row["remediation_logs"]) if row and row["remediation_logs"] else []
        
        if log_message:
            logs.append(log_message)
            
        if resolved:
            cursor.execute(
                "UPDATE incidents SET status = ?, resolved_at = CURRENT_TIMESTAMP, remediation_logs = ? WHERE id = ?",
                (status, json.dumps(logs), incident_id)
            )
        else:
            cursor.execute(
                "UPDATE incidents SET status = ?, remediation_logs = ? WHERE id = ?",
                (status, json.dumps(logs), incident_id)
            )
        self.conn.commit()

    def get_incidents(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_incident(self, incident_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # Vector RAG Search
    def find_similar_runbook(self, input_vector, threshold=0.3):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description, symptoms, symptoms_vector, remediation_steps FROM runbooks")
        rows = cursor.fetchall()
        
        best_match = None
        best_score = -1.0
        
        for row in rows:
            rb_vector = json.loads(row["symptoms_vector"])
            # Cosine similarity
            score = np.dot(input_vector, rb_vector) / (np.linalg.norm(input_vector) * np.linalg.norm(rb_vector))
            if score > best_score:
                best_score = score
                best_match = row
                
        if best_score >= threshold and best_match:
            return {
                "id": best_match["id"],
                "name": best_match["name"],
                "description": best_match["description"],
                "symptoms": best_match["symptoms"],
                "remediation_steps": json.loads(best_match["remediation_steps"]),
                "similarity_score": float(best_score)
            }
        return None

# Singleton instance
db_manager = DatabaseManager()
