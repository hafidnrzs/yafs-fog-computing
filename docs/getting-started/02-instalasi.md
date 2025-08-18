# Instalasi

Untuk menjalankan proyek ini, diperlukan **Python 3.9** (versi yang sudah diuji dan direkomendasikan).  
Dependencies akan otomatis terinstall melalui `pip`.

## Langkah Instalasi

1. Clone repository

```bash
git clone https://github.com/hafidnrzs/yafs-fog-computing.git
```

2. Navigasi ke folder

```bash
cd yafs-fog-computing
```
  
3. Install dependencies

```bash
pip install -e .
```

Perintah ini akan membaca file `setup.py` dan menginstall library berikut:
    - simpy, pandas, networkx, numpy
    - tqdm, matplotlib
    - pulp (untuk optimasi ILP)
    - shapely, pyproj, smopy (untuk pemrosesan topologi geografis)
    - scipy, ipykernel

> ⚠️ **Catatan**:  
> Pastikan Anda menggunakan **virtual environment** (`venv` atau `conda`) agar dependencies tidak bentrok dengan proyek lain.

---
Setelah menyelesaikan instalasi, ada dua hal yang bisa Anda pilih:
- Mempelajari konsep [[01-arsitektur-fog-computing|Arsitektur Fog Computing]]
- Langsung praktik dengan [[01-menjalankan-simulasi-sederhana|Menjalankan Simulasi Sederhana]].