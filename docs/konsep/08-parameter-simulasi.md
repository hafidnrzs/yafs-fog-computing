# Parameter simulasi

Parameter simulasi pada YAFS merepresentasikan konfigurasi dasar dari lingkungan **fog computing**. Parameter ini mencakup aspek jaringan, node, aplikasi, hingga perangkat IoT. 

Berikut adalah pemetaan parameter default dari tabel dengan variabel yang digunakan di dalam kode `experimentConfiguration.py`.

## 1. Link (Koneksi Jaringan)

| Parameter | Nilai contoh    | Deskripsi            | Variabel di Python                               |
| --------- | --------------- | -------------------- | ------------------------------------------------ |
| **BW**    | 75.000 bytes/ms | Bandwidth antar node | `func_BANDWITDH = "random.randint(75000,75000)"` |
| **PD**    | 3 – 5 ms        | Propagation time     | `func_PROPAGATIONTIME = "random.randint(3,5)"`   |

## 2. Node (Fog Node)

| Parameter | Nilai contoh | Deskripsi | Variabel di Python |
|-----------|--------------|-----------|--------------------|
| **Fog**  | 100 | Jumlah node fog | `func_NETWORKGENERATION = "nx.barabasi_albert_graph(n=100, m=2)"` |
| **RAM**  | 10 – 25 MB | Kapasitas memori | `func_NODERESOURECES = "random.randint(10,25)"` |
| **IPT**  | 100 – 1000 instr/ms | Kecepatan eksekusi instruksi | `func_NODESPEED = "random.randint(100,1000)"` |
| **TB**   | 0.2 – 100 TB | Storage node | `func_NODESTORAGE = "random.uniform(0.2,100)"` |

## 3. Gateway

| Parameter | Nilai contoh | Deskripsi | Variabel di Python |
|-----------|--------------|-----------|--------------------|
| **FG**   | 25% | Persentase node sebagai Fog Gateway | `PERCENTATGEOFGATEWAYS = 0.25` |
| **CFG**  | 5%  | Persentase node sebagai Cloud-Fog Gateway | `PERCENTAGEOFCLOUDGATEWAYS = 0.05` |

## 4. Application

| Parameter | Nilai contoh | Deskripsi | Variabel di Python |
|-----------|--------------|-----------|--------------------|
| **Deadline** | 2600 – 6600 ms | Batas waktu eksekusi aplikasi | `func_APPDEADLINE = "random.randint(2600,6600)"` |
| **Service**  | 2 – 10 | Jumlah modul layanan dalam aplikasi | `func_APPGENERATION = "nx.gn_graph(random.randint(2,10))"` |
| **Resource** | 1 – 6 MB | RAM yang dikonsumsi setiap service | `func_SERVICERESOURCES = "random.randint(1,6)"` |
| **Packet**   | 1.5M – 4.5M bytes | Ukuran data per pesan | `func_SERVICEMESSAGESIZE = "random.randint(1500000,4500000)"` |
| **Instruksi**| 20K – 60K instr | Beban komputasi per pesan | `func_SERVICEINSTR = "random.randint(20000,60000)"` |

## 5. IoT Device

| Parameter | Nilai contoh | Deskripsi | Variabel di Python |
|-----------|--------------|-----------|--------------------|
| **Request rate** | 1/1000 – 1/200 (ms) | Frekuensi permintaan sensor | `func_USERREQRAT = "random.randint(200,1000)"` |
| **Popularity**   | 0.25 | Probabilitas aplikasi dipanggil pengguna | `func_REQUESTPROB = "random.random()/4"` |

---

## Ringkasan

- **Link** mengatur parameter jaringan (bandwidth dan propagasi).  
- **Node** menentukan jumlah perangkat fog, kapasitas RAM, kecepatan eksekusi, dan kapasitas storage.  
- **Gateway** digunakan untuk menentukan persentase node yang menjadi **fog gateway (FG)** maupun **cloud-fog gateway (CFG)**.  
- **Application** mencakup struktur DAG aplikasi, jumlah modul, ukuran paket pesan, instruksi komputasi, serta deadline.  
- **IoT Device** mengontrol seberapa sering perangkat mengirim request ke aplikasi dan seberapa populer aplikasi digunakan.  

Semua parameter ini dapat diubah di file **`experimentConfiguration.py`** agar simulasi sesuai dengan skenario penelitian yang diinginkan.
