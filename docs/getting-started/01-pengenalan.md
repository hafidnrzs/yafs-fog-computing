# Pengenalan

Proyek ini bertujuan untuk melakukan **simulasi penempatan layanan (service placement) pada Fog Computing** menggunakan simulator **YAFS (Yet Another Fog Simulator)**.

Service placement adalah proses menentukan di node mana (cloud, edge, fog devices) sebuah layanan/aplikasi ditempatkan agar memenuhi **Quality of Service (QoS)** seperti latensi rendah, efisiensi resource, atau throughput tinggi.

Dalam proyek ini, terdapat dua pendekatan algoritma yang dibandingkan:
1. **Graph Partition Optimization**  
   Menggunakan algoritma *community detection* untuk membagi topologi jaringan ke dalam beberapa komunitas, lalu menempatkan aplikasi berdasarkan hasil pembagian tersebut.
2. **ILP (Integer Linear Programming)**  
   Menggunakan pendekatan matematis optimasi ILP untuk mencari solusi optimal penempatan aplikasi.

Hasil eksperimen dari kedua pendekatan akan dievaluasi menggunakan metrik seperti latensi end-to-end, penggunaan resource, serta pola traffic jaringan.

Proyek ini mengadaptasi dan mengembangkan kode dari:
- **YAFS (Yet Another Fog Simulator)**: [GitHub](https://github.com/acsicuib/YAFS)  
- **FogServicePlacement-ILPvsCN**: [GitHub](https://github.com/acsicuib/FogServicePlacement-ILPvsCN)

Lisensi proyek ini adalah **GNU General Public License v3.0**.
