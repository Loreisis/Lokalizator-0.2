"""
Skrypt aktualizujący przypisanie sal do grup kolorystycznych.

Czyta słownik ROOM_GROUPS z pliku room_groups.py i porównuje go
ze stanem bazy. Sale, których grupa się różni, są aktualizowane.
Sale obecne w bazie, ale nieobecne w słowniku, dostają grupę „inne”.

Uruchamiać po każdej zmianie w room_groups.py:

    python apply_room_groups.py

Skrypt jest idempotentny — można go uruchamiać wielokrotnie bez
szkody. Jeśli nic nie wymaga zmiany, poinformuje o tym i zakończy
się bez zapisu.
"""

from database import get_db_connection
from room_groups import ROOM_GROUPS



def main():
    """
    Główna funkcja skryptu — synchronizacja grup sal z room_groups.py.

    Wyświetla listę zmian (stara grupa -> nowa grupa) dla każdej sali,
    której przypisanie się różni. Sale, których grupa jest już zgodna,
    są pomijane w wydruku. Wszystkie zmiany zapisywane są jednym commitem
    na końcu — nie ma stanu pośredniego.
    """
    
    connection = get_db_connection()

    rooms = connection.execute(
        "SELECT id, name, group_name FROM rooms ORDER BY name"
    ).fetchall()

    if not rooms:
        print("Brak sal w bazie.")
        connection.close()
        return

    print("Zastosowanie grup z room_groups.py:")
    print()

    changed = 0
    for r in rooms:
        new_group = ROOM_GROUPS.get(r["name"], "inne")

        if new_group != r["group_name"]:
            connection.execute(
                "UPDATE rooms SET group_name = ? WHERE id = ?",
                (new_group, r["id"])
            )
            changed += 1
            print(f"  {r['name']:<30}  {r['group_name']}  ->  {new_group}")

    connection.commit()
    connection.close()

    if changed == 0:
        print("  (nic nie wymagało zmiany)")
    else:
        print()
        print(f"Zmieniono {changed} sal.")


if __name__ == "__main__":
    main()