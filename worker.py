from supabase import create_client
from dotenv import load_dotenv
import os, time

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

processed_count = 0  # global counter

def process_vote(queue_item):
    global processed_count
    vote = queue_item["payload"]
    queue_id = queue_item["id"]

    doc_id = f"{vote['user_id']}_{vote['poll_id']}"

    try:
        # Calculate latency
        latency = time.time() - vote.get("time_created", time.time())

        # Store in votes table (upsert = idempotent write)
        supabase.table("votes").upsert({
            "id": doc_id,
            "user_id": vote["user_id"],
            "poll_id": vote["poll_id"],
            "choice": vote["choice"],
            "edge_id": vote.get("edge_id"),
            "timestamp": vote.get("timestamp"),
            "time_created": vote.get("time_created"),
        }).execute()

        # Mark queue item as processed
        supabase.table("vote_queue").update({"status": "processed"}).eq("id", queue_id).execute()
        
        processed_count += 1
        print(f"Processed vote: {vote['user_id']} | Poll: {vote['poll_id']} | Choice: {vote['choice']} | Latency: {latency:.2f}s | Total: {processed_count}")

    except Exception as e:
        # Mark as failed — allows retry on next loop
        supabase.table("vote_queue").update({"status": "failed"}).eq("id", queue_id).execute()
        print(f"Error processing vote {queue_id}: {e}")

def run_worker():
    print("Worker started. Listening for votes...")
    while True:
        # Pull pending messages (replaces Pub/Sub pull)
        result = supabase.table("vote_queue") \
            .select("*") \
            .eq("status", "pending") \
            .limit(10) \
            .execute()

        messages = result.data
        if messages:
            for item in messages:
                process_vote(item)
        else:
            time.sleep(2)  # wait before polling again

if __name__ == "__main__":
    run_worker()