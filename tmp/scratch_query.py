import requests
import json
import time
import sqlite3

def run_test():
    base_url = "http://127.0.0.1:5000"
    
    # 1. Login
    login_url = f"{base_url}/api/auth/login"
    payload = {"email": "operator@aios", "password": "operator123"}
    r = requests.post(login_url, json=payload)
    print("Login Response:", r.status_code)
    token = r.json()["token"]
    
    # 2. Submit query
    query_url = f"{base_url}/api/query"
    headers = {"Authorization": f"Bearer {token}"}
    query_payload = {"query": "Test query: firefox memory leaks and out of memory killing."}
    r = requests.post(query_url, json=query_payload, headers=headers)
    print("Query Response:", r.status_code)
    print(r.json())
    query_id = r.json()["query_id"]
    
    # 3. Wait for execution to finish and check audit DB
    print("Waiting 15 seconds for query execution and token generation...")
    time.sleep(15)
    
    conn = sqlite3.connect("data/aios_audit.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, created_at, action_type, validation_result, rejection_reason, execution_status FROM aios_audit ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    print("Last 5 audit logs:")
    for row in rows:
        print(row)
    conn.close()

if __name__ == "__main__":
    run_test()
