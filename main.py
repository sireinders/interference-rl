import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
import torch
import wandb
from stable_baselines3.common.callbacks import BaseCallback
from wandb.integration.sb3 import WandbCallback
import os
from gymnasium.wrappers import TimeLimit

from environment import InterferenceEnvironment 
from utilities import Config

class CheckpointCallback(BaseCallback):
    """
    Custom callback for saving a model every N steps.
    """
    def __init__(self, save_freq: int, save_path: str, verbose: int = 0):
        super().__init__(verbose)
        self.save_freq = save_freq
        self.save_path = save_path

    def _on_step(self) -> bool:
        # Save the model periodically (not every single step, which is too much I/O)
        if self.n_calls % self.save_freq == 0:
            save_file = os.path.join(self.save_path, f"model_step_{self.n_calls}")
            self.model.save(save_file)
            if self.verbose > 0:
                print(f"Saved model to {save_file}")
        return True
    
def run_experiment(conf: dict):
    project_name = "PRB_ALLOCATION_MULTI_GNB"
    
    # Setup Experiment Folder
    i = 1
    while os.path.exists(f"./Experiment/{i}"):
        i += 1
    path = f"./Experiment/{i}"
    os.makedirs(path, exist_ok=True)
    os.makedirs(f"{path}/checkpoints", exist_ok=True) # Subfolder for checkpoints

    # Init WandB
    run = wandb.init(project=project_name, 
                     config=conf,
                     sync_tensorboard=True,
                     save_code=True,
                     mode="online",
                     name=f"Exp_{i}_Interference",)
    
    # Initialize Environment
    env = InterferenceEnvironment(Config())
    env = TimeLimit(env, max_episode_steps=100) # force episode to end after 100 steps, monitor produces total reward for 100 steps
    env = Monitor(env) # Wraps env to track rewards for SB3 and WandB

    # Setup Callbacks
    # Save model every 1000 steps
    checkpoint_callback = CheckpointCallback(save_freq=1000, save_path=f"{path}/checkpoints", verbose=1)
    wandb_callback = WandbCallback(verbose=2, gradient_save_freq=100, model_save_path=f"{path}/wandb_models", log="all")
    
    # Initialize PPO Agent
    # We use MlpPolicy because our state is a vector of numbers (not an image).
    model = PPO(
        "MlpPolicy", 
        env, 
        n_steps=2048,       # Buffer size (standard PPO default)
        batch_size=64,      # Minibatch size
        n_epochs=20,        # How many times to re-use data
        learning_rate=1e-3, # Learn faster (3e-4) 
        ent_coef=0.01,
        verbose=1, 
        tensorboard_log=f"{path}/tensorboard/"
    )

    print(f"Starting training on device: {model.device}")

    # Training Loop
    # We train in "Sessions". Each session adds more experiences to the agent.
    for i in range(conf["total_sessions"]):
        print(f"--- Starting Session {i+1}/{conf['total_sessions']} ---")
        
        # Train
        model.learn(
            total_timesteps=conf["timesteps_per_session"], 
            callback=[wandb_callback, checkpoint_callback],
            reset_num_timesteps=False # Keep learning accumulation
        )
        
        # Save Session Model
        model.save(path + f"/model_session_{i}")
        
    run.finish()
    env.close()

if __name__ == "__main__":
    # Updated config
    conf = {
        "total_users": 5,           # Updated to match Config.user_scenarios
        "timesteps_per_session": 5000, # Increased from 20 to 5000 (RL needs data!)
        "total_sessions": 10,       # 10 sessions * 5000 steps = 50,000 total training steps
        "algorithm": "PPO",
        "env_type": "Interference_3gNB"
    }
    
    # Ensure utilities.PRE_TRAIN is True for simulation!
    import utilities
    utilities.PRE_TRAIN = True 
    print(f"Training Mode (Simulation): {utilities.PRE_TRAIN}")
    
    run_experiment(conf)
