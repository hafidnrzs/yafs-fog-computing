# Dynamic policies

YAFS mendukung tiga jenis kebijakan dinamis untuk membuat skenario simulasi lebih realistis. Kebijakan ini dapat dijalankan secara **statis (sejak awal)** maupun **dinamis (berubah selama simulasi berjalan)**.

## 1. Placement Policy

Menentukan **alokasi modul aplikasi** ke node-node dalam topologi.
- Bisa diatur statis sebelum simulasi dimulai.
- Bisa dipanggil ulang selama simulasi berlangsung untuk **re-konfigurasi** penempatan layanan.
- Fokus utama dalam eksperimen service placement.

### Contoh Service Placement

```json
// allocDefinition.json
{
  "initialAllocation": [
    {"module_name": "S0", "app": "0", "id_resource": 153},
    {"module_name": "S1", "app": "0", "id_resource": 153}
  ]
}
```

Definisi ini menunjukkan modul aplikasi (`module_name`) beserta identitas aplikasi (`app`) dan node target (`id_resource`).

## 2. Population Policy

Mengatur sumber beban kerja (*workload generators*):
- Menentukan lokasi node tempat workload berasal.
- Mengatur intensitas permintaan (misalnya seberapa sering sensor mengirim data).
- Dapat memodelkan **pergerakan pengguna** dalam jaringan.

### Contoh Population Policy

```json
// usersDefinition.json
{
  "sources": [
    {"id_resource": 20, "app": "0", "message": "M.USER.APP.0", "lambda": 229},
    {"id_resource": 33, "app": "1", "message": "M.USER.APP.1", "lambda": 223}
  ]
}
```
`id_resource` menunjukkan node yang menghasilkan permintaan, `app` aplikasi terkait, `message` jenis pesan, dan `lambda` parameter distribusi eksponensial untuk interval waktu pengiriman.

## 3. Selection Policy

Berfungsi sebagai algoritma **routing** dan **pemilihan layanan**:
- Memutuskan **node** atau **service instance** mana yang akan memproses sebuah pesan.
- Menentukan **jalur komunikasi** pesan untuk mencapai tujuan.
- Mendukung simulasi strategi load balancing atau QoS-aware routing.


