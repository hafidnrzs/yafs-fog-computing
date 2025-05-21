import heapq
import random
import numpy as np  

def run_simulation(graph, population, placement, routes, services, service_pairs):
    """
    Simulasikan pengiriman request dari population ke service tujuan melalui route.
    Hitung total delay (latency) untuk setiap request.
    """
    results = []
    # Buat mapping nama service ke spesifikasi (packet_size, dll)
    service_map = {svc['name']: svc for svc in services}

    for pop in population:
        source = pop['source']
        target_service = pop['target_service']
        rate = pop['rate']
        # Cari node tujuan (tempat service ditempatkan)
        dst_node = placement[target_service]
        # Cari route dari source ke dst_node (jika ada)
        # Asumsi: source tidak ada di graph, request masuk ke node tujuan langsung
        # Jika ingin source ada di graph, tambahkan node sensor ke graph dan route-nya
        path = [dst_node]
        total_delay = 0
        # Hitung delay di sepanjang path (jika ada edge)
        if len(path) > 1:
            for i in range(len(path)-1):
                edge = (path[i], path[i+1])
                pr = graph.edges[edge].get('PR', 0)
                total_delay += pr
        # Tambahkan delay pemrosesan di node tujuan
        proc_delay = service_map[target_service].get('IPT', 0)
        total_delay += proc_delay
        results.append({
            "source": source,
            "target_service": target_service,
            "rate": rate,
            "total_delay": total_delay
        })
    return results



def run_event_driven_simulation_advanced(
    graph, population, placement, routes, services, service_pairs,
    sim_time=10000, arrival_rate=1.0, service_rate=2.0, seed=42
):
    """
    Event-driven simulation dengan waktu, arrival process (Poisson), dan antrian di node.
    - Setiap source (sensor) menghasilkan request dengan arrival process (Poisson).
    - Setiap node tujuan (service) punya antrian FIFO.
    - Setiap event: arrival, start_service, end_service.
    - Delay dihitung dari waktu arrival sampai selesai diproses.
    """
    random.seed(seed)
    np.random.seed(seed)
    service_map = {svc['name']: svc for svc in services}
    event_queue = []
    current_time = 0
    event_id = 0
    results = []

    # Inisialisasi: generate arrival events untuk setiap population entity
    for pop in population:
        source = pop['source']
        target_service = pop['target_service']
        rate = pop.get('rate', arrival_rate)
        t = 0
        while t < sim_time:
            inter_arrival = np.random.exponential(1.0 / rate)
            t += inter_arrival
            heapq.heappush(event_queue, (t, event_id, {
                "type": "arrival",
                "source": source,
                "target_service": target_service,
                "arrival_time": t
            }))
            event_id += 1

    # Antrian di setiap node tujuan (service)
    node_queues = {placement[svc['name']]: [] for svc in services}
    node_busy_until = {node: 0 for node in node_queues}

    while event_queue:
        current_time, _, event = heapq.heappop(event_queue)
        if event["type"] == "arrival":
            # Request tiba di node tujuan (langsung, atau bisa lewat route jika mau)
            dst_node = placement[event["target_service"]]
            queue = node_queues[dst_node]
            queue.append(event)
            # Jika node idle, langsung proses
            if node_busy_until[dst_node] <= current_time:
                svc_time = np.random.exponential(1.0 / service_rate)
                node_busy_until[dst_node] = current_time + svc_time
                heapq.heappush(event_queue, (current_time, event_id, {
                    "type": "start_service",
                    "node": dst_node
                }))
                event_id += 1
        elif event["type"] == "start_service":
            node = event["node"]
            queue = node_queues[node]
            if queue:
                req = queue.pop(0)
                svc_time = np.random.exponential(1.0 / service_rate)
                finish_time = current_time + svc_time
                node_busy_until[node] = finish_time
                heapq.heappush(event_queue, (finish_time, event_id, {
                    "type": "end_service",
                    "node": node,
                    "req": req,
                    "start_time": current_time,
                    "finish_time": finish_time
                }))
                event_id += 1
        elif event["type"] == "end_service":
            node = event["node"]
            req = event["req"]
            start_time = event["start_time"]
            finish_time = event["finish_time"]
            delay = finish_time - req["arrival_time"]
            results.append({
                "source": req["source"],
                "target_service": req["target_service"],
                "arrival_time": req["arrival_time"],
                "start_time": start_time,
                "finish_time": finish_time,
                "delay": delay
            })
            # Jika masih ada di queue, proses berikutnya
            queue = node_queues[node]
            if queue:
                svc_time = np.random.exponential(1.0 / service_rate)
                next_finish = finish_time + svc_time
                node_busy_until[node] = next_finish
                heapq.heappush(event_queue, (finish_time, event_id, {
                    "type": "start_service",
                    "node": node
                }))
                event_id += 1
    return results