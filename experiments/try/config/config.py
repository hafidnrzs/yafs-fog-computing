# ==============================================================================
# KONFIGURASI EKSPERIMEN FSPCN
# ==============================================================================

# -- Parameter untuk Debug dan Reproducibility --
RANDOM_SEED = 42 # Seed untuk memastikan hasil acak bisa direproduksi

# -- Parameter Lingkungan Jaringan --
NUM_FOG_NODES = 100
GATEWAY_NODES_PERCENTAGE = 0.25 # 25% node dengan centrality terendah
CLOUD_GATEWAY_NODES_PERCENTAGE = 0.05 # 5% node dengan centrality tertinggi
CLOUD_NODE_ID = NUM_FOG_NODES # ID untuk node cloud (misal: 100)

# Atribut Node (rentang nilai acak)
NODE_RAM_RANGE = (10, 25)      # MB
NODE_IPT_RANGE = (100, 1000)   # Instructions Per Time Unit (ms)
NODE_STORAGE_RANGE = (0.2, 100) # Terabyte

# Atribut Link (rentang nilai acak)
LINK_BANDWIDTH_RANGE = (6_000_000, 60_000_000) # bit/s
LINK_PROPAGATION_RANGE = (3, 5)                # ms

# -- Parameter Aplikasi --
APP_DEADLINE_RANGE = (2600, 6600) # ms
APP_SERVICES_RANGE = (2, 10)      # Jumlah service per aplikasi
SERVICE_RESOURCES_RANGE = (1, 6)  # Unit
PACKET_SIZE_RANGE = (1_500_000, 4_500_000) # bytes

# -- Parameter Algoritma Genetika (Fase 1) --
# Bobot Fungsi Fitness (Eq. 23)
W1, W2, W3 = 0.4, 0.25, 0.35
LAMBDA1, LAMBDA2, LAMBDA3 = 0.35, 0.50, 0.15

# Bobot Atribut di Fitness Function (Eq. 17 & 18)
WEIGHTS_RESOURCES = {'RAM': 0.25, 'TB': 0.20, 'IPT': 0.25, 'BW': 0.15, 'PD': 0.15}
WEIGHTS_VARIANCES = {'RAM': 0.25, 'TB': 0.20, 'IPT': 0.25, 'BW': 0.15, 'PD': 0.15}

PENALTY_FACTOR = 0.0001
NOMINAL_COMMUNITIES = 10 # Jumlah awal komunitas yang diinginkan

# Parameter Operator GA
CROSSOVER_DIV_PARAMETER = 6 # 'div' pada Algoritma 1

# -- Parameter Algoritma Placement (Fase 2) --
RANK_THRESHOLD = 0.35 # Threshold untuk pemilihan komunitas tetangga

# -- Parameter Simulasi & Evaluasi --
# Paper menyebutkan 500-1000, kita bisa gunakan nilai lebih kecil untuk debug
REPETITIONS_FOR_STATISTICS = 10