import uuid, random, time, requests, os
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:5000/vote")
EDGE_ID = f"edge-{uuid.uuid4().hex[:6]}"  # unique per node instance

def generate_vote():
    return {
        "user_id": str(uuid.uuid4()),
        "poll_id": "poll_1",
        "choice": random.choice(["A", "B", "C"]),
        "timestamp": time.time(),
        "edge_id": EDGE_ID,
        "time_created": time.time()
    }

def send_vote(vote, retries=3):
    for attempt in range(retries):
        try:
            r = requests.post(API_URL, json=vote, timeout=5)
            print(f"[{EDGE_ID}] Vote sent: {vote['user_id']} | Choice: {vote['choice']} | Status: {r.status_code}")
            return
        except Exception as e:
            print(f"[{EDGE_ID}] Attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)  # exponential backoff
    print(f"[{EDGE_ID}] All retries failed for vote {vote['user_id']}")

def run_edge_node():
    print(f"[{EDGE_ID}] Edge node started.")
    while True:
        vote = generate_vote()
        send_vote(vote)
        time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    run_edge_node()