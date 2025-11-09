#!/usr/bin/env python3
"""
queuectl - Complete version

Features:
- enqueue, list, status
- worker start (multi worker), graceful shutdown
- retries with exponential backoff (configurable)
- DLQ (dead letter queue) management (list/retry/purge)
- config set/get (persisted)
- job priorities and scheduling (priority, run_at)
- job control: pause / resume / cancel
- job output logging to logs/job_<id>.log
- persistent storage via SQLite (queue.db by default)
"""

import json
import sqlite3
import os
import time
import signal
import subprocess
from datetime import datetime, timezone
import click
from multiprocessing import Process, Event, current_process

# ---------------- Configuration ---------------- #

DB_PATH = os.environ.get("QUEUECTL_DB", "queue.db")
LOG_DIR = os.environ.get("QUEUECTL_LOG_DIR", "logs")
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2
STOP_EVENT = Event()

# ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)


# ---------------- Helper Functions ---------------- #

def now_iso():
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    """Get SQLite connection with dict-style rows."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Initialize database if not already created."""
    cur = conn.cursor()
    # jobs table with priority and run_at
    cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    run_at TEXT
)
""")
    # config table
    cur.execute("""
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
""")
    conn.commit()


def get_config(conn, key, default=None):
    """Fetch a config value from the database or return default (tries to convert to int)."""
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key=?", (key,))
    row = cur.fetchone()
    if row:
        v = row["value"]
        try:
            return int(v)
        except Exception:
            return v
    return default


def set_config_value(conn, key, value):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()


# ---------------- Worker Logic ---------------- #

def fetch_pending_job(conn):
    """
    Atomically fetch one pending job that's ready to run and mark it as processing.
    Prioritizes by priority DESC and created_at; skips future run_at.
    """
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
    except sqlite3.OperationalError:
        # failed to acquire lock - return None and let caller retry
        return None

    cur.execute("""
    SELECT id, command, attempts, max_retries, priority, run_at
    FROM jobs
    WHERE state = 'pending'
      AND (run_at IS NULL OR run_at <= ?)
    ORDER BY priority DESC, created_at
    LIMIT 1
    """, (now_iso(),))
    row = cur.fetchone()
    if not row:
        conn.rollback()
        return None

    cur.execute(
        "UPDATE jobs SET state='processing', updated_at=? WHERE id=?",
        (now_iso(), row["id"]),
    )
    conn.commit()
    return row


def write_job_log(job_id, stdout_bytes, stderr_bytes, append=True):
    """Write stdout/stderr to a per-job log file."""
    mode = "ab" if append else "wb"
    path = os.path.join(LOG_DIR, f"job_{job_id}.log")
    with open(path, mode) as f:
        f.write(b"--- START LOG ENTRY: " + now_iso().encode() + b" ---\n")
        if stdout_bytes:
            f.write(b"--- STDOUT ---\n")
            f.write(stdout_bytes)
            f.write(b"\n")
        if stderr_bytes:
            f.write(b"--- STDERR ---\n")
            f.write(stderr_bytes)
            f.write(b"\n")
        f.write(b"--- END LOG ENTRY ---\n\n")
    return path


def execute_job_with_logging(job):
    """
    Execute the job command using subprocess, capture stdout/stderr and write to log.
    Returns (success: bool, returncode: int).
    """
    job_id = job["id"]
    cmd = job["command"]
    try:
        # run the command; don't set shell=False because commands are provided as shell strings by design
        result = subprocess.run(cmd, shell=True, capture_output=True)
        # write logs
        write_job_log(job_id, result.stdout, result.stderr)
        return (result.returncode == 0, result.returncode)
    except Exception as e:
        # log the exception
        write_job_log(job_id, b"", str(e).encode())
        print(f"[Worker] Error running job {job_id}: {e}")
        return (False, -1)


def update_job_state(conn, job_id, new_state, attempts):
    cur = conn.cursor()
    cur.execute(
        "UPDATE jobs SET state=?, attempts=?, updated_at=? WHERE id=?",
        (new_state, attempts, now_iso(), job_id),
    )
    conn.commit()


def process_loop(worker_id, stop_event):
    """
    Worker loop: continuously poll for jobs and execute them.
    Reads configuration values from DB at start.
    """
    proc_name = current_process().name
    conn = get_conn()
    init_db(conn)
    print(f"[{proc_name} | Worker {worker_id}] started.")

    # Load configuration from DB (snapshotted at worker start)
    max_retries_conf = get_config(conn, "max_retries", DEFAULT_MAX_RETRIES)
    backoff_base_conf = get_config(conn, "backoff_base", DEFAULT_BACKOFF_BASE)

    while not stop_event.is_set():
        job = fetch_pending_job(conn)
        if not job:
            time.sleep(1)
            continue

        job_id = job["id"]
        print(f"[{proc_name} | Worker {worker_id}] picked job {job_id} (priority={job['priority']})")
        success, returncode = execute_job_with_logging(job)

        if success:
            print(f"[{proc_name} | Worker {worker_id}] Job {job_id} completed successfully (rc={returncode}).")
            update_job_state(conn, job_id, "completed", job["attempts"])
        else:
            new_attempts = job["attempts"] + 1
            # job-specific max_retries takes precedence; if 0 or None, fall back to config
            job_max_retries = job["max_retries"] or max_retries_conf
            if new_attempts < job_max_retries:
                # compute delay using configured backoff base
                try:
                    base = int(backoff_base_conf)
                except Exception:
                    base = DEFAULT_BACKOFF_BASE
                delay = base ** new_attempts
                print(f"[{proc_name} | Worker {worker_id}] Job {job_id} failed (attempt {new_attempts}), retrying in {delay}s.")
                update_job_state(conn, job_id, "pending", new_attempts)
                # small sleep to avoid busy loops; we delay the worker itself
                slept = 0
                while slept < delay and not stop_event.is_set():
                    time.sleep(1)
                    slept += 1
            else:
                print(f"[{proc_name} | Worker {worker_id}] Job {job_id} permanently failed -> moved to DLQ.")
                update_job_state(conn, job_id, "dead", new_attempts)

    conn.close()
    print(f"[{proc_name} | Worker {worker_id}] stopped gracefully.")


def start_workers(count):
    """Start one or more worker processes."""
    workers = []
    # set signals to set STOP_EVENT which child processes will inherit behavior for
    signal.signal(signal.SIGINT, lambda s, f: STOP_EVENT.set())
    signal.signal(signal.SIGTERM, lambda s, f: STOP_EVENT.set())

    for i in range(count):
        p = Process(target=process_loop, args=(i + 1, STOP_EVENT), daemon=False)
        p.start()
        workers.append(p)

    print(f"Started {count} worker(s). Press Ctrl+C to stop.")
    for p in workers:
        p.join()


# ---------------- CLI Commands ---------------- #

@click.group()
def cli():
    """queuectl — simple job queue CLI."""
    pass


# ----- Enqueue Command ----- #
@cli.command("enqueue")
@click.argument("job_json")
def enqueue(job_json):
    """Add a new job to the queue. Provide a JSON string with at least id and command.
    Optional fields: max_retries (int), priority (int), run_at (ISO timestamp)
    Example:
      queuectl.py enqueue '{"id":"job1","command":"echo hi","priority":5}'
    """
    try:
        data = json.loads(job_json)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")

    job_id = data.get("id")
    if not job_id:
        raise click.ClickException("Job must include an 'id'.")
    command = data.get("command")
    if not command:
        raise click.ClickException("Job must include a 'command'.")

    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    ts = now_iso()

    try:
        cur.execute("""
INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at, priority, run_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
            job_id,
            command,
            "pending",
            0,
            data.get("max_retries", DEFAULT_MAX_RETRIES),
            ts,
            ts,
            data.get("priority", 0),
            data.get("run_at", None),
        ))
        conn.commit()
        click.echo(f"Enqueued job {job_id}")
    except sqlite3.IntegrityError:
        raise click.ClickException(f"Job {job_id} already exists.")
    finally:
        conn.close()


# ----- List Jobs ----- #
@cli.command("list")
@click.option("--state", default=None, help="Filter by job state")
def list_jobs(state):
    """List jobs by state (or all)."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    if state:
        cur.execute("SELECT * FROM jobs WHERE state=? ORDER BY created_at", (state,))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at")
    rows = cur.fetchall()
    if not rows:
        click.echo("No jobs found.")
    else:
        for r in rows:
            # convert sqlite.Row to JSON-friendly dict
            d = dict(r)
            click.echo(json.dumps(d))
    conn.close()


# ----- Status ----- #
@cli.command("status")
def status():
    """Show summary of job states and DB path."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) as c FROM jobs GROUP BY state")
    rows = cur.fetchall()
    click.echo("Job counts:")
    states = {r["state"]: r["c"] for r in rows}
    for s in ["pending", "processing", "completed", "failed", "dead", "paused"]:
        click.echo(f"  {s:10s}: {states.get(s, 0)}")
    click.echo(f"\nDB file: {DB_PATH}")
    click.echo(f"Log dir: {os.path.abspath(LOG_DIR)}")
    conn.close()


# ----- Worker Commands ----- #
@cli.group()
def worker():
    """Manage workers."""
    pass


@worker.command("start")
@click.option("--count", default=1, help="Number of workers to start")
def start_worker_cmd(count):
    """Start one or more workers."""
    start_workers(count)


# ---------------- DLQ Commands ---------------- #
@cli.group()
def dlq():
    """Manage the Dead Letter Queue (DLQ)."""
    pass


@dlq.command("list")
def dlq_list():
    """List all jobs in the DLQ."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE state='dead' ORDER BY updated_at DESC")
    rows = cur.fetchall()
    if not rows:
        click.echo("No dead jobs found.")
    else:
        for r in rows:
            click.echo(json.dumps(dict(r), indent=2))
    conn.close()


@dlq.command("retry")
@click.argument("job_id")
def dlq_retry(job_id):
    """Move a dead job back to pending for retry."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id=? AND state='dead'", (job_id,))
    job = cur.fetchone()
    if not job:
        click.echo(f"Job {job_id} not found in DLQ.")
        conn.close()
        return

    cur.execute(
        "UPDATE jobs SET state='pending', attempts=0, updated_at=? WHERE id=?",
        (now_iso(), job_id),
    )
    conn.commit()
    click.echo(f"Job {job_id} moved back to pending for retry.")
    conn.close()


@dlq.command("purge")
def dlq_purge():
    """Delete all jobs from the DLQ."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM jobs WHERE state='dead'")
    conn.commit()
    click.echo("All dead jobs purged.")
    conn.close()


# ---------------- Config Commands ---------------- #

@cli.group()
def config():
    """Manage global configuration for queuectl."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a configuration key/value (persisted)."""
    conn = get_conn()
    init_db(conn)
    set_config_value(conn, key, value)
    click.echo(f"Set config {key} = {value}")
    conn.close()


@config.command("get")
def config_get():
    """Show all configuration values."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("SELECT * FROM config")
    rows = cur.fetchall()
    if not rows:
        click.echo("No configuration set yet.")
    else:
        for r in rows:
            click.echo(f"{r['key']} = {r['value']}")
    conn.close()


# ---------------- Job Control Commands ---------------- #

@cli.group()
def job():
    """Manual job controls: pause/resume/cancel."""
    pass


@job.command("pause")
@click.argument("job_id")
def pause_job(job_id):
    """Pause a job (set state -> paused). Workers skip paused jobs."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET state='paused', updated_at=? WHERE id=?", (now_iso(), job_id))
    if cur.rowcount == 0:
        click.echo(f"No job found with id {job_id}")
    else:
        conn.commit()
        click.echo(f"Job {job_id} paused.")
    conn.close()


@job.command("resume")
@click.argument("job_id")
def resume_job(job_id):
    """Resume a paused job (set state -> pending)."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET state='pending', updated_at=? WHERE id=? AND state='paused'", (now_iso(), job_id))
    if cur.rowcount == 0:
        click.echo(f"Job {job_id} not found or not paused.")
    else:
        conn.commit()
        click.echo(f"Job {job_id} resumed.")
    conn.close()


@job.command("cancel")
@click.argument("job_id")
def cancel_job(job_id):
    """Cancel (delete) a job completely."""
    conn = get_conn()
    init_db(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    if cur.rowcount == 0:
        click.echo(f"No job found with id {job_id}")
    else:
        conn.commit()
        click.echo(f"Job {job_id} cancelled and removed.")
    conn.close()


# ----- Main Entrypoint ----- #
if __name__ == "__main__":
    cli()
