# Menjalankan simulasi sederhana

> **Tujuan**: menghasilkan berkas definisi skenario lalu menjalankan simulasi untuk mendapatkan CSV hasil.

Sebelum mulai
- Pastikan sudah melakukan instalasi semua dependency sesuai dengan dokumentasi [[02-instalasi|Instalasi]].
- Jalankan perintah dari root repo atau masuk ke folder eksperimen.

## Langkah-Langkah

1. **Masuk ke folder eksperimen**

```bash
cd experiments/rev
```

2. **Generate berkas definisi**

```bash
python placementMain.py
```

Hasil: `allocDefinition.json`, `networkDefinition.json`, `usersDefinition.json`, `appDefinition.json`.

3. **Jalankan simulasi**

```bash
python main_nf.py
```

4. **Cek hasil simulasi**
    - Akan muncul file CSV, umumnya:
        - `results__1000000.csv` (eksekusi/pemrosesan di node)
        - `results__1000000_link.csv` (transmisi pada link)