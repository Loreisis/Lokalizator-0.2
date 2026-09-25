-- =============================================================
-- Schemat bazy danych „Lokalizator sprzętu”.
-- Uruchamiany przy każdym starcie aplikacji (init_db w database.py).
-- Wszystkie tabele mają IF NOT EXISTS, więc istniejące dane nie są
-- nadpisywane.
-- =============================================================


-- Włącza egzekwowanie kluczy obcych w bieżącym połączeniu.
-- W SQLite klucze obce są domyślnie ignorowane — bez tej linii
-- ON DELETE / ON UPDATE nie działają.

PRAGMA foreign_keys = ON;

-- Użytkownicy systemu. Hasło przechowywane wyłącznie jako hash.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Sale. group_name określa grupę kolorystyczną (deb, sww, snw,
-- magazyn, inne) — wpływa na gradient tła i kafelków. Ustawiane
-- przez apply_room_groups.py, domyślnie „inne”.
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    group_name TEXT NOT NULL DEFAULT 'inne'
);

-- Sprzęt. Każda nazwa może mieć wiele instancji (np. „Laptop #1”,
-- „Laptop #2”) — numeracja jest w kolumnie instance_no i razem
-- z name tworzy unikalną parę.
CREATE TABLE IF NOT EXISTS eq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    instance_no INTEGER NOT NULL DEFAULT 1,
    room_id INTEGER NOT NULL,

    -- Sprzęt zawsze musi należeć do jakiejś sali.
    -- ON DELETE RESTRICT — nie można usunąć sali, dopóki jest w niej sprzęt.
    FOREIGN KEY (room_id) 
        REFERENCES rooms(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (name, instance_no)
);

-- Historia przeniesień sprzętu. Każdy wpis to jedno zdarzenie:
-- sprzęt przeszedł z sali from_room_id do sali to_room_id.
-- Wypełniane automatycznie przy operacjach /move_eq i /eq/<id> (POST).
CREATE TABLE IF NOT EXISTS movement_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eq_id INTEGER NOT NULL,
    from_room_id INTEGER NOT NULL,
    to_room_id INTEGER NOT NULL,
    moved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- user_id jest NULL dla wpisów sprzed wprowadzenia logowania.
    -- Dla nowych wpisów trzyma ID użytkownika, który wykonał przeniesienie.
    user_id INTEGER,

    -- Usunięcie sprzętu usuwa całą jego historię przeniesień.
    FOREIGN KEY (eq_id)
        REFERENCES eq(id)
        ON DELETE CASCADE,

    -- Sal nie można usunąć, jeśli występują w historii.
    FOREIGN KEY (from_room_id)
        REFERENCES rooms(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (to_room_id)
        REFERENCES rooms(id)
        ON DELETE RESTRICT,
    
    -- Usunięcie użytkownika nie usuwa historii — tylko czyści
    -- pole user_id (wpis zostaje z adnotacją „Wykonał: —”).
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);

-- Indeksy przyspieszające najczęstsze zapytania:
-- filtrowanie sprzętu po sali, wyszukiwanie po nazwie,
-- oraz pobieranie historii konkretnego sprzętu.
CREATE INDEX IF NOT EXISTS idx_eq_room_id
ON eq(room_id);
CREATE INDEX IF NOT EXISTS idx_eq_name
ON eq(name);
CREATE INDEX IF NOT EXISTS idx_history_eq_id
ON movement_history(eq_id);