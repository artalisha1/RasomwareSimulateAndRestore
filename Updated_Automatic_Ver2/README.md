# Restic Ransomware Simulation & Auto-Recovery Lab (V2)

This notebook (`SimulateRansom+Restore_Periodic_V2.ipynb`) demonstrates ransomware resilience using Restic:
it initializes a repo, creates sample data, captures baseline snapshots on a schedule only when real file-tree changes occur, simulates an AES-encrypted attack, and restores the latest clean baseline, verifying critical files and comparing against the live tree.

> NOTE on memory usage: In this V2, logging via watchdog and the background log producer are intentionally not included to reduce runtime memory and thread overhead. The core periodic baseline and restore flow remains intact.

---

## Table of Contents

1. Project Overview
2. Prerequisites
3. Notebook Workflow Step-by-Step
4. Detailed Walkthrough (by Step)
5. What's New in V2
6. Customization Tips
7. Next Steps

---

## Project Overview

Pipeline stages executed in the notebook:

1. Persist to Drive - keeps your lab state across Colab VM resets.
2. Install Restic & utils - restic, gnupg, tree (watchdog is installed but not used).
3. Configure repo & paths - initializes Restic repository and helper utilities.
4. Generate sample data - creates docs + binary blob.
5. Snapshot helpers - list snapshots, compute diffs, and create baselines only when needed.
6. Periodic baselines - thread re-runs baseline logic every N seconds with stop control.
7. Simulate ransomware - encrypts docs with OpenSSL and tags the event as `attack`.
8. Automatic clean restore - finds the latest readable baseline, restores into a clean target, and swaps.
9. Validation - verifies plaintext content, shows tree, and diffs original vs restored.
10. Shutdown - stops the periodic baseline thread.

---

## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| Google Colab | any |
| Python | 3.9+ |
| Restic CLI | 0.12+ |
| Utilities | tree, gnupg |
| (Optional) | watchdog (installed here but not used in V2) |

> Set `RESTIC_PASSWORD` in the environment. The notebook does this for demo purposes.

---

## Notebook Workflow Step-by-Step

| Step | Action |
|------|--------|
| ** 0** | Persist everything to Google Drive |
| ** 1** | Install Tools |
| ** 2** | Configure Restic Repo |
| ** 3** | Generate sample "production" files |
| ** 4** | Define Helper to Print List of Snapshots |
| ** 5** | Define Baseline Snapshot Helper |
| ** 6** | Define Periodic Baseline Scheduler |
| ** 7** | Define Helper to Restore Latest Baseline Snapshot that is Readable |
| ** 8** | 15 Seconds Pause |
| ** 9** | Validate the Accuracy of Baseline Function |
| **10** | Simulate Ransomware attack |
| **11** | Attempt to Read |
| **12** | Restore the Latest Clean Snapshot |
| **13** | Verify Restored File Exists and Matches Expected Content |
| **14** | Compare Original to Restored |
| **15** | Stop Periodic Baseline |

---

## Detailed Walkthrough (by Step)

**Step 0 - Persist to Google Drive**  
Mounts Drive at `/content/drive` and defines `ROOT`, so the lab persists across VM resets.

**Step 1 - Install Tools**  
Installs `restic`, `gnupg`, `tree`. Also installs `inotify-tools` and `watchdog` (watchdog is not used in V2).

**Step 2 - Configure Restic Repo**  
Sets `DATA_DIR`, `RESTIC_REPO`, `RESTORE_DIR`, sets `RESTIC_PASSWORD`, and initializes the repo if needed.

**Step 3 - Generate sample "production" files**  
Creates a small docs folder and a 1 MiB binary to simulate mixed data. Prints a tree.

**Step 4 - Snapshot listing helper** (`print_current_snapshots`)  
Lists repository snapshots with `restic snapshots`.

**Step 5 - Baseline helpers**  
- `run(cmd)` - thin wrapper around `subprocess.run` that captures stdout/stderr.  
- `get_baseline_snapshot_ids(repo)` - returns baseline short IDs.  
- `get_diff_details(old, new, repo)` - parses `restic diff` output into added/modified/removed/meta.  
- `print_diff_details(diff)` - pretty-prints categorized diffs.  
- `ensure_baseline_snapshot(data_dir, repo)` - creates initial baseline, or backs up then diffs; forgets the new snapshot if no real changes, otherwise keeps it and prints the diff.

**Step 6 - Periodic baseline scheduler**  
`start_periodic_baseline(data_dir, repo, interval)` creates a `threading.Event` and a daemon thread that calls `ensure_baseline_snapshot(...)` every `interval` seconds using `stop_event.wait(interval)`.  
Use:  
```python
stop_ev, thread = start_periodic_baseline(DATA_DIR, RESTIC_REPO, interval=15)
# later…
stop_ev.set(); thread.join(timeout=5)
```

**Step 7 - Restore helper** (`restore_latest_clean_baseline`)  
Iterates baseline snapshots (newest->oldest). For each:
1) restores into a temp dir,  
2) locates `victim_data`,  
3) verifies readability of `docs/report_Q1.txt`,  
4) swaps the restored content into `RESTORE_DIR`.  
Returns `(success: bool, restored_snapshot_id)`.

**Step 8 - Pause**  
Short sleeps to allow at least one periodic baseline cycle.

**Step 9 - Validate baseline logic**  
- Show existing baselines.  
- Create a `verify_<ts>.txt` file, print the tree.  
- Delete the file, print the tree again.  
This drives observable changes so the periodic baseline logic keeps or skips snapshots correctly.

**Step 10 - Simulate ransomware**  
- `mark_attack_snapshot` tags a snapshot as `attack`.  
- Encrypts `docs/*.txt` with OpenSSL AES-256 and shreds originals.

**Step 11 - Attempt plaintext read**  
Intentionally fails to read `docs/report_Q1.txt` to prove the attack removed plaintext.

**Step 12 - Restore latest clean baseline**  
Runs `restore_latest_clean_baseline`. Captures the restored snapshot ID.

**Step 13 - Verify restore**  
Locates the restored `victim_data`, lists docs, and prints the plaintext of `report_Q1.txt`.

**Step 14 - Compare original vs restored**  
Shows a `diff -rq` between the live tree and the restored tree.

**Step 15 - Stop periodic baseline**  
Signals the scheduler to stop with `stop_ev.set()` and joins the thread.

---

## What's New in V2

* Removed near-real-time watchdog listener and the background log producer workload to lower memory usage in Colab-style notebooks.
* Added a smarter `ensure_baseline_snapshot()` that:
  * Creates an initial baseline if none exists.
  * On subsequent runs, backs up and diffs old->new; if no real changes, the new baseline snapshot is forgotten (pruned) to avoid churn.
* Introduced a clean start/stop for the periodic baseline thread using a `threading.Event`.

---

## Customization Tips

* Interval tuning - adjust `start_periodic_baseline(..., interval=...)` to match your RPO budget.
* Diff sensitivity - `get_diff_details` currently parses Restic's textual diff; extend it if you need path filters.
* Critical file checks - add more invariants in `restore_latest_clean_baseline` (e.g., checksum lists).
* Cloud repos - point `RESTIC_REPO` to S3/MinIO/Azure for off-host recovery drills.

---

## Next Steps

* Emit metrics (counts, durations) to Prometheus/Grafana for observability.
* Integrate into CI to routinely prove that a clean baseline can be restored.
* Add a smoke test that writes/edits files between baseline cycles and asserts snapshot behavior.

