from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ===================== USER =====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, guru, siswa
    nama = db.Column(db.String(100))
    kelas_id = db.Column(db.Integer, db.ForeignKey('kelas.id'))

    # RELASI KE KELAS (hanya untuk siswa)
    kelas = db.relationship('Kelas', backref='siswa', lazy=True)

    # Relasi untuk guru → mapel yang diajar
    mapel_diajar = db.relationship('Mapel', backref='guru', lazy=True)


# ===================== KELAS =====================
class Kelas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_kelas = db.Column(db.String(50), unique=True, nullable=False)


# ===================== MATA PELAJARAN =====================
class Mapel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    guru_id = db.Column(db.Integer, db.ForeignKey('user.id'))


# ===================== UJIAN =====================
class Ujian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(150), nullable=False)
    mapel_id = db.Column(db.Integer, db.ForeignKey('mapel.id'), nullable=False)
    waktu_mulai = db.Column(db.DateTime, nullable=False)
    waktu_selesai = db.Column(db.DateTime, nullable=False)
    durasi_menit = db.Column(db.Integer, default=60)

    # Simpan soal dalam format JSON (string)
    soal_pg = db.Column(db.Text)  # [{"soal": "...", "a": "...", "b": "...", "c": "...", "d": "...", "kunci": "A"}, ...]
    soal_essay = db.Column(db.Text)  # [{"soal": "...", "bobot": 20}, ...]

    # Relasi
    mapel = db.relationship('Mapel', backref='ujian')


# ===================== JAWABAN SISWA =====================
class JawabanSiswa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ujian_id = db.Column(db.Integer, db.ForeignKey('ujian.id'), nullable=False)

    jawaban_pg = db.Column(db.Text)  # JSON: {"1": "A", "2": "C", ...}
    jawaban_essay = db.Column(db.Text)  # JSON: {"1": "Jawaban siswa...", "2": "..."}

    nilai_pg = db.Column(db.Float, default=0)
    nilai_essay = db.Column(db.Float, default=0)
    total_nilai = db.Column(db.Float, default=0)
    waktu_submit = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi
    siswa = db.relationship('User', backref='jawaban')
    ujian = db.relationship('Ujian', backref='jawaban_siswa')