from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Ujian, JawabanSiswa
from werkzeug.security import generate_password_hash, check_password_hash
import json, random
from datetime import datetime

bp = Blueprint('siswa', __name__)

# ==================== DASHBOARD SISWA ====================
@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'siswa': return redirect('/')
    ujian = Ujian.query.filter(Ujian.waktu_selesai > datetime.now()).order_by(Ujian.waktu_mulai).all()

    return render_template('siswa/dashboard.html', ujian=ujian, datetime=datetime)


# ==================== HALAMAN UJIAN (LOGIK TIMER & SECURITY UPDATED) ====================
@bp.route('/ujian/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def ujian(ujian_id):
    if current_user.role != 'siswa': return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)
    now = datetime.now()

    # 1. Validasi: Apakah ujian sudah dimulai / selesai?
    if now < ujian.waktu_mulai:
        flash('Ujian belum dimulai!', 'warning')
        return redirect('/siswa/dashboard')
    if now > ujian.waktu_selesai:
        flash('Waktu ujian sudah habis!', 'danger')
        return redirect('/siswa/dashboard')

    # 2. Validasi: Apakah siswa sudah pernah mengerjakan? (Sistem Lock Satu Kali)
    if JawabanSiswa.query.filter_by(siswa_id=current_user.id, ujian_id=ujian_id).first():
        flash('Anda sudah menyelesaikan ujian ini! Tidak bisa mengulang.', 'info')
        return redirect('/siswa/dashboard')

    # --- LOGIKA TIMER BARU (DURASI vs TIMEOUT) ---
    # Hitung durasi ujian dalam detik (misal: 90 menit = 5400 detik)
    durasi_detik = ujian.durasi_menit * 60
    
    # Hitung sisa waktu global sampai ujian ditutup (Waktu Selesai - Sekarang)
    sisa_global_detik = int((ujian.waktu_selesai - now).total_seconds())
    
    # Logika: Jika Durasi > Sisa Timeout Global, maka pakai Timeout. Jika tidak, pakai Durasi.
    # Contoh: Durasi 90 menit. Sisa waktu global tinggal 10 menit. Maka timer = 10 menit.
    # Fungsi min() otomatis mengambil nilai terkecil.
    sisa_waktu_detik = min(durasi_detik, sisa_global_detik)
    
    # Safety check agar tidak minus
    if sisa_waktu_detik < 0:
        sisa_waktu_detik = 0

    # Load Soal dari Database
    pg_db = json.loads(ujian.soal_pg) if ujian.soal_pg else []
    essay_db = json.loads(ujian.soal_essay) if ujian.soal_essay else []

    if request.method == 'POST':
        # --- PROSES PENILAIAN & SIMPAN JAWABAN ---
        total_bobot_essay = sum(int(e.get('bobot', 0)) for e in essay_db)
        max_score_pg = max(0, 100 - total_bobot_essay)

        jawaban_pg_siswa = {}
        jml_benar = 0

        for i, soal in enumerate(pg_db):
            jawaban = request.form.get(f'pg_{i}')
            jawaban_pg_siswa[str(i)] = jawaban
            if jawaban and jawaban == soal['kunci']:
                jml_benar += 1

        nilai_pg = (jml_benar / len(pg_db)) * max_score_pg if pg_db else 0

        jawaban_essay_siswa = {}
        for i, soal in enumerate(essay_db):
            jawaban_essay_siswa[str(i)] = request.form.get(f'essay_{i}', '').strip()

        # Simpan ke Database (Ini yang membuat siswa tidak bisa ujian lagi)
        jwb = JawabanSiswa(
            siswa_id=current_user.id,
            ujian_id=ujian_id,
            jawaban_pg=json.dumps(jawaban_pg_siswa),
            jawaban_essay=json.dumps(jawaban_essay_siswa),
            nilai_pg=round(nilai_pg, 2),
            nilai_essay=0,
            total_nilai=round(nilai_pg, 2),
            waktu_submit=datetime.now()
        )
        db.session.add(jwb)
        db.session.commit()

        flash('Jawaban berhasil dikirim otomatis oleh sistem.', 'success')
        return redirect('/siswa/dashboard')

    # --- PENGACAKAN SOAL UNTUK TAMPILAN ---
    pg_tampil = []
    for idx, item in enumerate(pg_db):
        opsi_list = []
        for kode in ['a', 'b', 'c', 'd', 'e']:
            if item.get(kode):
                opsi_list.append({'kode': kode.upper(), 'teks': item[kode]})
        random.shuffle(opsi_list)
        pg_tampil.append({
            'original_index': idx,
            'soal': item['soal'],
            'opsi_acak': opsi_list
        })
    random.shuffle(pg_tampil)

    essay_tampil = []
    for idx, item in enumerate(essay_db):
        essay_tampil.append({
            'original_index': idx,
            'soal': item['soal'],
            'bobot': item['bobot']
        })
    random.shuffle(essay_tampil)

    return render_template('siswa/ujian.html',
                           ujian=ujian,
                           pg_tampil=pg_tampil,
                           essay_tampil=essay_tampil,
                           sisa_waktu_detik=sisa_waktu_detik) # Mengirim detik yang sudah dihitung logic-nya


# ==================== GANTI PASSWORD ====================
@bp.route('/ganti_password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if current_user.role != 'siswa': return redirect('/')

    if request.method == 'POST':
        old_pass = request.form['old_pass']
        new_pass = request.form['new_pass']
        confirm_pass = request.form['confirm_pass']

        if not check_password_hash(current_user.password, old_pass):
            flash('Password lama salah!', 'danger')
        elif new_pass != confirm_pass:
            flash('Konfirmasi password baru tidak cocok!', 'warning')
        elif len(new_pass) < 6:
            flash('Password baru minimal 6 karakter!', 'warning')
        else:
            current_user.password = generate_password_hash(new_pass)
            db.session.commit()
            flash('Password berhasil diubah! Silakan login ulang nanti.', 'success')
            return redirect('/siswa/dashboard')

    return render_template('siswa/ganti_password.html')