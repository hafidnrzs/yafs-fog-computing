import pandas as pd
import json
import os
from config import config

RESULTS_PATH = "results"
DATA_PATH = "data"
SIM_TRACE_FOLDER = os.path.join(RESULTS_PATH, f"sim_trace_100000ms")


def analyze_simulation_results():
    """
    Menganalisis file trace dari simulasi YAFS untuk menghitung metrik kinerja dinamis.
    """
    print("--- Memulai Analisis Hasil Simulasi Dinamis ---")
    try:
        trace_file = os.path.join(SIM_TRACE_FOLDER, "results.csv")
        df = pd.read_csv(trace_file)
        app_file = os.path.join(DATA_PATH, "appDefinition.json")
        app_definitions = json.load(open(app_file))
        app_deadlines = {app["name"]: app["deadline"] for app in app_definitions}
        network_file = os.path.join(DATA_PATH, "networkDefinition.json")
        network_def = json.load(open(network_file))
    except FileNotFoundError as e:
        print(
            f"Error: Tidak dapat menemukan file. Pastikan simulasi sudah dijalankan. File: {e.filename}"
        )
        return

    # METRIK 1: Meet Deadline
    print("\n1. Menghitung Metrik 'Meet Deadline'...")
    requests = {}
    for _, row in df.iterrows():
        req_id = row["id"]
        if req_id not in requests:
            requests[req_id] = {
                "start_time": float("inf"),
                "end_time": float("-inf"),
                "app": row["app"],
            }
        requests[req_id]["start_time"] = min(
            requests[req_id]["start_time"], row["time_emit"]
        )
        requests[req_id]["end_time"] = max(
            requests[req_id]["end_time"], row["time_out"]
        )
    met_deadline_count = sum(
        1
        for req_id, times in requests.items()
        if app_deadlines.get(str(times["app"]))
        and (times["end_time"] - times["start_time"])
        <= app_deadlines[str(times["app"])]
    )
    meet_deadline_rate = (met_deadline_count / len(requests)) * 100 if requests else 0
    print(f"  - Tingkat Pemenuhan Deadline: {meet_deadline_rate:.2f}%")

    # METRIK 2: Resource Usage
    print("\n2. Menghitung Metrik 'Resource Usage'...")
    total_simulation_time = df["time_out"].max()
    fog_nodes = [node for node in network_def["entity"] if node.get("type") != "CLOUD"]
    node_busy_time = {
        node["id"]: df[df["TOPO.dst"] == node["id"]]["service"].sum()
        for node in fog_nodes
    }
    node_utilization = (
        [(busy_time / total_simulation_time) for busy_time in node_busy_time.values()]
        if total_simulation_time > 0
        else []
    )
    avg_resource_usage = (
        (sum(node_utilization) / len(node_utilization)) * 100 if node_utilization else 0
    )
    print(f"  - Rata-rata Utilisasi Sumber Daya Fog: {avg_resource_usage:.2f}%")

    # METRIK 3: Availability
    print("\n3. Menghitung Metrik 'Availability'...")
    started_requests = df[df["type"] == "SRC_M"]["id"].nunique()
    completed_requests = df[df["type"] == "SINK_M"]["id"].nunique()
    availability_rate = (
        (completed_requests / started_requests) * 100 if started_requests > 0 else 0
    )
    print(f"  - Tingkat Ketersediaan (Permintaan Selesai): {availability_rate:.2f}%")

    # METRIK 4: Average Delay (ADRA & ADSA)
    print("\n4. Menghitung Metrik 'Average Delay'...")
    df["latency"] = df["time_reception"] - df["time_emit"]
    avg_adra = df[df["type"] == "SRC_M"]["latency"].mean()
    avg_adsa = df[df["type"] == "FWD_M"]["latency"].mean()
    print(f"  - Rata-rata Delay ADRA (Client -> App): {avg_adra:.2f} ms")
    print(f"  - Rata-rata Delay ADSA (Antar Layanan): {avg_adsa:.2f} ms")
    print(f"  - Rata-rata Total Delay: {(avg_adra + avg_adsa):.2f} ms")

    print("\n--- Analisis Selesai ---")


if __name__ == "__main__":
    analyze_simulation_results()
