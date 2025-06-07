from .config import get_configs, set_config
from pynput import keyboard
import fire


key_to_hotkey_string = lambda key: f"<{key.name}>" if isinstance(key, keyboard.Key) else str(key.char)

def capture_hotkey():

    hotkeys = []
    print("Enter your desired hotkey combination. <cmd>+<shift>+<alt>+<space>: ")

    # def on_press(key):
    #     if key == keyboard.Key.enter:
    #         return False
    #     elif key == keyboard.Key.backspace and hotkeys:
    #         hotkeys.pop()
    #         print("\r" + " " * 80, end="", flush=True)
    #         print("\rHotkeys: " + "+".join(key_to_hotkey_string(k) for k in hotkeys), end="", flush=True)
    #     else:
    #         hotkeys.append(key)
    #         print("+" + key_to_hotkey_string(key), end="", flush=True)        

    with keyboard.Listener(on_press=on_press) as listener:  # type: ignore
        input()
        listener.join()
    
    return "+".join(key_to_hotkey_string(key) for key in hotkeys)




# def set(config_name, new_value=None):

#     if config_name == "hotkey":
        

#     set_config(config_name, new_value)

# def on_activate():
#     print("Command + B pressed!")


# with GlobalHotKeys({'<cmd>+b': on_activate}) as h:
#     h.join()



def run_cli():
    fire.Fire(capture_hotkey)
    

if __name__ == "__main__":
    run_cli()
