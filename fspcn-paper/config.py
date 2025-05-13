"""Configuration file containing all parameters and constants."""
import random
import numpy as np
from pathlib import Path

# Seed untuk reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# --- Parameter Konfigurasi Topologi Berdasarkan Table 3 ---
# Node
NUM_FOG_NODES = 100
MIN_FOG_RAM_MB = 10
MAX_FOG_RAM_MB = 25
MIN_FOG_IPT_INSTR_MS = 100
MAX_FOG_IPT_INSTR_MS = 1000
MIN_FOG_TB_TERABYTE = 0.2
MAX_FOG_TB_TERABYTE = 100

# Link
MIN_LINK_BW_BPS = 6 * 10**6  # 6 Mbps
MAX_LINK_BW_BPS = 6 * 10**7  # 60 Mbps
MIN_LINK_PD_MS = 3
MAX_LINK_PD_MS = 5

# Gateways
PERCENT_CFG_NODES = 0.05  # 5%
PERCENT_FG_NODES = 0.25   # 25%

# --- Parameter Komunitas dari Table 2 ---
NUM_COMMUNITIES = 10

# Parameter Lain (Tidak dari Table 3 untuk fog environment, bisa disesuaikan)
NUM_CLOUD_NODES = 3
BARABASI_M = 2  # Untuk Barabasi-Albert graph

# Atribut default untuk Cloud Nodes (sumber daya besar)
DEFAULT_CLOUD_RAM_MB = 200000  # Jauh lebih besar dari fog
DEFAULT_CLOUD_IPT_INSTR_MS = 100000
DEFAULT_CLOUD_STO_TB = 200

# Atribut untuk link CFG ke Cloud (biasanya lebih baik dari link fog-fog)
CFG_CLOUD_LINK_BW_BPS = MAX_LINK_BW_BPS * 2  # Misal 2x BW maks fog link
CFG_CLOUD_LINK_PD_MS = MIN_LINK_PD_MS  # Misal delay minimum

# --- Folder untuk menyimpan hasil ---
RESULTS_FOLDER = "results"
Path(RESULTS_FOLDER).mkdir(parents=True, exist_ok=True)
