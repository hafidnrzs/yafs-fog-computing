## How to Install

1. Clone repository
   ```
   git clone https://github.com/hafidnrzs/yafs-fog-computing.git
   ```
2. Navigasi ke folder
   ```
   cd yafs-fog-computing
   ```
3. Install dependency
   ```
   pip install -e .
   ```
4. Jalankan kode program
   ```
   cd fspcn-paper
   python main.py
   ```

Hasil akan tersimpan pada folder results yang terdiri dari file `graph_barabasi_albert_2.gexf` dan visualisasi `topology_visualization.png`

## Citation

This project uses [YAFS (Yet Another Fog Simulator)](https://github.com/acsicuib/YAFS).  
If you use this project, please cite YAFS as follows:

```bibtex
 @ARTICLE{8758823,
    author={I. {Lera} and C. {Guerrero} and C. {Juiz}},
    journal={IEEE Access},
    title={YAFS: A Simulator for IoT Scenarios in Fog Computing},
    year={2019},
    volume={7},
    number={},
    pages={91745-91758},
    keywords={Relays;Large scale integration;Wireless communication;OFDM;Interference cancellation;Channel estimation;Real-time systems;Complex networks;fog computing;Internet of Things;simulator},
    doi={10.1109/ACCESS.2019.2927895},
    ISSN={2169-3536},
    month={},
    }
```
