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

    kelas = db.relationship('Kelas', backref='siswa', lazy=True)
    mapel_diajar = db.relationship('Mapel', backref='guru', lazy=True)
    jawaban = db.relationship("JawabanSiswa", backref="siswa", passive_deletes=True)


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
    mapel_id = db.Column(db.Integer, db.ForeignKey('mapel.id', ondelete='CASCADE'), nullable=False)
    waktu_mulai = db.Column(db.DateTime, nullable=False)
    waktu_selesai = db.Column(db.DateTime, nullable=False)
    durasi_menit = db.Column(db.Integer, default=60)

    soal_pg = db.Column(db.Text)
    soal_essay = db.Column(db.Text)

    mapel = db.relationship('Mapel', backref='ujian', passive_deletes=True)

    # ✔ RELASI YANG BENAR (1↔Many)
    jawaban_siswa = db.relationship(
        'JawabanSiswa',
        backref='ujian',
        passive_deletes=True
    )


# ===================== JAWABAN SISWA =====================
class JawabanSiswa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    ujian_id = db.Column(
        db.Integer,
        db.ForeignKey('ujian.id', ondelete='CASCADE'),
        nullable=False
    )

    jawaban_pg = db.Column(db.Text)
    jawaban_essay = db.Column(db.Text)

    nilai_pg = db.Column(db.Float, default=0)
    nilai_essay = db.Column(db.Float, default=0)
    total_nilai = db.Column(db.Float, default=0)

    waktu_submit = db.Column(db.DateTime, default=datetime.utcnow)