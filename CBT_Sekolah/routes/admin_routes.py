from datetime import datetime
from operator import or_

import pandas as pd  # <--- WAJIB DITAMBAHKAN UNTUK BACA EXCEL

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user, login_user
from sqlalchemy.orm import joinedload

from models import db, User, Kelas, Mapel, Ujian
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('admin', __name__)


# ==================== DASHBOARD ====================
@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return redirect('/')

    total_kelas = Kelas.query.count()
    total_siswa = User.query.filter_by(role='siswa').count()
    total_guru = User.query.filter_by(role='guru').count()
    total_mapel = Mapel.query.count()

    return render_template('admin/dashboard.html',
                           total_kelas=total_kelas,
                           total_siswa=total_siswa,
                           total_guru=total_guru,
                           total_mapel=total_mapel,
                           now=datetime.now())


# ==================== KELOLA KELAS ====================
@bp.route('/kelola_kelas', methods=['GET', 'POST'])
@login_required
def kelola_kelas():
    if current_user.role != 'admin':
        return redirect('/')

    if request.method == 'POST':

        # Tambah Kelas
        if 'tambah' in request.form:
            nama = request.form['nama_kelas'].strip()

            if not Kelas.query.filter_by(nama_kelas=nama).first():
                db.session.add(Kelas(nama_kelas=nama))
                db.session.commit()
                flash('Kelas berhasil ditambah!', 'success')
            else:
                flash('Kelas sudah ada!', 'warning')

        # Edit Kelas
        elif 'edit' in request.form:
            kelas_id = request.form['kelas_id']
            kelas = Kelas.query.get_or_404(kelas_id)
            kelas.nama_kelas = request.form['nama_edit']
            db.session.commit()
            flash('Kelas berhasil diupdate!', 'success')

        # Hapus Kelas
        elif 'hapus' in request.form:
            kelas_id = request.form['kelas_id_hapus']
            kelas = Kelas.query.get_or_404(kelas_id)
            db.session.delete(kelas)
            db.session.commit()
            flash('Kelas berhasil dihapus!', 'success')

    # Query Kelas + hitung jumlah siswa
    kelas = (
        Kelas.query
        .outerjoin(User, User.kelas_id == Kelas.id)
        .add_columns(Kelas, db.func.count(User.id).label("jumlah_siswa"))
        .group_by(Kelas.id)
        .all()
    )

    return render_template('admin/kelola_kelas.html', kelas=kelas)


# ==================== KELOLA SISWA (UPDATED & REVISED) ====================
@bp.route('/kelola_siswa', methods=['GET', 'POST'])
@login_required
def kelola_siswa():
    # 1. CEK OTORISASI
    if current_user.role != 'admin':
        return redirect('/')

    # 2. PROSES REQUEST POST (TAMBAH, EDIT, HAPUS, IMPORT)
    if request.method == 'POST':
        # --- FITUR BARU: IMPORT EXCEL ---
        if 'import_siswa' in request.form:
            file = request.files.get('file_excel')
            if file and file.filename.endswith(('.xlsx', '.xls')):
                try:
                    df = pd.read_excel(file)
                    berhasil = 0
                    gagal = 0

                    for index, row in df.iterrows():
                        # Ambil data & bersihkan format angka/kosong
                        try:
                            # Menggunakan int() untuk menghilangkan desimal, lalu str()
                            # Tambahkan penanganan NaN dari pandas
                            nis = str(int(row['NIS']))
                        except ValueError:
                            # Jika NIS tidak bisa diubah ke int (misal: NaN atau string non-angka)
                            gagal += 1
                            continue

                        nama = str(row['Nama']).strip()
                        nama_kelas = str(row['Kelas']).strip()

                        # Pastikan semua data penting tidak kosong
                        if not all([nis, nama, nama_kelas]):
                            gagal += 1
                            continue

                        # 1. Cek duplikat NIS
                        if User.query.filter_by(username=nis).first():
                            gagal += 1
                            continue

                            # 2. Cari ID Kelas
                        kelas_obj = Kelas.query.filter_by(nama_kelas=nama_kelas).first()
                        if not kelas_obj:
                            gagal += 1
                            continue

                            # 3. Tambahkan User Baru (Password Default = NIS)
                        db.session.add(User(
                            username=nis,
                            password=generate_password_hash(nis),
                            role='siswa',
                            nama=nama,
                            kelas_id=kelas_obj.id
                        ))
                        berhasil += 1

                    db.session.commit()
                    flash(
                        f'Import Selesai! Berhasil: {berhasil}, Gagal: {gagal} (NIS duplikat / Nama Kelas salah / data kosong)',
                        'info')

                except Exception as e:
                    # Log error untuk debugging jika perlu
                    # print(f"Error import: {e}")
                    flash(f'Gagal memproses file: {str(e)}. Pastikan format kolom (NIS, Nama, Kelas) sudah benar.',
                          'danger')
            else:
                flash('File Excel tidak ditemukan atau format file salah!', 'warning')

            return redirect(url_for('.kelola_siswa'))  # <--- REDIRECT setelah import

        # --- FITUR LAMA: TAMBAH MANUAL ---
        elif 'tambah' in request.form:
            nis = request.form['nis'].strip()
            nama = request.form['nama'].strip()
            kelas_id = int(request.form['kelas_id'])
            pwd = request.form.get('password', nis).strip()

            if User.query.filter_by(username=nis).first():
                flash('NIS sudah terdaftar!', 'warning')
            else:
                db.session.add(User(
                    username=nis,
                    password=generate_password_hash(pwd),
                    role='siswa',
                    nama=nama,
                    kelas_id=kelas_id
                ))
                db.session.commit()
                flash('Siswa berhasil ditambah!', 'success')

            return redirect(url_for('.kelola_siswa'))  # <--- REDIRECT setelah tambah

        # --- FITUR LAMA: EDIT ---
        elif 'edit' in request.form:
            user_id = request.form['user_id']
            user = User.query.get_or_404(user_id)
            user.nama = request.form['nama_edit'].strip()
            user.kelas_id = int(request.form['kelas_edit'])

            if request.form['password_edit']:
                user.password = generate_password_hash(request.form['password_edit'].strip())

            db.session.commit()
            flash('Data siswa berhasil diupdate!', 'success')

            return redirect(url_for('.kelola_siswa'))  # <--- REDIRECT setelah edit

        # --- FITUR LAMA: HAPUS ---
        elif 'hapus' in request.form:
            user_id = request.form['user_id_hapus']
            user = User.query.get_or_404(user_id)
            db.session.delete(user)
            db.session.commit()
            flash('Siswa berhasil dihapus!', 'success')

            return redirect(url_for('.kelola_siswa'))  # <--- REDIRECT setelah hapus

    # 3. PROSES REQUEST GET (ATAU SETELAH REDIRECT DARI POST)

    # --- CARI & FILTER ---
    q = request.args.get('q', '').strip()
    kelas_id_filter = request.args.get('kelas')  # Ganti nama variabel agar tidak ambigu

    # Query dasar untuk siswa
    siswa_query = User.query.filter_by(role='siswa').options(joinedload(User.kelas))

    # Terapkan filter pencarian
    if q:
        siswa_query = siswa_query.filter(
            or_(User.nama.ilike(f'%{q}%'), User.username.ilike(f'%{q}%'))
        )

    # Terapkan filter kelas
    if kelas_id_filter:
        try:
            kelas_id_filter = int(kelas_id_filter)
            siswa_query = siswa_query.filter(User.kelas_id == kelas_id_filter)
        except ValueError:
            # Abaikan jika kelas_id_filter bukan angka yang valid
            pass

    # Ambil data siswa yang sudah difilter
    siswa = siswa_query.order_by(User.nama).all()

    # Ambil data semua kelas untuk filter dan form
    kelas_list = Kelas.query.order_by(Kelas.nama_kelas).all()

    # Kirim data ke template
    # Gunakan 'kelas_list' untuk konsistensi
    return render_template('admin/kelola_siswa.html', siswa=siswa, kelas=kelas_list)


# ==================== KELOLA GURU (UPDATED) ====================
@bp.route('/kelola_guru', methods=['GET', 'POST'])
@login_required
def kelola_guru():
    if current_user.role != 'admin': return redirect('/')

    if request.method == 'POST':
        # --- FITUR BARU: IMPORT EXCEL ---
        if 'import_guru' in request.form:
            file = request.files.get('file_excel')
            if file:
                try:
                    df = pd.read_excel(file)
                    berhasil = 0
                    skip = 0

                    for _, row in df.iterrows():
                        nip = str(row['NIP']).split('.')[0].strip()
                        nama = str(row['Nama']).strip()

                        # Cek duplikat NIP
                        if User.query.filter_by(username=nip).first():
                            skip += 1
                            continue

                        # Tambah Guru (Password Default = NIP)
                        db.session.add(User(
                            username=nip,
                            password=generate_password_hash(nip),
                            role='guru',
                            nama=nama
                        ))
                        berhasil += 1

                    db.session.commit()
                    flash(f'Import Guru Selesai! Berhasil: {berhasil}, Skip (Duplikat): {skip}', 'info')

                except Exception as e:
                    flash(f'Gagal memproses file: {str(e)}', 'danger')

        # --- FITUR LAMA: TAMBAH MANUAL ---
        elif 'tambah' in request.form:
            nip = request.form['nip']
            nama = request.form['nama']
            pwd = request.form.get('password', nip)
            if User.query.filter_by(username=nip).first():
                flash('NIP sudah terdaftar!', 'warning')
            else:
                db.session.add(User(
                    username=nip,
                    password=generate_password_hash(pwd),
                    role='guru',
                    nama=nama
                ))
                db.session.commit()
                flash('Guru berhasil ditambah!', 'success')

        # --- FITUR LAMA: EDIT ---
        elif 'edit' in request.form:
            user = User.query.get_or_404(request.form['user_id'])
            user.nama = request.form['nama_edit']
            if request.form['password_edit']:
                user.password = generate_password_hash(request.form['password_edit'])
            db.session.commit()
            flash('Data guru berhasil diupdate!', 'success')

        # --- FITUR LAMA: HAPUS ---
        elif 'hapus' in request.form:
            user = User.query.get_or_404(request.form['user_id_hapus'])
            db.session.delete(user)
            db.session.commit()
            flash('Guru berhasil dihapus!', 'success')

    guru = User.query.filter_by(role='guru').all()
    return render_template('admin/kelola_guru.html', guru=guru)


# ==================== KELOLA MATA PELAJARAN ====================
@bp.route('/kelola_mapel', methods=['GET', 'POST'])
@login_required
def kelola_mapel():
    if current_user.role != 'admin': return redirect('/')
    guru_list = User.query.filter_by(role='guru').all()
    if request.method == 'POST':
        if 'tambah' in request.form:
            nama = request.form['nama_mapel']
            guru_id = request.form['guru_id']
            if not Mapel.query.filter_by(nama=nama).first():
                db.session.add(Mapel(nama=nama, guru_id=guru_id))
                db.session.commit()
                flash('Mapel berhasil ditambah!', 'success')
            else:
                flash('Mapel sudah ada!', 'warning')
        elif 'edit' in request.form:
            mapel = Mapel.query.get_or_404(request.form['mapel_id'])
            mapel.nama = request.form['nama_edit']
            mapel.guru_id = request.form['guru_edit']
            db.session.commit()
            flash('Mapel berhasil diupdate!', 'success')
        elif 'hapus' in request.form:
            mapel = Mapel.query.get_or_404(request.form['mapel_id_hapus'])
            db.session.delete(mapel)
            db.session.commit()
            flash('Mapel berhasil dihapus!', 'success')
    mapel = Mapel.query.all()
    return render_template('admin/kelola_mapel.html', mapel=mapel, guru_list=guru_list)


# ==================== MONITORING UJIAN ====================
@bp.route('/ujian', methods=['GET', 'POST'])
@login_required
def ujian():
    if current_user.role != 'admin': return redirect('/')
    if request.method == 'POST' and 'hapus' in request.form:
        ujian_id = request.form['ujian_id']
        ujian_obj = Ujian.query.get_or_404(ujian_id)
        db.session.delete(ujian_obj)
        db.session.commit()
        flash('Ujian berhasil dihapus permanen!', 'success')
        return redirect(url_for('admin.ujian'))
    data_ujian = Ujian.query.order_by(Ujian.waktu_mulai.desc()).all()
    return render_template('admin/ujian.html', ujian=data_ujian, datetime=datetime)
