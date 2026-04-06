from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "todenso.sqlite3"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "todenso-dev-secret")


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS drawings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                drawing_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def serialize_drawing(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "notes": row["notes"],
        "drawing": json.loads(row["drawing_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.route("/")
def index():
    selected_user_id = request.args.get("user_id", type=int)

    with get_db() as connection:
        users = connection.execute(
            """
            SELECT id, username, full_name, created_at
            FROM users
            ORDER BY datetime(created_at) DESC, id DESC
            """
        ).fetchall()

        selected_user = None
        drawings: list[dict] = []

        if selected_user_id is not None:
            selected_user = connection.execute(
                """
                SELECT id, username, full_name, created_at
                FROM users
                WHERE id = ?
                """,
                (selected_user_id,),
            ).fetchone()

            if selected_user is None:
                abort(404)

            drawing_rows = connection.execute(
                """
                SELECT id, title, notes, drawing_json, created_at, updated_at
                FROM drawings
                WHERE user_id = ?
                ORDER BY datetime(updated_at) DESC, id DESC
                """,
                (selected_user_id,),
            ).fetchall()
            drawings = [serialize_drawing(row) for row in drawing_rows]

    return render_template(
        "index.html",
        users=users,
        selected_user=selected_user,
        drawings=drawings,
    )


@app.route("/users", methods=["POST"])
def create_user():
    username = request.form.get("username", "").strip()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")

    if not username or not full_name or not password:
        flash("Username, full name, and password are required.", "error")
        return redirect(url_for("index"))

    now = datetime.utcnow().isoformat(timespec="seconds")

    try:
        with get_db() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, password_hash, full_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, generate_password_hash(password), full_name, now),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        flash("That username already exists.", "error")
        return redirect(url_for("index"))

    flash("User created successfully.", "success")
    return redirect(url_for("index", user_id=user_id))


@app.route("/drawings", methods=["POST"])
def create_drawing():
    user_id = request.form.get("user_id", type=int)
    password = request.form.get("password", "")
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip()
    drawing_payload = request.form.get("drawing_payload", "").strip()

    if not user_id or not password or not title or not drawing_payload:
        flash("User, password, title, and drawing data are required.", "error")
        return redirect(url_for("index", user_id=user_id))

    try:
        drawing_data = json.loads(drawing_payload)
    except json.JSONDecodeError:
        flash("Drawing data is invalid.", "error")
        return redirect(url_for("index", user_id=user_id))

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if user is None:
            abort(404)

        if not check_password_hash(user["password_hash"], password):
            flash("Password verification failed. Drawing was not saved.", "error")
            return redirect(url_for("index", user_id=user_id))

        now = datetime.utcnow().isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO drawings (user_id, title, notes, drawing_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, notes, json.dumps(drawing_data), now, now),
        )

    flash("Drawing saved successfully.", "success")
    return redirect(url_for("index", user_id=user_id))


@app.route("/api/drawings/<int:drawing_id>")
def drawing_detail(drawing_id: int):
    with get_db() as connection:
        row = connection.execute(
            """
            SELECT id, title, notes, drawing_json, created_at, updated_at
            FROM drawings
            WHERE id = ?
            """,
            (drawing_id,),
        ).fetchone()

    if row is None:
        abort(404)

    return jsonify(serialize_drawing(row))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
