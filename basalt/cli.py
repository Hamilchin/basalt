from basalt.config import get_configs, set_config
from pynput import keyboard
from ipc_client import send_job
from pyperclip import paste
import fire, sys, json

def set(config_name, new_value=None):
    if config_name == "hotkey":
        hk_string = input("Enter your desired hotkey combination. <cmd>+<shift>+<alt>+<space>+b: ")
        hk_string = hk_string.strip()
        try: keyboard.HotKey.parse(hk_string) 
        except:
            print(f"Error: '{hk_string}' is not a valid path", file=sys.stderr); 
            sys.exit(1)
        new_value = hk_string
    set_config(config_name, new_value)

def list(to_list):
    if to_list not in ("config", "configs", "cards"):
        print(f"Error: '{to_list}' not recognizable"); 
        sys.exit(1)
    if to_list in ("config", "configs"):
        print(json.dumps(get_configs(), indent=2))

    

def capture(input, file_path=None, **user_inputs):
    configs = get_configs()
    custom_commands = configs["custom_commands"]

    valid_inputs = {key:value for key, value in user_inputs if key in custom_commands}

    if len(valid_inputs) < len(user_inputs):
        invalid_flags = [key for key in user_inputs if key not in custom_commands]
        print(f"Error: unrecognized flags: {', '.join(invalid_flags)}", file=sys.stderr)
        sys.exit(1)

    if input == "file":
        if not file_path: 
            print(f"Error: no file path provided", file=sys.stderr)
            sys.exit(1)
        else:
            try: 
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
            except:
                print(f"Error: file does not exist or cannot be read", file=sys.stderr)
                sys.exit(1)

    elif input == "clip":
        try:
            content = paste()
            if not content.strip():
                print("Clipboard is empty", file=sys.stderr)
                sys.exit(1)
        except:
            print("Error: clipboard could not be accessed", file=sys.stderr)
            sys.exit(1)

    else:
        content = input
        if not content.strip():
            print("No text provided", file=sys.stderr)
            sys.exit(1)

    send_job(
        {"content" : content, 
         "user_inputs" : user_inputs, 
         "configs": configs}
        )

    


    


def run_cli():
    new_argv = []
    for arg in sys.argv: #hacky stuff for fire
        if arg.startswith("-") and not arg.startswith("--"):
            if len(arg) == 2:
                new_argv.append(f"--{arg[1:]}")
            else:  # bundled: -not -> --n --o --t
                new_argv.extend(f"--{c}" for c in arg[1:])
        else:
            new_argv.append(arg)

    sys.argv = new_argv

    fire.Fire({
        "set": set,
        "list": list,
        "capture": capture,
        })
    

if __name__ == "__main__":
    run_cli()
