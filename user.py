import numpy as np
from datetime import datetime as T
import copy
import math

import wandb
import utilities

from task_executor import execute_tasks

class User:
    # Define user QoS and which gNB connected to
    def __init__(self, id: int, category: str, position: dict, gnb_id: int, GlobalConfig: dict) -> None:
        assert isinstance(id, int)
        self.id = id
        assert category in ['URLLC', 'eMBB_high', 'eMBB_low', 'mMTC_high', 'mMTC_low']
        self.category = category
        self.gc = GlobalConfig
        
        self.history = []
        self.gnb_id = gnb_id # Track which gNB user belongs to

        if self.gnb_id == 1:
            self.position = {"x": np.random.uniform(self.gc.gnb1_ue_position_bound["x"]["min"], 
                                                    self.gc.gnb1_ue_position_bound["x"]["max"]),
                            "y": np.random.uniform(self.gc.gnb1_ue_position_bound["y"]["min"],
                                                    self.gc.gnb1_ue_position_bound["y"]["max"])}
        elif self.gnb_id == 2:
            self.position = {"x": np.random.uniform(self.gc.gnb2_ue_position_bound["x"]["min"], 
                                                    self.gc.gnb2_ue_position_bound["x"]["max"]),
                            "y": np.random.uniform(self.gc.gnb2_ue_position_bound["y"]["min"],
                                                    self.gc.gnb2_ue_position_bound["y"]["max"])}
        else: # self.gnb_id == 3
            self.position = {"x": np.random.uniform(self.gc.gnb3_ue_position_bound["x"]["min"], 
                                                    self.gc.gnb3_ue_position_bound["x"]["max"]),
                            "y": np.random.uniform(self.gc.gnb3_ue_position_bound["y"]["min"],
                                                    self.gc.gnb3_ue_position_bound["y"]["max"])}
            
        self.velocity = {"x": np.random.uniform(self.gc.ue_velocity_bound["x"]["min"],
                                                self.gc.ue_velocity_bound["x"]["max"]),
                         "y": np.random.uniform(self.gc.ue_velocity_bound["y"]["min"],
                                                self.gc.ue_velocity_bound["y"]["max"])}
    
        self.path_loss = 0.
        self.calculatePathLoss()
        self.metrics_last_step = {}
        self.time = T.now()

    # Calculate path loss in dB based on the distance between the user and the gNB
    def calculatePathLoss(self) -> None:
        gnb_x = self.gc.gnbs[self.gnb_id]["pos"]["x"]
        gnb_y = self.gc.gnbs[self.gnb_id]["pos"]["y"]
        
        distance = np.sqrt((self.position["x"] - gnb_x)**2 + \
                           (self.position["y"] - gnb_y)**2)

        # Calculate Path Loss in dB
        # FSPL [dB] = 20log10(d_m) + 60 + 20log10(4*np.pi*f_dl/c)
        #
        # 60 is a conversion factor given distance is expressed in m, not km
        #
        # For f_dl = 1842.5 MHz, c = 299,792,458 m/s this reduces to:
        distance = max(distance, 1.0) # Avoid log(0) errors if user on top of gNB
        
        path_loss = 20 * math.log10(distance) + 37.75 # Changed from 1805MHz value ~ 37.58
        self.path_loss = path_loss
    
    # Updates the position of the user based on the velocity and the elapsed time
    # The user is bounded by its gNB's global configuration dimensions
    # Also calculates the updated position path loss
    def updatePosition(self) -> None:
        elapsed_time = (T.now() - self.time).total_seconds()
        self.time = T.now()
        inBound = False
        while not inBound:
            new_x = self.position["x"] + self.velocity["x"] * elapsed_time
            new_y = self.position["y"] + self.velocity["y"] * elapsed_time
            if self.gnb_id == 1:
                if self.gc.gnb1_ue_position_bound["x"]["min"] <= new_x <= self.gc.gnb1_ue_position_bound["x"]["max"] and \
                   self.gc.gnb1_ue_position_bound["y"]["min"] <= new_y <= self.gc.gnb1_ue_position_bound["y"]["max"]:
                    inBound = True
                    self.position["x"] = new_x
                    self.position["y"] = new_y
                else:
                    self.velocity = {"x": np.random.uniform(self.gc.ue_velocity_bound["x"]["min"],
                                                            self.gc.ue_velocity_bound["x"]["max"]),
                                    "y": np.random.uniform(self.gc.ue_velocity_bound["y"]["min"],
                                                        self.gc.ue_velocity_bound["y"]["max"])}
            elif self.gnb_id == 2:
                if self.gc.gnb2_ue_position_bound["x"]["min"] <= new_x <= self.gc.gnb2_ue_position_bound["x"]["max"] and \
                   self.gc.gnb2_ue_position_bound["y"]["min"] <= new_y <= self.gc.gnb2_ue_position_bound["y"]["max"]:
                    inBound = True
                    self.position["x"] = new_x
                    self.position["y"] = new_y
                else:
                    self.velocity = {"x": np.random.uniform(self.gc.ue_velocity_bound["x"]["min"],
                                                            self.gc.ue_velocity_bound["x"]["max"]),
                                    "y": np.random.uniform(self.gc.ue_velocity_bound["y"]["min"],
                                                        self.gc.ue_velocity_bound["y"]["max"])}
            else: # self.gnb_id == 3
                if self.gc.gnb3_ue_position_bound["x"]["min"] <= new_x <= self.gc.gnb3_ue_position_bound["x"]["max"] and \
                   self.gc.gnb3_ue_position_bound["y"]["min"] <= new_y <= self.gc.gnb3_ue_position_bound["y"]["max"]:
                    inBound = True
                    self.position["x"] = new_x
                    self.position["y"] = new_y
                else:
                    self.velocity = {"x": np.random.uniform(self.gc.ue_velocity_bound["x"]["min"],
                                                            self.gc.ue_velocity_bound["x"]["max"]),
                                    "y": np.random.uniform(self.gc.ue_velocity_bound["y"]["min"],
                                                        self.gc.ue_velocity_bound["y"]["max"])}
        self.calculatePathLoss()

    # Generates a task for the user based on the category
    # Also updates the position of the user and the path loss
    def generateTask(self) -> dict:
        self.metrics_last_step = {"duration": 0., "bit_rate": 0.}
        gen_freq = None
        gen_size = None
        bit_rate = None

        if self.category == 'URLLC':
            gen_freq = np.random.randint(self.gc.ue_task_gen_spec["URLLC"]["gen_freq"]["min"],
                                         self.gc.ue_task_gen_spec["URLLC"]["gen_freq"]["max"]+1)
            assert isinstance(gen_freq, int)
            gen_size = np.random.randint(self.gc.ue_task_gen_spec["URLLC"]["gen_bytes"]["min"],
                                         self.gc.ue_task_gen_spec["URLLC"]["gen_bytes"]["max"]+1)
            assert isinstance(gen_size, int)
        elif self.category == 'eMBB_high':
            bit_rate = np.random.randint(self.gc.ue_task_gen_spec["eMBB_high"]["bit_rate"]["min"],
                                         self.gc.ue_task_gen_spec["eMBB_high"]["bit_rate"]["max"]+1)
            assert isinstance(bit_rate, int)
        elif self.category == 'eMBB_low':
            bit_rate = np.random.randint(self.gc.ue_task_gen_spec["eMBB_low"]["bit_rate"]["min"],
                                         self.gc.ue_task_gen_spec["eMBB_low"]["bit_rate"]["max"]+1)
            assert isinstance(bit_rate, int)
        elif self.category == 'mMTC_high':
            gen_freq = np.random.randint(self.gc.ue_task_gen_spec["mMTC_high"]["gen_freq"]["min"],
                                         self.gc.ue_task_gen_spec["mMTC_high"]["gen_freq"]["max"]+1)
            assert isinstance(gen_freq, int)
            gen_size = np.random.randint(self.gc.ue_task_gen_spec["mMTC_high"]["gen_bytes"]["min"],
                                         self.gc.ue_task_gen_spec["mMTC_high"]["gen_bytes"]["max"]+1)
            assert isinstance(gen_size, int)
        elif self.category == 'mMTC_low':
            gen_freq = np.random.randint(self.gc.ue_task_gen_spec["mMTC_low"]["gen_freq"]["min"],
                                         self.gc.ue_task_gen_spec["mMTC_low"]["gen_freq"]["max"]+1)
            assert isinstance(gen_freq, int)
            gen_size = np.random.randint(self.gc.ue_task_gen_spec["mMTC_low"]["gen_bytes"]["min"],
                                         self.gc.ue_task_gen_spec["mMTC_low"]["gen_bytes"]["max"]+1)
            assert isinstance(gen_size, int)
        else:
            raise ValueError("Invalid category")
        
        self.task = {
                    "user_id": self.id,
                    "gnb_id": self.gnb_id,
                    "task_type": self.category, 
                    "gen_freq": gen_freq, 
                    "gen_size": gen_size, 
                    "bit_rate": bit_rate,
                    "position": self.position,
                    "path_loss": self.path_loss,
                    "time": self.time,
                    "metrics": self.metrics_last_step
                    }
        return self.task

# Need to update UsersHandler with relavent info for 3 gNBs
class UsersHandler:
    def __init__(self, GlobalConfig: dict, save=False, path_to_save="") -> None:
        self.gc = GlobalConfig

    def initUsers(self) -> None:
        self.users = []
        self.task_queue = []
        self.users_history = []

        for scenario in self.gc.user_scenarios:
            new_user = User(
                id=scenario["user_id"],
                category=scenario["type"],
                position=scenario["pos"],
                gnb_id=scenario["gnb_id"],
                GlobalConfig=self.gc
            )
            self.users.append(new_user)

    def generateTasks(self) -> list:
        self.task_queue = []
        for user in self.users:
            self.task_queue.append(user.generateTask())
        return self.task_queue
    
    def executeTasks(self) -> float:
        # Pass the queue to the Physics/Network Simulator
        execute_tasks(self.task_queue, pre_train=utilities.PRE_TRAIN)
        
        # Save history for offline training data
        self.users_history.append(copy.deepcopy(self.task_queue))
        return self.calculateReward()

    def calculateReward(self) -> float:
        reward = 0.
        for user in self.users:
            if user.category == 'URLLC':
                # Average interval in ms
                number_of_sent_buffers = user.task["gen_freq"] * utilities.DATA_GATHERING_DURATION
                avg_buffer_transmission_time = user.task["metrics"]["duration"] / number_of_sent_buffers
                m = (self.gc.ue_task_gen_spec["URLLC"]["send_ms"] - avg_buffer_transmission_time) / self.gc.ue_task_gen_spec["URLLC"]["send_ms"]
                reward += np.max([ -1.0, np.min([0., m])])
            elif user.category == 'eMBB_high' or user.category == 'eMBB_low':
                # Average bandwidth in Bytes/sec
                total_bytes = user.task["bit_rate"] * utilities.DATA_GATHERING_DURATION * 1. # Expected
                avg_bandwidth = total_bytes / (user.task["metrics"]["duration"] / 1000) # Actual - duration indicates how long it ACTUALLY took to get this amount of data
                m = (avg_bandwidth - user.task["bit_rate"]) / user.task["bit_rate"]
                reward += np.max([ -1.0, np.min([0., m])])
            elif user.category == 'mMTC_high' or user.category == 'mMTC_low':
                expected_bytes = user.task["gen_size"] * user.task["gen_freq"] * utilities.DATA_GATHERING_DURATION # Expected
                got_bytes = expected_bytes * (utilities.DATA_GATHERING_DURATION / (user.task["metrics"]["duration"] / 1000)) # Actual
                m = (got_bytes - expected_bytes) / expected_bytes
                reward += np.max([ -1.0, np.min([0., m])])
            else:
                raise ValueError("Invalid category [reward calculation]")
        if wandb.run is not None:
            wandb.log({"reward": reward})
        # print(reward)
        return reward
