# Topology

![[topology-graph.webp]]
Model topologi pada YAFS direpresentasikan sebagai sebuah **graf**. Semua entitas fisik dalam jaringan, seperti *fog node*, *router*, atau *data center*, dianggap sebagai **node** (titik), sedangkan koneksi antar perangkat direpresentasikan sebagai **edge** (garis).

## Definisi Topologi

Topologi dapat didefinisikan dengan dua cara:
1. **Deklaratif**: menggunakan file konfigurasi berformat **JSON**.
2. **Programatik**: menggunakan **Application Programming Interface (API)** yang disediakan oleh YAFS.

## Atribut Node dan Edge

- **Node**
  - `id`: identitas unik node
  - `IPT (Instruction Per Time)`: kecepatan pemrosesan instruksi
  - `RAM`: kapasitas memori
- **Edge**
  - `BW (Bandwidth)`: kapasitas transfer data
  - `PR (Propagation Time)`: waktu propagasi sinyal

## Contoh Definisi Topology

```json
// networkDefinition.json
{
  "entity": [
	{"id": 0, "model": "cloud", "IPT": 5000000, "RAM": 40000, "COST": 3, "WATT": 20.0},
	{"id": 1, "model": "sensor-device", "IPT": 100000, "RAM": 4000, "COST": 3, "WATT": 40.0},
	{"id": 2, "model": "actuator-device", "IPT": 100000, "RAM": 4000, "COST": 3, "WATT": 40.0}
  ],
  "link": [
    {"s": 0, "d": 1, "BW": 1, "PR": 10},
    {"s": 0, "d": 2, "BW": 1, "PR": 1}
  ]
}
```

## Analisis Graf

YAFS menggunakan library **NetworkX** untuk menangani operasi graf seperti menghitung metrik jaringan, seperti **centrality**, **shortest path**, dan lainnya.