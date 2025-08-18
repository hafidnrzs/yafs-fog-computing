# YAFS (Yet Another Fog Simulator)

![[yafs-logo.webp]]

**YAFS** adalah simulator berbasis Python yang digunakan untuk **menganalisis dan mengevaluasi skenario fog computing dalam konteks Internet of Things (IoT)**.
Simulator ini berfungsi sebagai *laboratorium virtual* yang memungkinkan peneliti menguji desain aplikasi dan strategi **service placement** sebelum benar-benar diterapkan di sistem nyata.

Berbeda dengan simulator berbasis GUI, YAFS sepenuhnya dijalankan melalui **Command Line Interface (CLI)**. Skenario simulasi didefinisikan dalam bentuk **script Python** dan **file konfigurasi JSON**. Pendekatan ini menjadikan eksperimen lebih fleksibel, detail, dan dapat disesuaikan sesuai kebutuhan.

## Keunggulan YAFS

Beberapa alasan YAFS banyak digunakan dalam penelitian fog computing:
- Dibangun dengan **Simpy** (Discrete Event Simulator), sehingga dapat mengelola proses komunikasi dan komputasi secara efisien.
- Fleksibel dalam mendukung skenario dinamis, misalnya:
	- pemindahan pengguna (*user mobility*),  
	- kegagalan node secara tiba-tiba,  
	- penambahan modul aplikasi selama simulasi berjalan.
- Terintegrasi dengan **NetworkX**, sehingga pengguna bisa menerapkan berbagai algoritma teori graf (misalnya untuk menghitung sentralitas node).
- Kode *open source* dapat diakses di [GitHub Repository](https://github.com/acsicuib/YAFS).

## Arsitektur YAFS

![[arsitektur-YAFS.webp]]
YAFS dirancang secara modular agar mudah diperluas. Komponen utama dalam arsitekturnya adalah:
- **Core**. Mengatur siklus simulasi dan mengintegrasikan seluruh komponen.  
- **Topology**. Representasi jaringan dalam bentuk graf.  
	- **Node**: merepresentasikan entitas fisik (cloud, fog node, edge device, router).  
	    - Atribut utama: `ID`, kecepatan pemrosesan (Instruction Per Time / IPT), kapasitas RAM.  
	- **Edge**: koneksi antar node.  
	    - Atribut utama: `Bandwidth (BW)`, `Propagation (PR)`.  
	Topologi dapat didefinisikan dengan **file JSON** atau langsung melalui **API Python**.
- **Application**. Aplikasi direpresentasikan sebagai **Directed Acyclic Graph (DAG)**.  
	- **Modules** = node pada graf, masing-masing menjalankan fungsi/layanan tertentu (misalnya kalkulasi, data processing, interaksi user).  
	- **Messages** = edge pada graf, merepresentasikan aliran data antar modul.  
		- Atribut: `instructions` (jumlah instruksi), `bytes` (ukuran data).  
- **Placement Policy**. Algoritma yang menentukan di node mana modul aplikasi ditempatkan (misalnya Graph Partition, ILP, atau kebijakan kustom).
- **Population Model**. Representasi workload atau pengguna yang menghasilkan request ke aplikasi.
- **Selection Policy**. Mekanisme pemilihan jalur komunikasi dan eksekusi layanan.
- **Metrics & Results**. Fasilitas untuk mengukur hasil simulasi, misalnya latensi, throughput, dan pemanfaatan resource. Hasil biasanya disimpan dalam format CSV.

---

📌 Selanjutnya: pelajari lebih detail bagaimana **topologi jaringan** didefinisikan dalam YAFS di bagian [[04-topology|Topology]].
