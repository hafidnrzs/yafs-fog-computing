# Evaluation metric

Setelah simulasi selesai, YAFS menghasilkan dua file CSV utama yang merekam hasil mentah secara rinci:
- **`results.csv`**: mencatat semua kejadian pemrosesan pesan pada node.
- **`results_link.csv`**: mencatat semua transmisi data antar node (edge).

Pendekatan ini memisahkan tahap simulasi dan analisis sehingga Anda dapat memanfaatkan tools eksternal (seperti **Pandas**, **R**, atau lainnya) untuk analisis lebih lanjut.

![[result-timestamp.webp]]

##  File `results.csv`

File ini menyimpan informasi detail setiap event pemrosesan pesan. Setiap baris merekam sejumlah atribut penting, termasuk empat timestamp utama (dilihat di ilustrasi timestamp YAFS):

- `time_emit`: waktu pesan dikirim dari node sumber.
- `time_reception`: waktu pesan diterima dan masuk antrean pada node tujuan.
- `time_in`: waktu pesan mulai diproses pada modul layanan.
- `time_out`: waktu pesan selesai diproses.

Dari kombinasi keempat timestamp tersebut, Anda bisa menghitung metrik kinerja seperti:
- **Latency** (waktu respons total)
- **Wait time** (waktu tunggu antrean sebelum diproses)
- **Service time** (durasi pemrosesan)
- **Response time** (jumlah waktu dari pengiriman hingga proses selesai)

##  File `results_link.csv`

File ini secara eksklusif merekam transmisi data di jaringan antar node. Informasi penting yang dicatat meliputi:

- `type`: selalu bernilai `LINK` untuk mencatat transmisi.
- `src` / `dst`: ID node sumber dan tujuan transmisi.
- `latency`: waktu tempuh pesan di jaringan.
- `message`: nama pesan.
- `ctime`: waktu simulasi saat transmisi terjadi.
- `size`: ukuran pesan (bytes).
- `buffer`: jumlah pesan yang menunggu dalam buffer jaringan saat itu.

##  Tujuan dan Manfaat Evaluasi

Dengan data rinci dari kedua file tersebut, Anda dapat melakukan analisis mendalam seperti:

- **Distribusi latensi**: analisis waktu tunggu antar node.
- **Utilisasi sumber daya**: menghitung beban pemrosesan setiap modul dan node.
- **Kemacetan jaringan (congestion)**: identifikasi titik dengan buffering tinggi.
- **Statistik performa**: seperti rata-rata, maksimum, dan distribusi dari response time, service time, dan lainnya.
- **Evaluasi kebijakan**: membandingkan efektivitas berbagai placement, population, atau selection policy berdasarkan hasil performa.