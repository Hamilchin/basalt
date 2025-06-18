import sqlite3, json, os

def make_default_rep_data():
    return {
    "history" : []
    }

DEFAULT_FOLDER_SETTINGS = {
    "algorithm" : "sm2", 
    "sm2_settings": {
        "unit_time": 24,
        "initial_intervals": [1, 6],
        "initial_ease": 2.5,
        "min_ease": 1.3,
        "ease_bonus": 0.1,
        "ease_penalty_linear": 0.08,
        "ease_penalty_quadratic": 0.02,
        "pass_threshold": 3,
        "choices": {          # UI → grade map
            "again": 1,
            "hard": 3,
            "good": 4,
            "easy": 5
        }
    },
    "leitner_settings" : {
        "buckets" : 4 #not yet supported
    }
}

ROOT_FOLDER_DEFAULTS = {
    "id": 0,           # root folder id
    "name": "/",       # or "root"
    "parent_id": None,
    "folder_settings": DEFAULT_FOLDER_SETTINGS
}

def row_to_dict(row):
    d = dict(row)
    required_json_cols = {"other_data", "rep_data", "folder_settings"}
    for k, v in list(d.items()):
        if v is None or not isinstance(v, str):
            continue
        if v.startswith("{") or v.startswith("["):
            try:
                d[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError) as e:
                if k in required_json_cols:
                    raise ValueError(f"Invalid JSON stored in column '{k}': {e}") from e
    return d

def init_schema(conn: sqlite3.Connection):
    """Create core tables once and enforce foreign keys."""
    cur = conn.cursor()
    cur.executescript(f"""
    CREATE TABLE IF NOT EXISTS folders (
        id         INTEGER PRIMARY KEY,
        name       TEXT UNIQUE,
        parent_id  INTEGER,
        folder_settings JSON,
        FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL
                      
        CHECK (parent_id IS NOT NULL OR id = {ROOT_FOLDER_DEFAULTS['id']})
    );

    CREATE TABLE IF NOT EXISTS flashcards (
        id         INTEGER PRIMARY KEY,
        folder_id    INTEGER NOT NULL DEFAULT {ROOT_FOLDER_DEFAULTS['id']},
        batch_id   INTEGER, 

        question   TEXT NOT NULL,
        answer     TEXT NOT NULL,
        other_data      JSON,

        rep_data      JSON,
        next_due      TIMESTAMP,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS batches (
        id          INTEGER PRIMARY KEY,
        source_text TEXT, 
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );          

    """)

    cur.executescript(f"""
    INSERT OR IGNORE INTO folders(id, name, parent_id) VALUES ({ROOT_FOLDER_DEFAULTS["id"]}, '{ROOT_FOLDER_DEFAULTS["name"]}', NULL);

    CREATE TRIGGER IF NOT EXISTS prevent_root_update
    BEFORE UPDATE OF name, parent_id ON folders
    WHEN old.id = {ROOT_FOLDER_DEFAULTS["id"]}
    BEGIN
    SELECT RAISE(ABORT, 'root folder is locked');
    END;

    CREATE TRIGGER IF NOT EXISTS prevent_root_delete
    BEFORE DELETE ON folders
    WHEN old.id = {ROOT_FOLDER_DEFAULTS["id"]}
    BEGIN
    SELECT RAISE(ABORT, 'root folder cannot be deleted');
    END;
    """)
    conn.commit()

def store_batch(db_path: str, cards: list[dict], content:str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)

    batch_id = create_batch(conn, content)

    for card in cards:
        create_flashcard(conn, card, batch_id)
    conn.close()



# =========== Creators ================

def create_folder(conn: sqlite3.Connection, folder_name: str) -> int:
    cur = conn.cursor()
    cur.execute("INSERT INTO folders (name) VALUES (?)", (folder_name,))
    conn.commit()

    assert cur.lastrowid is not None
    return cur.lastrowid

def create_batch(conn: sqlite3.Connection, content: str) -> int:
    """Ensure a folder exists; return its id."""

    cur = conn.cursor()
    cur.execute("INSERT INTO batches (source_text) VALUES (?)", (content,))
    conn.commit()

    assert cur.lastrowid is not None
    return cur.lastrowid

def create_flashcard(conn: sqlite3.Connection, card: dict, batch_id: int):

    cur = conn.cursor()

    question = card["question"]
    answer = card["answer"]
    other_data = json.dumps({k: v for k, v in card.items() if k not in ("question", "answer")})
    rep_data = json.dumps(make_default_rep_data())

    cur.execute(
        "INSERT INTO flashcards (question, answer, other_data, rep_data, batch_id) VALUES (?, ?, ?, ?, ?)",
        (question, answer, other_data, rep_data, batch_id)
    )
    conn.commit()

    assert cur.lastrowid is not None
    return cur.lastrowid

# =========== Updaters ================


def update_flashcard_fields(conn: sqlite3.Connection, card_id: int, fields: dict):
    cur = conn.cursor()
    keys = ", ".join([f"{k} = ?" for k in fields])
    values = list(fields.values()) + [card_id]
    cur.execute(f"UPDATE flashcards SET {keys} WHERE id = ?", values)
    if cur.rowcount == 0:
        raise ValueError(f"No flashcard with id {card_id} found to update")
    conn.commit()

def update_folder_fields(conn: sqlite3.Connection, folder_id: int, fields: dict):
    cur = conn.cursor()
    keys = ", ".join([f"{k} = ?" for k in fields])
    values = list(fields.values()) + [folder_id]
    cur.execute(f"UPDATE folders SET {keys} WHERE id = ?", values)
    if cur.rowcount == 0:
        raise ValueError(f"No folder with id {folder_id} found to update")
    conn.commit()    

# =========== Deleters ================


def delete_flashcard(conn: sqlite3.Connection, card_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
    if cur.rowcount == 0:
        raise ValueError(f"No flashcard with id {card_id} found to delete")
    conn.commit()

def delete_folder(conn: sqlite3.Connection, folder_id: int, recursive: bool = False):
    cur = conn.cursor()
    if recursive: 
        cur.execute("DELETE FROM flashcards WHERE folder_id = ?", (folder_id,))
        cur.execute("SELECT id FROM folders WHERE parent_id = ?", (folder_id,))
        rows = cur.fetchall()
        for child_id in rows:
            delete_folder(conn, child_id[0], recursive=True)

    cur.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    if cur.rowcount == 0:
        raise ValueError(f"No folder with id {folder_id} found to delete")
    conn.commit()

def delete_batch(conn: sqlite3.Connection, batch_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM flashcards WHERE batch_id = ?", (batch_id,))
    cur.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
    if cur.rowcount == 0:
        raise ValueError(f"No batch with id {batch_id} found to delete")
    conn.commit()



# =========== Getters ================

def get_card(conn: sqlite3.Connection, card_id: int):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No flashcard with id {card_id} found")
    return row_to_dict(row)


def get_folder(conn: sqlite3.Connection, folder_id: int):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No folder with id {folder_id} found")
    return row_to_dict(row)


def get_batch(conn: sqlite3.Connection, batch_id: int):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No batch with id {batch_id} found")
    return row_to_dict(row)

# ----------- new getters for all folders/cards/batches -----------
def get_all_folders(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM folders ORDER BY name ASC")
    rows = cur.fetchall()
    return [row_to_dict(r) for r in rows]

def get_all_cards(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM flashcards ORDER BY id ASC")
    rows = cur.fetchall()
    return [row_to_dict(r) for r in rows]

def get_all_batches(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM batches ORDER BY id ASC")
    rows = cur.fetchall()
    return [row_to_dict(r) for r in rows]



def get_cards_in_batch(conn: sqlite3.Connection, batch_id: int):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM flashcards WHERE batch_id = ?", (batch_id,))
    rows = cur.fetchall()
    return [row_to_dict(r) for r in rows]


def get_cards_in_folder(conn: sqlite3.Connection, folder_id: int):
    """Return all flashcards (as dicts) whose folder_id == folder_id."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM flashcards WHERE folder_id = ?", (folder_id,))
    rows = cur.fetchall()
    return [row_to_dict(r) for r in rows]

def get_folder_id_from_name(conn: sqlite3.Connection, folder_name: str):
    """Convenience wrapper that resolves a folder name → id and delegates to get_cards_in_folder."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No folder named '{folder_name}' found")
    return row["id"]

# ----------- Effective folder settings -----------
def get_folder_settings(conn: sqlite3.Connection, folder_id: int):
    """
    Return the *effective* spaced‑repetition settings for the given folder.

    The search starts at `folder_id` and walks **upward** through the
    `parent_id` chain until it finds the first non‑NULL `folder_settings`
    JSON blob.
    """

    cur = conn.cursor()
    current_id = folder_id

    while current_id is not None:
        cur.execute(
            "SELECT parent_id, folder_settings FROM folders WHERE id = ?",
            (current_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No folder with id {current_id} found")

        parent_id, settings_json = row
        if settings_json:
            try:
                return json.loads(settings_json)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in folder_settings for folder {current_id}: {exc}"
                ) from exc

        current_id = parent_id

    raise ValueError(f"No parent folder with settings found!")



def get_due_cards(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM flashcards WHERE next_due IS NOT NULL AND next_due <= CURRENT_TIMESTAMP ORDER BY next_due ASC"
    )
    rows = cur.fetchall()
    return [row_to_dict(r) for r in rows]


# =========== Folder tree ================

def _build_folder_node(conn: sqlite3.Connection, folder_row: sqlite3.Row):
    """Internal recursive helper that builds a single folder node."""
    folder_id = folder_row["id"]

    cur = conn.cursor()
    # card ids directly within this folder
    cur.execute("SELECT id FROM flashcards WHERE folder_id = ?", (folder_id,))
    card_ids = [r[0] for r in cur.fetchall()]

    # recurse on children
    cur.execute("SELECT * FROM folders WHERE parent_id = ?", (folder_id,))
    child_rows = cur.fetchall()
    children = [_build_folder_node(conn, child) for child in child_rows]

    return {
        "id": folder_id,
        "name": folder_row["name"],
        "cards": card_ids,
        "children": children,
    }

def get_folder_tree(conn: sqlite3.Connection, root_id: int):
    """
    Return the folder hierarchy as JSON‑serialisable dict(s).

    If root_id is None → return a list of top‑level folders.
    Otherwise → return the subtree rooted at the given folder id.
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM folders WHERE id = ?", (root_id,))
    root_row = cur.fetchone()
    if root_row is None:
        raise ValueError(f"No folder with id {root_id} found")
    return _build_folder_node(conn, root_row)

def print_db(conn: sqlite3.Connection):
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        print(f"\n=== {table.upper()} ===")
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [col[1] for col in cursor.fetchall()]
        print(" | ".join(cols))
        print("-" * (len(" | ".join(cols))))

        cursor.execute(f"SELECT * FROM {table}")
        for row in cursor.fetchall():
            print(" | ".join(str(x) for x in row))


# =========== Database class wrapper ================

class FlashcardDB:
    """
    Minimal wrapper around the module-level helpers; the only state is the
    SQLite connection held in `self.conn`.
    """

    def __init__(self, db_path: str):        
        db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_schema(self.conn)

    # ---------- creators ----------
    def create_folder(self, folder_name: str) -> int:
        return create_folder(self.conn, folder_name)

    def create_batch(self, content: str) -> int:
        return create_batch(self.conn, content)

    def create_flashcard(self, card: dict, batch_id: int) -> int:
        return create_flashcard(self.conn, card, batch_id)

    def store_batch(self, cards: list[dict], content: str) -> int:
        """Insert a new batch and all associated cards, returning the batch id."""
        batch_id = self.create_batch(content)
        for card in cards:
            self.create_flashcard(card, batch_id)
        return batch_id

    # ---------- updaters ----------
    def update_flashcard_fields(self, card_id: int, fields: dict):
        update_flashcard_fields(self.conn, card_id, fields)

    def update_folder_fields(self, folder_id: int, fields: dict):
        update_folder_fields(self.conn, folder_id, fields)

    # ---------- deleters ----------
    def delete_flashcard(self, card_id: int):
        delete_flashcard(self.conn, card_id)

    def delete_folder(self, folder_id: int, recursive: bool = False):
        delete_folder(self.conn, folder_id, recursive)

    def delete_batch(self, batch_id: int):
        delete_batch(self.conn, batch_id)

    # ---------- getters ----------
    def get_card(self, card_id: int):
        return get_card(self.conn, card_id)

    def get_cards_in_batch(self, batch_id: int):
        return get_cards_in_batch(self.conn, batch_id)

    def get_cards_in_folder(self, folder_id: int):
        return get_cards_in_folder(self.conn, folder_id)

    def get_folder(self, folder_id: int):
        return get_folder(self.conn, folder_id)

    def get_batch(self, batch_id: int):
        return get_batch(self.conn, batch_id)

    def get_all_folders(self):
        return get_all_folders(self.conn)

    def get_all_cards(self):
        return get_all_cards(self.conn)

    def get_all_batches(self):
        return get_all_batches(self.conn)

    def get_folder_id_from_name(self, folder_name: str):
        return get_folder_id_from_name(self.conn, folder_name)

    def get_due_cards(self):
        return get_due_cards(self.conn)

    def get_folder_tree(self, root_id: int):
        return get_folder_tree(self.conn, root_id)

    def get_folder_settings(self, folder_id: int):
        return get_folder_settings(self.conn, folder_id)

    def print_db(self):
        print_db(self.conn)

    # ---------- misc ----------
    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()