# QueueCTL 🧩  
### A Simple CLI-Based Background Job Queue System

QueueCTL is a lightweight CLI tool that manages background jobs using worker processes.  
It supports retries with exponential backoff, Dead Letter Queue (DLQ) management, and persistent storage — all accessible from a command-line interface.

---

## 🚀 Features
- Enqueue and manage background jobs easily  
- Run multiple workers in parallel  
- Auto-retry failed jobs using exponential backoff  
- Persistent SQLite storage (jobs survive restarts)  
- Dead Letter Queue for permanently failed jobs  
- Graceful worker shutdown  
- Simple configuration management

---

## ⚙️ Tech Stack
- **Language:** Python 3  
- **Database:** SQLite (persistent storage)  
- **CLI Framework:** Click  
- **Concurrency:** Multiprocessing / subprocess

---

## 📦 Installation

Clone the repository and set up your environment:

```bash
git clone https://github.com/<your-username>/QueueCTL.git
cd QueueCTL
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

2️⃣ Start workers
queuectl worker start --count 3

3️⃣ View queue status
queuectl status

4️⃣ List jobs by state
queuectl list --state pending

5️⃣ View Dead Letter Queue
queuectl dlq list

🧠 Configuration Example

You can easily modify global configurations using the CLI:

queuectl config set max-retries 3
queuectl config set backoff-base 2

🧩 Architecture Overview

Each job is stored in an SQLite database with details like id, command, state, and retry count.
Workers fetch jobs from the queue, execute them, and update their state accordingly.
Failed jobs are retried automatically using exponential backoff:

delay = base ^ attempts   # e.g. base=2 → 2, 4, 8, 16 seconds...


After the maximum number of retries, they are moved to the Dead Letter Queue (DLQ).

🧪 Test Scenarios
Test Case	Expected Outcome
Enqueue + Worker	Job executes successfully
Invalid Command	Job fails and retries
Max Retries	Moves to DLQ
Restart App	Jobs persist in DB
Multiple Workers	No duplicate job execution
🧰 Setup & Run
1️⃣ Clone this Repository
git clone git@github.com:<your-username>/queuectl.git
cd queuectl

2️⃣ Create Virtual Environment
python3 -m venv venv
source venv/bin/activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Initialize Database
python queuectl.py init

5️⃣ Run Example
queuectl enqueue '{"id":"demo1","command":"echo Job Running"}'
queuectl worker start --count 2

🧮 Example Database Entries

Below is an example of what your jobs.db might contain after a few test runs:

id	command	state	attempts	max_retries	created_at
job1	echo Hello	completed	0	3	2025-11-08T10:00:00Z
job2	sleep 2	pending	0	3	2025-11-08T10:01:00Z
job3	badcommand	dead	3	3	2025-11-08T10:02:00Z
📘 Design Decisions

SQLite was chosen for simplicity and persistent storage.

Click CLI provides a clean, modular command-line interface.

Multiprocessing ensures concurrent job execution.

Graceful shutdowns prevent job corruption.

DLQ support improves reliability for long-running or failing jobs.

🧠 Assumptions

Commands are short and safe for shell execution.

Failed jobs are retryable unless they exceed max retries.

Configurations can be updated via CLI.

🧾 Submission Info

Author: <Your Name>

GitHub: https://github.com/<your-username>/queuectl

Demo Video: <Add your Google Drive or YouTube link here>

🧩 Project Checklist

 CLI Functional Commands

 Persistent Job Storage

 Retry & Backoff

 DLQ Support

 Worker Management

 Configurable Parameters

 Clean Code Structure

 Detailed Documentation

🌟 Bonus Features (Optional)

These features can earn bonus points if implemented:

Job priority queues

Scheduled/delayed jobs (run_at)

Job output logging

Timeout handling

Web dashboard for monitoring

Metrics and job analytics

🧭 Example Commands Summary
Command	Description
queuectl enqueue <job_json>	Add a new job to the queue
queuectl worker start --count N	Start N workers
queuectl worker stop	Stop workers gracefully
queuectl list --state <state>	List jobs by state
queuectl dlq list	View dead jobs
queuectl dlq retry <job_id>	Retry job from DLQ
queuectl config set <key> <value>	Update configuration
queuectl status	Show summary of job and worker states
💬 Example Output
$ queuectl enqueue '{"id":"job1","command":"echo Hello"}'
✅ Job job1 added successfully.

$ queuectl worker start --count 2
👷 Worker 1 started...
👷 Worker 2 started...
⚙️  Executing job: echo Hello
✅ Job job1 completed!

$ queuectl status
Jobs Summary:
Pending: 1 | Processing: 0 | Completed: 3 | Failed: 1 | Dead: 1
Active Workers: 2

📘 Testing Instructions

To verify functionality:

python -m unittest test_queuectl.py


(You can include or create test scripts validating enqueue, retry, DLQ logic, etc.)

🧭 Architecture Overview (Diagram)
           ┌───────────────┐
           │    enqueue     │
           └──────┬────────┘
                  │
                  ▼
          ┌───────────────┐
          │   jobs.db     │
          │ (SQLite Store)│
          └──────┬────────┘
                  │
           ┌──────▼────────┐
           │   worker(s)   │
           │ execute jobs  │
           └──────┬────────┘
                  │
     ┌────────────▼────────────┐
     │ Retry + Backoff Manager │
     └────────────┬────────────┘
                  │
          ┌───────▼────────┐
          │   DLQ Storage   │
          └────────────────┘

Acknowledgments
  Built as part of a Backend Developer Internship Assignment to demonstrat understanding of background job queues, retries, and CLI architecture.
