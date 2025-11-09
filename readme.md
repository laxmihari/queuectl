# QueueCTL  
### A Simple CLI-Based Background Job Queue System

QueueCTL is a lightweight CLI tool that manages background jobs using worker processes.  
It supports retries with **exponential backoff**, **Dead Letter Queue (DLQ)** management, and **persistent storage** — all accessible from a single command-line interface.

---

## Features
- Enqueue and manage background jobs  
- Multiple concurrent worker processes  
- Automatic retries with exponential backoff  
- Dead Letter Queue (DLQ) for permanently failed jobs  
- Persistent storage using SQLite  
- Configurable retry and backoff settings via CLI  
- Graceful worker shutdowns  
- Clean and modular CLI structure using `click`

---

## Setup & Run

### Clone this Repository
    git clone git@github.com:<your-username>/queuectl.git
    cd queuectl

### Create Virtual Environment
    python3 -m venv venv
    source venv/bin/activate

### Install Dependencies
    pip install -r requirements.txt

### Initialize Database
    python queuectl.py init

### Run Example
    queuectl enqueue '{"id":"demo1","command":"echo Job Running"}'
    queuectl worker start --count 2

---

## Example Usage

### Enqueue a Job  
    queuectl enqueue '{"id":"job1","command":"echo Hello World"}'

### Start Workers  
    queuectl worker start --count 3

### View Queue Status  
    queuectl status

### List Jobs by State  
    queuectl list --state pending

### View Dead Letter Queue  
    queuectl dlq list

---

##  Configuration Example
You can modify configurations easily using CLI commands:

    queuectl config set max-retries 3  
    queuectl config set backoff-base 2

---

##  Architecture Overview

Each job is stored in an **SQLite database** with details like:
- Job ID
- Command
- State
- Attempts
- Max retries
- Created timestamp

Workers fetch jobs from the queue, execute them, and update their state accordingly.  
Failed jobs are retried automatically using **exponential backoff**:

    delay = base ^ attempts   (e.g., base=2 → 2s, 4s, 8s, 16s...)

After the maximum number of retries, jobs move to the **Dead Letter Queue (DLQ)**.

---

##  Test Scenarios

| Test Case | Expected Outcome |
|------------|------------------|
| Enqueue + Worker | Job executes successfully |
| Invalid Command | Job fails and retries |
| Max Retries | Moves to DLQ |
| Restart App | Jobs persist in DB |
| Multiple Workers | No duplicate execution |

---

## Example Database Entries

| id | command | state | attempts | max_retries | created_at |
|----|----------|--------|-----------|--------------|-------------|
| job1 | echo Hello | completed | 0 | 3 | 2025-11-08T10:00:00Z |
| job2 | sleep 2 | pending | 0 | 3 | 2025-11-08T10:01:00Z |
| job3 | badcommand | dead | 3 | 3 | 2025-11-08T10:02:00Z |

---

##  Design Decisions
- **SQLite** for lightweight persistence  
- **Click CLI** for modular command structure  
- **Multiprocessing** for concurrency  
- **Graceful shutdown** for reliability  
- **DLQ** for failed job tracking  

---

## Assumptions
- Commands are safe shell operations  
- Failed jobs retry until reaching max limit  
- Configurations can be changed dynamically  

---


## Project Checklist

✅ CLI Functional Commands  
✅ Persistent Job Storage  
✅ Retry & Backoff Logic  
✅ DLQ Support  
✅ Worker Management  
✅ Configurable Parameters  
✅ Clean Code Structure  
✅ Detailed Documentation  

---

## Bonus Features (Optional)
These can be added for extra credit:
- Job priority queues  
- Scheduled or delayed jobs (`run_at`)  
- Job output logging  
- Timeout handling  
- Web dashboard for monitoring  
- Job analytics and metrics  

---

## Example Commands Summary

| Command | Description |
|----------|-------------|
| queuectl enqueue <job_json> | Add a new job to the queue |
| queuectl worker start --count N | Start N workers |
| queuectl worker stop | Stop workers gracefully |
| queuectl list --state <state> | List jobs by state |
| queuectl dlq list | View dead jobs |
| queuectl dlq retry <job_id> | Retry job from DLQ |
| queuectl config set <key> <value> | Update configuration |
| queuectl status | Show summary of jobs and workers |

---

## Example Output

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

---

##  Testing Instructions

To verify functionality, run:

    python -m unittest test_queuectl.py

You can include test scripts validating enqueue, retry, and DLQ logic.

---

## Architecture Diagram

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

---

##  Acknowledgments
Built as part of a **Backend Developer Internship Assignment**  
to demonstrate understanding of background job queues, retries, and CLI architecture.
