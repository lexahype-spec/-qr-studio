from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from io import BytesIO
from datetime import datetime
import sqlite3
import qrcode
from qrcode.constants import ERROR_CORRECT_M

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DATABASE = "qr_history.db"
MAX_TEXT_LENGTH = 2000

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qr_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                image_png BLOB NOT NULL
            )
        """)

def make_qr_png(text):
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()

@app.get("/")
def index():
    with get_db() as conn:
        history = conn.execute(
            "SELECT id, content, created_at FROM qr_history ORDER BY id DESC"
        ).fetchall()
    return render_template("index.html", history=history, max_text_length=MAX_TEXT_LENGTH)

@app.post("/generate")
def generate():
    content = (request.form.get("content") or "").strip()
    if not content:
        flash("Введите текст или ссылку.", "warning")
        return redirect(url_for("index"))
    if len(content) > MAX_TEXT_LENGTH:
        flash(f"Слишком длинный текст. Максимум — {MAX_TEXT_LENGTH} символов.", "warning")
        return redirect(url_for("index"))

    try:
        png = make_qr_png(content)
    except Exception:
        flash("Не удалось создать QR-код. Попробуйте сократить текст.", "danger")
        return redirect(url_for("index"))

    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO qr_history (content, created_at, image_png) VALUES (?, ?, ?)",
            (content, created_at, png),
        )
        new_id = cursor.lastrowid
    return redirect(url_for("index", created=new_id))

@app.get("/download/<int:qr_id>")
def download(qr_id):
    with get_db() as conn:
        item = conn.execute("SELECT image_png FROM qr_history WHERE id = ?", (qr_id,)).fetchone()
    if item is None:
        abort(404)
    return send_file(
        BytesIO(item["image_png"]),
        mimetype="image/png",
        as_attachment=True,
        download_name=f"qr-code-{qr_id}.png",
    )

@app.post("/delete/<int:qr_id>")
def delete(qr_id):
    with get_db() as conn:
        conn.execute("DELETE FROM qr_history WHERE id = ?", (qr_id,))
    flash("Запись удалена из истории.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
