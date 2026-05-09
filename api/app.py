from flask import Flask, request, jsonify
from supabase import create_client
from dotenv import load_dotenv
import os, json

load_dotenv()
app = Flask(__name__)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@app.route("/vote", methods=["POST"])
def receive_vote():
    vote = request.get_json()

    # Validate payload
    if not vote or not all(k in vote for k in ["user_id", "poll_id", "choice"]):
        return jsonify({"error": "Invalid payload"}), 400

    # Publish to queue (replaces Pub/Sub)
    try:
        supabase.table("vote_queue").insert({"payload": vote, "status": "pending"}).execute()
        return jsonify({"status": "accepted"}), 200
    except Exception as e:
        # print("FULL ERROR:", str(e))  # add this line
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)