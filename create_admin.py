"""
Skrypt do tworzenia pierwszego administratora w bazie.

Uruchamiany jednorazowo, ręcznie, po pierwszym starcie aplikacji:

    python create_admin.py

Pyta interaktywnie o imię i hasło, hashuje hasło i zapisuje konto
z uprawnieniami administratora. Bezpieczny do wielokrotnego uruchomienia —
odmawia utworzenia konta, jeśli użytkownik o tej nazwie już istnieje.
"""

from getpass import getpass

from database import init_db, create_user, get_user_by_username


def main():
    """
    Główna funkcja skryptu — interaktywne tworzenie konta administratora.

    Kroki:
    1. Tworzy tabele (jeśli nie istnieją) przez init_db.
    2. Pobiera imię od użytkownika i sprawdza, czy nie jest puste
       oraz czy nie istnieje już taki użytkownik.
    3. Pobiera hasło (bez echa w terminalu) i prosi o powtórzenie.
    4. Waliduje zgodność haseł i minimalną długość (5 znaków).
    5. Zapisuje konto z flagą is_admin=True.
    """
    
    init_db()

    username = input("Imię administratora: ").strip()

    if not username:
        print("Imię nie może być puste.")
        return

    if get_user_by_username(username) is not None:
        print(f"Użytkownik '{username}' już istnieje.")
        return

    password = getpass("Hasło: ")
    password2 = getpass("Powtórz hasło: ")

    if password != password2:
        print("Hasła nie są identyczne.")
        return

    if len(password) < 5:
        print("Hasło musi mieć co najmniej 5 znaków.")
        return

    create_user(username, password, is_admin=True)
    print(f"Utworzono administratora: {username}")


if __name__ == "__main__":
    main()