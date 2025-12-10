ALLOCATION_SAVE_PATH = './alloc.json' # Change when move to real environment
DATA_GATHERING_DURATION = 1  # in seconds
DATA_GATHERING_TIMEOUT = 50  # in seconds
NUM_RETRIES = 5
PRE_TRAIN = True
PRB_PER_GNB = 52

class Config:
    def __init__(self):
        
        # Define gNBs and locations for proper interference
        self.gnbs = {
            1: {"pos": {"x": 0., "y": 0.}, "type": "SDR", "total_prb": 52, "total_BW": 10},
            2: {"pos": {"x": 250., "y": 433.}, "type": "virtual", "total_prb": 52, "total_BW": 10},
            3: {"pos": {"x": 500., "y": 0.}, "type": "virtual", "total_prb": 52, "total_BW": 10}
        }

        # UE Position bound in meters for each gNB
        self.gnb1_ue_position_bound = {"x": {"min": 75., "max": 175.},
                                  "y": {"min": 160., "max": 260.}}
        self.gnb2_ue_position_bound = {"x": {"min": 200., "max": 300.},
                                  "y": {"min": 100., "max": 200.}}
        self.gnb3_ue_position_bound = {"x": {"min": 200., "max": 300.},
                                  "y": {"min": -50., "max": 50.}}

        # UE velocity bound in m/s
        self.ue_velocity_bound = {"x": {"min": -10., "max": 10.},
                                  "y": {"min": -10., "max": 10.}}

        # Interference masks
        # PRBs are 0-indexed (0 to 51)
        self.interference_pairs = [
            {
                "aggressor_gnb": 2,
                "victim_gnb": 1,
                "aggressor_prbs": range(30, 52), # If gNB2 uses these...
                "victim_prbs":    range(0, 22)   # ...gNB1 cannot use these.
            },
            {
                "aggressor_gnb": 3,
                "victim_gnb": 1,
                "aggressor_prbs": range(30, 52), # If gNB3 uses these...
                "victim_prbs":    range(30, 52)   # ...gNB1 cannot use these.
            }
        ]
        
        # Explicitly map user ID -> gNB -> location -> slice type
        # Position are chosen to be relatively close to their serving gNB -- may need to adjust
        self.user_scenarios = [
            # gNB 1 User (SDR-based)
            {"user_id": 0, "gnb_id": 1, "type": "eMBB_high", "pos": {"x": 250., "y": 144.}},
            # {"user_id": 0, "gnb_id": 1, "type": "mMTC_high", "pos": {"x": 250., "y": 144.}},

            # gNB 2 User (Virtual)
            {"user_id": 1, "gnb_id": 2, "type": "eMBB_low", "pos": {"x": -450., "y": 10.}},
            {"user_id": 2, "gnb_id": 2, "type": "eMBB_low", "pos": {"x": -480., "y": -10.}},

            # gNB 3 User (Virtual)
            {"user_id": 3, "gnb_id": 3, "type": "mMTC_low", "pos": {"x": 480., "y": 10.}},
            {"user_id": 4, "gnb_id": 3, "type": "mMTC_low", "pos": {"x": 520., "y": -10.}}
        ]

        # Task generation specifications
        # gen_freq: generation frequency in Seconds (Hz)
        # gen_bytes: number of Bytes to generate (Bytes)
        # bit_rate: bit rate in Bytes per second (Bytes/s)
        self.ue_task_gen_spec = {"URLLC": {"gen_freq": {"min": 2, "max":2}, "gen_bytes": {"min": 1e5, "max": 2e5}, "send_ms": 500.},
                                 "eMBB_high": {"bit_rate": {"min": 625e3, "max": 30e5}}, # 5Mbps - 24Mbps
                                 "eMBB_low": {"bit_rate": {"min": 1875e2, "max": 10625e2}}, # 1.5Mbps - 8.5Mbps
                                 "mMTC_high": {"gen_freq": {"min": 4, "max": 4}, "gen_bytes": {"min": 25e3, "max": 50e3}}, # Need to update value to match problem def
                                 "mMTC_low": {"gen_freq": {"min": 4, "max": 4}, "gen_bytes": {"min": 25e3, "max": 50e3}}   # Need to update
                                }
        
        self.category_enum = {"URLLC": 0, "eMBB_high": 1, "eMBB_low": 2, "mMTC_high": 3, "mMTC_low": 4}
        self.total_ue_num = len(self.user_scenarios)
        
        self.data_gathering_duration = 10  # in seconds
