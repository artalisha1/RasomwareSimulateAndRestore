# Restic Ransomware Simulation & Auto‑Recovery Notebook

This Jupyter notebook (`SimulateRansom+Restore.ipynb`) spins up a **self‑contained lab** that demonstrates how to:

* back up live files with [Restic](https://restic.net) in near real‑time,  
* simulate a ransomware encryption event, and  
* automatically roll back to the latest **clean baseline** snapshot—verifying data integrity along the way.

Use it as a hands‑on playground to test backup / recovery RPO‑RTO targets or to teach ransomware‑resilience concepts.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)  
2. [Prerequisites](#prerequisites)  
3. [Notebook Walkthrough](#notebook-walkthrough)  
4. [Customization Tips](#customization-tips)  
5. [Next Steps](#next-steps)  

---

## Project Overview

Pipeline steps performed by the notebook:

1. **Persist workspace** – Optionally mounts Google Drive so data survives Colab VM resets.  
2. **Install tooling** – Installs Restic CLI, `inotify-tools`, and the `watchdog` Python package.  
3. **Configure paths & repo** – Sets `ROOT`, `DATA_DIR`, `RESTIC_REPO`, `RESTORE_DIR`, and exports `RESTIC_PASSWORD`; initializes the repository if missing.  
4. **Generate sample data** – Creates a small folder hierarchy with docs, images, and a rolling log stream.  
5. **Real‑time snapshots** – A `watchdog` observer triggers `restic backup --tag auto` every time a file is closed.  
6. **Baseline backup** – Takes an initial “golden” snapshot tagged `baseline`.  
7. **Background producer** – A thread writes a new 1 KiB log file every 15 s to emulate workload churn.  
8. **Simulate attack** – Encrypts all `*.txt` files with OpenSSL AES‑256 and securely shreds the originals; tags an `attack` snapshot for audit.  
9. **Clean restore** – Restores the most‑recent snapshot tagged `baseline` into a temp dir, validates critical files, and atomically swaps the recovered data back in place.  
10. **Verification & cleanup** – Compares original vs. restored checksums, prints snapshot lists, and stops background threads; optional workspace prune.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python**  | 3.9 or newer |
| **Restic CLI** | 0.12 or newer |
| **pip** | 22 or newer |
| **Colab / Ubuntu tools** | `sudo apt‑get install -y restic tree inotify-tools` |
| **Python pkgs** | `pip install watchdog` |

> **Tip:** The notebook also runs fine on a local Linux/Mac workstation—just comment out the Google Drive mount cell.

---

## Notebook Walkthrough

| Step | Purpose |
|------|---------|
| **0 — Persist to Drive** | Keeps lab data between Colab sessions. |
| **1 — Install Tools** | Gets Restic, `tree`, and Python dependencies. |
| **2 — Configure Repo** | Defines directories, exports the repo password, and runs `restic init`. |
| **3 — Create Sample Data** | Builds `victim_data/` with docs/images/logs. |
| **4 — Watchdog Listener** | Backs up the dataset after every file close. |
| **5 — Background Producer** | Generates new log files every 15 s. |
| **6 — Baseline Snapshot** | Captures a golden baseline for future restores. |
| **7 — Idle Pause** | Lets activity accumulate for more snapshots. |
| **8 — Ransomware Simulation** | Encrypts text files and shreds the originals. |
| **9 — Read Failure Demo** | Shows that compromised files are unreadable. |
| **10 — Restore Clean Snapshot** | Restores latest `baseline` snapshot to a temp dir. |
| **11 — Verify Recovery** | Confirms the critical file is readable again. |
| **12 — Compare Checksums** | Sanity‑checks restored vs. original content. |
| **13 — Stop Threads** | Terminates producer and watchdog observer. |
| **14 — Optional Prune** | Cleans temp folders & extra snapshots. |

---

## Customization Tips

* **Adjust RPO/RTO tests** – Tweak the producer interval or the watchdog event to suit your workload.  
* **Add critical file checks** – Extend the integrity‑verification block for more business‑critical artifacts.  
* **Change attack vector** – Swap the OpenSSL command with a different encryption routine or a benign ransomware sample.  
* **Off‑site backups** – Point `RESTIC_REPO` at an S3/MinIO bucket to exercise cloud‑based restores.

---

## Next Steps

* **Add Prometheus metrics** for snapshot latency, size, and restore duration.  
* **Automate via GitHub Actions** – Run the notebook nightly and fail the CI job if restore integrity tests don’t pass.  
* **Integrate with cron/systemd** for on‑prem servers instead of Colab threads.  
* **Experiment with Restic prune policies** to compare long‑term retention strategies.
