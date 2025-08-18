# Application
![[YAFS-application.webp]]
Dalam YAFS, sebuah aplikasi tidak dianggap sebagai satu program tunggal, melainkan sebagai sekumpulan **modul** yang saling terhubung. Struktur aplikasi direpresentasikan sebagai **Directed Acyclic Graph (DAG)**.

## Struktur Aplikasi

- **Modules (Node dalam DAG)**
	- Mewakili komponen perangkat lunak atau layanan tertentu.
	- Contoh: pemroses data sensor, modul kalkulasi, antarmuka pengguna.
- **Messages (Edge dalam DAG)**
	- Mewakili komunikasi antar modul berupa aliran data atau dependensi.
	- Atribut:
		- `id`, `name`, `s` (source), `d` (destination)
		- `instruction`: jumlah instruksi yang dibutuhkan untuk pemrosesan
		- `bytes`: ukuran data yang ditransmisikan
## Workload

Workload (`WL`) merepresentasikan sumber permintaan dari pengguna atau sensor terhadap aplikasi. Permintaan ini memicu interaksi antar modul.

## Ilustrasi

Sebagai contoh:
- `S_0, S_1, S_2, ...` → Modul aplikasi.
- `M_01, M_12, M_13, ...` → Pesan antar modul.
- `WL_i` → Workload generator yang mengirimkan permintaan.

## Contoh Definisi Application

```json
// applicationDefinition.json
{
  "id": 1,
  "name": "MapReduce_1",
  "module": [
    {"type": "CLOUD", "id": 0, "HD": 0, "name": "CLOUD_0"},
    {"type": "REPLICA", "id": 1, "HD": 2, "name": "0_0"},
    {"type": "REPLICA", "id": 2, "HD": 2, "name": "0_1"},
    {"type": "REPLICA", "id": 3, "HD": 2, "name": "0_2"}
  ],
  "message": [
    {"id": 0, "name": "M.USER.APP1", "s": "None", "d": "S0", "instructions": 0, "bytes": 2770205},
    {"id": 1, "name": "M0_0", "s": "S0", "d": "S0", "instructions": 20, "bytes": 2770205},
    {"id": 2, "name": "M0_1", "s": "S0", "d": "S1", "instructions": 0, "bytes": 22}
  ],
  "transmission": [
    {"module": "S0", "message_in": "M.USER.APP1"},
    {"module": "S0", "message_in": "M.USER.APP1", "message_out": "M0_0", "fractional": 0.5},
    {"module": "S0", "message_in": "M0_0"},
    {"module": "S0", "message_in": "M.USER.APP1", "message_out": "M0_1", "fractional": 1.0},
    {"module": "S1", "message_in": "M0_1"}
  ]
}
```
Struktur ini mencakup definisi modul, pesan, dan bagaimana pesan diteruskan/transmisi antar modul.