import os
from datetime import date
from functools import wraps

import psycopg2
from flask import (Flask, flash, redirect, render_template, request, session, url_for)

from psycopg2 import errors
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ganti-secret-key-ini")

LAMA_PINJAM_HARI = 7  # Lama peminjaman buku dalam hari


# Helper
#------------------------------
def query_all(sql, params=None):
    conn = get_db_connection()
    try :
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

def query_one(sql, params=None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()

def execute(sql, params=None):
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    finally:
        conn.close()

def login_required(role):
    """Batasi halaman hanya untuk 'admin' atau 'user' """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                flash("Silakan login terlebih dahulu.", "warning")
                return redirect(url_for("login" if role == "admin" else "login_user"))
            if session.get("role") != role:
                flash("Kamu tidak mempunyai akses ke halaman itu.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def login_any(fn):
    """Halaman yang hanya boleh dibuka admin maupun user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login_user"))
        return fn(*args, **kwargs)
    return wrapper

def seed_admin_dari_env():
    """Buat admin awal dari ADMIN_USERNAME / ADMIN_PASSWORD di .env (jika belum ada)."""
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        return
    ada = query_one("SELECT id FROM admin WHERE username = %s", (username,))
    if not ada:
        execute("INSERT INTO admin (username, password) VALUES (%s, %s)",
                (username, generate_password_hash(password)))


#Auth Admin
#------------------------------
@app.route("/")
def index():
    if "username" in session:
        # Cek apakah dia admin atau user
        if session.get("role") == "admin":
            return redirect(url_for("dashboard"))
        else:
            return redirect(url_for("dashboard_user"))
    return redirect(url_for("login_user"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        admin = query_one("SELECT * FROM admin WHERE username = %s", (username,))
        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session.update(user_id=admin["id"], username=admin["username"], role="admin")
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "danger")
    return render_template("login.html", peran="admin",
                        aksi=url_for("login"),
                        link_daftar=url_for("register"),
                        link_lain=url_for("login_user"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if password != request.form["konfirmasi_password"]:
            flash("Konfirmasi password tidak sama.", "danger")
        elif len(password) < 8:
            flash("Password minimal 8 karakter.", "danger")
        else:
            try:
                execute("INSERT INTO admin (username, password) VALUES (%s, %s)",
                        (username, generate_password_hash(password)))
                flash("Registrasi admin berhasil. Silakan login.", "success")
                return redirect(url_for("login"))
            except errors.UniqueViolation:
                flash("Username sudah dipakai.", "danger")
    return render_template("register.html", peran="admin",
                        aksi=url_for("register"),
                        link_login=url_for("login"))

# Auth User (tabel user)
#------------------------------

@app.route("/user/login", methods=["GET", "POST"])
def login_user():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        user = query_one('SELECT * FROM "user" WHERE username = %s', (username,))

        if user and check_password_hash(user["password"], password):
            session.clear()
            session.update(user_id=user["id"],
                            username=user["username"], 
                            nama=user["nama_lengkap"],
                            role="user")
            return redirect(url_for("peminjaman"))
        
        flash("Username atau password salah.", "danger")
    return render_template("login.html", peran="user",
                        aksi=url_for("login_user"),
                        link_daftar=url_for("register_user"),
                        link_lain=url_for("login"))

@app.route("/user/register", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        nama = request.form["nama_lengkap"].strip()
        username = request.form["username"].strip()
        password = request.form["password"]
        email = request.form["email"].strip().lower()

        if password != request.form["konfirmasi_password"]:
            flash("Konfirmasi password tidak sama.", "danger")
        elif len(password) < 8:
            flash("Password minimal 8 karakter.", "danger")
        else:
            try:
                execute('INSERT INTO "user" (nama_lengkap, username, email, password) '
                "VALUES (%s, %s, %s, %s)",
                (nama, username, email, generate_password_hash(password)))
                flash("Registrasi user berhasil. Silakan login.", "success")
                return redirect(url_for("login_user"))
            
            except errors.UniqueViolation as e:
                pesan_error = str(e)
                if "email" in pesan_error:
                    flash("Email sudah terdaftar. Gunakan email lain.", "danger")
                else:
                    flash("Username sudah terdaftar.", "danger")
    return render_template("register.html", peran="user",
                        aksi=url_for("register_user"),
                        link_login=url_for("login_user"))

@app.route("/logout", methods=["POST"])
def logout():
    role = session.get("role")
    session.clear()
    flash("Berhasil logout.", "success")
    return redirect(url_for("login" if role == "admin" else "login_user"))


#Dashboard Admin & User
#------------------------------

@app.route("/dashboard")
@login_any
def dashboard():
    buku_tersedia = query_all(
        "SELECT id, judul, penerbit, stok FROM buku WHERE stok > 0 ORDER BY judul")
    stat = query_one(
        "SELECT COUNT(*) as total_buku, COALESCE(SUM(stok), 0) AS total_stok FROM buku")
    return render_template("dashboard.html", 
                        buku_tersedia=buku_tersedia,
                        total_buku=stat["total_buku"],
                        total_stok=stat["total_stok"])

@app.route("/dashboard_user")
@login_required("user")
def dashboard_user():
    # Ambil data buku yang tersedia
    buku_tersedia = query_all("SELECT * FROM buku WHERE stok > 0 ORDER BY judul")
    total_judul = len(buku_tersedia)
    
    # Ambil total stok semua buku
    stat = query_one("SELECT COALESCE(SUM(stok), 0) AS total_stok FROM buku")
    total_stok = stat["total_stok"]
    
    # Ambil jumlah buku yang sedang dipinjam oleh user ini
    pinjam = query_one(
        "SELECT COUNT(*) as sedang_dipinjam FROM peminjaman WHERE user_id = %s AND status = 'dipinjam'", 
        (session["user_id"],)
    )
    sedang_dipinjam = pinjam["sedang_dipinjam"]
    
    return render_template("dashboard_user.html", 
                           buku_tersedia=buku_tersedia,
                           total_judul=total_judul,
                           total_stok=total_stok,
                           sedang_dipinjam=sedang_dipinjam)



#Peminjaman buku (Khusus User)
#------------------------------

@app.route("/peminjaman")
@login_required("user")
def peminjaman():
    buku_tersedia = query_all(
        """SELECT b.id, b.judul, b.penulis, b.penerbit, b.stok,
        EXISTS (SELECT 1
        FROM peminjaman p
        WHERE p.buku_id = b.id AND p.user_id = %s
        AND p.status = 'dipinjam') AS sedang_dipinjam
        FROM buku b
        WHERE b.stok > 0
        ORDER BY b.judul""", (session["user_id"],))

    riwayat = query_all("""
        SELECT p.id, b.judul, p.tanggal_pinjam, p.jatuh_tempo, p.tanggal_kembali, p.status
        FROM peminjaman p
        JOIN buku b ON b.id = p.buku_id
        WHERE p.user_id = %s
        ORDER BY p.status = 'dipinjam' DESC, p.id DESC""", (session["user_id"],))
    return  render_template("peminjaman.html", buku_tersedia=buku_tersedia, 
                            riwayat=riwayat, lama_pinjam=LAMA_PINJAM_HARI,
                            hari_ini=date.today())

@app.route("/peminjaman/ajukan/<int:buku_id>", methods=["POST"])
@login_required("user")
def ajukan_peminjaman(buku_id):
    conn = get_db_connection()
    try:
        with conn: # satu transaksi: kurangi stok + catat peminjaman
            with conn.cursor() as cur:
                # Atomik: stok hanya berkurang jika masih > 0 (aman dari rebutan).
                cur.execute(
                    "UPDATE buku SET stok = stok - 1 "
                    "WHERE id = %s AND stok > 0 RETURNING judul", (buku_id,))
                buku = cur.fetchone()
                if not buku:
                    flash("Buku tidak ditemukan atau stok sudah habis.", "danger")
                    return redirect(url_for("peminjaman"))
                cur.execute(
                    "INSERT INTO peminjaman (user_id, buku_id, jatuh_tempo)"
                    "VALUES (%s, %s, CURRENT_DATE + %s)",
                    (session["user_id"], buku_id, LAMA_PINJAM_HARI))
        flash(f"Peminjaman \"{buku['judul']}\" berhasil. "
            f"Harap kembalikan dalam {LAMA_PINJAM_HARI} hari.", "success")
    except errors.UniqueViolation:
        flash("Kamu masih meminjam buku ini, kembalikan dulu sebelum meminjam yang lain.", "warning")
    finally:
        conn.close()
    return redirect(url_for("peminjaman"))

@app.route("/peminjaman/kembalikan/<int:peminjaman_id>", methods=["POST"])
@login_required("user")
def kembalikan(peminjaman_id):
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # Tandai peminjaman sebagai dikembalikan (menggunakan triple quotes bersih tanpa kutipan tambahan di dalamnya)
                cur.execute("""
                    UPDATE peminjaman 
                    SET status = 'dikembalikan', tanggal_kembali = CURRENT_DATE 
                    WHERE id = %s AND user_id = %s AND status = 'dipinjam' 
                    RETURNING buku_id
                """, (peminjaman_id, session["user_id"]))
                
                row = cur.fetchone()
                if not row:
                    flash("Data peminjaman tidak ditemukan.", "danger")
                    return redirect(url_for("peminjaman"))
                
                # Tambah stok buku
                cur.execute("UPDATE buku SET stok = stok + 1 WHERE id = %s", (row["buku_id"],))
                
        flash("Buku berhasil dikembalikan. Terima kasih!", "success")
    finally:
        conn.close()
    return redirect(url_for("peminjaman"))


#CRUD buku (Khusus Admin)
#------------------------------

def _ambil_form_buku():
    return (request.form["judul"].strip(), request.form["penulis"].strip(),
            request.form["penerbit"].strip(),
            int(request.form["tahun_terbit"]), int(request.form["stok"]))

@app.route("/buku")
@login_required("admin")
def daftar_buku():
    daftar = query_all("SELECT * FROM buku ORDER BY id")
    return render_template("buku.html", daftar=daftar)


@app.route("/buku/tambah", methods=["GET", "POST"])
@login_required("admin")
def tambah_buku():
    if request.method == "POST":
        try:
            execute(
                "INSERT INTO buku (judul, penulis, penerbit, tahun_terbit, stok)"
                "VALUES (%s, %s, %s, %s, %s)", _ambil_form_buku())
            flash("Buku berhasil ditambahkan.", "success")
            return redirect(url_for("daftar_buku"))
        except (psycopg2.Error, ValueError):
            flash(f"Data tidak valid (cek tahun terbit 1901-2155 dan stok >= 0).", "danger")
    return render_template("form_buku.html", buku=None, tahun_sekarang=date.today().year)

@app.route("/buku/<int:id>/edit", methods=["GET", "POST"])
@login_required("admin")
def edit_buku(id):
    buku = query_one("SELECT * FROM buku WHERE id = %s", (id,))
    if not buku:
        flash("Buku tidak ditemukan.", "danger")
        return redirect(url_for("daftar_buku"))

    if request.method == "POST":
        try:
            execute(
                "UPDATE buku SET judul = %s, penulis = %s, penerbit = %s,"
                "tahun_terbit = %s, stok = %s WHERE id = %s", _ambil_form_buku() + (id,))
            flash("Data buku berhasil diubah.", "success")
            return redirect(url_for("daftar_buku"))
        except (psycopg2.Error, ValueError):
            flash(f"Data tidak valid (cek tahun terbit 1901-2155 dan stok >= 0).", "danger")
    return render_template("form_buku.html", buku=buku, tahun_sekarang=date.today().year)

@app.route("/buku/<int:id>/hapus", methods=["POST"])
@login_required("admin")
def hapus_buku(id):
    try:
        execute("DELETE FROM buku WHERE id = %s", (id,))
        flash("Buku berhasil dihapus.", "success")
    except errors.ForeignKeyViolation:
        flash("Gagal menghapus buku. Buku masih dipinjam.", "danger")
    return redirect(url_for("daftar_buku"))


if __name__ == "__main__":
    seed_admin_dari_env()
    app.run(debug=True)