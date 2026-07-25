#!/usr/bin/env python3
import sys
import json
import random
import subprocess
from datetime import datetime

PROJECTS_CONFIG = {
    "technical": 5,
    "system": 4,
    "yuko": 4,
    "life": 3,
    "radiant": 2,
    "re-l": 2,
}

def run_cmd(args):
    # Added rc.confirmation=no to ensure non-interactive adds succeed
    result = subprocess.run(["task", "rc.confirmation=no"] + args, capture_output=True, text=True)
    return result.stdout.strip()

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Check existing trackers
    status = run_cmd(["rc.verbose=nothing", "rc.hooks=off", "+carousel_tracker", "export"])
        
    if status:
        try:
            tasks = json.loads(status)
            if tasks:
                # Handle both list and single dict returns from old/new TW versions
                task_list = tasks if isinstance(tasks, list) else [tasks]
                for tracker in task_list:
                    if tracker.get("description") == f"Carousel Ran: {today_str}":
                        print("Carousel already ran today. Exiting.")
                        sys.exit(0)
                    else:
                        run_cmd(["rc.hooks=off", str(tracker["uuid"]), "delete"])
        except Exception as e:
            print(f"Error parsing tracker: {e}")

    project_names = list(PROJECTS_CONFIG.keys())
    project_weights = list(PROJECTS_CONFIG.values())
    selected_project = random.choices(project_names, weights=project_weights, k=1)[0]

    # Run and print output for debugging
    out1 = run_cmd(["rc.hooks=off", "add", f"=^-.-^= Neural Ordinance: {selected_project} project", "due:today", "+inbox", f"project:{selected_project}"])
    print("Add task output:", out1)

    out2 = run_cmd(["rc.hooks=off", "add", f"Carousel Ran: {today_str}", "+carousel_tracker", "status:completed"])
    print("Tracker task output:", out2)

if __name__ == "__main__":
    main()
