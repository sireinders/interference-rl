import itertools
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import tqdm

from utilities import Config # Number of UEs, positions, gNB
from user import UsersHandler # Traffic generator + channel/path-loss source for UEs
from apply_config import apply_config

# Preliminary execution: source ./rl_env/bin/activate

class InterferenceEnvironment(gym.Env):
    def __init__(self, global_config: Config) -> None:
        super(InterferenceEnvironment, self).__init__()
        self.gc = global_config
        self.user_handler = UsersHandler(self.gc)
        self.user_handler.initUsers()

        # Define State Space
        _, self.state = self.getState() # determine how much data environment returns
        obs_shape = len(self.state)
        self.observation_space = spaces.Box(low=0, high=10, shape=(obs_shape,))

        # Action Space - create list of all possible valid resource allocations
        self.createActionList()
        self.action_space = spaces.Discrete(len(self.actions_list))

    # Define all possible ways the bandwidth can be split between users
    # Output: single integer index mapping to one of the valid splits
    def createActionList(self):
        """
            Creates the discrete action space for the multi-gNB setup

            Virtual gNBs
            - gNB2 (User 1, User 2): agent decides PRB split
            - gNB3 (User 3, User 4): agent decides PRB split
            SDR gNB
            - gNB1 (User 0): Determined by remaining PRBs, not agent directly

            Constraints:
            1. Minimum 8 PRBs per active user (User 0, 1, 2, 3, 4)
            2. Total PRBs per gNB <= 52
        """
        self.actions_list = []

        # Step size
            # step = 1 --> ~500,000 actions
            # step = 2 --> ~36,000 actions
            # step = 4 --> ~3,000 actions
        step_size = 4

        max_prb = 52
        min_prb = 8
        
        # Valid Splits for Virtual gNB2
            # UE mins: 8, UE max: 44 to keep all UEs connected
        gnb2_splits = []
        for u1 in range(min_prb, max_prb - min_prb + 1, step_size):
            remaining_for_u2 = max_prb - u1
            for u2 in range(min_prb, remaining_for_u2 + 1, step_size):
                gnb2_splits.append((u1, u2))
       
        # Valid Splits for Virtual gNB3
        gnb3_splits = []
        for u4 in range(min_prb, max_prb - min_prb + 1, step_size):
            remaining_for_u5 = max_prb - u4
            for u5 in range(min_prb, remaining_for_u5 + 1, step_size):
                gnb3_splits.append((u4, u5))

        # Combine gNB2 and gNB3 splits
        combined_splits = list(itertools.product(gnb2_splits, gnb3_splits))
        self.actions_list = [x[0] + x[1] for x in combined_splits]
        

    def getState(self, continue_flag=True):
        state = []
        self.path_loss_config = []
        path_loss_norm_factor = 100.
        gen_size_norm_factor = 1.
        bit_rate_norm_factor = 1.

        # Generate current traffic demands
        task_queue = self.user_handler.generateTasks()

        # Ensure state vector is always [User0, User1, User2, User3, User4]
        task_queue.sort(key=lambda x: x["user_id"])
        
        for task in task_queue:
            # Store metadata for step()
            self.path_loss_config.append({"user_id": task["user_id"], 
                                          "gnb_id": task["gnb_id"],
                                          "task_type": task["task_type"], 
                                          "loss": task["path_loss"]
                                         })

            # Feature normalization
            if task["task_type"] in ['URLLC', 'mMTC_high', 'mMTC_low']:
                demand_norm = task["gen_size"] / self.gc.ue_task_gen_spec[task["task_type"]]["gen_bytes"]["max"]
            elif task["task_type"] == 'eMBB_high' or task["task_type"] == 'eMBB_low':
                demand_norm = task["bit_rate"] / self.gc.ue_task_gen_spec[task["task_type"]]["bit_rate"]["max"]
            else:
                raise ValueError("Invalid category")

            # Construct state vector: [Category num, Normalized demand, Normalized path loss]
            s = [
                self.gc.category_enum[task["task_type"]] * 1.0,
                demand_norm,
                task["path_loss"] / path_loss_norm_factor
            ]
            
            assert len(s) == 3 # Ensure exactly three features per user
            assert all([isinstance(x, float) for x in s]) # Ensure every feature is a float
            state.extend(s)
            
        return continue_flag, np.array(state, dtype=float)
    
    # Updated getAction function to include inter-cell interference
    def decodeActionAndCalcInterference(self, action_idx):
        # createActionList combines gnb2 (u1, u2) and gnb3 (u3, u4)
        # tuple structure = (u1, u2, u3, u4)
        u1, u2, u3, u4 = self.actions_list[action_idx]
        
        # 2. Calculate gNB1 (User 0) remaining PRBs
        gnb2_prbs_used = u1 + u2
        gnb3_prbs_used = u3 + u4
        gnb2_interference = max(0, gnb2_prbs_used - 30) # Change "30" depending on interference pattern
        gnb3_interference = max(0, gnb3_prbs_used - 30) # Change "30" depending on interference pattern

        u0_available = 52 - gnb2_interference - gnb3_interference
        u0 = max(8, u0_available) # 8 is minimum amount of PRBs to be allocated and remain connected
        
        # Format for apply_config
        # Map specific Users to their PRB counts
        allocation_dict = {
            1: {0: u0},          # Victim gNB (gNB1)
            2: {1: u1, 2: u2},   # Virtual gNB (gNB2)
            3: {3: u3, 4: u4}    # Virtual gNB (gNB3)
        }
        return allocation_dict

    def reset(self, seed=None, options=None):
        self.user_handler.initUsers()
        #self.userHandler.user_initialize()
        continue_flag, self.state = self.getState()
        # Convert state dictionary to numpy array
        return self.state, {}

    def step(self, action):
        # CHANGED: Use the new decoder
        action_dict = self.decodeActionAndCalcInterference(action)
        
        apply_config(action_dict, self.path_loss_config)
        reward = self.user_handler.executeTasks()
        continue_flag, self.state = self.getState()
        
        # Standard Gym Return
        return self.state, reward, not continue_flag, False, {}
    
    def render(self, mode='human'):
        # Render the environment (optional)
        pass
        
if __name__ == '__main__':
    env = InterferenceEnvironment(Config())
    for i in tqdm.tqdm(range(5000)):
        env.reset()
        done = False
        step_ctr = 0 # Used to force an end of an episode after a fixed number of steps (20)
        while not done and step_ctr < 20:
            sample = env.action_space.sample()
            state, reward, done, tmp1, tmp2 = env.step(sample)
            step_ctr += 1
