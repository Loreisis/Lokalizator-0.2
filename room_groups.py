"""
Konfiguracja przypisania sal do grup kolorystycznych.

Każda sala ma przypisaną grupę, która decyduje o kolorze jej kafelka
na stronie głównej oraz kolorze nagłówka w widoku sali. Gradienty
dla poszczególnych grup są zdefiniowane w static/style.css
(klasy .bg-grad-<grupa>).

Dostępne grupy:
    deb       — niebieski
    sww       — czerwony
    snw       — żółty
    magazyn   — fioletowy
    inne      — szary (domyślna, gdy sala nie jest wymieniona poniżej)

Jak dodać lub zmienić przypisanie:
    1. Wpisz nazwę sali (dokładnie tak, jak w bazie) i grupę w słowniku
       ROOM_GROUPS poniżej.
    2. Uruchom skrypt aktualizujący:

        python apply_room_groups.py

    Skrypt porówna stan bazy z tym plikiem i zaktualizuje kolumnę
    group_name w tabeli rooms.

Uwaga: nazwy sal muszą się zgadzać co do znaku (włącznie z polskimi
znakami i wielkością liter). Jeśli sala jest w bazie, ale nie ma jej
w tym słowniku, przyjmie grupę domyślną „inne”.
"""


# Słownik: nazwa sali (jak w bazie) -> nazwa grupy kolorystycznej.
# Formatowanie wyrównane kolumnami dla czytelności.

ROOM_GROUPS = {
    "Deb 1":           "deb",
    "BO":              "sww",
    "SOR":             "sww",
    "Magazyn główny":  "magazyn",
    "Wypożyczone":     "inne",
    "OIT":             "sww",
    "OITD":            "sww",
    "PuTech 1":        "snw",
}