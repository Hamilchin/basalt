from basalt.core.config import get_configs
import os, shutil
from appdirs import user_cache_dir, user_config_dir

def clear_db():
    """
    Delete the flashcard database defined in the current Basalt configs.
    """
    configs = get_configs()
    db_path = os.path.join(configs["data_dir"], "flashcard_data.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted DB at: {db_path}")
    else:
        print("No DB file found to delete.")

def clear_cache():
    """
    Remove Basalt's cache directory (found via appdirs).
    """
    cache_path = user_cache_dir("basalt")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Deleted cache at: {cache_path}")
    else:
        print("No cache directory found.")

def clear_configs():
    """
    Remove the user‑specific Basalt configuration directory so that default
    configs are regenerated on the next run.
    """
    config_dir = user_config_dir("basalt")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
        print(f"Deleted configs at: {config_dir}")
    else:
        print("No configs directory found.")