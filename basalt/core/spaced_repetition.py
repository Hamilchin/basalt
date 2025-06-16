from basalt.core.database import FlashcardDB as db
from basalt.core.config import get_configs
from basalt.core.datetime_utils import dt_to_sql_timestamp, now_dt, datetime
from typing import List, Tuple



def review_flashcard(flashcard_id, score:int): #to avoid double-reviewing at start, call after every flashcard init with score=5. 
    configs = get_configs()
    data_dir = configs["data_dir"]
    with db(data_dir) as database:
        flashcard = database.get_card(flashcard_id)
        if flashcard: 

            rep_settings = database.get_folder_settings(flashcard["folder_id"])
            history = flashcard["rep_data"]["history"]
            now = now_dt()
            history.append((score, dt_to_sql_timestamp(now)))
            database.update_flashcard_fields(flashcard_id, {"rep_data": flashcard["rep_data"]})
            #rep_data has been mutated

            if rep_settings["algorithm"] == "sm2":
                sm2_settings = rep_settings["sm2_settings"]
                interval = get_interval_sm2(history, sm2_settings) #in hours
                next_due = now + datetime.timedelta(hours=interval)
                sql_next_due = dt_to_sql_timestamp(next_due)
                database.update_flashcard_fields(flashcard_id, {"next_due": sql_next_due})
            else:
                raise NotImplementedError(f"Other spaced repetition algorithm {rep_settings["algorithm"]} not supported yet!")

        else:
            raise ValueError(f"Missing flashcard requested to update: id {flashcard_id}")


def get_interval_sm2(
    history: List[Tuple[int, str]],
    sm2_settings: dict,
) -> float:
    """
    Compute the next review interval in *hours* for a card using the classic SM‑2 algorithm.

    Parameters
    ----------
    history : List[Tuple[int, str]]
        A chronological list of tuples (score, timestamp_str).  Only `score`
        (int 0‑5) is used.
    sm2_settings : dict
        Dictionary matching the keys described in README:
            unit_time (hours in one interval “day”)
            initial_intervals (list[int])  -- [I1, I2] e.g. [1, 6]
            initial_ease   (float)          -- starting EF
            min_ease       (float)          -- EF floor
            ease_bonus     (float)
            ease_penalty_linear (float)
            ease_penalty_quadratic (float)
            pass_threshold (int, default 3)

    Returns
    -------
    float
        Next interval expressed in *hours* (unit_time * interval_days).

    Raises
    ------
    ValueError
        If the history contains an invalid score or the settings are missing
        required keys.
    """
    # --- validate essential settings ---
    required_keys = (
        "unit_time",
        "initial_intervals",
        "initial_ease",
        "min_ease",
        "ease_bonus",
        "ease_penalty_linear",
        "ease_penalty_quadratic",
        "pass_threshold",
    )
    missing = [k for k in required_keys if k not in sm2_settings]
    if missing:
        raise ValueError(f"sm2_settings missing keys: {', '.join(missing)}")
    
    history = history.copy()
    history.insert(0, (5, "synthetic")) #add a "fake" initial review to represent creation.
    #changes [create] -1-> | -1-> | -6-> to [create] -1-> | -6->

    unit_time = sm2_settings["unit_time"]
    I1, I2 = sm2_settings["initial_intervals"]
    ease = sm2_settings["initial_ease"]
    min_ease = sm2_settings["min_ease"]
    pass_th = sm2_settings["pass_threshold"]

    reps = 0
    interval_days = I1  # will be overwritten on first successful review

    # --- iterate over past reviews in chronological order ---
    for score, _ in history:
        if not isinstance(score, int) or score < 0 or score > 5:
            raise ValueError(f"Invalid SM‑2 score {score}; must be int 0‑5")

        if score < pass_th:  # lapse
            reps = 0
            interval_days = I1
            # EF unchanged per original SM‑2
            continue

        # success ‑‑ update EF first
        delta = (
            sm2_settings["ease_bonus"]
            - (5 - score)
            * (
                sm2_settings["ease_penalty_linear"]
                + (5 - score) * sm2_settings["ease_penalty_quadratic"]
            )
        )
        ease = max(min_ease, ease + delta)

        # then update repetitions & interval
        if reps == 0:
            interval_days = I1
        elif reps == 1:
            interval_days = I2
        else:
            interval_days = round(interval_days * ease)

        reps += 1

    if not history:
        interval_days = I1

    return interval_days * unit_time
