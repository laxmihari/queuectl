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
