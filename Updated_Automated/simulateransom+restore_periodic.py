# -*- coding: utf-8 -*-
"""SimulateRansom+Restore_Periodic.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/12N_oF3AZfAEYh4qhYjh_M7t8m0xFeTjV

#Restic Ransomware Simulation & Auto‑Recovery Lab

Integrates automated Restic snapshots, simulates a ransomware attack, and then verifies and restores the latest clean baseline—all without manual intervention.

##Summary

This notebook spins up a self‑contained playground that

* sets up a Restic repo and captures an initial **baseline** snapshot
* launches a watchdog that backs up every file‑close (`--tag auto`)
  plus a background producer that keeps writing fresh log files
* runs a periodic scheduler that re‑tags the latest state as a new baseline
* simulates a ransomware attack by encrypting docs and tagging an **attack** snapshot
* automatically finds the latest *readable* baseline, restores it, verifies
  key files, and swaps the clean data back into place—deleting malicious
  artifacts and pruning old logs.

##Step 0: Persist everything to Google Drive
"""

from google.colab import drive
drive.mount('/content/drive')          # Skip this cell if you don't need persistence

# Choose a root dir that survives VM resets if you mounted Drive
ROOT = "/content/drive/MyDrive/ransomware_lab"  # or "/content" if Drive not mounted
!mkdir -p $ROOT

"""##Step 1: Install Tools"""

# Commented out IPython magic to ensure Python compatibility.
# %%bash
# sudo apt-get update -qq
# sudo apt-get install -y restic gnupg tree

# Commented out IPython magic to ensure Python compatibility.
# #Install extra utilities
# %%bash
# sudo apt-get install -y inotify-tools   # for near real‑time backup
# pip install --quiet watchdog            # Python file‑watcher library

"""##Step 2: Configure Restic Repo"""

import os, subprocess, textwrap, getpass, json, pathlib, shutil, time

# Change these if you like
DATA_DIR      = f"{ROOT}/victim_data"
RESTIC_REPO   = f"{ROOT}/backup_repo"
RESTORE_DIR   = f"{ROOT}/restore"
os.makedirs(DATA_DIR,   exist_ok=True)
os.makedirs(RESTORE_DIR, exist_ok=True)

# One‑liner to set the repo password (DON'T lose it!)
os.environ["RESTIC_PASSWORD"] = "colab‑demo‑super‑secret"  # choose a strong one IRL

# Initialize repository once
if not pathlib.Path(RESTIC_REPO, "config").exists():
    !restic -r $RESTIC_REPO init

"""##Step 3: Generate sample "production" files"""

# Commented out IPython magic to ensure Python compatibility.
# %%bash -s "$DATA_DIR"
# TARGET=$1
# mkdir -p "$TARGET/docs" "$TARGET/images"
# 
# # simple text data
# echo "Quarterly revenue: \$123,456"  > "$TARGET/docs/report_Q1.txt"
# echo "User list (PII redacted)"      > "$TARGET/docs/users.txt"
# 
# # simulate binary data
# head -c 1M </dev/urandom > "$TARGET/images/raw_sensor_dump.bin"
# 
# tree -h "$TARGET"

"""##Step 4: Define Helper to Print List of Snapshots"""

import subprocess
import sys
import os

def print_current_snapshots(restic_repo: str):
    """
    Prints the list of snapshots in the specified Restic repository.
    Relies on RESTIC_PASSWORD env var for authentication.
    """
    common_args = ["restic", "--repo", restic_repo]

    try:
        # Use --no-lock for faster listing if appropriate
        output = subprocess.check_output(
            common_args + ["snapshots", "--no-lock"],
            env=os.environ,
            text=True
        )
        print("🔍 Current snapshots in repository:")
        print(output)
    except subprocess.CalledProcessError as e:
        err = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
        print("❗ Error listing snapshots:", err, file=sys.stderr)

"""##Step 5: Define Baseline Snapshot Helper"""

import subprocess, sys
from datetime import datetime

def ensure_baseline_snapshot(data_dir: str, restic_repo: str):
    """
    Checks for an existing Restic snapshot; if none, takes the baseline backup.
    """
    common_args = [
        "restic",
        "--repo", restic_repo
    ]

    # 1) List existing snapshots
    try:
        result = subprocess.run(
            common_args + ["snapshots", "--no-lock"],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        print("❗ Error listing snapshots:", e.stderr, file=sys.stderr)
        sys.exit(1)

    # 2) If none exist, make the baseline
    if any(line.startswith("snapshot ") for line in result.stdout.splitlines()):
        print("✅  Baseline already exists; skipping.")
    else:
        #print("🚀  No baseline found—taking initial snapshot…")
        try:
            subprocess.run(
                common_args + ["backup", data_dir, "--tag", "baseline"],
                check=True
            )
            print(f"✅  Baseline complete at {datetime.now().isoformat()}")
        except subprocess.CalledProcessError as e:
            print("❗ Backup failed:", e.stderr, file=sys.stderr)
            sys.exit(1)

# Immediately take your golden snapshot tagged "baseline"
#ensure_baseline_snapshot(DATA_DIR, RESTIC_REPO)
# After setting up DATA_DIR, RESTIC_REPO, and exporting RESTIC_PASSWORD
#print_current_snapshots(RESTIC_REPO)

"""##Step 6: Start Watchdog that Snapshots on Every File-close"""

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess, os

class ResticOnClose(FileSystemEventHandler):
    def __init__(self, repo, path): self.repo, self.path = repo, path
    def on_closed(self, event):
        if event.is_directory: return
        print(f"[Watch] {event.src_path} closed → instant backup")
        subprocess.run(
            ["restic","-r",self.repo,"backup",self.path,"--tag","auto"],
            env=os.environ, check=False
        )

observer = Observer()
observer.schedule(ResticOnClose(RESTIC_REPO, DATA_DIR), str(DATA_DIR), recursive=True)
observer.start()
print("📡 Watchdog active — every write triggers a restic backup")

"""##Step 7: Start Background Producer
Writes new log file every 15 seconds
"""

import threading, random, string, pathlib, time
STREAM_DIR = pathlib.Path(DATA_DIR) / "logs"; STREAM_DIR.mkdir(exist_ok=True)

def producer(stop_event, interval=15):
    while not stop_event.is_set():
        fn = STREAM_DIR / f"log_{int(time.time())}.txt"
        fn.write_text(''.join(random.choices(string.ascii_letters, k=1024)))
        print(f"[Producer] wrote {fn.name}")
        time.sleep(interval)

stop_event = threading.Event()
prod_thr   = threading.Thread(target=producer, args=(stop_event,), daemon=True)
prod_thr.start()

"""##Step 8: Define Periodic Baseline Scheduler"""

import threading
import time

def start_periodic_baseline(data_dir: str, restic_repo: str, interval: int = 30):
    """
    Spawns a background thread that re-tags the latest state as a new baseline
    every `interval` seconds by calling ensure_baseline_snapshot().
    """
    def loop():
        while True:
            ensure_baseline_snapshot(data_dir, restic_repo)
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print(f"🕒 Started periodic baseline thread (every {interval}s)")

start_periodic_baseline(DATA_DIR, RESTIC_REPO, interval=30)

"""##Step 9: Define Helper to Restore Latest Baseline Snapshot that is Readable"""

import subprocess
import os
import pathlib
import shutil
import sys
import json
import tempfile
from datetime import datetime

def restore_latest_clean_baseline(restic_repo: str, restore_dir: str):
    """
    Attempts to restore the latest clean baseline snapshot.
    Iterates through snapshots tagged 'baseline' in reverse chronological order,
    restores to a temporary directory, verifies critical files, moves data,
    and returns the restored snapshot ID.
    """
    print("🔍 Searching for clean baseline snapshots...")

    # 1. List baseline snapshots
    try:
        proc = subprocess.run(
            ["restic", "-r", restic_repo, "snapshots", "--tag", "baseline", "--json"],
            capture_output=True, text=True, check=True, env=os.environ
        )
        snapshots = json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        print("❌ Failed to list baseline snapshots:", e.stderr.strip(), file=sys.stderr)
        return False, None

    if not snapshots:
        print("❌ No baseline snapshots found.")
        return False, None

    # 2. Sort by timestamp descending
    for snap in snapshots:
        snap["parsed_time"] = datetime.fromisoformat(snap["time"].rstrip("Z"))
    snapshots.sort(key=lambda s: s["parsed_time"], reverse=True)

    restore_path = pathlib.Path(restore_dir)
    tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="restic_tmp_"))

    try:
        # 3. Try each snapshot until valid
        for snap in snapshots:
            sid = snap["id"]
            print(f"🕵️ Trying snapshot {sid}...")

            tmp_dir = tmp_root / sid
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            tmp_dir.mkdir(parents=True)

            # Restore
            try:
                subprocess.run(
                    ["restic", "-r", restic_repo, "restore", sid, "--target", str(tmp_dir)],
                    capture_output=True, text=True, check=True
                )
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Restore failed for {sid}: {e.stderr.strip()}")
                continue

            # Locate victim_data
            victim_dirs = list(tmp_dir.rglob("victim_data"))
            if not victim_dirs:
                print(f"❌ victim_data not found in {sid}")
                continue
            victim_path = victim_dirs[0]

            # Verify critical file readability
            critical = victim_path / "docs" / "report_Q1.txt"
            if not critical.exists():
                print(f"❌ report_Q1.txt missing in {sid}")
                continue
            try:
                with open(critical, 'r') as f:
                    f.read(1)
            except Exception as e:
                print(f"❌ Cannot read report_Q1.txt in {sid}: {e}")
                continue

            # 4. Prepare restore_dir
            if restore_path.exists():
                shutil.rmtree(restore_path)
            restore_path.mkdir(parents=True)

            # Move contents
            for item in tmp_dir.iterdir():
                shutil.move(str(item), str(restore_path / item.name))

            print(f"✅ Restored clean baseline {sid} into {restore_dir}")
            return True, sid

        print("❌ No clean baseline snapshot found.")
        return False, None

    finally:
        shutil.rmtree(tmp_root)

"""##Step 10: 30 Seconds Pause
Producer and Watchdog can create auto snapshots
"""

import time, subprocess, os
print("⌛ Sleeping 30 s so real‑time activity accumulates …")
time.sleep(30)
print_current_snapshots(RESTIC_REPO)
#!restic -r $REPO_DIR snapshots | tail -n +3       # show newest snapshots

"""##Step 11: Simulate Ransomware attack

###Define Helper to Mark Simulated Ransomware Attack in Snapshots
"""

import subprocess, os

def mark_attack_snapshot(data_dir: str, restic_repo: str):
    """
    Takes a Restic backup of data_dir and tags it 'attack' to mark
    the moment of the simulated ransomware event.
    """
    common_args = ["restic", "--repo", restic_repo]
    print("⚠️  Ransomware attack simulated — taking 'attack' snapshot…")
    subprocess.run(
        common_args + ["backup", data_dir, "--tag", "attack"],
        check=True, env=os.environ
    )
    print("✅  'attack' snapshot complete.")

"""###Encrypt the files and Simulate Attack"""

# Commented out IPython magic to ensure Python compatibility.
# %%bash -s "$DATA_DIR"
# VICTIM=$1
# # Encrypt *.txt as a stand‑in for ransomware, then delete originals
# cd "$VICTIM/docs"
# for f in *.txt; do
#   openssl enc -aes-256-cbc -md sha256 -salt -in "$f" -out "${f}.enc" -pass pass:evil123
#   shred -u "$f"
# done
# echo "After attack:"
# tree -h "$VICTIM"

##mark the attack in Restic
mark_attack_snapshot(DATA_DIR, RESTIC_REPO)

print_current_snapshots(RESTIC_REPO)

"""##Step 12: Attempt to Read
Will fail
"""

import pathlib, sys

plaintext = pathlib.Path(DATA_DIR) / "docs" / "report_Q1.txt"   # original file path

try:
    text = plaintext.read_text()          # should raise FileNotFoundError
    print("❌  UNEXPECTED: plaintext still readable!", text[:100])
    sys.exit(1)
except (FileNotFoundError, PermissionError):
    print("✅  Expected failure: plaintext is gone or unreadable — ransomware succeeded.")

"""##Step 13: Restore the Latest Clean Snapshot"""

#List all snapshots
print_current_snapshots(RESTIC_REPO)

success, restored_id = restore_latest_clean_baseline(RESTIC_REPO, RESTORE_DIR)

"""##Step 14: Verify Restored File Exists and Matches Expected Content"""

# Commented out IPython magic to ensure Python compatibility.
# %%bash
# # 1. Point to your restore directory
# export RESTORE_DIR="/content/drive/MyDrive/ransomware_lab/restore"
# 
# # 2. Locate the nested victim_data folder
# VICTIM_PATH=$(find "$RESTORE_DIR" -type d -name victim_data | head -n1)
# if [ -z "$VICTIM_PATH" ]; then
#   echo "❌ Could not find victim_data under $RESTORE_DIR"
#   exit 1
# fi
# 
# echo "✅ Restored data is at: $VICTIM_PATH"
# 
# # 3. List the docs you recovered
# echo; echo "Recovered docs:"
# tree -h "$VICTIM_PATH/docs" | sed -n '1,5p'
# 
# # 4. Show the contents of report_Q1.txt
# echo; echo "Contents of report_Q1.txt:"
# cat "$VICTIM_PATH/docs/report_Q1.txt"

import pathlib, hashlib, sys

# Adjust this to your actual restore path variable if needed
restore_root = pathlib.Path(RESTORE_DIR)
victim = next(restore_root.rglob("victim_data"), None)
if victim is None:
    print("❌  victim_data not found!"); sys.exit(1)

file = victim / "docs" / "report_Q1.txt"
if not file.exists():
    print("❌  report_Q1.txt missing!"); sys.exit(1)

content = file.read_text()
assert "Quarterly revenue: $123,456" in content, "Content mismatch!"

sha = hashlib.sha256(file.read_bytes()).hexdigest()
print(f"✅  report_Q1.txt verified — SHA‑256: {sha[:12]}…")

"""##Step 15: Compare Original to Restored
Sanity Check
"""

# Commented out IPython magic to ensure Python compatibility.
# %%bash -s "$DATA_DIR" "$RESTORE_DIR"
# # $1 is the live data dir, $2 is where Restic put your restore tree
# ORIG="$1"
# RESTORE_ROOT="$2"
# 
# # 2. Locate the restored victim_data under RESTORE_ROOT
# RESTORED_V=$(find "$RESTORE_ROOT" -type d -name victim_data | head -n1)
# if [ -z "$RESTORED_V" ]; then
#   echo "❌  Could not find victim_data under $RESTORE_ROOT"
#   exit 1
# fi
# 
# echo "✅  Restored data is at: $RESTORED_V"
# echo
# 
# # 3. Compare original vs restored
# echo "Comparing live vs restored:"
# echo "  live:     $ORIG"
# echo "  restored: $RESTORED_V"
# echo
# 
# diff -rq "$ORIG" "$RESTORED_V" \
#   && echo "✅  No unexpected differences." \
#   || echo "🔶  Differences above are expected for encrypted docs."

"""##Step 16: Stop Background Producer and Watchdog"""

stop_event.set()               # stop producer loop
observer.stop(); observer.join()
print("✅ Real‑time components shut down")

print_current_snapshots(RESTIC_REPO)

"""##Optional: Prune Workspace
* Locating the deepest nested 'victim_data' directory inside restore_root
* Removing any '.enc' encrypted files
* Moving the restored data to the original victim_data_path
* Pruning the logs directory to keep only the latest .txt file
* Deleting all contents of the restore_root directory
"""

import os
import shutil
import pathlib

def finalize_restoration(restore_root: str, victim_data_path: str):
    restore_root = pathlib.Path(restore_root)
    victim_data_path = pathlib.Path(victim_data_path)

    # Locate the deepest nested victim_data directory
    nested_victim_dirs = sorted(restore_root.rglob("victim_data"), key=lambda p: len(str(p)), reverse=True)
    if not nested_victim_dirs:
        print("❌ No victim_data directory found in restore root.")
        return False

    restored_victim = nested_victim_dirs[0]
    print(f"✅ Found restored victim_data at: {restored_victim}")

    # Remove encrypted files
    for enc_file in restored_victim.rglob("*.enc"):
        try:
            enc_file.unlink()
            print(f"🗑️ Deleted encrypted file: {enc_file}")
        except Exception as e:
            print(f"⚠️ Failed to delete {enc_file}: {e}")

    # Replace original victim_data with restored version
    if victim_data_path.exists():
        shutil.rmtree(victim_data_path)
    shutil.copytree(restored_victim, victim_data_path)
    print(f"📦 Moved restored data to: {victim_data_path}")

    # Prune logs to keep only the latest .txt file
    logs_dir = victim_data_path / "logs"
    if logs_dir.exists():
        txt_files = sorted(logs_dir.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
        if txt_files:
            latest = txt_files[0]
            for f in txt_files[1:]:
                try:
                    f.unlink()
                    print(f"🗑️ Deleted old log file: {f.name}")
                except Exception as e:
                    print(f"⚠️ Failed to delete log file {f.name}: {e}")
            print(f"📝 Kept latest log file: {latest.name}")
        else:
            print("ℹ️ No .txt log files found to prune.")
    else:
        print("ℹ️ No logs directory found.")

    # Delete all contents of the restore_root directory
    for item in restore_root.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            print(f"🧹 Deleted: {item}")
        except Exception as e:
            print(f"⚠️ Failed to delete {item}: {e}")

    return True

if success:
  finalize_restoration(
      restore_root=RESTORE_DIR,
      victim_data_path=DATA_DIR
  )

# Commented out IPython magic to ensure Python compatibility.
# %%bash
# #!/bin/bash
# 
# # Define the root directory
# VICTIM_PATH="/content/drive/MyDrive/ransomware_lab/victim_data"
# RESTORE_PATH="/content/drive/MyDrive/ransomware_lab/restore"
# 
# # Check if the directory exists
# if [ ! -d "$VICTIM_PATH" ]; then
#   echo "❌ Directory not found: $VICTIM_PATH"
#   exit 1
# fi
# if [ ! -d "$RESTORE_PATH" ]; then
#   echo "❌ Directory not found: $RESTORE_PATH"
#   exit 1
# fi
# 
# # Print the tree with human-readable sizes
# echo "📁 Directory tree for: $VICTIM_PATH"
# echo
# 
# tree -h "$VICTIM_PATH"
# # Print the tree with human-readable sizes
# echo "📁 Directory tree for: $RESTORE_PATH"
# echo
# 
# tree -h "$RESTORE_PATH"