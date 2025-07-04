import random
import json
from config import config

def generate_users(network, num_apps):
    """
    Menghasilkan permintaan pengguna untuk aplikasi berdasarkan topologi jaringan.
    Menyimpan hasilnya ke dalam file 'usersDefinition.json'.
    """
    random.seed(config.RANDOM_SEED)

    # Dapatkan daftar gateway devices dari graf jaringan
    gateway_devices = [node_id for node_id, data in network.nodes(data=True) if data.get('type') == 'FOG_GATEWAY']
    if not gateway_devices:
        print("Peringatan: Tidak ada Fog Gateway yang ditemukan di jaringan.")
        return None

    my_users = []
    
    # Fungsi probabilitas dan rate, seperti yang disiratkan oleh eval()
    # Ini perlu didefinisikan atau diimpor, di sini kita buat versi sederhananya
    # Sesuai paper "Availability-aware...", probabilitas request adalah 0.25
    request_probability = 0.25 
    # Rata-rata request rate adalah 1/557 ms
    request_rate_avg = 1.0 / 557.0 

    for i in range(num_apps):
        at_least_one_allocated = False
        # Iterasi semua gateway device
        for gateway_id in gateway_devices:
            if random.random() < request_probability:
                user = {
                    "app": str(i),
                    "message": f"M.USER.APP.{i}",
                    "id_resource": gateway_id,
                    "lambda": request_rate_avg 
                }
                my_users.append(user)
                at_least_one_allocated = True

        # Memastikan setiap aplikasi memiliki minimal satu pengguna
        if not at_least_one_allocated:
            gateway_id = random.choice(gateway_devices)
            user = {
                "app": str(i),
                "message": f"M.USER.APP.{i}",
                "id_resource": gateway_id,
                "lambda": request_rate_avg
            }
            my_users.append(user)

    user_json = {"sources": my_users}

    # Simpan ke file JSON
    try:
        with open("data/usersDefinition.json", "w") as f:
            json.dump(user_json, f, indent=4)
        print("File 'usersDefinition.json' berhasil dibuat.")
    except IOError as e:
        print(f"Gagal menulis file 'usersDefinition.json': {e}")
        
    return user_json
