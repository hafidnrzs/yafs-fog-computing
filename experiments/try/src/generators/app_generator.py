import random
import networkx as nx
from config import config


def generate_applications(num_apps: int):
    """
    Membuat daftar definisi aplikasi secara acak menggunakan model gn_graph.
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
            app_modules.append(
                {
                    "name": module_name,
                    "id": module_id_counter,
                    "RAM": random.randint(*config.SERVICE_RESOURCES_RANGE),
                    "type": "MODULE",
                }
            )
            module_id_counter += 1

        app_messages = []
        app_transmissions = []

        if num_services > 0:
            service_graph_raw = nx.gn_graph(n=num_services, seed=config.RANDOM_SEED)
            service_graph = service_graph_raw.reverse(copy=True)

            entry_module = app_modules[0]
            user_message_name = f"M.USER.APP.{app_name}"

            app_messages.append(
                {
                    "name": user_message_name,
                    "s": "None",
                    "d": entry_module["name"],
                    "bytes": random.randint(*config.PACKET_SIZE_RANGE),
                    "instructions": random.randint(20000, 60000),
                }
            )

            # Logika transmisi disederhanakan untuk memastikan alur kerja yang valid
            for u, v in service_graph.edges():
                source_module = app_modules[u]
                dest_module = app_modules[v]

                # Pesan pemicu untuk sebuah modul
                # Jika tidak ada predecessor, pemicunya adalah pesan dari user ke entry point
                predecessors = list(service_graph.predecessors(u))
                if not predecessors:
                    msg_in_name = user_message_name
                else:
                    # Ambil predecessor pertama sebagai pemicu (penyederhanaan)
                    pred_node_idx = predecessors[0]
                    pred_module = app_modules[pred_node_idx]
                    msg_in_name = (
                        f"{app_name}_({pred_module['name']}-{source_module['name']})"
                    )

                msg_out_name = (
                    f"{app_name}_({source_module['name']}-{dest_module['name']})"
                )

                if not any(msg["name"] == msg_out_name for msg in app_messages):
                    app_messages.append(
                        {
                            "name": msg_out_name,
                            "s": source_module["name"],
                            "d": dest_module["name"],
                            "bytes": random.randint(*config.PACKET_SIZE_RANGE),
                            "instructions": random.randint(20000, 60000),
                        }
                    )

                app_transmissions.append(
                    {
                        "module": source_module["name"],
                        "message_in": msg_in_name,
                        "message_out": msg_out_name,
                    }
                )
                app_transmissions.append(
                    {"module": dest_module["name"], "message_in": msg_out_name}
                )

        applications.append(
            {
                "name": app_name,
                "deadline": random.uniform(*config.APP_DEADLINE_RANGE),
                "module": app_modules,
                "message": app_messages,
                "transmission": app_transmissions,
            }
        )

    return applications
