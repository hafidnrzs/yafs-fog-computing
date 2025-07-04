import random
import networkx as nx
from config import config


def generate_applications(num_apps: int):
    """
    Membuat daftar definisi aplikasi secara acak.
    Struktur layanan internal aplikasi menggunakan model Growing Network (gn_graph)
    dengan arah edge yang sudah dibalik agar sesuai alur aplikasi.
    """
    random.seed(config.RANDOM_SEED)
    applications = []
    module_id_counter = 0

    for i in range(num_apps):
        app_name = str(i)
        num_services = random.randint(*config.APP_SERVICES_RANGE)
        
        app_modules = []
        for _ in range(num_services):
            module_name = f"{app_name}_{module_id_counter}"
            app_modules.append({
                "name": module_name,
                "id": module_id_counter,
                "RAM": random.randint(*config.SERVICE_RESOURCES_RANGE),
                "type": "MODULE"
            })
            module_id_counter += 1
            
        app_messages = []
        app_transmissions = []
        
        if num_services > 0:
            # Membuat graf ketergantungan layanan
            service_graph_raw = nx.gn_graph(n=num_services, seed=config.RANDOM_SEED)
            
            # BALIK ARAH EDGE: gn_graph membuat edge dari node baru ke lama, kita butuh sebaliknya.
            service_graph = service_graph_raw.reverse(copy=True)

            # Modul pertama (node 0 di gn_graph) tetap menjadi entry point
            entry_module = app_modules[0]
            user_message_name = f"M.USER.APP.{app_name}"
            
            # Pesan awal dari pengguna, selalu ditujukan ke entry_module
            app_messages.append({
                "name": user_message_name,
                "s": "None",
                "d": entry_module['name'],
                "bytes": random.randint(*config.PACKET_SIZE_RANGE),
                "instructions": random.randint(20000, 60000)
            })

            # Aturan transmisi untuk entry module: saat menerima pesan user, picu pesan keluar pertama
            # Ini adalah asumsi, kita anggap pesan user hanya memicu satu alur awal
            if service_graph.out_degree(0) > 0:
                # Ambil salah satu edge keluar dari node 0 untuk memulai
                # Dalam gn_graph yang dibalik, node 0 akan punya out_degree > 0
                initial_edge = list(service_graph.out_edges(0))[0]
                source_module = app_modules[initial_edge[0]]
                dest_module = app_modules[initial_edge[1]]
                msg_out_name = f"{app_name}_({source_module['name']}-{dest_module['name']})"
                
                app_transmissions.append({
                    "module": source_module['name'],
                    "message_in": user_message_name,
                    "message_out": msg_out_name
                })

            # Menentukan alur pesan berdasarkan sisa edge di graf layanan
            for u, v in service_graph.edges():
                source_module = app_modules[u]
                dest_module = app_modules[v]
                
                msg_in_name = f"{app_name}_({app_modules[list(service_graph.predecessors(u))[0]]['name'] if service_graph.in_degree(u)>0 else 'USER'}-{source_module['name']})"
                msg_out_name = f"{app_name}_({source_module['name']}-{dest_module['name']})"

                if not any(msg['name'] == msg_out_name for msg in app_messages):
                    app_messages.append({
                        "name": msg_out_name, "s": source_module['name'], "d": dest_module['name'],
                        "bytes": random.randint(*config.PACKET_SIZE_RANGE),
                        "instructions": random.randint(20000, 60000)
                    })

                if u != 0: # Transmisi untuk non-entry point
                     app_transmissions.append({
                        "module": source_module['name'],
                        "message_in": msg_in_name,
                        "message_out": msg_out_name
                    })

                app_transmissions.append({
                    "module": dest_module['name'],
                    "message_in": msg_out_name
                })


        applications.append({
            "name": app_name,
            "deadline": random.uniform(*config.APP_DEADLINE_RANGE),
            "module": app_modules,
            "message": app_messages,
            "transmission": app_transmissions
        })
        
    return applications