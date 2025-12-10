import json
import subprocess
import threading
import time
import os
import utilities

# Main function to process all tasks simultaneously
def process_tasks(tasks, pre_train=False):
    output_store = []
    start_time = 0.
    
    # List to store all threads
    threads = []
    
    if not pre_train:
        print("INFO: Applying the config and reading from the metrics")
        time.sleep(10)
        # Wait until the file is not empty
        path_metric_json = "/home/oai/oran-sc-ric/xApps/python/res.json"
        while os.stat(path_metric_json).st_size == 0:
            time.sleep(1)
        # Reading the metrics json
        with open(path_metric_json, "r") as file:
            metrics = json.load(file)
        for task in tasks:
            id = task["user_id"]
            for item in metrics:
                if item["id"] == id:
                    task["metrics"]["bit_rate"] = (item["dl_thp"] * 1e3) / 8    # Bytes / Sec
                    if task["task_type"] in ["URLLC", "mMTC_high", "mMTC_low"]:
                        gen_freq = task["gen_freq"]
                        gen_size = task["gen_size"]
                        total_bytes = int(gen_size * gen_freq * utilities.DATA_GATHERING_DURATION)
                        duration = total_bytes / task["metrics"]["bit_rate"]
                        task["metrics"]["duration"] = duration * 1000
                    
                    elif task["task_type"] == "eMBB_high" or task["task_type"] == "eMMB_low":
                        total_bytes = int(task["bit_rate"] * utilities.DATA_GATHERING_DURATION)
                        duration = total_bytes / task["metrics"]["bit_rate"]
                        task["metrics"]["duration"] = duration * 1000
        #print(tasks)
        # Empty the file
        #with open(path_metric_json, "w") as file:
            #file.write("")
    
    else:
        # Reading the PRB allocation json
        try:
            with open(utilities.ALLOCATION_SAVE_PATH, "r") as file:
                prb_alloc = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            prb_alloc = []
        
        # Convert list to dictionary for faster lookup: {user_id: ratio}
        alloc_map = {}
        for item in prb_alloc:
            if "id" in item and "max_prb_ratio" in item:
                alloc_map[item["id"]] = item["max_prb_ratio"]

        for task in tasks:
            user_id = task["user_id"]
            gnb_id = task["gnb_id"]

            # Find PRBs assigned to this user
            prb_ratio = alloc_map.get(user_id, 0) # Default to 0 if not found
            prb = int((prb_ratio / 100.0) * utilities.PRB_PER_GNB)
            
            tpt_bps = 0.0

            # SDR-based gNB1 (Hardware specific regression)
            if gnb_id == 1:
                tpt_bps = ((0.4341 * prb + 3.4841) * 1e6)
            # Virtual gNB2, gNB3 (Software specific regression)
            else:
                tpt_bps = ((0.1752 * prb - 0.0648) * 1e6)

            # Calculate duration/latency
            if task["task_type"] in ["URLLC", "mMTC_low", "mMTC_high"]:
                gen_freq = task.get("gen_freq", 1)
                gen_size = task.get("gen_size", 1000)

                total_bytes = int(gen_size * gen_freq * utilities.DATA_GATHERING_DURATION)
                bit_rate_bytes = tpt_bps / 8.
                duration = total_bytes / bit_rate_bytes
                task["metrics"]["duration"] = duration * 1000
                task["metrics"]["bit_rate"] = bit_rate_bytes
                # Retrive path loss for corresponding task/UE
                # path_loss = task["path_loss"]
                # Compute SINR in dB
                # p_tx_dbm = 23
                # n0_dbm = 0
                # sinr_db = p_tx_dbm - path_loss - n0_dbm
                # Convert SINR to linear scale
                #sinr_linear = 10 ** (sinr_db / 10)
                # Adjust Throughput using SINR/Shannon-Hartley Theorem ideal max for speed of channel
                # Capacity = Bandwidth * log_2(1 + SINR)
                # adjusted_tpt_byte_ps = bit_rate * math.log2(1 + sinr_linear)
            elif task["task_type"] == "eMBB_low" or task["task_type"] == "eMBB_high":
                total_bytes = int(task["bit_rate"] * utilities.DATA_GATHERING_DURATION)
                bit_rate_bytes = tpt_bps / 8.
                duration = total_bytes / bit_rate_bytes
                task["metrics"]["duration"] = duration * 1000
                task["metrics"]["bit_rate"] = bit_rate_bytes

    
def execute_tasks(task_queue, pre_train=False):
    # Process all tasks in the task queue
    process_tasks(task_queue, pre_train=pre_train)

if __name__ == "__main__":

    # Open and load the existing JSON data
    with open(utilities.ALLOCATION_SAVE_PATH, 'r') as file:
        data = json.load(file)

    # Add the new key-value pair
    data.append({"version": 1})

    # Write the updated data back to the JSON file
    with open(utilities.ALLOCATION_SAVE_PATH, 'w') as file:
        json.dump(data, file, indent=4)

    # Sample task queue -- Unit Test (not actual used)
    ''' Updated values to match task definition
        SDR-based eMBB UE: Target throughput of ~20Mbps
        Virtual eMBB UEs: Target throughput of ~3.5Mbps
        Virtual mMTC UEs: ???
    '''
    task_queue = [
        {"task_type": "eMBB_high", "gnb_id": 1, "user_id": 0, "bit_rate": 2500000, "metrics":{"duration": 0., "bit_rate": 0.}},
        #{"task_type": "mMTC_high", "gnb_id": 1, "user_id": 0, "gen_freq": 4, "gen_size": 35000, "metrics":{"duration": 0., "bit_rate": 0.}},
        {"task_type": "eMBB_low", "gnb_id": 2, "user_id": 1, "bit_rate": 437500, "metrics":{"duration": 0., "bit_rate": 0.}},
        {"task_type": "eMBB_low", "gnb_id": 2, "user_id": 2, "bit_rate": 437500, "metrics":{"duration": 0., "bit_rate": 0.}},
        {"task_type": "mMTC_low", "gnb_id": 3, "user_id": 3, "gen_freq": 4, "gen_size": 35000, "metrics":{"duration": 0., "bit_rate": 0.}},
        {"task_type": "mMTC_low", "gnb_id": 3, "user_id": 4, "gen_freq": 4, "gen_size": 35000, "metrics":{"duration": 0., "bit_rate": 0.}}
        #{"task_type": "URLLC", "user_id": 1, "gen_freq": 2, "gen_size": 150000, "metrics":{"duration": 0., "bit_rate": 0.}},
        #{"task_type": "URLLC", "user_id": 2, "gen_freq": 2, "gen_size": 150000, "metrics":{"duration": 0., "bit_rate": 0.}}
    ]
    
    # Process all tasks in the task queue
    execute_tasks(task_queue, pre_train=True)
    
    # Print the output store
    print("Result Metrics")

    for i, task in enumerate(task_queue):
        print(f"Task {i} (User {task['user_id']}): Rate={task['metrics']['bit_rate']:.2f} B/s, Dur={task['metrics']['duration']:.2f} ms")

'''
[{'user_id': 1, 'task_type': 'URLLC', 'gen_freq': 2, 'gen_size': 138524, 'bit_rate': None, 'position': {'x': 223.1149439056643, 'y': 340.4357161273778}, 'path_loss': 92.23861281784767, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 344033), 'metrics': {'duration': 71220.56555269923, 'bit_rate': 3890.0}}, 
{'user_id': 2, 'task_type': 'URLLC', 'gen_freq': 2, 'gen_size': 112556, 'bit_rate': None, 'position': {'x': 315.1712269424807, 'y': 210.06577808215002}, 'path_loss': 91.61332143320406, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 345472), 'metrics': {'duration': 68489.71644152366, 'bit_rate': 3286.8}}, 
{'user_id': 3, 'task_type': 'URLLC', 'gen_freq': 2, 'gen_size': 128393, 'bit_rate': None, 'position': {'x': -139.10686044496543, 'y': 348.69851975687}, 'path_loss': 91.53638210129385, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 348396), 'metrics': {'duration': 78121.69151201703, 'bit_rate': 3287.0}}, 
{'user_id': 4, 'task_type': 'URLLC', 'gen_freq': 2, 'gen_size': 140099, 'bit_rate': None, 'position': {'x': -490.8669563788944, 'y': 226.42336469985196}, 'path_loss': 94.70306530732384, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 349809), 'metrics': {'duration': 72030.33419023136, 'bit_rate': 3890.0}}, 
{'user_id': 5, 'task_type': 'eMBB', 'gen_freq': None, 'gen_size': None, 'bit_rate': 280962, 'position': {'x': -22.94657277017879, 'y': -36.762225420010566}, 'path_loss': 72.78296774541782, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 350463), 'metrics': {'duration': 142403.44652812977, 'bit_rate': 1973.0}}, 
{'user_id': 6, 'task_type': 'eMBB', 'gen_freq': None, 'gen_size': None, 'bit_rate': 234411, 'position': {'x': -337.48215884095987, 'y': 231.05437407671235}, 'path_loss': 92.28044582003527, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 350539), 'metrics': {'duration': 118845.5688501318, 'bit_rate': 1972.4}},
{'user_id': 7, 'task_type': 'eMBB', 'gen_freq': None, 'gen_size': None, 'bit_rate': 269395, 'position': {'x': -226.49926174393363, 'y': 31.819329223529564}, 'path_loss': 87.23220828560747, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 352318), 'metrics': {'duration': 136540.80081094778, 'bit_rate': 1973.0}}, 
{'user_id': 8, 'task_type': 'eMBB', 'gen_freq': None, 'gen_size': None, 'bit_rate': 287237, 'position': {'x': -131.74555265445173, 'y': 332.7639253228132}, 'path_loss': 91.12110589936103, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 352362), 'metrics': {'duration': 145583.88241256968, 'bit_rate': 1973.0}}, 
{'user_id': 9, 'task_type': 'mMTC', 'gen_freq': 4, 'gen_size': 49733, 'bit_rate': None, 'position': {'x': -479.6993290449984, 'y': 156.16077243274214}, 'path_loss': 94.10283449714406, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 352572), 'metrics': {'duration': 100837.38848337388, 'bit_rate': 1972.8}}, 
{'user_id': 10, 'task_type': 'mMTC', 'gen_freq': 4, 'gen_size': 36828, 'bit_rate': None, 'position': {'x': -216.93184360966535, 'y': 246.36536642042597}, 'path_loss': 90.37038417120971, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 355127), 'metrics': {'duration': 74663.96350734921, 'bit_rate': 1973.0}}, 
{'user_id': 11, 'task_type': 'mMTC', 'gen_freq': 4, 'gen_size': 45453, 'bit_rate': None, 'position': {'x': -358.9554829168398, 'y': -97.83595415532204}, 'path_loss': 91.45801410347642, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 355459), 'metrics': {'duration': 92150.02534211859, 'bit_rate': 1973.0}}, 
{'user_id': 12, 'task_type': 'mMTC', 'gen_freq': 4, 'gen_size': 45628, 'bit_rate': None, 'position': {'x': -4.422142625855685, 'y': -325.41309044908655}, 'path_loss': 90.29549934404088, 'time': datetime.datetime(2024, 11, 28, 16, 49, 45, 355805), 'metrics': {'duration': 92504.81500253422, 'bit_rate': 1973.0}}]
'''
