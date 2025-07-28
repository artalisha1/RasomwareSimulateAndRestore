# Restic Ransomware Simulation & Auto‑Recovery Lab

This notebook (simulateransom_restore_periodic.ipynb) is a self‑contained script that stands up a mini‑lab to **practice ransomware resilience** with Restic.  
It automatically captures baseline and near‑real‑time snapshots, simulates an encryption attack, and then restores the most recent *clean* baseline—verifying data integrity and sweeping away malicious files.

---
## 📋 Table of Contents

1. [Project Overview](#project-overview)  
2. [Prerequisites](#prerequisites)  
3. [Script Walkthrough](#script-walkthrough)  
4. [Customization Tips](#customization-tips)  
5. [Next Steps](#next-steps)  

---

## Project Overview

Pipeline steps:

1. **Configure lab directories** – Sets `ROOT`, `DATA_DIR`, `RESTIC_REPO`, `RESTORE_DIR` and exports `RESTIC_PASSWORD`.
2. **Generate sample data** – Creates a small hierarchy with docs, images & rolling log files.
3. **Auto‑snapshot watchdog** – A [`watchdog`](https://pypi.org/project/watchdog/) observer takes an *instant* Restic backup each time a file is closed (`--tag auto`).
4. **Baseline scheduler** – A background thread re‑tags the latest state every *30 s* (`--tag baseline`) for quick rollbacks.
5. **Simulated attack** – Encrypts the docs with OpenSSL & tags an `attack` snapshot.
6. **Clean restore** – `restore_latest_clean_baseline()` iterates `baseline` snapshots (newest → oldest), restores to a temp dir, verifies `report_Q1.txt`, then moves the good data into place.
7. **Workspace cleanup** – Optionally deletes encrypted `.enc` leftovers and prunes old logs, keeping your lab tidy.

---

## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| **Python**  | 3.9+ |
| **Restic CLI** | 0.12+ |
| **pip** | 22+ |

### OS packages (Ubuntu)

```bash
sudo apt-get update -qq
sudo apt-get install -y restic tree inotify-tools
```

### Python packages

```bash
pip install watchdog
```

---

## Script Walkthrough

| Step | Purpose |
|------|---------|
| **1 — Mount Drive / set paths** | Ensures persistence when run in Google Colab. |
| **2 — Initialize repository** | `restic init` if `config` is missing. |
| **3 — Create sample data** | Writes demo text & binary files under `victim_data/`. |
| **4 — print_current_snapshots()** | Helper to list snapshots (`restic snapshots --no-lock`). |
| **5 — ensure_baseline_snapshot()** | Takes first *golden* backup tagged **baseline**. |
| **6 — ResticOnClose handler** | Fires `restic backup` on every file‑close event. |
| **7 — Producer thread** | Writes a new 1 KiB log file every 15 s to mimic live activity. |
| **8 — start_periodic_baseline()** | Scheduler that calls *Step 5* every 30 s. |
| **9 — restore_latest_clean_baseline()** | Restores the most recent readable **baseline** snapshot to `restore/`. |
| **10 — mark_attack_snapshot()** | Simulates encryption + takes an **attack** snapshot for auditing. |
| **11 — finalize_restoration()** | Replaces compromised data, prunes encrypted files & stale logs. |

---

## Customization Tips

* **Interval tuning** – change `interval` in `start_periodic_baseline()` and `producer()` to suit your RPO/RTO tests.  
* **Critical file list** – add more checks inside `restore_latest_clean_baseline()` to validate additional artifacts.  
* **Encryption payload** – swap OpenSSL for real ransomware samples in an isolated lab.  
* **Off‑host backups** – point `RESTIC_REPO` to S3/MinIO/Azure to test cloud recovery.  

---

## Next Steps

* **Prometheus‑exported metrics** for snapshot latency & failures.  
* **CI pipeline** that runs the lab, executes attack/restore, and asserts pass criteria.  
* **Cron or systemd timers** for *on‑prem* deployments instead of Colab threads.  
* **Compare deduplication stats** for different backup strategies (whole VM, volume snapshot, file‑level, etc.).

---
