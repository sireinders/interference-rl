#!/usr/bin/env python3

import json
import subprocess
import time
import os

def read_json():
    try:
        with open("./ue_id.json", "r") as file:
            content = file.read().strip()
            if not content:  # Check if file is empty
                return {}
            data = json.loads(content)
            #return data.get("ue_id", None)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def kill_all_iperf():
    """Kill any running iperf processes to ensure clean state"""
    try:
        subprocess.run("pkill -9 iperf", shell=True, stderr=subprocess.DEVNULL)
    except:
        pass

def main():
    gnb_to_ues = {
        1: [1],     # gNB1 eMBB users
        2: [2, 3],  # gNB2 eMBB users
        3: [4, 5]   # gNB3 mMTC users
    }
    
    last_read = read_json()

    print("=== Traffic Generator Started ===")
    print("Monitoring for UE/slice changes...")
    
    while True:
        current_read = read_json()
        
        if current_read != last_read and current_read:
            # Check if UE_ID present (initialization phase - ONE UE at a time)
            ue_id = current_read.get("ue_id", None)
            if ue_id is not None:
                print(f"\n[INIT] Starting traffic for UE {ue_id}")
                
                # Kill any existing iperf to ensure clean state
                kill_all_iperf()
                time.sleep(0.2)
                
                # Generate traffic for THIS UE ONLY
                target_ip = f"10.45.1.{ue_id}"
                command = f"iperf -c {target_ip} -u -t 2 -b 5M"
                
                print(f"  Command: {command}")
                proc = subprocess.Popen(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                    print(f"  ✓ Traffic generation complete for UE {ue_id}")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print(f"  ✗ Command timed out for UE {ue_id}")
                
                # Ensure process is dead
                kill_all_iperf()
                
                last_read = current_read
            
            # Check for gNB (measurement phase - multiple UEs)
            gnb_id = current_read.get("gnb", None)
            
            if gnb_id is not None and gnb_id in gnb_to_ues:
                print(f"\n[MEASURE] Starting traffic for gNB {gnb_id}")
                
                # Kill existing iperf
                kill_all_iperf()
                time.sleep(0.2)
                
                ue_list = gnb_to_ues[gnb_id]
                print(f"  UEs: {ue_list}")
                
                # Start traffic for all UEs on this gNB
                processes = []
                for ue_logical_id in ue_list:
                    target_ip = f"10.45.1.{ue_logical_id}"
                    command = f"iperf -c {target_ip} -u -t 2 -b 5M"
                    
                    print(f"    Starting traffic to UE {ue_logical_id}: {target_ip}")
                    proc = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    processes.append(proc)
                
                # Wait for all processes to complete
                for i, proc in enumerate(processes):
                    try:
                        proc.wait(timeout=5)
                        print(f"    ✓ UE {ue_list[i]} traffic complete")
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        print(f"    ✗ UE {ue_list[i]} timed out")
                
                kill_all_iperf()
                last_read = current_read
        
        time.sleep(0.1)  # Reduced sleep for faster response

if __name__ == "__main__":
    main()
