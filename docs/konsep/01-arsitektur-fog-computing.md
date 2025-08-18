# Arsitektur Fog Computing

**Fog computing** adalah arsitektur komputasi terdistribusi yang menambahkan lapisan perantara di antara **cloud** dan **perangkat edge** (sensor, IoT device, atau end-user device). 

![[arsitektur-fog-computing.webp]]

Jika pada model cloud tradisional seluruh data harus dikirim ke pusat data untuk diproses, pendekatan ini sering menimbulkan masalah **latensi tinggi** dan **konsumsi bandwidth besar**. Fog computing hadir untuk mengatasi keterbatasan tersebut dengan menempatkan **fog node** (seperti gateway, router pintar, atau server lokal) lebih dekat ke sumber data.

## Tujuan dan Keuntungan

Dengan memindahkan sebagian proses ke fog node, arsitektur ini memberikan beberapa keuntungan:
- **Mengurangi latensi**: data diproses di dekat sumbernya sehingga respon lebih cepat.
- **Optimalisasi bandwidth**: tidak semua data dikirim ke cloud, hanya data hasil olahan atau ringkasannya.
- **Kapasitas komputasi tambahan**: beban pemrosesan didistribusikan ke lapisan fog, tidak hanya bergantung pada cloud.

## Contoh Penerapan

Fog computing menjadi solusi penting untuk aplikasi yang membutuhkan **respon real-time** dan **keandalan tinggi**, misalnya:
- **Kendaraan otonom** – pemrosesan sensor dan keputusan cepat di jalan raya.
- **Smart city** – pengelolaan lalu lintas, pencahayaan, dan infrastruktur publik berbasis IoT.
- **Pemantauan kesehatan real-time** – mendukung perangkat medis yang harus merespons cepat terhadap kondisi pasien.

---

📌 Selanjutnya: pelajari lebih lanjut mengenai [[02-service-placement|Service Placement]], yaitu bagaimana layanan ditempatkan secara optimal pada arsitektur fog ini.
