// Variable flag untuk menandai apakah siswa sedang submit jawaban
let isSubmitting = false;

if (window.location.pathname.includes('/siswa/ujian/')) {
    
    // 1. Deteksi saat tombol submit ditekan
    const formUjian = document.getElementById('formUjian');
    if (formUjian) {
        formUjian.addEventListener('submit', function() {
            isSubmitting = true; // Set flag menjadi true
        });
    }

    // 2. Blokir refresh / tutup tab / back button
    window.addEventListener('beforeunload', function(e) {
        // Jika sedang submit, JANGAN munculkan peringatan
        if (isSubmitting) {
            return undefined;
        }

        // Jika bukan submit (misal refresh/close tab), munculkan peringatan
        e.preventDefault();
        e.returnValue = 'Yakin keluar? Jawaban Anda mungkin tidak tersimpan!';
        return e.returnValue;
    });

    // 3. Peringatan saat pindah tab (Anti-Cheat Sederhana)
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            document.title = "⚠️ KEMBALI KE UJIAN!";
            // Opsional: alert('DILARANG PINDAH TAB!'); 
        } else {
            document.title = "Ujian Berlangsung";
        }
    });
}