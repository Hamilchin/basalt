
from appdirs import user_config_dir, user_data_dir
import os, json, sys

config_dir = user_config_dir("basalt")
config_file_path = os.path.join(config_dir, "config.json")

def default_configs():
    return { 
        "data_dir" : user_data_dir("basalt"), #should look like /Users/alexanderchin/Library/Application Support/basalt
        "custom_prompt" : "Focus on the important ideas that will help me learn as much as possible. ",
        "custom_commands" : {
            "n" : "Please generate {} flashcards.", 
            "c" : "Include detailed explanations."
        },
        "hotkeys" : {
            "<cmd>+b" : "capture clip",
        },
        "provider" : None, 
        "model" : None,
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
    else:
        configs[config_name] = new_value #NEED TO ADD ERROR CHECKING LIKE DATA_DIR
    
    set_configs(configs)


def get_db_path():
    return os.path.join(get_configs()["data_dir"], "flashcard_data.db")