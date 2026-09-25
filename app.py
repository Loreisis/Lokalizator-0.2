"""
Główny moduł aplikacji Flask — „Lokalizator sprzętu”.

Definiuje konfigurację aplikacji, logowanie użytkowników, wszystkie trasy
HTTP oraz panel administratora. Warstwa dostępu do bazy znajduje się
w module database.
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask_wtf.csrf import CSRFProtect

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    url_for,
    flash,
)

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from database import (
    init_db,
    get_db_connection,
    add_display_names,
    get_user_by_id,
    verify_user,
    create_user,
    get_all_users,
    delete_user,
    count_admins,
    update_password,
    get_user_by_username,
    get_rooms_with_counts,
    get_room_by_id,
    rename_room,
    room_has_equipment,
    room_has_history,
    delete_room,
    get_all_eq_with_rooms,
    get_eq_by_id,
    update_eq,
    delete_eq,
    rename_eq,
    migrate_db,
)


app = Flask(__name__)

# zmienić na losowy ciąg ze zmiennej środowiskowej.
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "zmien-mnie-na-losowy-ciag-znakow",
)

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Zaloguj się, aby kontynuować."
login_manager.login_message_category = "warning"


init_db()
migrate_db()

class User(UserMixin):
    """
    Reprezentacja zalogowanego użytkownika dla Flask-Login.

    Trzyma tylko minimum potrzebne w trakcie sesji — reszta danych
    jest pobierana z bazy w razie potrzeby.

    Attributes:
        id: ID użytkownika z bazy.
        username: Nazwa użytkownika.
        is_admin: Czy użytkownik ma uprawnienia administratora.
    """

    def __init__(self, user_id, username, is_admin):
        self.id = user_id
        self.username = username
        self.is_admin = is_admin


@login_manager.user_loader
def load_user(user_id):
    """
    Callback Flask-Login — ładuje użytkownika z bazy po ID.

    Wywoływany przy każdym żądaniu, żeby odtworzyć obiekt użytkownika
    z ID zapisanego w ciasteczku sesji.

    Args:
        user_id: ID użytkownika (jako string z sesji).

    Returns:
        Obiekt User albo None, jeśli użytkownik nie istnieje.
    """

    row = get_user_by_id(int(user_id))
    if row is None:
        return None
    return User(row["id"], row["username"], bool(row["is_admin"]))


def admin_required(view):
    """
    Dekorator ograniczający dostęp trasy do administratorów.

    Wymaga zalogowania (przez login_required) i sprawdza flagę is_admin.
    Niezalogowany użytkownik jest przekierowany na login, zalogowany
    nie-admin dostaje odpowiedź 403.

    Args:
        view: Funkcja widoku do udekorowania.
    """

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            return "Brak uprawnień", 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Formularz logowania i obsługa uwierzytelnienia.

    GET — pokazuje formularz.
    POST — weryfikuje dane; przy sukcesie tworzy sesję i przekierowuje
    na stronę docelową (parametr next) albo na stronę główną.

    Returns:
        GET: widok login.html.
        POST (sukces): redirect na next lub na home.
        POST (błąd): ponownie login.html ze statusem 401.
    """

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        row = verify_user(username, password)

        if row is None:
            flash("Nieprawidłowe imię lub hasło.", "danger")
            return render_template("login.html"), 401

        user = User(row["id"], row["username"], bool(row["is_admin"]))
        login_user(user)

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Kończy sesję użytkownika i przekierowuje na stronę logowania."""
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    """
    Strona główna — lista wszystkich sal jako kolorowe kafelki.

    Sale są posortowane po grupie (sww, snw, deb, magazyn, inne),
    a w obrębie grupy alfabetycznie. Każdy kafelek ma gradient
    odpowiadający grupie kolorystycznej.
    """

    connection = get_db_connection()

    rooms = connection.execute(
        """
        SELECT * FROM rooms
        ORDER BY
            CASE group_name
                WHEN 'sww' THEN 1
                WHEN 'snw' THEN 2
                WHEN 'deb' THEN 3
                WHEN 'magazyn' THEN 4
                ELSE 5
            END,
            name
        """
    ).fetchall()

    connection.close()

    return render_template("index.html", rooms=rooms)


@app.route("/room/<int:room_id>")
@login_required
def room(room_id):
    """
    Widok sali z listą znajdującego się w niej sprzętu.

    Pozwala na rozwinięcie akcji przy sprzęcie i przeniesienie go
    do innej sali (bezpośrednio przez AJAX /move_eq).

    Args:
        room_id: ID sali do wyświetlenia.

    Returns:
        Widok room.html albo odpowiedź 404, jeśli sala nie istnieje.
    """

    connection = get_db_connection()

    room = connection.execute(
        "SELECT * FROM rooms WHERE id = ?",
        (room_id,)
    ).fetchone()

    if room is None:
        connection.close()
        return "Nie znaleziono sali", 404

    eq = connection.execute(
        "SELECT * FROM eq WHERE room_id = ? ORDER BY name, instance_no",
        (room_id,)
    ).fetchall()

    eq = add_display_names(eq)

    rooms = connection.execute(
        """
        SELECT * FROM rooms
        ORDER BY
            CASE group_name
                WHEN 'sww' THEN 1
                WHEN 'snw' THEN 2
                WHEN 'deb' THEN 3
                WHEN 'magazyn' THEN 4
                ELSE 5
            END,
            name
        """
    ).fetchall()

    connection.close()

    return render_template(
        "room.html",
        room=room,
        eq=eq,
        rooms=rooms
    )


@app.route("/search")
@login_required
def search():
    """
    Pełnostronicowy widok wyników wyszukiwania sprzętu.

    Wyszukiwanie jest frazowe (LIKE %query%) i obejmuje tylko nazwę
    sprzętu. Wyniki zawierają nazwę sali, w której sprzęt się znajduje.

    Query string:
        q: fraza do wyszukania (opcjonalna — brak zwraca pustą listę).
    """

    query = request.args.get("q", "")

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT 
            eq.id,
            eq.name,
            eq.instance_no, 
            rooms.name AS room_name
        FROM eq
        JOIN rooms ON eq.room_id = rooms.id
        WHERE eq.name LIKE ?
        ORDER BY eq.name, eq.instance_no
        """,
        (f"%{query}%",)
    ).fetchall()

    results = add_display_names(results)

    connection.close()

    return render_template(
        "search.html",
        query=query,
        results=results
    )


@app.route("/api/search")
@login_required
def api_search():
    """
    Endpoint JSON z podpowiedziami do wyszukiwarki (autocomplete).

    Zwraca maksymalnie 10 wyników pasujących do frazy. Pusty parametr q
    zwraca pustą listę — bez tego każde żądanie bez frazy uderzałoby
    w bazę i zwracało cały katalog.

    Query string:
        q: fraza do wyszukania.

    Returns:
        Lista obiektów JSON z polami: id, display_name, room_name.
    """

    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT
            eq.id,
            eq.name,
            eq.instance_no,
            rooms.name AS room_name
        FROM eq
        JOIN rooms
            ON eq.room_id = rooms.id
        WHERE eq.name LIKE ?
        ORDER BY eq.name, eq.instance_no
        LIMIT 10
        """,
        (f"%{query}%",)
    ).fetchall()

    connection.close()

    results = add_display_names(results)

    return jsonify(results)


@app.route("/move_eq/<int:eq_id>", methods=["POST"])
@login_required
def move_eq(eq_id):
    """
    Przenosi sprzęt do innej sali i zapisuje zdarzenie w historii.

    Wykonuje trzy operacje w jednej transakcji:
    1. sprawdza poprawność danych wejściowych,
    2. aktualizuje pole room_id w tabeli eq,
    3. zapisuje wpis w movement_history z informacją kto i kiedy.

    Args:
        eq_id: ID sprzętu do przeniesienia.

    Returns:
        JSON z polami: success, old_room, new_room, moved_at (przy sukcesie)
        albo success=False + error (przy błędzie, wraz z kodem 400/404).
    """

    data = request.get_json()

    if not data or "room_id" not in data:
        return jsonify({"success": False, "error": "Nie podano sali"}), 400

    try:
        new_room_id = int(data["room_id"])
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Nieprawidłowa sala"}), 400

    connection = get_db_connection()

    try:
        eq = connection.execute(
            "SELECT * FROM eq WHERE id = ?",
            (eq_id,)
        ).fetchone()

        if eq is None:
            return jsonify({
                "success": False,
                "error": "Nie znaleziono sprzętu."
            }), 404

        old_room_id = eq["room_id"]

        if new_room_id == old_room_id:
            return jsonify({
                "success": False,
                "error": "Sprzęt już znajduje się w tej sali"
            }), 400

        old_room = connection.execute(
            "SELECT * FROM rooms WHERE id = ?",
            (old_room_id,)
        ).fetchone()

        new_room = connection.execute(
            "SELECT * FROM rooms WHERE id = ?",
            (new_room_id,)
        ).fetchone()

        if new_room is None:
            return jsonify({
                "success": False,
                "error": "Nie znaleziono wybranej sali"
            }), 404

        moved_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        connection.execute(
            "UPDATE eq SET room_id = ? WHERE id = ?",
            (new_room_id, eq_id)
        )

        connection.execute(
            """
            INSERT INTO movement_history
            (eq_id, from_room_id, to_room_id, moved_at, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (eq_id, old_room_id, new_room_id, moved_at, current_user.id)
        )

        connection.commit()

        return jsonify({
            "success": True,
            "old_room_id": old_room_id,
            "old_room": old_room["name"],
            "new_room_id": new_room_id,
            "new_room": new_room["name"],
            "moved_at": moved_at
        })

    finally:
        connection.close()


@app.route("/eq/<int:eq_id>", methods=["GET", "POST"])
@login_required
def eq_detail(eq_id):
    """
    Szczegóły sprzętu — aktualna lokalizacja, historia przeniesień,
    możliwość przeniesienia do innej sali.

    GET — pokazuje widok z historią.
    POST — obsługuje przeniesienie z formularza HTML (fallback dla
    przeglądarek bez JavaScriptu albo dla zwykłego submit) i przekierowuje
    z powrotem na ten sam widok.

    Args:
        eq_id: ID sprzętu.

    Query string:
        from: skąd użytkownik przyszedł (np. "search") — wpływa na link powrotu.
        q: fraza wyszukiwania, zachowana przy powrocie do wyników.
    """

    connection = get_db_connection()

    try:
        eq = connection.execute(
            """
            SELECT
                eq.*,
                (
                    SELECT COUNT(*)
                    FROM eq AS same_eq
                    WHERE same_eq.name = eq.name
                ) AS name_count
            FROM eq
            WHERE eq.id = ?
            """,
            (eq_id,)
        ).fetchone()

        if eq is None:
            return "Nie znaleziono sprzętu", 404

        eq = dict(eq)

        if eq["name_count"] > 1:
            eq["display_name"] = f'{eq["name"]} #{eq["instance_no"]}'
        else:
            eq["display_name"] = eq["name"]

        if request.method == "POST":
            try:
                new_room_id = int(request.form["room_id"])
            except (KeyError, ValueError):
                return "Nieprawidłowa sala", 400

            old_room_id = eq["room_id"]

            if new_room_id != old_room_id:
                new_room = connection.execute(
                    "SELECT * FROM rooms WHERE id = ?",
                    (new_room_id,)
                ).fetchone()

                if new_room is None:
                    return "Nie znaleziono wybranej sali", 404

                connection.execute(
                    "UPDATE eq SET room_id = ? WHERE id = ?",
                    (new_room_id, eq_id)
                )

                connection.execute(
                    """
                    INSERT INTO movement_history
                    (eq_id, from_room_id, to_room_id, moved_at, user_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        eq_id,
                        old_room_id,
                        new_room_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        current_user.id
                    )
                )

                connection.commit()

            from_page = request.args.get("from")
            search_query = request.args.get("q", "")

            if from_page == "search":
                return redirect(
                    f"/eq/{eq_id}?from=search&q={search_query}"
                )

            return redirect(f"/eq/{eq_id}")

        room = connection.execute(
            "SELECT * FROM rooms WHERE id = ?",
            (eq["room_id"],)
        ).fetchone()

        rooms = connection.execute(
            """
            SELECT * FROM rooms
            ORDER BY
                CASE group_name
                    WHEN 'sww' THEN 1
                    WHEN 'snw' THEN 2
                    WHEN 'deb' THEN 3
                    WHEN 'magazyn' THEN 4
                    ELSE 5
                END,
                name
            """
        ).fetchall()

        history = connection.execute(
            """
            SELECT
                movement_history.id,
                movement_history.from_room_id,
                movement_history.to_room_id,
                movement_history.moved_at,
                from_room.name AS from_room_name,
                to_room.name AS to_room_name,
                users.username AS performed_by
            FROM movement_history
            JOIN rooms AS from_room
                ON movement_history.from_room_id = from_room.id
            JOIN rooms AS to_room
                ON movement_history.to_room_id = to_room.id
            JOIN users
                ON movement_history.user_id = users.id
            WHERE movement_history.eq_id = ?
            ORDER BY movement_history.id DESC
            """,
            (eq_id,)
        ).fetchall()

        return render_template(
            "eq_detail.html",
            eq=eq,
            room=room,
            rooms=rooms,
            history=history,
            from_page=request.args.get("from"),
            search_query=request.args.get("q", "")
        )

    finally:
        connection.close()

@app.route("/account/password", methods=["GET", "POST"])
@login_required
def account_password():
    """
    Formularz zmiany własnego hasła (dla każdego zalogowanego użytkownika).

    Wymaga podania aktualnego hasła, nowego hasła oraz jego powtórzenia.
    Nowe hasło musi mieć co najmniej 5 znaków.
    """

    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        new2 = request.form.get("new_password2", "")

        row = verify_user(current_user.username, current)

        if row is None:
            flash("Aktualne hasło jest nieprawidłowe.", "danger")
            return render_template("account_password.html")

        if len(new) < 5:
            flash("Nowe hasło musi mieć co najmniej 5 znaków.", "danger")
            return render_template("account_password.html")

        if new != new2:
            flash("Nowe hasła nie są identyczne.", "danger")
            return render_template("account_password.html")

        update_password(current_user.id, new)
        flash("Hasło zostało zmienione.", "success")
        return redirect(url_for("home"))

    return render_template("account_password.html")


@app.route("/admin/users")
@admin_required
def admin_users():
    """
    Panel administratora — lista wszystkich użytkowników.

    Pozwala dodawać konta, resetować hasła i usuwać użytkowników.
    Dostęp tylko dla admina.
    """

    users = get_all_users()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@admin_required
def admin_users_add():
    """
    Dodaje nowego użytkownika (tylko admin).

    Waliduje: niepusta nazwa, minimalna długość hasła (5 znaków),
    unikalność nazwy. Hasło jest hashowane przed zapisem.
    """

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"

    if not username:
        flash("Imię nie może być puste.", "danger")
        return redirect(url_for("admin_users"))

    if len(password) < 5:
        flash("Hasło musi mieć co najmniej 5 znaków.", "danger")
        return redirect(url_for("admin_users"))

    if get_user_by_username(username) is not None:
        flash(f"Użytkownik '{username}' już istnieje.", "danger")
        return redirect(url_for("admin_users"))

    create_user(username, password, is_admin=is_admin)
    flash(f"Utworzono użytkownika: {username}", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/reset_password", methods=["POST"])
@admin_required
def admin_users_reset_password(user_id):
    """
    Resetuje hasło wskazanego użytkownika (tylko admin).

    Nie wymaga podania starego hasła — admin ma prawo zresetować je
    każdemu. Waliduje tylko minimalną długość nowego hasła.

    Args:
        user_id: ID użytkownika, którego hasło resetujemy.
    """

    target = get_user_by_id(user_id)

    if target is None:
        flash("Nie znaleziono użytkownika.", "danger")
        return redirect(url_for("admin_users"))

    new = request.form.get("new_password", "")

    if len(new) < 5:
        flash("Hasło musi mieć co najmniej 5 znaków.", "danger")
        return redirect(url_for("admin_users"))

    update_password(user_id, new)
    flash(f"Zresetowano hasło użytkownika: {target['username']}", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_users_delete(user_id):
    """
    Usuwa użytkownika (tylko admin).

    Zabezpieczenia:
    - admin nie może usunąć własnego konta,
    - nie można usunąć ostatniego administratora w systemie
      (żeby nie zablokować dostępu do panelu).

    Args:
        user_id: ID użytkownika do usunięcia.
    """

    target = get_user_by_id(user_id)

    if target is None:
        flash("Nie znaleziono użytkownika.", "danger")
        return redirect(url_for("admin_users"))

    if user_id == current_user.id:
        flash("Nie możesz usunąć własnego konta.", "danger")
        return redirect(url_for("admin_users"))

    if target["is_admin"] and count_admins() <= 1:
        flash("Nie można usunąć ostatniego administratora.", "danger")
        return redirect(url_for("admin_users"))

    delete_user(user_id)
    flash(f"Usunięto użytkownika: {target['username']}", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/rooms")
@admin_required
def admin_rooms():
    """
    Panel administratora — zarządzanie salami.

    Lista wszystkich sal z liczbą sprzętu w każdej oraz akcjami
    zmiany nazwy i usunięcia. Dostęp tylko dla admina.
    """

    rooms = get_rooms_with_counts()
    return render_template("admin_rooms.html", rooms=rooms)


@app.route("/admin/rooms/add", methods=["POST"])
@admin_required
def admin_rooms_add():
    """
    Dodaje nową salę (tylko admin).

    Nazwa musi być niepusta i unikalna. Nowa sala dostaje domyślnie
    grupę kolorystyczną "inne" — przypisanie do właściwej grupy
    robi się przez plik room_groups.py + apply_room_groups.py.
    """

    name = request.form.get("name", "").strip()

    if not name:
        flash("Nazwa sali nie może być pusta.", "danger")
        return redirect(url_for("admin_rooms"))

    connection = get_db_connection()
    try:
        connection.execute(
            "INSERT INTO rooms (name) VALUES (?)",
            (name,)
        )
        connection.commit()
        flash(f"Dodano salę: {name}", "success")
    except sqlite3.IntegrityError:
        flash(f"Sala '{name}' już istnieje.", "danger")
    finally:
        connection.close()

    return redirect(url_for("admin_rooms"))


@app.route("/admin/rooms/<int:room_id>/rename", methods=["POST"])
@admin_required
def admin_rooms_rename(room_id):
    """
    Zmienia nazwę sali (tylko admin).

    Args:
        room_id: ID sali do zmiany nazwy.
    """

    target = get_room_by_id(room_id)

    if target is None:
        flash("Nie znaleziono sali.", "danger")
        return redirect(url_for("admin_rooms"))

    new_name = request.form.get("name", "").strip()

    if not new_name:
        flash("Nazwa sali nie może być pusta.", "danger")
        return redirect(url_for("admin_rooms"))

    if new_name == target["name"]:
        return redirect(url_for("admin_rooms"))

    if rename_room(room_id, new_name):
        flash(f"Zmieniono nazwę na: {new_name}", "success")
    else:
        flash(f"Sala '{new_name}' już istnieje.", "danger")

    return redirect(url_for("admin_rooms"))


@app.route("/admin/rooms/<int:room_id>/delete", methods=["POST"])
@admin_required
def admin_rooms_delete(room_id):
    """
    Usuwa salę (tylko admin).

    Usunięcie jest zablokowane, jeśli sala zawiera jakikolwiek sprzęt
    albo występuje w historii przeniesień — chroni to integralność
    danych i zapobiega osieroceniu referencji.

    Args:
        room_id: ID sali do usunięcia.
    """

    target = get_room_by_id(room_id)

    if target is None:
        flash("Nie znaleziono sali.", "danger")
        return redirect(url_for("admin_rooms"))

    if room_has_equipment(room_id):
        flash(
            f"Nie można usunąć sali '{target['name']}' — znajduje się w niej sprzęt.",
            "danger"
        )
        return redirect(url_for("admin_rooms"))

    if room_has_history(room_id):
        flash(
            f"Nie można usunąć sali '{target['name']}' — występuje w historii przeniesień.",
            "danger"
        )
        return redirect(url_for("admin_rooms"))

    if delete_room(room_id):
        flash(f"Usunięto salę: {target['name']}", "success")
    else:
        flash("Nie udało się usunąć sali.", "danger")

    return redirect(url_for("admin_rooms"))

@app.route("/admin/eq")
@admin_required
def admin_eq():
    """
    Panel administratora — zarządzanie sprzętem.

    Wyświetla cały sprzęt (z nazwą sali) i umożliwia dodawanie,
    zmianę nazwy oraz usuwanie. Lista jest filtrowana i stronicowana
    po stronie klienta (JavaScript).
    """

    items = get_all_eq_with_rooms()
    items = add_display_names(items)

    rooms = get_rooms_with_counts()

    return render_template(
        "admin_eq.html",
        items=items,
        rooms=rooms
    )


@app.route("/admin/eq/add", methods=["POST"])
@admin_required
def admin_eq_add():
    """
    Dodaje nowy sprzęt do wskazanej sali (tylko admin).

    Numer instancji (instance_no) jest nadawany automatycznie —
    najwyższy dotychczasowy numer dla tej nazwy + 1. Dzięki temu
    można dodać kilka sztuk tego samego sprzętu.
    """

    name = request.form.get("name", "").strip()
    room_id_raw = request.form.get("room_id", "")

    if not name:
        flash("Nazwa sprzętu nie może być pusta.", "danger")
        return redirect(url_for("admin_eq"))

    try:
        room_id = int(room_id_raw)
    except (ValueError, TypeError):
        flash("Wybierz salę.", "danger")
        return redirect(url_for("admin_eq"))

    target_room = get_room_by_id(room_id)

    if target_room is None:
        flash("Nie znaleziono wybranej sali.", "danger")
        return redirect(url_for("admin_eq"))

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

    flash(f"Dodano sprzęt: {name}", "success")
    return redirect(url_for("admin_eq"))


@app.route("/admin/eq/<int:eq_id>/edit", methods=["POST"])
@admin_required
def admin_eq_edit(eq_id):
    """
    Zmienia nazwę sprzętu (tylko admin).

    Nie zmienia sali — przenoszenie odbywa się przez widok użytkownika
    (/eq/<id> albo /move_eq/<id>), żeby historia przeniesień była spójna.

    Args:
        eq_id: ID sprzętu do zmiany nazwy.
    """

    target = get_eq_by_id(eq_id)

    if target is None:
        flash("Nie znaleziono sprzętu.", "danger")
        return redirect(url_for("admin_eq"))

    new_name = request.form.get("name", "").strip()

    if not new_name:
        flash("Nazwa sprzętu nie może być pusta.", "danger")
        return redirect(url_for("admin_eq"))

    if new_name == target["name"]:
        return redirect(url_for("admin_eq"))

    if rename_eq(eq_id, new_name):
        flash(f"Zmieniono nazwę na: {new_name}", "success")
    else:
        flash(
            "Nie można zmienić nazwy — konflikt z istniejącym sprzętem.",
            "danger"
        )

    return redirect(url_for("admin_eq"))


@app.route("/admin/eq/<int:eq_id>/delete", methods=["POST"])
@admin_required
def admin_eq_delete(eq_id):
    """
    Usuwa sprzęt (tylko admin).

    Historia przeniesień tego sprzętu jest usuwana automatycznie
    dzięki ON DELETE CASCADE w schemacie bazy.

    Args:
        eq_id: ID sprzętu do usunięcia.
    """
    
    target = get_eq_by_id(eq_id)

    if target is None:
        flash("Nie znaleziono sprzętu.", "danger")
        return redirect(url_for("admin_eq"))

    delete_eq(eq_id)
    flash(f"Usunięto sprzęt: {target['name']}", "success")
    return redirect(url_for("admin_eq"))




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)