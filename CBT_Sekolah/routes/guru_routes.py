# Tambahkan ini di atas route (pastikan ada)
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Mapel, Ujian
from datetime import datetime
import json
import pandas as pd

bp = Blueprint('guru', __name__)


# DASHBOARD GURU
@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'guru':
        return redirect('/')
    mapel = Mapel.query.filter_by(guru_id=current_user.id).all()
    ujian = Ujian.query.join(Mapel).filter(Mapel.guru_id == current_user.id).all()
    return render_template('guru/dashboard.html', mapel=mapel, ujian=ujian)


# UPLOAD SOAL (SUDAH BENAR — HANYA TAMBAH VALIDASI)
@bp.route('/upload_soal/<int:mapel_id>', methods=['GET', 'POST'])
@login_required
def upload_soal(mapel_id):
    if current_user.role != 'guru':
        return redirect('/')

    mapel = Mapel.query.get_or_404(mapel_id)
    if mapel.guru_id != current_user.id:
        flash('Anda tidak berhak mengunggah soal untuk mapel ini!', 'danger')
        return redirect('/guru/dashboard')

    if request.method == 'POST':
        judul = request.form['judul'].strip()
        waktu_mulai = request.form['waktu_mulai']
        waktu_selesai = request.form['waktu_selesai']
        file = request.files['excel']

        if not judul or not waktu_mulai or not waktu_selesai or not file:
            flash('Semua field wajib diisi!', 'danger')
            return redirect(request.url)

        try:
            mulai = datetime.strptime(waktu_mulai, '%Y-%m-%dT%H:%M')
            selesai = datetime.strptime(waktu_selesai, '%Y-%m-%dT%H:%M')
        except:
            flash('Format waktu salah!', 'danger')
            return redirect(request.url)

        df = pd.read_excel(file)
        pg = []
        essay = []

        for _, row in df.iterrows():
            tipe = str(row['tipe']).strip().lower()
            if tipe == 'pg':
                pg.append({
                    "soal": str(row['soal']),
                    "a": str(row['a']), "b": str(row['b']),
                    "c": str(row['c']), "d": str(row['d']),
                    "kunci": str(row['kunci']).upper()
                })
            elif tipe == 'essay':
                essay.append({
                    "soal": str(row['soal']),
                    "bobot": int(row['bobot'])
                })

        ujian = Ujian(
            mapel_id=mapel_id,
            judul=judul,
            waktu_mulai=mulai,
            waktu_selesai=selesai,
            durasi_menit=60,  # bisa ditambah form kalau mau
            soal_pg=json.dumps(pg, ensure_ascii=False),
            soal_essay=json.dumps(essay, ensure_ascii=False)
        )
        db.session.add(ujian)
        db.session.commit()
        flash(f'Ujian "{judul}" berhasil dibuat!', 'success')
        return redirect('/guru/dashboard')

    return render_template('guru/upload_soal.html', mapel=mapel)