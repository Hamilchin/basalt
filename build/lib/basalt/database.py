import sqlite3, json

#all functions assume that the database conn points to has been initialized
#using init_schema

def _row_to_card(row):
    d = dict(row)
    for k in ("other_data", "rep_data"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(f"Invalid JSON stored in column '{k}': {e}") from e
    return d

def init_schema(conn: sqlite3.Connection):
    """Create core tables once and enforce foreign keys."""
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS folders (
        id         INTEGER PRIMARY KEY,
        name       TEXT UNIQUE,
        parent_id  INTEGER,
        folder_settings JSON,
        FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS flashcards (
        id         INTEGER PRIMARY KEY,
        folder_id    INTEGER,
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

    cur.execute(
        "INSERT INTO flashcards (question, answer, other_data, batch_id) VALUES (?, ?, ?, ?)",
        (question, answer, other_data, batch_id)
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
    return _row_to_card(row) if row else None


def get_cards_in_batch(conn: sqlite3.Connection, batch_id: int):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM flashcards WHERE batch_id = ?", (batch_id,))
    rows = cur.fetchall()
    return [_row_to_card(r) for r in rows]


def get_cards_in_folder(conn: sqlite3.Connection, folder_id: int):
    """Return all flashcards (as dicts) whose folder_id == folder_id."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM flashcards WHERE folder_id = ?", (folder_id,))
    rows = cur.fetchall()
    return [_row_to_card(r) for r in rows]

def get_cards_in_folder_by_name(conn: sqlite3.Connection, folder_name: str):
    """Convenience wrapper that resolves a folder name → id and delegates to get_cards_in_folder."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No folder named '{folder_name}' found")
    return get_cards_in_folder(conn, row["id"])



def get_due_cards(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM flashcards WHERE next_due IS NOT NULL AND next_due <= CURRENT_TIMESTAMP ORDER BY next_due ASC"
    )
    rows = cur.fetchall()
    return [_row_to_card(r) for r in rows]


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


def get_folder_tree(conn: sqlite3.Connection, root_id: int | None = None):
    """
    Return the folder hierarchy as JSON‑serialisable dict(s).

    If root_id is None → return a list of top‑level folders.
    Otherwise → return the subtree rooted at the given folder id.
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if root_id is None:
        cur.execute("SELECT * FROM folders WHERE parent_id IS NULL")
        root_rows = cur.fetchall()
        return [_build_folder_node(conn, r) for r in root_rows]

    cur.execute("SELECT * FROM folders WHERE id = ?", (root_id,))
    root_row = cur.fetchone()
    if root_row is None:
        raise ValueError(f"No folder with id {root_id} found")
    return _build_folder_node(conn, root_row)



# =========== Database class wrapper ================

class FlashcardDB:
    """
    Minimal wrapper around the module-level helpers; the only state is the
    SQLite connection held in `self.conn`.
    """

    def __init__(self, db_path: str):
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

    def get_cards_in_folder_by_name(self, folder_name: str):
        return get_cards_in_folder_by_name(self.conn, folder_name)

    def get_due_cards(self):
        return get_due_cards(self.conn)

    def get_folder_tree(self, root_id: int | None = None):
        return get_folder_tree(self.conn, root_id)

    # ---------- misc ----------
    def close(self):
        self.conn.close()