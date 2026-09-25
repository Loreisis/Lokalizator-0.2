"""
Warstwa dostępu do bazy danych SQLite.

Zawiera wszystkie funkcje odczytu i zapisu danych: użytkowników, sale,
sprzęt oraz historię przeniesień. Aplikacja używa pliku eq.db w katalogu
głównym projektu; schemat bazy znajduje się w schema.sql.
"""

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


DATABASE = "eq.db"

def get_db_connection():
    """
    Otwiera nowe połączenie z bazą danych.

    Włącza klucze obce (PRAGMA foreign_keys) oraz tryb WAL
    (Write-Ahead Logging), który pozwala na równoczesne czytanie
    i zapisywanie bez blokowania.

    Returns:
        sqlite3.Connection z ustawionym row_factory = sqlite3.Row,
        dzięki czemu wiersze można indeksować po nazwie kolumny.
    """
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection

def init_db():
    """
    Tworzy tabele w bazie na podstawie pliku schema.sql.

    Używa CREATE TABLE IF NOT EXISTS, więc można ją wywoływać
    przy każdym starcie aplikacji bez ryzyka utraty danych.
    """
    connection = get_db_connection()

    with open("schema.sql", "r", encoding="utf-8") as file:
        connection.executescript(file.read())

    connection.commit()
    connection.close()

def add_room(name):
    """
    Dodaje nową salę o podanej nazwie.

    Args:
        name: Nazwa sali. Musi być unikalna w całej tabeli rooms.
    """
    connection = get_db_connection()

    connection.execute(
        "INSERT INTO rooms (name) VALUES (?)",
        (name,)
    )

    connection.commit()
    connection.close()

def add_eq(name, room_id):
    """
    Dodaje nowy sprzęt do wskazanej sali.

    Numer instancji (instance_no) jest nadawany automatycznie jako
    kolejny numer dla danej nazwy sprzętu. Dzięki temu można mieć
    kilka sztuk tego samego sprzętu (np. „Laptop #1”, „Laptop #2”).

    Args:
        name: Nazwa sprzętu.
        room_id: ID sali, w której sprzęt się znajduje.
    """
    connection = get_db_connection()

    result = connection.execute(
        """
        SELECT MAX(instance_no) AS max_instance
        FROM eq
        WHERE name = ?
        """,
        (name,)
    ).fetchone()

    if result["max_instance"] is None:
        instance_no = 1
    else:
        instance_no = result["max_instance"] + 1

    connection.execute(
        """
        INSERT INTO eq (name, instance_no, room_id)
        VALUES (?, ?, ?)
        """,
        (name, instance_no, room_id)
    )

    connection.commit()
    connection.close()

def add_display_names(rows):
    """
    Wzbogaca wiersze sprzętu o pola display_name i name_count.

    Jeśli w bazie istnieje kilka sztuk sprzętu o tej samej nazwie,
    do wyświetlanej nazwy dodawany jest numer instancji (np. „Laptop #2”).
    Przy unikalnej nazwie display_name jest równy nazwie.

    Args:
        rows: Lista wierszy (sqlite3.Row lub dict) reprezentujących sprzęt.
              Każdy wiersz musi zawierać kolumny „name” i „instance_no”.

    Returns:
        Nowa lista słowników — oryginalne wiersze nie są modyfikowane.
    """
    connection = get_db_connection()

    name_counts = connection.execute(
        """
        SELECT name, COUNT(*) AS count
        FROM eq
        GROUP BY name
        """
    ).fetchall()

    connection.close()

    counts = {
        row["name"]: row["count"]
        for row in name_counts
    }

    results = []

    for row in rows:
        item = dict(row)
        count = counts[row["name"]]
        item["name_count"] = count

        if count > 1:
            item["display_name"] = (
                f'{row["name"]} #{row["instance_no"]}'
            )
        else:
            item["display_name"] = row["name"]

        results.append(item)

    return results


def create_user(username, password, is_admin=False):
    """
    Tworzy nowego użytkownika z hasłem hashowanym przez Werkzeug.

    Hasło nigdy nie jest zapisywane w postaci jawnej — w bazie
    przechowywany jest wyłącznie hash PBKDF2.

    Args:
        username: Nazwa użytkownika (unikalna).
        password: Hasło w postaci jawnej (zostanie zahashowane).
        is_admin: Czy użytkownik ma uprawnienia administratora.
    """
    connection = get_db_connection()
    connection.execute(
        """
        INSERT INTO users (username, password_hash, is_admin)
        VALUES (?, ?, ?)
        """,
        (username, generate_password_hash(password), 1 if is_admin else 0)
    )
    connection.commit()
    connection.close()


def get_user_by_username(username):
    """
    Wyszukuje użytkownika po nazwie.

    Args:
        username: Nazwa użytkownika.

    Returns:
        sqlite3.Row z danymi użytkownika albo None, jeśli nie istnieje.
    """
    connection = get_db_connection()
    row = connection.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    connection.close()
    return row


def get_user_by_id(user_id):
    """
    Wyszukuje użytkownika po ID.

    Args:
        user_id: Identyfikator użytkownika.

    Returns:
        sqlite3.Row z danymi użytkownika albo None, jeśli nie istnieje.
    """
    connection = get_db_connection()
    row = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    connection.close()
    return row


def verify_user(username, password):
    """
    Sprawdza poprawność danych logowania.

    Args:
        username: Nazwa użytkownika.
        password: Hasło w postaci jawnej.

    Returns:
        sqlite3.Row z danymi użytkownika, jeśli hasło jest poprawne,
        w przeciwnym razie None.
    """
    row = get_user_by_username(username)
    if row is None:
        return None
    if check_password_hash(row["password_hash"], password):
        return row
    return None


def update_password(user_id, new_password):
    """
    Ustawia nowe hasło użytkownika (hashowane).

    Args:
        user_id: ID użytkownika.
        new_password: Nowe hasło w postaci jawnej.
    """
    connection = get_db_connection()
    connection.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id)
    )
    connection.commit()
    connection.close()


def get_all_users():
    """
    Zwraca wszystkich użytkowników posortowanych alfabetycznie.

    Returns:
        Lista sqlite3.Row z polami: id, username, is_admin, created_at.
        Hash hasła nie jest ujawniany.
    """
    connection = get_db_connection()
    rows = connection.execute(
        """
        SELECT id, username, is_admin, created_at
        FROM users
        ORDER BY username
        """
    ).fetchall()
    connection.close()
    return rows


def delete_user(user_id):
    """
    Usuwa użytkownika o podanym ID.

    Args:
        user_id: ID użytkownika do usunięcia.
    """
    connection = get_db_connection()
    connection.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )
    connection.commit()
    connection.close()


def count_admins():
    """
    Liczy użytkowników z uprawnieniami administratora.

    Używane do zabezpieczenia przed usunięciem ostatniego admina.

    Returns:
        Liczba administratorów w bazie.
    """
    connection = get_db_connection()
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM users WHERE is_admin = 1"
    ).fetchone()
    connection.close()
    return row["count"]

def get_rooms_with_counts():
    """
    Zwraca wszystkie sale wraz z liczbą znajdującego się w nich sprzętu.

    Sale są sortowane najpierw po grupie (sww, snw, deb, magazyn, inne),
    a następnie alfabetycznie po nazwie. Dzięki temu kafelki kolorów
    na stronie głównej są ułożone w spójne bloki.

    Returns:
        Lista sqlite3.Row z polami: id, name, group_name, eq_count.
    """
    connection = get_db_connection()
    rows = connection.execute(
        """
        SELECT
            rooms.id,
            rooms.name,
            rooms.group_name,
            (SELECT COUNT(*) FROM eq WHERE eq.room_id = rooms.id) AS eq_count
        FROM rooms
        ORDER BY
            CASE rooms.group_name
                WHEN 'sww' THEN 1
                WHEN 'snw' THEN 2
                WHEN 'deb' THEN 3
                WHEN 'magazyn' THEN 4
                ELSE 5
            END,
            rooms.name
        """
    ).fetchall()
    connection.close()
    return rows


def get_room_by_id(room_id):
    """
    Wyszukuje salę po ID.

    Args:
        room_id: Identyfikator sali.

    Returns:
        sqlite3.Row z danymi sali albo None, jeśli nie istnieje.
    """
    connection = get_db_connection()
    row = connection.execute(
        "SELECT * FROM rooms WHERE id = ?",
        (room_id,)
    ).fetchone()
    connection.close()
    return row


def rename_room(room_id, new_name):
    """
    Zmienia nazwę sali.

    Args:
        room_id: ID sali.
        new_name: Nowa nazwa sali.

    Returns:
        True — jeśli zmiana się powiodła.
        False — jeśli nowa nazwa narusza ograniczenie UNIQUE
                (sala o takiej nazwie już istnieje).
    """
    connection = get_db_connection()
    try:
        connection.execute(
            "UPDATE rooms SET name = ? WHERE id = ?",
            (new_name, room_id)
        )
        connection.commit()
        connection.close()
        return True
    except sqlite3.IntegrityError:
        connection.close()
        return False


def room_has_equipment(room_id):
    """
    Sprawdza, czy w sali znajduje się jakikolwiek sprzęt.

    Używane przed usunięciem sali — zabezpieczenie przed osieroceniem
    sprzętu.

    Args:
        room_id: ID sali.

    Returns:
        True, jeśli sala zawiera co najmniej jedną sztukę sprzętu.
    """
    connection = get_db_connection()
    row = connection.execute(
        "SELECT COUNT(*) AS c FROM eq WHERE room_id = ?",
        (room_id,)
    ).fetchone()
    connection.close()
    return row["c"] > 0


def room_has_history(room_id):
    """
    Sprawdza, czy sala występuje w historii przeniesień.

    Używane przed usunięciem sali — historia zachowuje referencje
    do sal (from_room_id, to_room_id), więc usunięcie sali bez tej
    weryfikacji naruszyłoby klucz obcy.

    Args:
        room_id: ID sali.

    Returns:
        True, jeśli sala pojawia się w jakimkolwiek wpisie historii.
    """
    connection = get_db_connection()
    row = connection.execute(
        """
        SELECT COUNT(*) AS c FROM movement_history
        WHERE from_room_id = ? OR to_room_id = ?
        """,
        (room_id, room_id)
    ).fetchone()
    connection.close()
    return row["c"] > 0


def delete_room(room_id):
    """
    Usuwa salę o podanym ID.

    Args:
        room_id: ID sali.

    Returns:
        True — jeśli usunięcie się powiodło.
        False — jeśli usunięcie narusza klucz obcy
                (sala zawiera sprzęt lub występuje w historii).
    """
    connection = get_db_connection()
    try:
        connection.execute(
            "DELETE FROM rooms WHERE id = ?",
            (room_id,)
        )
        connection.commit()
        connection.close()
        return True
    except sqlite3.IntegrityError:
        connection.close()
        return False


def get_all_eq_with_rooms():
    """
    Zwraca cały sprzęt wraz z nazwą sali, w której się znajduje.

    Używane w panelu administratora do wyświetlenia kompletnej listy.

    Returns:
        Lista sqlite3.Row z polami: id, name, instance_no, room_id, room_name.
    """
    connection = get_db_connection()
    rows = connection.execute(
        """
        SELECT
            eq.id,
            eq.name,
            eq.instance_no,
            eq.room_id,
            rooms.name AS room_name
        FROM eq
        JOIN rooms ON eq.room_id = rooms.id
        ORDER BY eq.name, eq.instance_no
        """
    ).fetchall()
    connection.close()
    return rows


def get_eq_by_id(eq_id):
    """
    Wyszukuje sprzęt po ID.

    Args:
        eq_id: Identyfikator sprzętu.

    Returns:
        sqlite3.Row z danymi sprzętu albo None, jeśli nie istnieje.
    """
    connection = get_db_connection()
    row = connection.execute(
        "SELECT * FROM eq WHERE id = ?",
        (eq_id,)
    ).fetchone()
    connection.close()
    return row


def update_eq(eq_id, new_name, new_room_id):
    """
    Aktualizuje nazwę i salę sprzętu.

    Args:
        eq_id: ID sprzętu.
        new_name: Nowa nazwa sprzętu.
        new_room_id: ID nowej sali.

    Returns:
        True — jeśli aktualizacja się powiodła.
        False — jeśli naruszono ograniczenie UNIQUE(name, instance_no).
    """
    connection = get_db_connection()
    try:
        connection.execute(
            "UPDATE eq SET name = ?, room_id = ? WHERE id = ?",
            (new_name, new_room_id, eq_id)
        )
        connection.commit()
        connection.close()
        return True
    except sqlite3.IntegrityError:
        connection.close()
        return False


def delete_eq(eq_id):
    """
    Usuwa sprzęt o podanym ID.

    Historia przeniesień tego sprzętu jest usuwana automatycznie
    dzięki ON DELETE CASCADE w schemacie bazy.

    Args:
        eq_id: ID sprzętu.
    """
    connection = get_db_connection()
    connection.execute(
        "DELETE FROM eq WHERE id = ?",
        (eq_id,)
    )
    connection.commit()
    connection.close()


def rename_eq(eq_id, new_name):
    """
    Zmienia nazwę sprzętu.

    Args:
        eq_id: ID sprzętu.
        new_name: Nowa nazwa.

    Returns:
        True — jeśli zmiana się powiodła.
        False — jeśli naruszono ograniczenie UNIQUE (konflikt nazwy).
    """
    connection = get_db_connection()
    try:
        connection.execute(
            "UPDATE eq SET name = ? WHERE id = ?",
            (new_name, eq_id)
        )
        connection.commit()
        connection.close()
        return True
    except sqlite3.IntegrityError:
        connection.close()
        return False


def migrate_db():
    """
    Wykonuje migracje schematu dla istniejącej bazy.

    Sprawdza, czy w tabelach movement_history i rooms istnieją
    nowsze kolumny (user_id, group_name), i dodaje je, jeśli brakuje.
    Uruchamiane raz przy starcie aplikacji — bezpieczne wielokrotnie.

    Uwaga: SQLite nie pozwala dodawać kluczy obcych przez ALTER TABLE,
    więc kolumna user_id nie ma w istniejących bazach zadeklarowanego
    FOREIGN KEY. Integralność jest pilnowana w warstwie aplikacji.
    """
    connection = get_db_connection()

    columns = connection.execute(
        "PRAGMA table_info(movement_history)"
    ).fetchall()
    column_names = [c["name"] for c in columns]
    if "user_id" not in column_names:
        connection.execute(
            "ALTER TABLE movement_history ADD COLUMN user_id INTEGER"
        )
        connection.commit()

    columns = connection.execute(
        "PRAGMA table_info(rooms)"
    ).fetchall()
    column_names = [c["name"] for c in columns]
    if "group_name" not in column_names:
        connection.execute(
            "ALTER TABLE rooms ADD COLUMN group_name TEXT NOT NULL DEFAULT 'inne'"
        )
        connection.commit()

    connection.close()
