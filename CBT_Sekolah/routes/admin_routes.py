from datetime import datetime

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user, login_user
from sqlalchemy.orm import joinedload

from models import db, User, Kelas, Mapel
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
    total_guru  = User.query.filter_by(role='guru').count()
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
    if current_user.role != 'admin': return redirect('/')
    if request.method == 'POST':
        if 'tambah' in request.form:
            nama = request.form['nama_kelas'].strip()
            if not Kelas.query.filter_by(nama_kelas=nama).first():
                db.session.add(Kelas(nama_kelas=nama))
                db.session.commit()
                flash('Kelas berhasil ditambah!', 'success')
            else:
                flash('Kelas sudah ada!', 'warning')
        elif 'edit' in request.form:
            kelas_id = request.form['kelas_id']
            kelas = Kelas.query.get_or_404(kelas_id)
            kelas.nama_kelas = request.form['nama_edit']
            db.session.commit()
            flash('Kelas berhasil diupdate!', 'success')
        elif 'hapus' in request.form:
            kelas_id = request.form['kelas_id_hapus']
            kelas = Kelas.query.get_or_404(kelas_id)
            db.session.delete(kelas)
            db.session.commit()
            flash('Kelas berhasil dihapus!', 'success')
    kelas = Kelas.query.all()
    return render_template('admin/kelola_kelas.html', kelas=kelas)

# ==================== KELOLA SISWA ====================
@bp.route('/kelola_siswa', methods=['GET', 'POST'])
@login_required
def kelola_siswa():
    if current_user.role != 'admin': return redirect('/')
    if request.method == 'POST':
        if 'tambah' in request.form:
            nis = request.form['nis']
            nama = request.form['nama']
            kelas_id = kelas_id = int(request.form['kelas_id'])
            pwd = request.form.get('password', nis)
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
        elif 'edit' in request.form:
            user_id = request.form['user_id']
            user = User.query.get_or_404(user_id)
            user.nama = request.form['nama_edit']
            user.kelas_id = int(request.form['kelas_edit'])
            if request.form['password_edit']:
                user.password = generate_password_hash(request.form['password_edit'])
            db.session.commit()
            flash('Data siswa berhasil diupdate!', 'success')
        elif 'hapus' in request.form:
            user_id = request.form['user_id_hapus']
            user = User.query.get_or_404(user_id)
            db.session.delete(user)
            db.session.commit()
            flash('Siswa berhasil dihapus!', 'success')
    siswa = User.query.filter_by(role='siswa').options(db.joinedload(User.kelas)).all()
    kelas = Kelas.query.all()
    return render_template('admin/kelola_siswa.html', siswa=siswa, kelas=kelas)

# ==================== KELOLA GURU ====================
@bp.route('/kelola_guru', methods=['GET', 'POST'])
@login_required
def kelola_guru():
    if current_user.role != 'admin': return redirect('/')
    if request.method == 'POST':
        if 'tambah' in request.form:
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
        elif 'edit' in request.form:
            user = User.query.get_or_404(request.form['user_id'])
            user.nama = request.form['nama_edit']
            if request.form['password_edit']:
                user.password = generate_password_hash(request.form['password_edit'])
            db.session.commit()
            flash('Data guru berhasil diupdate!', 'success')
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