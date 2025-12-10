#!/usr/bin/env python3

import time
import datetime
import argparse
import signal
from lib.xAppBase import xAppBase
import json
import subprocess

class MyXapp(xAppBase):
    def __init__(self, config, http_server_port, rmr_port):
        super(MyXapp, self).__init__(config, http_server_port, rmr_port)
        pass

    def write_ue_id_to_file(self, ue_id):
        with open("/opt/xApps/ue_id.json", "w") as file:
            json.dump({"ue_id": ue_id}, file)

    def clear_ue_id_file(self):
        with open("/opt/xApps/ue_id.json", "w") as file:
            file.write("")

    def my_subscription_callback(self, e2_agent_id, subscription_id, indication_hdr, indication_msg, kpm_report_style, ue_id):
        if self.initilization:
            meas_data = self.e2sm_kpm.extract_meas_data(indication_msg)
            for ue_id, ue_meas_data in meas_data["ueMeasData"].items():
                dl = ue_meas_data["measData"]["DRB.UEThpDl"][0]
                
                # KEY FIX: Only consider UEs that are actively transmitting (dl > threshold)
                # and haven't been mapped yet
                if dl > 10 and ue_id not in self.mapped_ue_ids:
                    # Store this as a candidate for current user
                    if ue_id not in self.ue_candidates:
                        self.ue_candidates[ue_id] = {
                            'count': 0,
                            'total_dl': 0,
                            'first_seen': time.time()
                        }
                    
                    self.ue_candidates[ue_id]['count'] += 1
                    self.ue_candidates[ue_id]['total_dl'] += dl
                    
                    # If we see consistent high throughput, this is likely our UE
                    if self.ue_candidates[ue_id]['count'] >= 3:
                        self.current_user_id = ue_id
                        self.initial_detection = True
                
                # Track when current user finishes transfer
                if self.current_user_id is not None and self.current_user_id == ue_id:
                    if dl < 3 and self.initial_detection:
                        self.finished_transfer = True

        if self.log:
            meas_data = self.e2sm_kpm.extract_meas_data(indication_msg)
            for ue_id, ue_meas_data in meas_data["ueMeasData"].items():
                # Check if UE belongs to current gNB and slice being tested
                if ue_id in self.slice_group[self.slice]:
                    if self.counter > 0 or self.ue_dict[ue_id]["store"]:
                        dl = ue_meas_data["measData"]["DRB.UEThpDl"][0]
                        self.ue_dict[ue_id]["dl_thp"].append(dl)
                        if self.counter < 0 and dl < 3:
                            self.ue_dict[ue_id]["store"] = False
                            
                            # Find the top 3 values in self.ue_dict[ue_id]["dl_thp"] and average them
                            average_top_3 = sum(sorted(self.ue_dict[ue_id]["dl_thp"], reverse=True)[:3]) / 3
                            key = next((k for k, v in self.user_map.items() if v == ue_id), None)
                            self.result.append([key, average_top_3])
                            print(f"UE {key} (E2_ID: {ue_id}), gNB{self.current_gnb}, Avg DL Thp: {average_top_3:.2f} Mbps")

                            self.remaining_cnt -= 1
                            
                            if self.remaining_cnt % 3 == 0:
                                # Check next gNB
                                if self.current_gnb < 3:  # Testing with 3 gNBs
                                    self.current_gnb += 1
                                    
                                self.counter = 10
                                with open("/opt/xApps/ue_id.json", "w") as file:
                                    json.dump({
                                        "gnb": self.current_gnb
                                    }, file)
                                print(f"Switching to gNB{self.current_gnb}")

            self.counter -= 1

            if self.remaining_cnt == 0:
                print("=== All UEs are done ===")
                self.log = False
                self.clear_ue_id_file()
                with open("/opt/xApps/res.json", "w") as file:
                    data = []
                    for ue_id, ue_data in self.result:
                        data.append({
                            "id": int(ue_id),
                            "dl_thp": ue_data,
                        })
                    json.dump(data, file)
                    print(f"Results saved")
                            

    @xAppBase.start_function
    def start(self, e2_node_ids, ue_id):
        self.initilization = False
        self.log = False
        self.user_map = {}
        self.slice = None
        report_period = 125
        granul_period = 125
        ue_ids = [0, 1, 2, 3, 4]
        gnb_ue_ids = [[0], [1, 2], [3, 4]]
        subscription_callback = lambda agent, sub, hdr, msg: self.my_subscription_callback(agent, sub, hdr, msg, 5, None)
        
        count = 0  # FIX: Changed from 1 to 0 to match array indexing
        for e2_node_id in e2_node_ids:
            ues = gnb_ue_ids[count]
            self.e2sm_kpm.subscribe_report_service_style_5(
                e2_node_id, 
                report_period, 
                ues, 
                ["DRB.UEThpDl"], 
                granul_period, 
                subscription_callback
            )
            print(f"Subscribed to E2 node: {e2_node_id}")
            count+=1

        # Initialization: map logical UE IDs to actual E2 node UE IDs
        self.initilization = True
        self.mapped_ue_ids = set()  # Track which UE IDs we've already mapped
        
        print("=== Starting UE Initialization ===")
        print("NOTE: Ensure only ONE UE generates traffic at a time!")
        
        for user in ue_ids:
            print(f"\n--- Mapping UE {user+1} ---")
            
            # Reset detection variables
            self.current_user = user
            self.current_user_id = None
            self.finished_transfer = False
            self.initial_detection = False
            self.ue_candidates = {}  # Clear candidates for this UE
            
            # Signal traffic generator to start traffic for this UE
            self.write_ue_id_to_file(user+1)
            print(f"Signaled traffic generator for UE {user+1}")
            
            # Wait a bit for traffic to stabilize
            time.sleep(0.5)
            
            # Wait for UE to be detected (with timeout)
            timeout = 10  # 10 seconds timeout
            start_time = time.time()
            
            while not self.finished_transfer:
                if time.time() - start_time > timeout:
                    print(f"WARNING: Timeout waiting for UE {user+1} detection!")
                    print(f"  Candidates seen: {self.ue_candidates}")
                    # Try to use the best candidate if available
                    if self.ue_candidates:
                        best_candidate = max(self.ue_candidates.items(), 
                                            key=lambda x: x[1]['total_dl'])
                        self.current_user_id = best_candidate[0]
                        print(f"  Using best candidate: {self.current_user_id}")
                    break
                time.sleep(0.1)
            
            if self.current_user_id is not None:
                self.user_map[user+1] = self.current_user_id
                self.mapped_ue_ids.add(self.current_user_id)
                print(f"✓ UE {user+1} mapped to ephemeral gNB RNTI ID: {self.current_user_id}")
            else:
                print(f"✗ FAILED to map UE {user+1}!")
            
            # Small delay between UEs
            time.sleep(0.5)
            
        self.initilization = False
        self.clear_ue_id_file()
        
        print("\n=== UE Mapping Complete ===")
        for logical_id, rnti_id in sorted(self.user_map.items()):
            print(f"  UE {logical_id} -> RNTI {rnti_id}")
        
        # Verify we have unique mappings
        if len(set(self.user_map.values())) != len(self.user_map):
            print("\n⚠️  WARNING: Duplicate RNTI IDs detected!")
            print("  This likely means multiple UEs were generating traffic simultaneously")
            print("  or the traffic generator script has an issue.")
        
        # Define gNB-to-UE mapping
        self.gnb_slice_ue_mapping = {
            1: [self.user_map.get(1)],
            2: [self.user_map.get(2), self.user_map.get(3)],
            3: [self.user_map.get(4), self.user_map.get(5)]
        }
        
        print("\n=== gNB-UE Mapping ===")
        for gnb, ues in self.gnb_slice_ue_mapping.items():
            print(f"gNB{gnb}: {ues}")

        with open("/opt/xApps/alloc.json", "r") as file:
            last_content = json.load(file)
        self.ue_dict = {}
        self.remaining_cnt = 0
        
        while self.running:
            with open("/opt/xApps/alloc.json", "r") as file:
                current_content = json.load(file)
                if current_content != last_content:
                    print("=== New allocation detected ===")
                    with open("/opt/xApps/res.json", "w") as file:
                        file.write("")
                    last_content = current_content
                    self.result = []
                    
                    for item in current_content:
                        if "version" in item:
                            continue
                        ue_logical_id = int(item['id'])
                        if ue_logical_id not in self.user_map:
                            print(f"Warning: UE ID {ue_logical_id} not in user_map, skipping")
                            continue
                        
                        # Determine which gNB this UE belongs to
                        ue_gnb = None
                        for gnb, ues in self.gnb_slice_ue_mapping.items():
                            if self.user_map[ue_logical_id] in ues:
                                ue_gnb = gnb
                                break

                        if ue_gnb is None:
                            print(f"Warning: Could not determine gNB for UE {ue_logical_id}")
                            continue

                        # Get corresponding E2 node ID for gNB
                        e2_node_id = e2_node_ids[ue_gnb - 1]
                        
                        # Configure UE and reset current throughput
                        self.ue_dict[self.user_map[ue_logical_id]] = {
                            "dl_thp":[],
                            "store":True,
                        }
                        self.remaining_cnt += 1
                        
                        # Apply PRB quota control to specific gNB
                        print(f"Applying PRB control: UE {ue_logical_id} (RNTI {self.user_map[ue_logical_id]}) on gNB{ue_gnb}")
                        print(f"  E2 Node: {e2_node_id}, Min: {item['min_prb']}, Max: {item['max_prb']}, Ded: {item['ded_prb']}")
                        
                        try:
                            self.e2sm_rc.control_slice_level_prb_quota(
                                e2_node_id, 
                                ue_id=self.user_map[int(item['id'])], 
                                min_prb_ratio=int(item['min_prb']), 
                                max_prb_ratio=int(item['max_prb']), 
                                dedicated_prb_ratio=int(item['ded_prb']), 
                                ack_request=1
                            )
                            print(f"  ✓ Control message sent successfully")
                        except Exception as e:
                            print(f"  ✗ Control message failed: {e}")
                    
                    # Start with first gNB, first slice and iterate
                    self.current_gnb = 1
                    with open("/opt/xApps/ue_id.json", "w") as file:
                        json.dump({
                            "gnb": self.current_gnb
                        }, file)
                    self.log = True
                    self.counter = 10
                    print(f"Starting throughput measurement at gNB{self.current_gnb}...")
                    
                    while self.log:
                        time.sleep(0.3)

            time.sleep(0.3)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='xApp for 5UEs across 3 gNBs with eMBB/mMTC slicing')
    parser.add_argument("--config", type=str, default='', help="xApp config file path")
    parser.add_argument("--http_server_port", type=int, default=8090, help="HTTP server listen port")
    parser.add_argument("--rmr_port", type=int, default=4560, help="RMR port")
    parser.add_argument("--e2_node_ids", type=str, default='gnbd_001_001_000001_0,gnbd_001_001_000002_0,gnbd_001_001_000003_0', help="E2 Node IDs for gNB1, gNB2, gNB3 (comma-separated)")
    parser.add_argument("--ran_func_id", type=int, default=3, help="E2SM RC RAN function ID")
    parser.add_argument("--ue_id", type=int, default=0, help="UE ID")


    args = parser.parse_args()
    config = args.config
    
    # FIX: Parse comma-separated E2 node IDs
    e2_node_ids = args.e2_node_ids.split(',')
    
    ran_func_id = args.ran_func_id
    ue_id = args.ue_id

    print(f"E2 Node IDs: {e2_node_ids}")

    # Create MyXapp
    myXapp = MyXapp(config, args.http_server_port, args.rmr_port)
    myXapp.e2sm_rc.set_ran_func_id(ran_func_id)

    # Connect exit signals
    signal.signal(signal.SIGQUIT, myXapp.signal_handler)
    signal.signal(signal.SIGTERM, myXapp.signal_handler)
    signal.signal(signal.SIGINT, myXapp.signal_handler)

    # Start xApp with all E2 node IDs
    myXapp.start(e2_node_ids, ue_id)
