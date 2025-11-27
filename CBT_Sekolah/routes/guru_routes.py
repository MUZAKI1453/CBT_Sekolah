from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from models import db, Mapel, Ujian, JawabanSiswa, User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import re
import pdfplumber
import pandas as pd
import io

bp = Blueprint('guru', __name__)


# ==================== DASHBOARD GURU ====================
@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'guru':
        return redirect('/')

    mapel = Mapel.query.filter_by(guru_id=current_user.id).all()
    # Mengambil semua ujian dari mapel yang diajar guru ini
    ujian = Ujian.query.join(Mapel).filter(Mapel.guru_id == current_user.id).order_by(Ujian.waktu_mulai.desc()).all()

    # PERBAIKAN: Kirim parameter 'datetime' agar tidak error di HTML
    return render_template('guru/dashboard.html', mapel=mapel, ujian=ujian, datetime=datetime)


# ==================== UPLOAD SOAL / BUAT UJIAN BARU ====================
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
        # Ambil data dari form
        judul = request.form['judul'].strip()
        waktu_mulai = request.form['waktu_mulai']
        waktu_selesai = request.form['waktu_selesai']
        durasi_input = int(request.form['durasi'])
        file = request.files.get('file_pdf')

        if not judul or not waktu_mulai or not waktu_selesai:
            flash('Judul, Waktu Mulai, dan Waktu Selesai wajib diisi!', 'danger')
            return redirect(request.url)

        try:
            mulai = datetime.strptime(waktu_mulai, '%Y-%m-%dT%H:%M')
            selesai = datetime.strptime(waktu_selesai, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Format waktu salah!', 'danger')
            return redirect(request.url)

        pg_list = []
        essay_list = []

        # --- JIKA ADA FILE PDF (PARSING CERDAS) ---
        if file and file.filename != '':
            if not file.filename.lower().endswith('.pdf'):
                flash('File harus berformat PDF (.pdf)', 'danger')
                return redirect(request.url)

            try:
                full_text = ""
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            full_text += extracted + "\n"

                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                
                current_soal = None
                last_state = 'soal' # Melacak posisi: 'soal', 'a', 'b', 'c', 'd', 'e'

                # Regex Lebih Fleksibel
                pola_nomor = re.compile(r'^(\d+)\.\s+(.*)')      # Tangkap angka dan isi
                pola_opsi = re.compile(r'^([A-E])\.\s+(.*)')      # Tangkap Huruf A-E
                pola_kunci = re.compile(r'\(Jawaban:\s*([A-E])\)', re.IGNORECASE) 
                pola_bobot = re.compile(r'\(Poin:\s*(\d+)\)', re.IGNORECASE)

                for line in lines:
                    match_nomor = pola_nomor.match(line)
                    match_opsi = pola_opsi.match(line)

                    # 1. JIKA MENEMUKAN NOMOR BARU (1. Bla bla)
                    if match_nomor:
                        # Simpan soal sebelumnya sebelum reset
                        if current_soal:
                            if current_soal['tipe'] == 'pg':
                                pg_list.append(current_soal['data'])
                            elif current_soal['tipe'] == 'essay':
                                essay_list.append(current_soal['data'])

                        # Buat soal baru
                        isi_soal_raw = match_nomor.group(2) # Ambil teks setelah angka
                        
                        # Cek apakah ini PG (ada kunci) atau Essay (ada poin)
                        cek_kunci = pola_kunci.search(isi_soal_raw)
                        cek_bobot = pola_bobot.search(isi_soal_raw)

                        if cek_kunci:
                            # TIPE PG
                            kunci_jawaban = cek_kunci.group(1).upper()
                            soal_bersih = pola_kunci.sub('', isi_soal_raw).strip()
                            current_soal = {
                                'tipe': 'pg',
                                'data': {
                                    'soal': soal_bersih,
                                    'a': '', 'b': '', 'c': '', 'd': '', 'e': '',
                                    'kunci': kunci_jawaban
                                }
                            }
                        elif cek_bobot:
                            # TIPE ESSAY
                            bobot_nilai = int(cek_bobot.group(1))
                            soal_bersih = pola_bobot.sub('', isi_soal_raw).strip()
                            current_soal = {
                                'tipe': 'essay',
                                'data': {'soal': soal_bersih, 'bobot': bobot_nilai}
                            }
                        else:
                            # Default ke PG jika tidak ada tag, nanti diasumsikan soal biasa
                            current_soal = {
                                'tipe': 'pg',
                                'data': {
                                    'soal': isi_soal_raw,
                                    'a': '', 'b': '', 'c': '', 'd': '', 'e': '',
                                    'kunci': 'A' # Default sementara
                                }
                            }
                        
                        last_state = 'soal' # Reset state pembacaan ke 'soal'

                    # 2. JIKA MENEMUKAN OPSI (A. Bla bla) - HANYA UNTUK PG
                    elif current_soal and current_soal['tipe'] == 'pg' and match_opsi:
                        opt_label = match_opsi.group(1).lower() # a, b, c...
                        opt_text = match_opsi.group(2)
                        
                        current_soal['data'][opt_label] = opt_text
                        last_state = opt_label # Ubah state pembacaan ke opsi ini

                    # 3. JIKA BARIS BIASA (LANJUTAN TEKS PANJANG)
                    elif current_soal:
                        # Perbaikan Utama: Tambahkan ke 'last_state' yang aktif
                        # Jika state terakhir 'soal', masuk ke soal. 
                        # Jika state terakhir 'b', masuk ke opsi B.
                        if last_state == 'soal':
                             current_soal['data']['soal'] += " " + line
                        elif last_state in ['a', 'b', 'c', 'd', 'e']:
                             current_soal['data'][last_state] += " " + line

                # Simpan soal terakhir (karena loop selesai)
                if current_soal:
                    if current_soal['tipe'] == 'pg':
                        pg_list.append(current_soal['data'])
                    elif current_soal['tipe'] == 'essay':
                        essay_list.append(current_soal['data'])

                if not pg_list and not essay_list:
                    flash('Gagal membaca PDF! Format tidak terdeteksi. Pastikan ada Nomor (1.) dan Opsi (A.)', 'warning')
                    return redirect(request.url)

            except Exception as e:
                flash(f'Error sistem membaca PDF: {str(e)}', 'danger')
                return redirect(request.url)

        # Simpan ke Database
        ujian = Ujian(
            mapel_id=mapel_id,
            judul=judul,
            waktu_mulai=mulai,
            waktu_selesai=selesai,
            durasi_menit=durasi_input,
            soal_pg=json.dumps(pg_list, ensure_ascii=False),
            soal_essay=json.dumps(essay_list, ensure_ascii=False)
        )
        db.session.add(ujian)
        db.session.commit()

        if file and file.filename != '':
            flash(f'Berhasil! {len(pg_list)} Soal PG dan {len(essay_list)} Soal Essay tersimpan.', 'success')
            return redirect('/guru/dashboard')
        else:
            flash('Kerangka ujian berhasil dibuat! Silakan tambahkan soal manual.', 'success')
            return redirect(url_for('guru.edit_ujian', ujian_id=ujian.id))

    return render_template('guru/upload_soal.html', mapel=mapel)


# ==================== EDIT UJIAN (MANUAL + UPLOAD) ====================
@bp.route('/edit_ujian/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def edit_ujian(ujian_id):
    if current_user.role != 'guru':
        return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)

    # Validasi: Pastikan guru ini pemilik mapel
    if ujian.mapel.guru_id != current_user.id:
        flash('Akses ditolak!', 'danger')
        return redirect('/guru/dashboard')

    # Load data lama untuk ditampilkan di form (GET Request)
    try:
        pg_existing = json.loads(ujian.soal_pg) if ujian.soal_pg else []
        essay_existing = json.loads(ujian.soal_essay) if ujian.soal_essay else []
    except:
        pg_existing = []
        essay_existing = []

    if request.method == 'POST':
        # 1. Update Metadata (Judul, Waktu, Durasi)
        ujian.judul = request.form['judul'].strip()
        ujian.durasi_menit = int(request.form['durasi'])

        try:
            # Format datetime-local HTML: 'YYYY-MM-DDTHH:MM'
            ujian.waktu_mulai = datetime.strptime(request.form['waktu_mulai'], '%Y-%m-%dT%H:%M')
            ujian.waktu_selesai = datetime.strptime(request.form['waktu_selesai'], '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Format waktu salah!', 'danger')
            return redirect(request.url)

        # 2. LOGIKA GANDA: Cek apakah ada file PDF baru?
        file = request.files.get('file_pdf')

        # --- A. JIKA ADA FILE PDF BARU DIUPLOAD (TIMPA SEMUA) ---
        if file and file.filename != '':
            if not file.filename.lower().endswith('.pdf'):
                flash('File harus format PDF!', 'danger')
                return redirect(request.url)

            try:
                # Proses Parsing PDF (Sama seperti upload_soal)
                full_text = ""
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            full_text += extracted + "\n"

                lines = [line.strip() for line in full_text.split('\n') if line.strip()]

                new_pg_list = []
                new_essay_list = []
                current_soal = None

                # Regex Patterns
                pola_nomor = re.compile(r'^\d+\.\s+(.*)')
                pola_opsi = re.compile(r'^([A-E])\.\s+(.*)')
                pola_kunci = re.compile(r'\(Jawaban:\s*([A-E])\)', re.IGNORECASE)
                pola_bobot = re.compile(r'\(Poin:\s*(\d+)\)', re.IGNORECASE)

                for line in lines:
                    match_nomor = pola_nomor.match(line)
                    if match_nomor:
                        # Simpan soal sebelumnya
                        if current_soal:
                            if current_soal['tipe'] == 'pg':
                                new_pg_list.append(current_soal['data'])
                            elif current_soal['tipe'] == 'essay':
                                new_essay_list.append(current_soal['data'])

                        # Mulai soal baru
                        isi_soal = match_nomor.group(1)
                        cek_kunci = pola_kunci.search(isi_soal)
                        cek_bobot = pola_bobot.search(isi_soal)

                        if cek_kunci:
                            kunci_jawaban = cek_kunci.group(1).upper()
                            soal_bersih = pola_kunci.sub('', isi_soal).strip()
                            current_soal = {
                                'tipe': 'pg',
                                'data': {
                                    'soal': soal_bersih,
                                    'a': '', 'b': '', 'c': '', 'd': '', 'e': '',
                                    'kunci': kunci_jawaban
                                }
                            }
                        elif cek_bobot:
                            bobot_nilai = int(cek_bobot.group(1))
                            soal_bersih = pola_bobot.sub('', isi_soal).strip()
                            current_soal = {
                                'tipe': 'essay',
                                'data': {'soal': soal_bersih, 'bobot': bobot_nilai}
                            }
                        else:
                            # Jika tidak ada tag, mungkin lanjutan soal sebelumnya
                            if current_soal:
                                current_soal['data']['soal'] += " " + line
                            else:
                                current_soal = None

                    elif current_soal and current_soal['tipe'] == 'pg':
                        match_opsi = pola_opsi.match(line)
                        if match_opsi:
                            current_soal['data'][match_opsi.group(1).lower()] = match_opsi.group(2)
                        else:
                            current_soal['data']['soal'] += " " + line

                    elif current_soal and current_soal['tipe'] == 'essay':
                        current_soal['data']['soal'] += " " + line

                # Simpan soal terakhir
                if current_soal:
                    if current_soal['tipe'] == 'pg':
                        new_pg_list.append(current_soal['data'])
                    elif current_soal['tipe'] == 'essay':
                        new_essay_list.append(current_soal['data'])

                if not new_pg_list and not new_essay_list:
                    flash('Gagal membaca PDF! Format tidak sesuai.', 'warning')
                    return redirect(request.url)

                # Update ke Database (Hasil Parsing PDF)
                ujian.soal_pg = json.dumps(new_pg_list, ensure_ascii=False)
                ujian.soal_essay = json.dumps(new_essay_list, ensure_ascii=False)
                flash('Soal berhasil diperbarui dari file PDF baru!', 'success')

            except Exception as e:
                flash(f'Error membaca PDF: {str(e)}', 'danger')
                return redirect(request.url)

        # --- B. JIKA TIDAK ADA FILE (EDIT MANUAL DARI FORM) ---
        else:
            # 1. Ambil Data PG dari Form (Array)
            soal_pg = request.form.getlist('pg_soal[]')
            opt_a = request.form.getlist('pg_a[]')
            opt_b = request.form.getlist('pg_b[]')
            opt_c = request.form.getlist('pg_c[]')
            opt_d = request.form.getlist('pg_d[]')
            opt_e = request.form.getlist('pg_e[]')
            kunci = request.form.getlist('pg_kunci[]')

            manual_pg_list = []
            for i in range(len(soal_pg)):
                # Validasi: Simpan hanya jika soal tidak kosong
                if soal_pg[i].strip():
                    manual_pg_list.append({
                        'soal': soal_pg[i],
                        'a': opt_a[i], 'b': opt_b[i], 'c': opt_c[i],
                        'd': opt_d[i], 'e': opt_e[i],
                        'kunci': kunci[i]
                    })

            # 2. Ambil Data Essay dari Form
            soal_essay = request.form.getlist('essay_soal[]')
            bobot_essay = request.form.getlist('essay_bobot[]')

            manual_essay_list = []
            for i in range(len(soal_essay)):
                if soal_essay[i].strip():
                    manual_essay_list.append({
                        'soal': soal_essay[i],
                        'bobot': int(bobot_essay[i]) if bobot_essay[i] else 0
                    })

            # Update ke Database (Hasil Edit Manual)
            ujian.soal_pg = json.dumps(manual_pg_list, ensure_ascii=False)
            ujian.soal_essay = json.dumps(manual_essay_list, ensure_ascii=False)
            flash('Perubahan manual berhasil disimpan!', 'success')

        # Commit ke Database
        db.session.commit()
        return redirect('/guru/dashboard')

    # Render Template (GET Request)
    return render_template('guru/edit_ujian.html',
                           ujian=ujian,
                           pg_list=pg_existing,
                           essay_list=essay_existing)


# ==================== HAPUS UJIAN ====================
@bp.route('/hapus_ujian/<int:ujian_id>', methods=['POST'])
@login_required
def hapus_ujian(ujian_id):
    if current_user.role != 'guru':
        return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)
    if ujian.mapel.guru_id != current_user.id:
        flash('Akses ditolak!', 'danger')
        return redirect('/guru/dashboard')

    db.session.delete(ujian)
    db.session.commit()
    flash('Ujian berhasil dihapus!', 'success')
    return redirect('/guru/dashboard')


# ==================== PREVIEW UJIAN (FITUR BARU) ====================
@bp.route('/preview/<int:ujian_id>')
@login_required
def preview(ujian_id):
    if current_user.role != 'guru':
        return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)

    # Pastikan guru hanya melihat ujian mapelnya sendiri
    if ujian.mapel.guru_id != current_user.id:
        flash('Akses ditolak!', 'danger')
        return redirect('/guru/dashboard')

    # Decode JSON ke Python List agar bisa di-loop di HTML
    pg = json.loads(ujian.soal_pg)
    essay = json.loads(ujian.soal_essay)

    return render_template('guru/preview_ujian.html', ujian=ujian, pg=pg, essay=essay)


# ==================== KOREKSI ESSAY ====================
@bp.route('/koreksi/<int:jawaban_id>', methods=['GET', 'POST'])
@login_required
def koreksi(jawaban_id):
    if current_user.role != 'guru': return redirect('/')

    # Ambil data jawaban siswa
    jawaban_siswa = JawabanSiswa.query.get_or_404(jawaban_id)
    ujian = jawaban_siswa.ujian

    # Validasi Hak Akses
    if ujian.mapel.guru_id != current_user.id:
        flash('Akses ditolak!', 'danger')
        return redirect('/guru/dashboard')

    # Load Soal & Jawaban
    soal_essay = json.loads(ujian.soal_essay) if ujian.soal_essay else []
    jawab_essay = json.loads(jawaban_siswa.jawaban_essay) if jawaban_siswa.jawaban_essay else {}

    if request.method == 'POST':
        total_skor_essay = 0

        # Loop setiap soal untuk ambil input nilai dari guru
        for i, soal in enumerate(soal_essay):
            input_name = f'nilai_{i}'
            try:
                # Ambil nilai yang diinput guru, pastikan tidak minus
                skor = float(request.form.get(input_name, 0))
                if skor < 0: skor = 0
                # Opsional: Batasi agar tidak melebihi bobot (skor > soal['bobot'])
            except:
                skor = 0

            total_skor_essay += skor

        # Update Database
        jawaban_siswa.nilai_essay = total_skor_essay
        jawaban_siswa.total_nilai = jawaban_siswa.nilai_pg + total_skor_essay

        db.session.commit()
        flash(f'Nilai berhasil disimpan! Total Essay: {total_skor_essay}', 'success')
        return redirect(url_for('guru.lihat_nilai', ujian_id=ujian.id))

    return render_template('guru/koreksi.html',
                           jawaban=jawaban_siswa,
                           soal_essay=soal_essay,
                           jawab_essay=jawab_essay)


# ==================== LIHAT NILAI & EXPORT EXCEL ====================
@bp.route('/lihat_nilai/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def lihat_nilai(ujian_id):
    if current_user.role != 'guru':
        return redirect('/')

    ujian = Ujian.query.get_or_404(ujian_id)
    # Validasi kepemilikan
    if ujian.mapel.guru_id != current_user.id:
        flash('Anda tidak memiliki akses ke data ini!', 'danger')
        return redirect('/guru/dashboard')

    # Ambil semua jawaban siswa untuk ujian ini
    data_nilai = JawabanSiswa.query.filter_by(ujian_id=ujian_id).all()

    # Urutkan berdasarkan Kelas, lalu Nama Siswa (aman terhadap None)
    data_nilai.sort(key=lambda x: (
        x.siswa.kelas.nama_kelas if x.siswa and x.siswa.kelas else "",
        x.siswa.nama if x.siswa else ""
    ))

    # DOWNLOAD EXCEL (POST dari form pada header, tetap bekerja)
    if request.method == 'POST' and request.form.get('download_excel'):
        if not data_nilai:
            flash('Belum ada siswa yang mengerjakan.', 'warning')
            return redirect(request.url)

        list_data = []
        for j in data_nilai:
            list_data.append({
                'NIS': j.siswa.username if j.siswa else '-',
                'Nama Siswa': j.siswa.nama if j.siswa else '-',
                'Kelas': j.siswa.kelas.nama_kelas if j.siswa and j.siswa.kelas else '-',
                'Nilai PG': j.nilai_pg,
                'Nilai Essay': j.nilai_essay,
                'Total Nilai': j.total_nilai,
                'Waktu Submit': j.waktu_submit.strftime('%Y-%m-%d %H:%M') if j.waktu_submit else '-'
            })

        df = pd.DataFrame(list_data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Nilai Ujian')
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name=f'Nilai_{ujian.judul}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    # Render halaman utama (header + tabel). Tbody akan include partial.
    return render_template('guru/lihat_nilai.html', ujian=ujian, data_nilai=data_nilai)


# ----------------------------------------------------------------
# Partial HTMX: hanya mengembalikan <tbody> tabel nilai
# Dipanggil oleh HTMX setiap X detik
# ----------------------------------------------------------------
@bp.route('/refresh_tabel_nilai/<int:ujian_id>')
@login_required
def refresh_tabel_nilai(ujian_id):
    if current_user.role != 'guru':
        return ('', 403)

    ujian = Ujian.query.get_or_404(ujian_id)
    if ujian.mapel.guru_id != current_user.id:
        return ('', 403)

    data_nilai = JawabanSiswa.query.filter_by(ujian_id=ujian_id).all()
    data_nilai.sort(key=lambda x: (
        x.siswa.kelas.nama_kelas if x.siswa and x.siswa.kelas else "",
        x.siswa.nama if x.siswa else ""
    ))

    # Render partial (hanya isi tbody)
    return render_template('guru/partials/tabel_nilai_body.html', data_nilai=data_nilai)


# ==================== RESET PESERTA (RESET LOGIN) ====================
@bp.route('/reset_peserta/<int:jawaban_id>', methods=['POST'])
@login_required
def reset_peserta(jawaban_id):
    if current_user.role != 'guru':
        return ('', 403)

    jawaban = JawabanSiswa.query.get_or_404(jawaban_id)
    ujian = jawaban.ujian
    if ujian.mapel.guru_id != current_user.id:
        flash('Akses ditolak!', 'danger')
        return ('', 403)

    db.session.delete(jawaban)
    db.session.commit()
    # HTMX akan mereset tabel dengan memanggil partial otomatis jika Anda set behavior JS.
    return ('', 204)


# ==================== GANTI PASSWORD (BARU) ====================
@bp.route('/ganti_password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if current_user.role != 'guru': return redirect('/')

    if request.method == 'POST':
        old_pass = request.form['old_pass']
        new_pass = request.form['new_pass']
        confirm_pass = request.form['confirm_pass']

        # 1. Validasi Password Lama
        if not check_password_hash(current_user.password, old_pass):
            flash('Password lama salah!', 'danger')

        # 2. Validasi Konfirmasi
        elif new_pass != confirm_pass:
            flash('Konfirmasi password baru tidak cocok!', 'warning')

        # 3. Validasi Panjang
        elif len(new_pass) < 6:
            flash('Password baru minimal 6 karakter!', 'warning')

        else:
            # 4. Simpan
            current_user.password = generate_password_hash(new_pass)
            db.session.commit()
            flash('Password berhasil diubah! Silakan login ulang.', 'success')
            return redirect('/guru/dashboard')

    return render_template('guru/ganti_password.html')