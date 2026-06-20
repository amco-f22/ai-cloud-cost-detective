import os
import psycopg
from dotenv import load_dotenv

# Load env variables from backend/.env
load_dotenv("backend/.env")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_metrics():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                print("=== Cloud Cost Detective DB Metrics ===")
                
                # Total Analyses Run
                cur.execute("SELECT COUNT(*) FROM analyses")
                res = cur.fetchone()[0]
                print(f"Total Scans Run: {res}")
                
                # Total Resources Scanned
                cur.execute("SELECT SUM(resources_scanned) FROM analyses")
                res = cur.fetchone()[0]
                print(f"Total AWS Resources Scanned: {res}")
                
                # Total Issues Detected
                cur.execute("SELECT SUM(issues_found) FROM analyses")
                res = cur.fetchone()[0]
                print(f"Total Issues Detected: {res}")
                
                # Average Time Taken
                cur.execute("SELECT AVG(CAST(analysis_result->>'time_taken_seconds' AS INTEGER)) FROM analyses WHERE analysis_result->>'time_taken_seconds' IS NOT NULL")
                res = cur.fetchone()[0]
                print(f"Average AI Analysis Time: {round(res, 1) if res else 'N/A'} seconds")
                
                # Fetch recent savings
                cur.execute("SELECT estimated_savings FROM analyses ORDER BY created_at DESC LIMIT 5")
                res = cur.fetchall()
                print(f"Recent Estimated Savings: {[r[0] for r in res]}")
                
                print("======================================")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_metrics()
