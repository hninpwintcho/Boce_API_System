import sqlite3
import time
import json

DB_PATH = "boce_api.db"

def monitor_results():
    print("⏳ Waiting for tasks to complete (approx 30s)...")
    time.sleep(30)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get recent tasks
    cursor.execute("""
        SELECT id, url, status, anomaly_count, global_availability_percent 
        FROM detection_tasks 
        ORDER BY created_at DESC 
        LIMIT 8
    """)
    rows = cursor.fetchall()
    
    print("\n--- 📊 Detection Summary ---")
    for row in rows:
        status_emoji = "✅" if row[2] == "completed" else "⏳" if row[2] in ["pending", "processing", "created"] else "❌"
        print(f"{status_emoji} {row[1]}")
        print(f"   Status: {row[2]} | Availability: {row[4]}% | AI Anomalies: {row[3]}")
    
    # Check for specific AI anomalies
    cursor.execute("""
        SELECT region, anomalies FROM region_results 
        WHERE anomalies LIKE '%AI_%' 
        LIMIT 5
    """)
    anoms = cursor.fetchall()
    if anoms:
        print("\n🧠 AI Insights:")
        for a in anoms:
            print(f" - [{a[0]}] Detected: {a[1]}")
    
    conn.close()

if __name__ == "__main__":
    monitor_results()
