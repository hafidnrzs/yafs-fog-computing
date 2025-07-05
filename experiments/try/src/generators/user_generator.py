import random
import json
from config import config


def generate_users(network, num_apps):
    """
    Menghasilkan permintaan pengguna untuk aplikasi berdasarkan topologi jaringan.
    """
    random.seed(config.RANDOM_SEED)
    gateway_devices = [
        node_id
        for node_id, data in network.nodes(data=True)
        if data.get("type") == "FOG_GATEWAY"
    ]
    if not gateway_devices:
        return None

    my_users = []
    request_probability = 0.25
    request_rate_avg = 1.0 / 557.0

    for i in range(num_apps):
        at_least_one_allocated = False
        for gateway_id in gateway_devices:
            if random.random() < request_probability:
                user = {
                    "app": str(i),
                    "message": f"M.USER.APP.{i}",
                    "id_resource": gateway_id,
                    "lambda": request_rate_avg,
                }
                my_users.append(user)
                at_least_one_allocated = True

        if not at_least_one_allocated:
            gateway_id = random.choice(gateway_devices)
            user = {
                "app": str(i),
                "message": f"M.USER.APP.{i}",
                "id_resource": gateway_id,
                "lambda": request_rate_avg,
            }
            my_users.append(user)

    user_json = {"sources": my_users}
    return user_json
