# Distributed Voting System with Edge–Cloud Architecture and Fault Tolerance
### CS323 — Laboratory Activity 2
**Group Name:** Snappy  
**Project:** `cs323-voting-system-Snappy`

---

## Table of Contents
- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup and Execution](#setup-and-execution)
- [Fault Injection Testing](#fault-injection-testing)
- [System Evaluation Results](#system-evaluation-results)
- [Individual Reflections](#individual-reflections)

---

## System Overview

This project implements a **Distributed Voting System** using an edge-to-cloud architecture. Instead of Google Cloud Platform (GCP), the system uses **Supabase** as the cloud backend due to accessibility constraints, with equivalent component mappings.

Multiple edge nodes independently generate and transmit votes to a Flask-based ingestion API. The API inserts incoming votes into a queue table in Supabase (acting as a message buffer, equivalent to Pub/Sub). A separate worker service continuously polls the queue, processes each vote with idempotency guarantees, and stores the final result in a persistent votes table (equivalent to Firestore).

The system is designed to remain functional even under partial failure — when the worker goes down, votes continue to be accepted and buffered, and automatically recovered once the worker is restored.

---

## Architecture


The system uses an event-driven pipeline with four main parts: edge nodes, an API, a message queue, and storage. Since Google Cloud Platform was not used, Supabase was used as the cloud backend to replace similar GCP services.

At the edge layer, each member runs an instance of edge_node.py that continuously generates sample vote data containing a user ID, poll ID, choice, and timestamp. Each node has a unique edge_id and sends votes to the API through HTTP requests.

The ingestion layer is handled by a Flask API (app.py) running on localhost:5000. It receives and validates incoming votes, then stores them in the vote_queue table. This API is lightweight and only handles receiving requests.

The vote_queue table works as a message buffer similar to Google Pub/Sub. Votes remain in the queue with a pending status until processed by the worker. This setup allows the API and worker to run independently and prevents data loss if the worker stops.

The processing layer is managed by worker.py, which continuously checks the queue for pending votes. It creates an idempotency key using the user_id and poll_id to avoid duplicate records, then stores valid votes in the votes table. After processing, messages are marked as processed or failed for possible retry. The votes table serves as the final storage for all valid votes.

```
┌─────────────────────────────────────────────────────────────┐
│                        EDGE LAYER                           │
│                                                             │
│   [Edge Node 1]   [Edge Node 2]   [Edge Node N]             │
│   edge_node.py    edge_node.py    edge_node.py              │
│   (Member 1)      (Member 2)      (Member N)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP POST /vote
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   INGESTION LAYER                           │
│                                                             │
│              Flask API — app.py (:5000)                     │
│         Validates payload → inserts to queue                │
└──────────────────────────┬──────────────────────────────────┘
                           │ INSERT (status: pending)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               SUPABASE (Cloud Backend)                      │
│                                                             │
│   ┌─────────────────────┐    ┌──────────────────────────┐   │
│   │    vote_queue table │    │       votes table        │   │
│   │  (acts as Pub/Sub)  │    │  (final persistent store)│   │
│   │  status: pending /  │    │  idempotent upsert by    │   │
│   │  processed / failed │    │  user_id + poll_id       │   │
│   └──────────┬──────────┘    └──────────────────────────┘   │
└──────────────┼──────────────────────────▲───────────────────┘
               │ Poll pending rows        │ UPSERT processed vote
               ▼                          │
┌─────────────────────────────────────────────────────────────┐
│                  PROCESSING LAYER                           │
│                                                             │
│              Worker Service — worker.py                     │
│     Pulls pending → processes → upserts → acknowledges      │
└─────────────────────────────────────────────────────────────┘
```


### Component Mapping (GCP → Supabase)

| GCP Component | Supabase Equivalent |
|--------------|---------------------|
| Cloud Run API | Flask app (`app.py`) on `localhost:5000` |
| Pub/Sub Topic (`vote-topic`) | `vote_queue` table with `status` column |
| Pub/Sub Subscription (`vote-sub`) | Worker polling `status = 'pending'` rows |
| Firestore (`votes` collection) | `votes` table in Supabase PostgreSQL |

---

## Technologies Used

- **Python 3** — Edge node, API, and worker scripts
- **Flask** — Lightweight HTTP server for the ingestion API
- **Supabase** — Cloud PostgreSQL database (queue + persistent storage)
- **supabase-py** — Python client for Supabase
- **python-dotenv** — Environment variable management
- **requests** — HTTP client for edge node transmission

---

## Project Structure

```
cs323-voting-system-Snappy/
├── app.py           # Flask ingestion API (Cloud Run equivalent)
├── worker.py        # Worker service (Pub/Sub subscriber equivalent)
├── edge_node.py     # Edge node script (run once per group member)
├── .env             # Environment variables (not committed to repo)
├── requirements.txt # Python dependencies
└── README.md
```

---

## Setup and Execution

### Prerequisites
- Python 3.8+
- A Supabase account at [https://supabase.com](https://supabase.com)

---

### Step 1: Create Supabase Project

1. Log in to [https://supabase.com](https://supabase.com)
2. Click **New Project** → name it `cs323-voting-system-Snappy`
3. Set a strong database password and save it
4. Choose region: **Southeast Asia (Singapore)**
5. Wait for the project to initialize (~2 minutes)

---

### Step 2: Create Database Tables

Go to **SQL Editor** in your Supabase project and run:

```sql
-- Final votes storage (equivalent to Firestore)
CREATE TABLE votes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  poll_id TEXT NOT NULL,
  choice TEXT NOT NULL,
  edge_id TEXT,
  timestamp FLOAT,
  time_created FLOAT,
  processed_at TIMESTAMP DEFAULT NOW()
);

-- Message queue (equivalent to Pub/Sub)
CREATE TABLE vote_queue (
  id SERIAL PRIMARY KEY,
  payload JSONB NOT NULL,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW()
);
```

Then disable Row Level Security to allow API writes:

```sql
ALTER TABLE vote_queue DISABLE ROW LEVEL SECURITY;
ALTER TABLE votes DISABLE ROW LEVEL SECURITY;
```

---

### Step 3: Configure Environment Variables

Create a `.env` file in the project root:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-public-key
API_URL=http://localhost:5000/vote
```

Get your `SUPABASE_URL` and `SUPABASE_KEY` from:  
**Supabase Dashboard → Project Settings → API**

---

### Step 4: Install Dependencies

Activate your virtual environment first:

```powershell
python -m venv env
.\env\Scripts\activate
```

Then install required packages:

```powershell
pip install flask supabase python-dotenv requests
```

---

### Step 5: Run the System

Open **4 separate terminals**, activate the virtual environment in each (`.\env\Scripts\activate`), then run:

**Terminal 1 — Start the API:**
```powershell
python app.py
```

**Terminal 2 — Start the Worker:**
```powershell
python worker.py
```

**Terminal 3 — Start Edge Node (Member 1):**
```powershell
python edge_node.py
```

**Terminal 4 — Start Edge Node (Member 2):**
```powershell
python edge_node.py
```

Each edge node instance gets a unique `edge_id` automatically, simulating independent distributed sources.

---

### Step 6: Verify the System

Once all terminals are running, go to **Supabase → Table Editor**:

- `vote_queue` — should show rows with `status: processed`
- `votes` — should show unique vote records with one entry per `user_id + poll_id`

---

## Fault Injection Testing

### Test 1: Message Duplication (Idempotency Check)

Modify `edge_node.py` to send the same vote twice:

```python
vote = generate_vote()
send_vote(vote)
send_vote(vote)  # intentional duplicate
```

**Expected result:**
- `vote_queue` will have 2 rows for the same vote
- `votes` table will only have **1 row** (upsert with idempotency key prevents duplicates)

---

### Test 2: Worker Failure Simulation

1. Stop the worker terminal (`Ctrl+C`)
2. Keep edge nodes running
3. Observe in Supabase → `vote_queue`:
   - `pending` rows accumulate continuously
   - `votes` table stops receiving new records
   - API continues accepting votes with no errors

---

### Test 3: Worker Recovery

1. Restart the worker: `python worker.py`
2. Observe the worker terminal — it will rapidly drain all queued messages
3. Check Supabase → `votes` — all previously buffered votes appear automatically

**No manual intervention or replay logic is required.**

---

## System Evaluation Results

### End-to-End Latency (Edge → Supabase `votes`)

Measured by comparing `time_created` (set at edge node) with worker processing time.

| Sample | Latency |
|--------|---------|
| 1 | 512.29s* |
| 2 | 506.05s* |
| 3 | 500.67s |
| 4 | 493.74s |
| 5 | 487.04s |
| 6 | 480.33s |
| 7 | 474.79s |
| 8 | 635.26s |
| 9 | 628.43s |
| 10 | 622.75s |

> *Note: High latency values reflect accumulated queue time during fault injection testing (worker was stopped). Under normal operation with the worker running continuously, latency is significantly lower.*

---

### Throughput Evaluation

Run the following in Supabase SQL Editor to measure throughput:

```sql
SELECT
  (SELECT COUNT(*) FROM vote_queue) AS total_queued,
  (SELECT COUNT(*) FROM vote_queue WHERE status = 'processed') AS total_processed,
  (SELECT COUNT(*) FROM votes) AS total_stored;

-- Votes per choice
SELECT choice, COUNT(*) FROM votes GROUP BY choice;
```

---

### Fault Tolerance Summary

| State | Behavior Observed |
|-------|------------------|
| **Normal Operation** | Votes flowed continuously from edge → API → queue → votes with low latency |
| **Failure State (Worker Down)** | API continued accepting votes; `vote_queue` accumulated pending rows; `votes` table paused |
| **Recovery State** | Worker restarted and automatically drained all queued messages in batch; no data was lost |

---

### Consistency Check

After full recovery, total votes in `vote_queue` (processed) should approximately equal total rows in `votes`. Any difference is expected due to intentional duplicate transmissions being correctly deduplicated by the idempotency key (`user_id + poll_id`).

---

### Trade-Off Observations

| Design Decision | Benefit | Trade-off |
|----------------|---------|-----------|
| `vote_queue` table as message buffer | Votes are never lost during worker downtime | Extra database writes per vote |
| Upsert with `doc_id` as primary key | Prevents duplicate entries in final `votes` table | Slight processing overhead per vote |
| Worker polling every 2 seconds | Simple implementation, no extra dependencies | Small delay between queuing and processing |
| Random delays in edge nodes | Realistic simulation of distributed behavior | Slower overall vote generation rate |
| Flask on localhost (no deployment) | Easy setup and debugging | Not accessible outside local network |

---

## Individual Reflections

### Mariann Mesa (mesamariann)
> This project fundamentally shifted my perspective on how software should be built. The most eye-opening part of the project was observing the fault injection tests in action. Seeing the system successfully filter out intentional duplicate votes using an idempotency key demonstrated the critical difference between merely receiving data and ensuring absolute data integrity. Furthermore, intentionally crashing the worker and watching the API seamlessly buffer incoming votes—which were then rapidly processed without intervention upon the worker's recovery—was incredibly satisfying. This hands-on experience bridged the gap between theoretical concepts and real-world implementation, teaching me that robust systems aren't built to never fail, but rather designed to fail gracefully and recover without losing data.

### Gwynette Galleros (gwyiomi03)
> Working on this activity helped me better understand the difference between sequential and distributed execution. In a sequential system, tasks happen one at a time in an organized order. In our distributed system, vote generation, sending, and processing happened at the same time in different terminals, which made the system more realistic but also more difficult to manage.

>One thing we noticed was that when the worker stopped, the edge nodes and API still continued working. Votes kept being stored in the vote_queue table as pending entries. When the worker started again, it quickly processed all the queued votes. This showed how the system can temporarily store data and recover without losing information. However, the waiting time became longer because some votes stayed in the queue before being processed.

>The most difficult part was configuring Supabase, especially fixing the Row Level Security issue that prevented data from being written into the queue table. It took time to find the real problem because the API only showed a 500 error at first. Since the worker and database worked asynchronously, it was also harder to track when a vote was completely processed.

>Overall, the distributed system improved reliability and scalability because different parts of the system could continue working even if one component failed. At the same time, it also made setup, debugging, and understanding the flow of data more complicated compared to a simple centralized system.*

### Aldwyn Betonio (darkel-io)
> Implementing the distributed voting system helped me better understand how distributed systems work in real-world environments compared to simple sequential programs. In our implementation, we used Supabase instead of Google Cloud Platform because Google Cloud required billing setup. I observed that the different components such as the edge nodes, API service, messaging process, worker service, and database worked independently while still coordinating through asynchronous communication. During normal execution, votes were processed correctly, while during failure scenarios, queued requests were still handled once the worker recovered, showing the importance of fault tolerance and message buffering. I also noticed that duplicate vote transmissions increased processing load, but implementing idempotency prevented duplicate records from being stored in the database. One challenge I encountered was configuring and connecting the services properly because debugging distributed systems was more difficult compared to traditional single-program execution. Overall, this activity helped me understand that distributed systems improve scalability and reliability, but they also introduce additional complexity in synchronization, monitoring, and troubleshooting.

### Franco Galendez (m3izu)
> *[Write your individual reflection here — discuss your experience with the edge nodes, what you observed during fault injection, challenges you faced, and what you learned about distributed systems.]*

### Rafi Panandigan (RafiSailal18)
> Working on the distributed voting system helped me better understand how distributed systems work compared to regular sequential programs. Our group used Supabase instead of Google Cloud Platform because GCP required billing setup, making Supabase easier to use for the project.*

> Through the implementation, I learned how components like the API, edge nodes, worker service, and database can work independently while still communicating through asynchronous processes. During testing, the system was still able to process queued votes after the worker service recovered, which showed the importance of fault tolerance and reliability*

>  I also realized that debugging distributed systems is more challenging since errors can happen across different services at different times. Overall, the activity gave me a better appreciation of the benefits and challenges of distributed systems, especially in scalability, synchronization, and troubleshooting.*

---

*CS323 — Parallel and Distributed Computing | Laboratory Activity 2*
