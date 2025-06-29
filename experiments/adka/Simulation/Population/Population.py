import random

def generate_population(services, num_sources=3, min_rate=1, max_rate=5):
    """
    Membuat daftar entitas penghasil data (misal: sensor/user) yang akan mengirim request ke service.
    :param services: List of dict service (hasil application.to_dict_list())
    :param num_sources: Jumlah entitas pengirim data (sensor/user)
    :param min_rate: Minimal request per detik
    :param max_rate: Maksimal request per detik
    :return: List of dict population
    """
    population = []
    for i in range(num_sources):
        source_name = f"Sensor_{i+1}"
        # Pilih service tujuan secara acak
        target_service = random.choice(services)['name']
        rate = random.randint(min_rate, max_rate)  # request per detik
        population.append({
            "source": source_name,
            "target_service": target_service,
            "rate": rate
        })
    return population