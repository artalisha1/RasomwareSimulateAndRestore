# Restic Ransomware Simulation & Auto‑Recovery Lab 

This notebook (SimulateRansom+Restore_Periodic.ipynb) integrates **ransomware resilience** with Restic.
It mounts persistent storage, auto‑snapshots live data, simulates an AES‑encrypted attack, and then restores the latest clean baseline—verifying that critical files remain intact.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Prerequisites](#prerequisites)
3. [Notebook Workflow Step‑by‑Step](#notebook-workflow-step‑by‑step)
4. [Customization Tips](#customization-tips)
5. [Next Steps](#next-steps)

---
## Project Overview

Pipeline stages executed in the notebook:

1. **Persist to Drive** – keeps your lab alive across Colab VM resets.
2. **Install Restic & deps** – gets all required CLI tools.
3. **Configure repo & paths** – initializes Restic repository and helper utilities.
4. **Generate sample data** – creates docs, images & log streams.
5. **Real‑time auto‑snapshots** – watchdog takes a snapshot each time a file closes.
6. **Periodic baselines** – scheduler re‑tags the latest state every 30 s.
7. **Simulate ransomware** – encrypts docs, tags `attack` snapshot.
8. **Automatic clean restore** – locates latest good baseline, restores and swaps.
9. **Validation & cleanup** – verifies integrity, compares trees, and stops background threads.

---
## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| **Google Colab** | any |
| **Python** | 3.9+ |
| **Restic CLI** | 0.12+ |
| **Utilities** | `tree`, `gnupg` |

Install commands are provided in **Step 1** of the notebook.

---
## Notebook Workflow Step‑by‑Step

| Step | Action |
|------|--------|
| ** 0** | Mounts Google Drive and sets a persistent `ROOT` directory. |
| ** 1** | Installs Restic, GnuPG, and tree via `apt`. |
| ** 2** | Initializes or opens the Restic repository and defines utility functions. |
| ** 3** | Creates sample `victim_data` hierarchy (docs, images, rolling logs). |
| ** 4** | Defines `print_snapshots()` helper to list Restic snapshots filtered by tags. |
| ** 5** | Implements `ensure_baseline_snapshot()` to capture the first **baseline** snapshot. |
| ** 6** | Starts a `watchdog` event handler that runs `restic backup --tag auto` on every file close. |
| ** 7** | Launches a background thread that writes a new log file every 15 s to simulate workload. |
| ** 8** | Creates `start_periodic_baseline(interval=30)` to retag the latest state as **baseline** every 30 s. |
| ** 9** | Defines `restore_latest_clean_baseline()` which iterates baseline snapshots, restores to a temp dir, and verifies key files. |
| **10** | Sleeps ~30 s so producer & watchdog can create auto snapshots. |
| **11** | Encrypts docs with OpenSSL AES‑256 and tags the snapshot as **attack**. |
| **12** | Attempts to view encrypted files—demonstrating access failure. |
| **13** | Runs the restore helper to recover the latest clean baseline. |
| **14** | Verifies that restored files (e.g., `report_Q1.txt`) match expected plaintext. |
| **15** | Performs a sanity `diff` between original and restored directories. |
| **16** | Signals producer and watchdog threads to stop and joins them. |

---
## Customization Tips

* **Change intervals** – adjust `producer()` and `start_periodic_baseline()` for different RPO/RTO goals.
* **Add critical files** – extend integrity checks inside `restore_latest_clean_baseline()`.
* **Swap encryption payload** – test other ransomware samples in an isolated lab.
* **Off‑host backups** – point `RESTIC_REPO` to S3, MinIO, or Azure for cloud recovery drills.

---
## Next Steps

* Export metrics to **Prometheus** for snapshot latency and failures.
* Integrate with **CI/CD** to automatically run attack/restore scenarios and assert SLOs.
* Use **systemd timers** or **cron** for on‑prem instead of Colab threads.
* Compare **Restic dedup stats** under different backup strategies.
