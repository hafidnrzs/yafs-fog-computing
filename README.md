# Service Placement using YAFS

Proyek ini menggunakan simulator YAFS (Yet Another Fog Simulator) untuk simulasi fog computing dengan algoritma service placement yang membandingkan pendekatan ILP (Integer Linear Programming) dan graph-partition (Partition) optimization.

## Requirements

- **Python 3.9** (telah diuji dan direkomendasikan)
- Dependencies akan diinstall otomatis melalui pip

## Installation

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

## Configuration

Sebelum menjalankan simulasi, Anda dapat mengkonfigurasi parameter eksperimen dengan mengedit file `experiments/rev/experimentConfiguration.py`. 

Beberapa parameter penting yang dapat disesuaikan:
- `TOTALNUMBEROFAPPS`: Jumlah aplikasi yang akan di-deploy
- `func_NETWORKGENERATION`: Algoritma untuk generate topologi jaringan
- `func_APPGENERATION`: Algoritma untuk generate aplikasi random
- Dan parameter lainnya untuk konfigurasi cloud, fog devices, dll.

## Running Simulation

### 1. Generate File Konfigurasi

Jalankan file berikut untuk membuat file-file konfigurasi yang dibutuhkan:

```bash
cd experiments/rev
python placementMain.py
```

Script ini akan menggenerate file-file berikut di folder `data/`:
- `networkDefinition.json` - Topologi jaringan yang terbentuk
- `appDefinition.json` - Definisi aplikasi yang akan di-deploy
- `usersDefinition.json` - Definisi user/workload untuk population
- `allocDefinition.json` - Hasil algoritma service placement (Graph Partition)
- `allocDefinitionILP.json` - Hasil algoritma service placement (ILP)

### 2. Jalankan Simulasi

Setelah file konfigurasi berhasil dibuat, jalankan simulasi utama:

```bash
python main_nf.py
```

Simulasi akan menjalankan dua algoritma:
1. **Graph Partition optimization** - Menggunakan algoritma community detection
2. **ILP optimization** - Menggunakan Integer Linear Programming

Hasil simulasi akan tersimpan dalam format CSV di folder `results/`:
- `results__1000000.csv` - Hasil Graph Partition algorithm
- `results_ILP_1000000.csv` - Hasil ILP algorithm
- File-file link results untuk analisis network traffic

## License and Citation

### License
Project ini menggunakan **GNU General Public License v3.0** untuk menjaga konsistensi dengan komponen-komponen yang diadaptasi dari proyek lain:

- **YAFS Simulator**: [GitHub Repository](https://github.com/acsicuib/YAFS)
- **Service Placement Algorithms**: Diadaptasi dari [FogServicePlacement-ILPvsCN](https://github.com/acsicuib/FogServicePlacement-ILPvsCN) yang menggunakan GNU General Public License v3.0

### Citation
Jika Anda menggunakan project ini dalam penelitian, mohon cite:
- YAFS (Yet Another Fog Simulator)
- "Availability-aware Service Placement Policy in Fog Computing Based on Graph Partitions" research implementation
