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

# ==================== HALAMAN UJIAN (FULL FEATURE: ACAK + VALIDASI) ====================
@bp.route('/ujian/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def ujian(ujian_id):
    # 1. Cek Role Siswa
    if current_user.role != 'siswa': 
        return redirect('/')
    
    # 2. Ambil Data Ujian
    ujian = Ujian.query.get_or_404(ujian_id)
    now = datetime.now()

    # 3. Validasi Waktu Ujian
    if now < ujian.waktu_mulai:
        flash('Ujian belum dimulai!', 'warning')
        return redirect('/siswa/dashboard')
    if now > ujian.waktu_selesai:
        flash('Waktu ujian sudah habis!', 'danger')
        return redirect('/siswa/dashboard')

    # 4. Cek Apakah Siswa Sudah Mengerjakan?
    sudah_jwb = JawabanSiswa.query.filter_by(siswa_id=current_user.id, ujian_id=ujian_id).first()
    if sudah_jwb:
        flash('Anda sudah mengerjakan ujian ini! Nilai akan keluar setelah dikoreksi guru.', 'info')
        return redirect('/siswa/dashboard')

    # Load Soal Asli dari Database (Urutan Asli untuk Kunci Jawaban)
    try:
        pg_db = json.loads(ujian.soal_pg) if ujian.soal_pg else []
        essay_db = json.loads(ujian.soal_essay) if ujian.soal_essay else []
    except:
        pg_db = []
        essay_db = []

    # --- JIKA METODE POST (SISWA MENGUMPULKAN JAWABAN) ---
    if request.method == 'POST':
        # A. Hitung Nilai Pilihan Ganda
        # Backend menilai berdasarkan urutan index asli database (0, 1, 2...)
        # Frontend mengirim name="pg_0", "pg_5" sesuai original_index walau tampilan diacak
        
        jawaban_pg_siswa = {}
        jml_benar = 0
        
        for i, soal in enumerate(pg_db):
            # Ambil jawaban dari input name="pg_{index_asli}"
            jawaban = request.form.get(f'pg_{i}') 
            jawaban_pg_siswa[str(i)] = jawaban
            
            # Cek Kunci Jawaban
            if jawaban and jawaban == soal['kunci']:
                jml_benar += 1
        
        # Hitung skor PG (Skala 100)
        nilai_pg = (jml_benar / len(pg_db)) * 100 if pg_db else 0

        # B. Simpan Jawaban Essay
        jawaban_essay_siswa = {}
        for i, soal in enumerate(essay_db):
            # Ambil jawaban dari input name="essay_{index_asli}"
            jawaban = request.form.get(f'essay_{i}', '').strip()
            jawaban_essay_siswa[str(i)] = jawaban

        # C. Simpan ke Database
        jwb = JawabanSiswa(
            siswa_id=current_user.id,
            ujian_id=ujian_id,
            jawaban_pg=json.dumps(jawaban_pg_siswa),
            jawaban_essay=json.dumps(jawaban_essay_siswa),
            nilai_pg=round(nilai_pg, 2),
            nilai_essay=0,                  # Essay default 0, menunggu koreksi guru
            total_nilai=round(nilai_pg, 2), # Sementara total = nilai PG
            waktu_submit=datetime.now()
        )
        db.session.add(jwb)
        db.session.commit()
        
        flash('Jawaban berhasil dikirim! Terima kasih telah mengerjakan ujian.', 'success')
        return redirect('/siswa/dashboard')

    # --- JIKA METODE GET (TAMPILKAN SOAL KE SISWA) ---
    
    # 1. Acak Soal Pilihan Ganda & Opsinya
    pg_tampil = []
    for idx, item in enumerate(pg_db):
        # Buat list opsi jawaban (A, B, C, D, E)
        opsi_list = []
        for kode in ['a', 'b', 'c', 'd', 'e']:
            if item.get(kode): # Jika opsi tidak kosong
                opsi_list.append({
                    'kode': kode.upper(), # Value yang dikirim ke server (A/B/C..)
                    'teks': item[kode]    # Teks yang tampil di layar
                })
        
        # Acak urutan opsi (A tidak selalu paling atas)
        random.shuffle(opsi_list)

        # Masukkan ke list soal tampil
        # PENTING: sertakan 'original_index' agar name input tetap valid (pg_{idx})
        pg_tampil.append({
            'original_index': idx,
            'soal': item['soal'],
            'opsi_acak': opsi_list
        })
    
    # Acak urutan nomor soal PG
    random.shuffle(pg_tampil)

    # 2. Acak Soal Essay
    essay_tampil = []
    for idx, item in enumerate(essay_db):
        essay_tampil.append({
            'original_index': idx, # Penting untuk name input (essay_{idx})
            'soal': item['soal'],
            'bobot': item['bobot']
        })
    
    # Acak urutan nomor soal Essay
    random.shuffle(essay_tampil)

    # Render Template dengan Data yang Sudah Diacak
    return render_template('siswa/ujian.html', 
                           ujian=ujian, 
                           pg_tampil=pg_tampil, 
                           essay_tampil=essay_tampil)

# ==================== GANTI PASSWORD (FITUR BARU) ====================
@bp.route('/ganti_password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if current_user.role != 'siswa': return redirect('/')

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
            flash('Password berhasil diubah! Silakan login ulang nanti.', 'success')
            return redirect('/siswa/dashboard')

    return render_template('siswa/ganti_password.html')