import requests
import time

BASE_URL = "http://localhost:8000/api/v1"
DEMO_PASS = "ReasonFlow#2026"

def login(email):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": DEMO_PASS})
    r.raise_for_status()
    return r.json()["data"]["access_token"]

# 1. Login as Executive
token_exec = login("priya.ceo@apexfoods.example")
headers_exec = {"Authorization": f"Bearer {token_exec}"}

# Start scenario 1
r = requests.post(f"{BASE_URL}/scenarios/sc-1/start", headers=headers_exec)

# Wait a second for queue to populate
time.sleep(1)

# Get queue (which runs detect->triage)
r = requests.post(f"{BASE_URL}/queue/refresh", headers=headers_exec)
queue = r.json()["data"]["queue"]
kpi_id = [q["kpi_id"] for q in queue if q["band"] == "CRITICAL"][0]

# Start investigation
r = requests.post(f"{BASE_URL}/investigations", json={"kpi_id": kpi_id}, headers=headers_exec)
inv_id = r.json()["data"]["id"]

# Wait for investigation to reach CERTAINTY_DECISION
for _ in range(10):
    r = requests.get(f"{BASE_URL}/investigations/{inv_id}", headers=headers_exec)
    state = r.json()["data"]["workflow_state"]
    if state in ("CERTAINTY_DECISION", "ABSTAINED", "CLARIFY"):
        break
    time.sleep(1)

# Get brief for Executive
r = requests.get(f"{BASE_URL}/investigations/{inv_id}/brief", headers=headers_exec)
brief_exec = r.json()["data"]

# 2. Login as Supply Chain
token_sc = login("rahul.sc@apexfoods.example")
headers_sc = {"Authorization": f"Bearer {token_sc}"}

# Get brief for Supply Chain
r = requests.get(f"{BASE_URL}/investigations/{inv_id}/brief", headers=headers_sc)
brief_sc = r.json()["data"]

print("Executive allowed actions:", brief_exec.get("allowed_actions"))
print("Supply Chain allowed actions:", brief_sc.get("allowed_actions"))
print("Executive Sections:", brief_exec.get("sections", {}).keys())
print("Supply Chain Sections:", brief_sc.get("sections", {}).keys())
