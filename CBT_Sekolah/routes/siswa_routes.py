from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Ujian, JawabanSiswa
from werkzeug.security import generate_password_hash, check_password_hash
import json
import random
from datetime import datetime, timedelta

bp = Blueprint('siswa', __name__)


# ==================== DASHBOARD SISWA ====================
@bp.route('/dashboard')
@login_required
def dashboard():
    # UPDATE: Izinkan Siswa ATAU Admin (untuk preview)
    if current_user.role not in ['siswa', 'admin']: 
        return redirect('/')

    now = datetime.now()
    # Tampilkan ujian yang sedang aktif ATAU baru saja selesai (toleransi 30 menit agar siswa tidak panik jika telat dikit)
    ujian = Ujian.query.filter(
        Ujian.waktu_mulai <= now,
        Ujian.waktu_selesai >= now - timedelta(minutes=30) 
    ).order_by(Ujian.waktu_mulai).all()

    return render_template('siswa/dashboard.html', ujian=ujian, datetime=datetime)


# ==================== HALAMAN UJIAN (FULL LOGIC + ANTI-GESER) ====================
@bp.route('/ujian/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def ujian(ujian_id):
    # UPDATE: Izinkan Siswa ATAU Admin (untuk simulasi)
    if current_user.role not in ['siswa', 'admin']: 
        return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)
    now = datetime.now()

    # Validasi Waktu Awal
    if now < ujian.waktu_mulai:
        flash('Ujian belum dimulai!', 'warning')
        return redirect('/siswa/dashboard')
    
    # [FIX] Toleransi Waktu Submit (misal 2 menit untuk lag jaringan)
    batas_waktu_toleransi = ujian.waktu_selesai + timedelta(minutes=2)
    
    # Jika request halaman (GET) sudah lewat waktu asli, tolak
    if request.method == 'GET' and now > ujian.waktu_selesai:
        flash('Waktu ujian sudah habis!', 'danger')
        return redirect('/siswa/dashboard')
        
    # Jika submit jawaban (POST) lewat toleransi, tolak
    if request.method == 'POST' and now > batas_waktu_toleransi:
        flash('Maaf, waktu batas pengumpulan jawaban sudah terlewati.', 'danger')
        return redirect('/siswa/dashboard')

    # Cek apakah user (Siswa/Admin) sudah pernah mengerjakan
    if JawabanSiswa.query.filter_by(siswa_id=current_user.id, ujian_id=ujian_id).first():
        flash('Anda sudah mengerjakan ujian ini!', 'info')
        return redirect('/siswa/dashboard')

    # Hitung sisa waktu dalam detik (untuk timer JS)
    sisa_waktu_detik = int((ujian.waktu_selesai - now).total_seconds())
    if sisa_waktu_detik < 0:
        sisa_waktu_detik = 0

    # Load Database Soal
    try:
        pg_db = json.loads(ujian.soal_pg) if ujian.soal_pg else []
        essay_db = json.loads(ujian.soal_essay) if ujian.soal_essay else []
    except json.JSONDecodeError:
        pg_db = []
        essay_db = []

    # ==================== PROSES SUBMIT JAWABAN (POST) ====================
    if request.method == 'POST':
        # 1. Hitung Bobot Maksimal Essay
        total_bobot_essay = 0
        for e in essay_db:
            total_bobot_essay += int(e.get('bobot', 0))

        # Max nilai PG adalah sisa dari 100 dikurangi bobot essay
        max_score_pg = 100 - total_bobot_essay
        if max_score_pg < 0: max_score_pg = 0 

        # 2. Proses Jawaban PG (Menggunakan ID sebagai Key)
        jawaban_pg_siswa = {}
        jml_benar = 0

        for i, soal in enumerate(pg_db):
            # Cek ID Soal
            soal_id = soal.get('id')
            
            # Tentukan nama field di form: pg_{ID} atau fallback ke pg_{INDEX}
            form_key = f'pg_{soal_id}' if soal_id else f'pg_{i}'
            
            # Ambil jawaban dari form
            jawaban = request.form.get(form_key)

            # Tentukan Key Penyimpanan: Gunakan ID jika ada, fallback ke Index
            storage_key = soal_id if soal_id else str(i)
            jawaban_pg_siswa[storage_key] = jawaban

            # Cek Kebenaran (Langsung hitung sementara)
            if jawaban and jawaban == soal.get('kunci'):
                jml_benar += 1

        # Hitung Nilai PG Sementara
        if pg_db and len(pg_db) > 0:
            nilai_pg = (jml_benar / len(pg_db)) * max_score_pg
        else:
            nilai_pg = 0

        # 3. Proses Jawaban Essay (Menggunakan ID sebagai Key)
        jawaban_essay_siswa = {}
        for i, soal in enumerate(essay_db):
            soal_id = soal.get('id')
            form_key = f'essay_{soal_id}' if soal_id else f'essay_{i}'
            
            jawaban = request.form.get(form_key, '').strip()
            
            storage_key = soal_id if soal_id else str(i)
            jawaban_essay_siswa[storage_key] = jawaban

        # 4. Simpan ke Database
        jwb = JawabanSiswa(
            siswa_id=current_user.id,
            ujian_id=ujian_id,
            jawaban_pg=json.dumps(jawaban_pg_siswa),
            jawaban_essay=json.dumps(jawaban_essay_siswa),
            nilai_pg=round(nilai_pg, 2),
            nilai_essay=0,  # Menunggu koreksi guru
            total_nilai=round(nilai_pg, 2),  # Sementara total = PG
            waktu_submit=datetime.now()
        )
        db.session.add(jwb)
        db.session.commit()

        flash('Jawaban berhasil dikirim! Nilai akan muncul setelah dikoreksi guru.', 'success')
        return redirect('/siswa/dashboard')

    # ==================== TAMPILAN UJIAN (GET) ====================

    # [FIX] Gunakan Instance Random Lokal agar Thread-Safe & Konsisten per User
    seed_key = f"{current_user.id}_{ujian_id}"
    rng = random.Random(seed_key) 

    # 1. Siapkan Soal PG untuk Tampilan
    pg_tampil = []
    for idx, item in enumerate(pg_db):
        opsi_list = []
        for kode in ['a', 'b', 'c', 'd', 'e']:
            has_text = item.get(kode)
            has_img = item.get(f'{kode}_gambar')

            if has_text or has_img:
                opsi_list.append({
                    'kode': kode.upper(),
                    'teks': item.get(kode, ''),        
                    'gambar': item.get(f'{kode}_gambar', '')
                })
        
        # Masukkan ID ke objek tampilan agar template bisa pakai ID tersebut
        pg_tampil.append({
            'id': item.get('id'),          # PASSING ID
            'original_index': idx,         # Fallback Index
            'soal': item.get('soal', ''),
            'gambar': item.get('gambar', ''),
            'opsi_acak': opsi_list
        })
    
    # Acak urutan soal (opsi jawaban tetap urut A-E sesuai request)
    rng.shuffle(pg_tampil)

    # 2. Siapkan Soal Essay untuk Tampilan
    essay_tampil = []
    for idx, item in enumerate(essay_db):
        essay_tampil.append({
            'id': item.get('id'),          # PASSING ID
            'original_index': idx,         # Fallback Index
            'soal': item.get('soal', ''),
            'gambar': item.get('gambar', ''),
            'bobot': item.get('bobot', 0)
        })
    
    # Acak urutan essay
    rng.shuffle(essay_tampil)

    return render_template('siswa/ujian.html',
                           ujian=ujian,
                           pg_tampil=pg_tampil,
                           essay_tampil=essay_tampil,
                           sisa_waktu_detik=sisa_waktu_detik)


# ==================== GANTI PASSWORD ====================
@bp.route('/ganti_password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if current_user.role not in ['siswa', 'admin']: 
        return redirect('/')

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
            flash('Password berhasil diubah!', 'success')
            return redirect('/siswa/dashboard')

    return render_template('siswa/ganti_password.html')