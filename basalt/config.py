
from appdirs import user_config_dir, user_data_dir
import os, json, fire
import sys


config_dir = user_config_dir("basalt")
config_file_path = os.path.join(config_dir, "config.json")

def default_configs():
    return { 
        "data_dir" : user_data_dir("basalt"), 
        "hotkey" : "<cmd>+b", 
        "prompt" : None,
        "api_endpoint" : None, 
        "api_key" : None
        }

def get_configs():

    if os.path.exists(config_file_path):
        with open(config_file_path, "r") as f: 
            configs = json.loads(f.read())

    else:
        configs = default_configs()
        set_configs(configs)

    return configs


def set_configs(configs):

    os.makedirs(config_dir, exist_ok=True)

    with open(config_file_path, "w") as f:
        json.dump(configs, f, indent=2)


def set_config(config_name, new_value):

    configs = get_configs()
    config_names = [c for c in default_configs()]

    if config_name not in config_names:
        print(f"Error: '{config_name}' is not a valid configuration option.")
        sys.exit(1)
    elif config_name == "data_dir":
        if os.path.exists(new_value):
            configs["data_dir"] = os.path.abspath(new_value)
        else:
            print(f"Error: '{new_value}' is not a valid path")
            sys.exit(1)
    elif config_name == "hotkey":
        configs["hotkey"] = new_value
    
    set_configs(configs)