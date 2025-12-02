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
    # UPDATE: Izinkan Siswa ATAU Admin (untuk preview)
    if current_user.role not in ['siswa', 'admin']: 
        return redirect('/')
    
    ujian = Ujian.query.filter(Ujian.waktu_selesai > datetime.now()).order_by(Ujian.waktu_mulai).all()

    return render_template('siswa/dashboard.html', ujian=ujian, datetime=datetime)


# ==================== HALAMAN UJIAN (FULL LOGIC) ====================
@bp.route('/ujian/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def ujian(ujian_id):
    # UPDATE: Izinkan Siswa ATAU Admin (untuk simulasi)
    if current_user.role not in ['siswa', 'admin']: 
        return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)
    now = datetime.now()

    # Validasi Waktu & Akses
    if now < ujian.waktu_mulai:
        flash('Ujian belum dimulai!', 'warning')
        return redirect('/siswa/dashboard')
    if now > ujian.waktu_selesai:
        flash('Waktu ujian sudah habis!', 'danger')
        return redirect('/siswa/dashboard')

    # Cek apakah user (Siswa/Admin) sudah pernah mengerjakan
    if JawabanSiswa.query.filter_by(siswa_id=current_user.id, ujian_id=ujian_id).first():
        flash('Anda sudah mengerjakan ujian ini!', 'info')
        return redirect('/siswa/dashboard')

    # Hitung sisa waktu dalam detik (untuk timer JS)
    sisa_waktu_detik = int((ujian.waktu_selesai - now).total_seconds())
    if sisa_waktu_detik < 0:
        sisa_waktu_detik = 0

    # Load Database Asli
    pg_db = json.loads(ujian.soal_pg) if ujian.soal_pg else []
    essay_db = json.loads(ujian.soal_essay) if ujian.soal_essay else []

    if request.method == 'POST':
        # --- 1. HITUNG BOBOT MAKSIMAL ---
        total_bobot_essay = 0
        for e in essay_db:
            total_bobot_essay += int(e.get('bobot', 0))

        # Max nilai PG adalah sisa dari 100 dikurangi bobot essay
        # Contoh: Jika Essay 40 poin, maka PG maksimal 60 poin.
        max_score_pg = 100 - total_bobot_essay
        if max_score_pg < 0: max_score_pg = 0  # Safety jika bobot essay > 100

        # --- 2. HITUNG SKOR PG SISWA ---
        jawaban_pg_siswa = {}
        jml_benar = 0

        for i, soal in enumerate(pg_db):
            # Ambil jawaban berdasarkan index asli
            jawaban = request.form.get(f'pg_{i}')
            jawaban_pg_siswa[str(i)] = jawaban

            if jawaban and jawaban == soal['kunci']:
                jml_benar += 1

        # Rumus Baru: (Benar / Total Soal) * Max Score PG
        if pg_db:
            nilai_pg = (jml_benar / len(pg_db)) * max_score_pg
        else:
            nilai_pg = 0

        # --- 3. SIMPAN JAWABAN ESSAY ---
        jawaban_essay_siswa = {}
        for i, soal in enumerate(essay_db):
            jawaban = request.form.get(f'essay_{i}', '').strip()
            jawaban_essay_siswa[str(i)] = jawaban

        # --- 4. SIMPAN KE DATABASE ---
        # Catatan: Jika Admin mengerjakan, data tersimpan dengan ID Admin
        jwb = JawabanSiswa(
            siswa_id=current_user.id,
            ujian_id=ujian_id,
            jawaban_pg=json.dumps(jawaban_pg_siswa),
            jawaban_essay=json.dumps(jawaban_essay_siswa),
            nilai_pg=round(nilai_pg, 2),
            nilai_essay=0,  # Menunggu koreksi guru
            total_nilai=round(nilai_pg, 2),  # Sementara total = PG (sampai guru mengoreksi)
            waktu_submit=datetime.now()
        )
        db.session.add(jwb)
        db.session.commit()

        flash('Jawaban berhasil dikirim! Nilai akan muncul setelah dikoreksi guru.', 'success')
        return redirect('/siswa/dashboard')

    # --- PENGACAKAN TAMPILAN (GET REQUEST) ---

    # [FIX] Set Seed agar urutan acak KONSISTEN per siswa per ujian
    # Ini mencegah soal berubah urutan saat siswa melakukan refresh halaman
    seed_key = f"{current_user.id}_{ujian_id}"
    random.seed(seed_key)

    # 1. Acak PG (Tapi Opsi Tidak Diacak)
    pg_tampil = []
    for idx, item in enumerate(pg_db):
        opsi_list = []
        for kode in ['a', 'b', 'c', 'd', 'e']:
            # Cek apakah ada teks ATAU ada gambar
            has_text = item.get(kode)
            has_img = item.get(f'{kode}_gambar')

            if has_text or has_img:
                opsi_list.append({
                    'kode': kode.upper(),
                    'teks': item.get(kode, ''),        # Teks opsi
                    'gambar': item.get(f'{kode}_gambar', '') # Gambar opsi (NEW)
                })
        
        # [UPDATE] Nonaktifkan pengacakan opsi agar urutan tetap A, B, C, D, E
        # random.shuffle(opsi_list) 
        
        pg_tampil.append({
            'original_index': idx,
            'soal': item['soal'],
            'gambar': item.get('gambar', ''),
            'opsi_acak': opsi_list
        })
    
    random.shuffle(pg_tampil) # Urutan SOAL tetap diacak (konsisten karena seed)

    # 2. Acak Essay
    essay_tampil = []
    for idx, item in enumerate(essay_db):
        essay_tampil.append({
            'original_index': idx,
            'soal': item['soal'],
            'gambar': item.get('gambar', ''),
            'bobot': item['bobot']
        })
    random.shuffle(essay_tampil) # Urutan ESSAY juga diacak

    return render_template('siswa/ujian.html',
                           ujian=ujian,
                           pg_tampil=pg_tampil,
                           essay_tampil=essay_tampil,
                           sisa_waktu_detik=sisa_waktu_detik)


# ==================== GANTI PASSWORD ====================
@bp.route('/ganti_password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    # UPDATE: Izinkan Siswa ATAU Admin
    if current_user.role not in ['siswa', 'admin']: 
        return redirect('/')

    if request.method == 'POST':
        old_pass = request.form['old_pass']
        new_pass = request.form['new_pass']
        confirm_pass = request.form['confirm_pass']

        # 1. Cek Password Lama
        if not check_password_hash(current_user.password, old_pass):
            flash('Password lama salah!', 'danger')

        # 2. Cek Konfirmasi Password Baru
        elif new_pass != confirm_pass:
            flash('Konfirmasi password baru tidak cocok!', 'warning')

        # 3. Validasi Panjang Password
        elif len(new_pass) < 6:
            flash('Password baru minimal 6 karakter!', 'warning')

        else:
            # 4. Update Password (Hash Dulu!)
            current_user.password = generate_password_hash(new_pass)
            db.session.commit()
            
            # Jika admin mengganti password di sini, yang terganti adalah password akun admin sendiri
            flash('Password berhasil diubah!', 'success')
            return redirect('/siswa/dashboard')

    return render_template('siswa/ganti_password.html')