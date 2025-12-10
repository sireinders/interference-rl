import json
import utilities

def apply_config(action_dict, path_loss_config):
    # Initialize a list to keep track of allocated resources in the desired format
    allocation_results = []

    # Changed to match new srsRAN RIC resource allocation operation
    total_prbs_per_gnb = 52
    min_prb_ratio = 15 # <-- Need to test lower values to see if they still work
    dedicated_prb_ratio = 100
    
    # Group path_loss data by user_id
    ''' path_loss_config: [{"user_id": task["user_id"], 
                            "gnb_id": task["gnb_id"],
                            "task_type": task["task_type"], 
                            "loss": task["path_loss"]}] '''    
    user_metadata = {item['user_id']: item for item in path_loss_config}

    # Iterate through the action dictionary (gnb_1, gnb_2, gnb_3)
    for gnb_key, users_in_gnb in action_dict.items():
        # users_in_gnb: {user_id: prb_count}
        for user_id, prb_count in users_in_gnb.items():
            
            # Convert raw PRBs to a percentage of the total carrier bandwidth (52 PRBs)
            max_prb_ratio = (prb_count / total_prbs_per_gnb) * 100
            
            # Ensure ratio doesn't exceed 100% or drop below a functional floor
            max_prb_ratio = max(min_prb_ratio, min(100, max_prb_ratio))

            # Get the pathloss for this user from metadata
            loss = user_metadata[user_id]["loss"]

            # Append results for this RNTI/User ID
            allocation_results.append({
                "id": user_id,
                "min_prb_ratio": min_prb_ratio,
                "max_prb_ratio": int(max_prb_ratio),
                "ded_prb_ratio": dedicated_prb_ratio,
                "pathloss": loss
            })

    # Save the results to a JSON file
    with open(utilities.ALLOCATION_SAVE_PATH, 'w') as json_file:
        json.dump(allocation_results, json_file, indent=4)

if __name__ == "__main__":
    # Example usage:
    action_dict = {
        1: {0: 30},
        2: {1: 10, 2: 12},
        3: {3: 15, 4: 15}
    }

    path_loss_config = [
        {"user_id": 0, "task_type": "eMBB_high", "loss": 30},
       #{"user_id": 0, "task_type": "mMTC_high", "loss": 30},
        {"user_id": 1, "task_type": "eMBB_low", "loss": 40},
        {"user_id": 2, "task_type": "eMBB_low", "loss": 10},
        {"user_id": 3, "task_type": "mMTC_low", "loss": 5},
        {"user_id": 4, "task_type": "mMTC_low", "loss": 15},
    ]

    apply_config(action_dict, path_loss_config)