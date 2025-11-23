if (window.location.pathname.includes('/siswa/ujian/')) {
    // Blokir refresh / tutup tab
    window.addEventListener('beforeunload', function(e) {
        e.preventDefault();
        e.returnValue = 'Yakin keluar? Jawaban akan hilang!';
    });

    // Blokir pindah tab
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            alert('JANGAN TINGGALKAN HALAMAN UJIAN!');
        }
    });
}