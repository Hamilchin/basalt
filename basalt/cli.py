from .config import get_configs, set_config
from .core import capture
from pynput import keyboard
import fire, sys, json

def set(config_name, new_value=None):

    if config_name == "hotkey":
        hk_string = input("Enter your desired hotkey combination. <cmd>+<shift>+<alt>+<space>+b: ")
        hk_string = hk_string.strip()
        try: keyboard.HotKey.parse(hk_string) 
        except:
            print(f"Error: '{hk_string}' is not a valid path"); 
            sys.exit(1)
        
        new_value = hk_string

    set_config(config_name, new_value)

def list(to_list):
    if to_list not in ("config", "configs", "cards"):
        print(f"Error: '{to_list}' not recognizable"); 
        sys.exit(1)
    if to_list in ("config", "configs"):
        print(json.dumps(get_configs(), indent=2))


def run_cli():
    sys.argv = ["-"+arg if len(arg) == 2 and arg[0]=="-" else arg for arg in sys.argv] #hacky, fix?

    fire.Fire({
    "set": set,
    "list": list,
    "capture": capture,
    })
    

if __name__ == "__main__":

    run_cli()
