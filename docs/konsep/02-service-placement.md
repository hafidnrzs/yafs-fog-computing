# Service Placement

Salah satu tantangan utama dalam **fog computing** adalah menentukan di **fog node** mana sebuah modul aplikasi sebaiknya dijalankan. Proses ini dikenal dengan istilah **service placement**.

## Mengapa Service Placement Penting?

Setiap fog node memiliki keterbatasan dan karakteristik yang berbeda, misalnya:
- **Kapasitas komputasi** (CPU, GPU)
- **Memori**
- **Penyimpanan**
- **Koneksi jaringan**

Jika penempatan tidak tepat, sistem dapat mengalami latensi tinggi, bottleneck, atau bahkan kegagalan layanan. Oleh karena itu, strategi service placement yang baik akan sangat memengaruhi **Quality of Service (QoS)** dari aplikasi.

## Tujuan Utama

Service placement berusaha menemukan **alokasi penempatan aplikasi yang optimal** untuk:
- Meminimalkan **latensi end-to-end**
- Mengoptimalkan **penggunaan sumber daya** pada node
- Menyeimbangkan **beban jaringan dan komputasi**
- Memenuhi **persyaratan QoS** dari aplikasi yang berjalan

## Pendekatan Optimasi

Berbagai pendekatan dapat digunakan untuk menyelesaikan masalah ini, mulai dari metode matematis hingga algoritma *heuristik*. Dalam proyek ini, dua metode yang dievaluasi adalah:
1. **Graph Partition Optimization** – membagi jaringan menjadi komunitas dengan algoritma *community detection* dan menempatkan layanan sesuai partisi tersebut.
2. **ILP (Integer Linear Programming)** – pendekatan berbasis optimisasi matematis untuk mencari solusi penempatan yang optimal.

## Evaluasi dalam Simulator

Proses evaluasi dilakukan menggunakan **YAFS (Yet Another Fog Simulator)** dengan skenario kustom. Setiap strategi placement akan diuji dalam kondisi jaringan dan beban kerja yang beragam, sehingga dapat dibandingkan kinerjanya berdasarkan metrik-metrik seperti:
- Latensi rata-rata
- Throughput
- Pemanfaatan sumber daya

---

📌 Selanjutnya: pelajari simulator yang digunakan yaitu [[03-YAFS|YAFS]].
