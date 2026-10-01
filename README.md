# Lokalizator sprzętu

Wewnętrzna aplikacja webowa do lokalizowania sprzętu i przenoszenia go
między salami. Umożliwia szybkie sprawdzenie, gdzie znajduje się dany
sprzęt, oraz zapisuje historię przeniesień (kto, kiedy, skąd, dokąd).

## Funkcje

- Logowanie użytkowników (hasła hashowane, długotrwałe sesje)
- Przeglądanie sal i sprzętu w nich się znajdującego
- Wyszukiwarka sprzętu z podpowiedziami
- Przenoszenie sprzętu między salami bez przeładowania strony (AJAX)
- Historia przeniesień z informacją o wykonującym
- Panel administratora (użytkownicy, sale, sprzęt)
- Grupy kolorystyczne sal
- Tryb ciemny, interfejs responsywny (Bootstrap 5.3)
- PWA — możliwość dodania do ekranu głównego telefonu

## Stack

- **Backend:** Python 3.10+, Flask
- **Baza:** SQLite (plik `eq.db`, tworzony automatycznie)
- **Autoryzacja:** Flask-Login, hasła hashowane przez Werkzeug
- **CSRF:** Flask-WTF
- **Frontend:** Bootstrap 5.3, Jinja2, waniliowy JavaScript

## Wymagania

- Python 3.10+
- pip

## Struktura projektu

Lokalizator/
 app.py # główna aplikacja Flask, trasy
 database.py # warstwa dostępu do bazy
 schema.sql # schemat bazy
 create_admin.py # skrypt tworzenia pierwszego admina
 room_groups.py # przypisanie sal do grup kolorystycznych
 apply_room_groups.py # skrypt synchronizujący grupy z bazą
 requirements.txt # zależności
 templates/ # szablony Jinja2
 static/ # pliki statyczne (CSS, ikony, manifest PWA)


## Konfiguracja produkcyjna

### Klucz sesji (SECRET_KEY)

Aplikacja używa zmiennej środowiskowej `SECRET_KEY` do podpisywania
ciasteczek sesji. W kodzie jest tylko placeholder deweloperski —
**na produkcji trzeba ustawić prawdziwy, losowy klucz.**

Wygeneruj go raz na serwerze:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Ustaw jako stałą zmienną środowiskową systemu (przez systemd, Docker
albo konfigurację serwera). Nigdy nie commituj prawdziwego klucza
do repozytorium.

Baza danych
Baza to plik eq.db (SQLite). Nie jest przechowywana w repozytorium —
trzeba ją dostarczyć osobno na serwer (patrz „Przekazanie bazy” poniżej).

Przy pierwszym uruchomieniu aplikacji, jeśli eq.db nie istnieje,
zostanie utworzony pusty plik bazy. Aby utworzyć pierwsze konto
administratora:
python create_admin.py
Uruchomienie produkcyjne
Wbudowany serwer Flaska (python app.py) nie nadaje się do produkcji.
Użyj serwera WSGI — np. Gunicorn:
gunicorn -w 4 -b 127.0.0.1:8000 app:app
Zalecany układ:

Internet → Nginx (HTTPS, 443) → Gunicorn (127.0.0.1:8000) → Flask
Nginx obsługuje HTTPS i pliki statyczne, Gunicorn — logikę aplikacji.
Procesem warto zarządzać przez systemd.

Ustawienia przed wystawieniem do internetu
Wyłącz debug — w app.py: debug=False (powinno już być).

Ustaw SECRET_KEY (patrz wyżej).

Włącz HTTPS — Nginx + certyfikat (np. Let's Encrypt).

Dodaj REMEMBER_COOKIE_SECURE = True w app.py — wymusza
wysyłanie ciasteczka tylko przez HTTPS.

Uprawnienia eq.db — czytelny i zapisywalny tylko dla
użytkownika, pod którym działa aplikacja.

Kopie zapasowe
Kopia zapasowa = plik eq.db. Najbezpieczniej przy zatrzymanej aplikacji,
albo przez sqlite3 eq.db ".backup kopia.db" na żywej bazie.

Uwagi dla administratora
Brak mechanizmu unieważniania pojedynczych sesji. Aby unieważnić
wszystkie sesje (np. po zwolnieniu pracownika), zmień SECRET_KEY
i zrestartuj aplikację.

Hasła hashowane PBKDF2 (Werkzeug, domyślne parametry).

SQLite z trybem WAL — bezpieczne dla kilku równoczesnych użytkowników,
nie skaluje się do setek. Przy skali 10 użytkowników w zupełności
wystarczająca.

Znane ograniczenia
Brak automatycznych testów.

Brak eksportu danych (CSV / PDF).

Wyszukiwarka działa tylko po nazwie sprzętu.

Uruchomienie lokalne (dla developera)

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
python create_admin.py
python app.py
Aplikacja: http://localhost:5000

Licencja
Aplikacja wewnętrzna — nieprzeznaczona do publicznej dystrybucji.
---
