from flask import Blueprint, render_template, request, flash, redirect
from flask_login import login_required, current_user, login_user
from models import db, User, Ujian, JawabanSiswa
from werkzeug.security import check_password_hash
import json, random
from datetime import datetime

bp = Blueprint('siswa', __name__)

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'siswa': return redirect('/')
    ujian = Ujian.query.all()  # nanti bisa difilter per kelas
    return render_template('siswa/dashboard.html', ujian=ujian)

@bp.route('/ujian/<int:ujian_id>', methods=['GET', 'POST'])
@login_required
def ujian(ujian_id):
    if current_user.role != 'siswa': return redirect('/')
    ujian = Ujian.query.get_or_404(ujian_id)
    now = datetime.now()
    if now < ujian.waktu_mulai or now > ujian.waktu_selesai:
        flash('Ujian belum dimulai atau sudah selesai')
        return redirect('/siswa/dashboard')

    pg = json.loads(ujian.soal_pg)
    essay = json.loads(ujian.soal_essay)
    random.shuffle(pg)

    if request.method == 'POST':
        jawaban_pg = request.form.getlist('pg')
        skor = 0
        for i, jawab in enumerate(jawaban_pg):
            if jawab == pg[i]['kunci']:
                skor += 100 / len(pg) if pg else 0

        jwb = JawabanSiswa(
            siswa_id=current_user.id,
            ujian_id=ujian_id,
            jawaban_pg=json.dumps(jawaban_pg),
            jawaban_essay=json.dumps(request.form.to_dict()),
            nilai_pg=round(skor, 2),
            total_nilai=round(skor, 2),
            waktu_selesai=datetime.now()
        )
        db.session.add(jwb)
        db.session.commit()
        flash('Ujian selesai dikumpulkan!')
        return redirect('/siswa/dashboard')

    return render_template('siswa/ujian.html', ujian=ujian, pg=pg, essay=essay)