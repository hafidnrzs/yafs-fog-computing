# --- Definisi Kelas Dummy (untuk kelengkapan contoh) ---
class Service:
    def __init__(self, service_id, cpu_req, ram_req):
        self.id = service_id
        self.cpu_req = cpu_req
        self.ram_req = ram_req

class Device:
    def __init__(self, dev_id, cpu_available, ram_available):
        self.id = dev_id
        self.cpu_available = cpu_available
        self.ram_available = ram_available

    def has_sufficient_resources(self, service):
        return (self.cpu_available >= service.cpu_req and 
                self.ram_available >= service.ram_req)

    def allocate_resources(self, service):
        if self.has_sufficient_resources(service):
            self.cpu_available -= service.cpu_req
            self.ram_available -= service.ram_req
            return True
        return False

# --- Fungsi Pembantu Dummy (PERLU IMPLEMENTASI NYATA) ---
# Ini adalah placeholder. Anda perlu implementasi yang sesuai dengan sistem Anda.

# Global state untuk existing placements (sederhana)
existing_placements_global = set() # Akan menyimpan tuple (appId, commId)

# Dummy data untuk komunitas dan device di dalamnya
# communities_devices = {
#     'comm0': [Device('dev0_0', 100, 1000), Device('dev0_1', 80, 800)],
#     'comm1': [Device('dev1_0', 120, 1200), Device('dev1_1', 90, 900)],
#     'comm2': [Device('dev2_0', 70, 700)]
# }

# Dummy data untuk ranked_communities (output Algorithm 2)
# ranked_communities_global = {
#     'comm0': [{'id': 'comm1', 'rank_score': 0.5}, {'id': 'comm2', 'rank_score': 0.8}],
#     'comm1': [{'id': 'comm0', 'rank_score': 0.5}, {'id': 'comm2', 'rank_score': 0.9}],
#     'comm2': [{'id': 'comm0', 'rank_score': 0.8}, {'id': 'comm1', 'rank_score': 0.9}]
# }

# Dummy resources per app (ini harusnya dari SAL)
# app_resources_needed = {
#     'app0': {'cpu': 50, 'ram': 500}, # Total resource, bukan per service
#     'app1': {'cpu': 30, 'ram': 300}
# }

def search_home_community_for_requester(all_communities_devices, req_id, app_requests_info):
    """
    Dummy: Mengembalikan home community berdasarkan req_id.
    Implementasi nyata akan memeriksa koneksi requester.
    """
    # Asumsikan app_requests_info menyimpan info home community untuk setiap req_id
    # app_requests_info = {'req0_app0': 'comm0', 'req1_app0': 'comm0', 'req0_app1': 'comm1'}
    if req_id in app_requests_info:
        return app_requests_info[req_id]
    # Fallback atau error handling jika req_id tidak dikenal
    # print(f"Warning: req_id {req_id} not found in app_requests_info. Returning a default community.")
    if all_communities_devices:
        return list(all_communities_devices.keys())[0] # Default community pertama
    return None


def update_community_resources(community_devices_dict, app_id_placed, services_placed_on_devs, comm_id_of_placement):
    """
    Dummy: Mengurangi sumber daya di komunitas.
    Implementasi nyata akan mengupdate objek Device.
    Di kode utama, kita sudah melakukan alokasi langsung di objek Device.
    Fungsi ini mungkin lebih untuk logging atau manajemen sumber daya tingkat komunitas.
    Untuk pseudocode, sepertinya ini hanya konseptual.
    """
    print(f"  Resources updated in {comm_id_of_placement} for {app_id_placed}.")
    # Logika alokasi sebenarnya terjadi saat `dev.allocate_resources(service)` dipanggil.
    # Fungsi ini bisa digunakan untuk mencatat total resource yang digunakan oleh aplikasi di komunitas.
    pass

# --- Algorithm 3: Application Placement ---
def algorithm_3_application_placement(
        ranked_communities_map,      # Output dari Algorithm 2
        sorted_application_list_map, # SAL: {appId: [Service, ...]}
        application_requests_list_map, # ARL: {appId: [reqId, ...]}
        all_communities_devices_map, # {commId: [Device, ...]}
        rank_threshold,              # Threshold untuk neighbor community
        app_requester_home_comm_map  # {reqId: homeCommId} - untuk fungsi search
    ):
    """
    Implementasi Algorithm 3 dari screenshot.
    """
    placementMatrix = {} # Output: {appId: {serviceId: deviceId}}
    
    # Asumsi SAL sudah diurutkan berdasarkan deadline, jadi kita iterasi keys-nya
    # Baris 1: # Place sorted applications by deadlines in the communities
    # Baris 2: for appId in SAL do:
    for app_id, services_for_app in sorted_application_list_map.items():
        
        if app_id not in application_requests_list_map or not application_requests_list_map[app_id]:
            print(f"Skipping {app_id}: No requests found in ARL.")
            continue

        app_placed_for_any_request = False # Flag apakah aplikasi ini sudah ditempatkan untuk salah satu requestnya

        # Baris 3: # Read request list of app
        # Baris 4: for reqId in ARL[appId] do:
        for req_id in application_requests_list_map[app_id]:
            if app_placed_for_any_request: # Jika sudah ditempatkan untuk request lain dari app yang sama
                break # Pindah ke aplikasi berikutnya

            # Baris 5: # find the home community which the requester is connected to it
            # Baris 6: commId = search (communities, reqId):
            # Kita gunakan all_communities_devices_map sebagai 'communities' dan app_requester_home_comm_map untuk 'reqId'
            home_comm_id = search_home_community_for_requester(all_communities_devices_map, req_id, app_requester_home_comm_map)

            if home_comm_id is None:
                print(f"Warning: Could not find home community for {req_id} of {app_id}. Skipping this request.")
                continue
            
            print(f"\nProcessing {app_id} for request {req_id} (Home: {home_comm_id})")

            # Baris 7: if appId in existing-placement (appId, commId) then:
            if (app_id, home_comm_id) in existing_placements_global:
                print(f"  {app_id} already exists in {home_comm_id} (for this or another request).")
                # Pseudocode hanya 'break', yang akan keluar dari loop reqId.
                # Ini berarti jika sudah ada di home, request ini terpenuhi.
                # Untuk aplikasi selanjutnya, kita perlu flag bahwa aplikasi ini sudah 'diurus'.
                app_placed_for_any_request = True # Tandai bahwa app ini sudah 'diurus'
                # Jika kita ingin setiap request menghasilkan penempatan baru (jika belum ada), logikanya beda.
                # Asumsi FSPCN: Satu instance aplikasi di-deploy di satu komunitas, bisa melayani banyak request.
                if app_id not in placementMatrix: # Jika ini pertama kali app ini 'ditemukan' sudah ada
                    # Kita perlu tahu di device mana service-servicenya. Ini tidak ada di existing_placements_global.
                    # Untuk FSPCN, jika app sudah ada di 'existing_placements_global', maka sudah ter-deploy.
                    # placementMatrix harusnya sudah diisi sebelumnya.
                    # Atau, kita asumsikan 'existing_placements_global' menyiratkan semua service sudah di placementMatrix.
                    print(f"  (Assuming services for {app_id} in {home_comm_id} are already in an implicit placementMatrix)")
                # Baris 8: break
                break # Keluar dari loop reqId, lanjut ke aplikasi berikutnya jika app_placed_for_any_request = True

            # Baris 9: else: (app belum ada di home community untuk request ini)
            else:
                # Baris 10: # check if there are sufficient resources in home communities then place app
                nserv_home = 0 # Jumlah service yang berhasil ditempatkan di home community
                temp_placements_home = {} # {service_id: device_id}
                devices_in_home_comm = all_communities_devices_map.get(home_comm_id, [])
                
                successfully_placed_in_home = True
                if not devices_in_home_comm:
                    successfully_placed_in_home = False

                if successfully_placed_in_home:
                    # Baris 11: for service in SAL [appId] do:
                    for service_obj in services_for_app:
                        placed_this_service_in_home = False
                        # Baris 12: for dev in community[commId] do:
                        for dev_obj in devices_in_home_comm:
                            # Baris 13: if there are sufficient resources in dev then:
                            if dev_obj.has_sufficient_resources(service_obj):
                                # Baris 14: placementMatrix[service] = dev
                                # Kita simpan sementara dulu, baru commit jika semua service bisa
                                temp_placements_home[service_obj.id] = dev_obj.id
                                # Baris 15: nserv =+ 1
                                nserv_home += 1
                                placed_this_service_in_home = True
                                break # Pindah ke service berikutnya
                        if not placed_this_service_in_home:
                            successfully_placed_in_home = False # Satu service gagal, seluruh app gagal di home
                            break 
                
                # Baris 16: if nserv == | SAL [appId] | then:
                if successfully_placed_in_home and nserv_home == len(services_for_app):
                    print(f"  Successfully placed all {len(services_for_app)} services of {app_id} in HOME community {home_comm_id}.")
                    # Commit penempatan
                    if app_id not in placementMatrix: placementMatrix[app_id] = {}
                    for service_id, dev_id_assigned in temp_placements_home.items():
                        placementMatrix[app_id][service_id] = dev_id_assigned
                        # Update resource di device asli
                        service_to_allocate = next(s for s in services_for_app if s.id == service_id)
                        device_to_allocate_on = next(d for d in devices_in_home_comm if d.id == dev_id_assigned)
                        device_to_allocate_on.allocate_resources(service_to_allocate)

                    # Baris 17: remaining-resources=update (community (resources[appId], commId))
                    # (resources[appId] mungkin maksudnya kebutuhan resource total app)
                    update_community_resources(all_communities_devices_map, app_id, temp_placements_home, home_comm_id)
                    # Baris 18: existing-placement.append (appId, commId)
                    existing_placements_global.add((app_id, home_comm_id))
                    app_placed_for_any_request = True # Tandai aplikasi ini sudah ditempatkan
                    # break # Keluar dari loop req_id, karena app sudah ditempatkan

                # Baris 19: else: (gagal ditempatkan di home community)
                else:
                    print(f"  Could not place {app_id} in HOME community {home_comm_id}. Trying neighbors...")
                    # Baris 20: # Find neighbor communities with sufficient resources for app placement
                    if home_comm_id in ranked_communities_map:
                        # Baris 21: for item in neighborRank[commId] do:
                        for neighbor_item in ranked_communities_map[home_comm_id]:
                            # Baris 22: commRank = item [0] -> rank_score
                            # Baris 23: rankId = Item [1]   -> neighbor_id
                            commRank_val = neighbor_item['rank_score']
                            rankId_val = neighbor_item['id'] # Ini adalah ID neighbor community

                            # Baris 24: if commRank <= rank_threshold then:
                            if commRank_val <= rank_threshold:
                                print(f"    Trying neighbor: {rankId_val} (Rank: {commRank_val:.2f})")
                                nserv_neighbor = 0
                                temp_placements_neighbor = {}
                                devices_in_neighbor_comm = all_communities_devices_map.get(rankId_val, [])
                                
                                successfully_placed_in_neighbor = True
                                if not devices_in_neighbor_comm:
                                    successfully_placed_in_neighbor = False

                                if successfully_placed_in_neighbor:
                                    # Baris 25: nserv=0 (sudah di atas)
                                    # Baris 26: for service in SAL [appId] do:
                                    for service_obj_n in services_for_app:
                                        placed_this_service_in_neighbor = False
                                        # Baris 27: for dev in community[rankId] do:
                                        for dev_obj_n in devices_in_neighbor_comm:
                                            # Baris 28: if there are sufficient resources in dev then:
                                            if dev_obj_n.has_sufficient_resources(service_obj_n):
                                                # Baris 29: placementMatrix[service] = dev
                                                temp_placements_neighbor[service_obj_n.id] = dev_obj_n.id
                                                # Baris 30: nserv=+1
                                                nserv_neighbor += 1
                                                placed_this_service_in_neighbor = True
                                                break # Pindah ke service berikutnya
                                        if not placed_this_service_in_neighbor:
                                            successfully_placed_in_neighbor = False
                                            break
                                
                                # Baris 31: if nserv == | SAL [appId] | then:
                                if successfully_placed_in_neighbor and nserv_neighbor == len(services_for_app):
                                    print(f"      Successfully placed all {len(services_for_app)} services of {app_id} in NEIGHBOR community {rankId_val}.")
                                    # Commit penempatan
                                    if app_id not in placementMatrix: placementMatrix[app_id] = {}
                                    for service_id_n, dev_id_assigned_n in temp_placements_neighbor.items():
                                        placementMatrix[app_id][service_id_n] = dev_id_assigned_n
                                        # Update resource di device asli
                                        service_to_allocate_n = next(s for s in services_for_app if s.id == service_id_n)
                                        device_to_allocate_on_n = next(d for d in devices_in_neighbor_comm if d.id == dev_id_assigned_n)
                                        device_to_allocate_on_n.allocate_resources(service_to_allocate_n)

                                    # Baris 32: remaining-resources=update (community (resources[appId], rankId))
                                    update_community_resources(all_communities_devices_map, app_id, temp_placements_neighbor, rankId_val)
                                    # Baris 33: existing-placement.append (appId, rankId)
                                    existing_placements_global.add((app_id, rankId_val))
                                    app_placed_for_any_request = True # Tandai aplikasi ini sudah ditempatkan
                                    # Baris 34: break
                                    break # Keluar dari loop neighbor_item, karena sudah berhasil ditempatkan
                                else:
                                    print(f"      Failed to place all services of {app_id} in NEIGHBOR {rankId_val}.")
                            else:
                                # Jika rank sudah melebihi threshold, tidak perlu cek tetangga lain (karena sudah diurutkan)
                                print(f"    Stopping neighbor search for {app_id}: Rank {commRank_val:.2f} > threshold {rank_threshold}.")
                                break # Keluar dari loop neighbor_item
                        # Akhir loop neighbor_item
                    else:
                        print(f"  No ranked neighbors found for home community {home_comm_id} of {app_id}.")
            # Akhir blok if/else (apakah app sudah ada di existing_placement)
            
            if app_placed_for_any_request:
                break # Keluar dari loop req_id, karena app ini sudah di-handle (ditempatkan atau ditemukan sudah ada)
        # Akhir loop req_id

        if not app_placed_for_any_request:
            print(f"Failed to place {app_id} for any of its requests.")
            # Di sini bisa ditambahkan logika untuk menempatkan di Cloud jika perlu

    # Baris 35: return placementMatrix
    return placementMatrix

# --- Contoh Penggunaan Dummy ---
if __name__ == "__main__":
    # 1. Buat Dummy Data yang lebih lengkap
    # Devices and Communities
    dev_c0_d0 = Device('dev_c0_d0', 100, 1000)
    dev_c0_d1 = Device('dev_c0_d1', 120, 1200)
    dev_c1_d0 = Device('dev_c1_d0', 80, 800)
    dev_c1_d1 = Device('dev_c1_d1', 90, 900)
    dev_c2_d0 = Device('dev_c2_d0', 150, 1500)

    communities_dev_map = {
        'comm0': [dev_c0_d0, dev_c0_d1],
        'comm1': [dev_c1_d0, dev_c1_d1],
        'comm2': [dev_c2_d0]
    }

    # Ranked Communities (Output Algorithm 2)
    ranked_comm_map = {
        'comm0': [{'id': 'comm1', 'rank_score': 0.5}, {'id': 'comm2', 'rank_score': 0.8}],
        'comm1': [{'id': 'comm0', 'rank_score': 0.5}, {'id': 'comm2', 'rank_score': 0.9}],
        'comm2': [{'id': 'comm0', 'rank_score': 0.8}, {'id': 'comm1', 'rank_score': 0.9}]
    }

    # SAL (Sorted Application List)
    # Aplikasi diurutkan berdasarkan urgensi (deadline)
    app0_s0 = Service('app0_s0', 20, 200)
    app0_s1 = Service('app0_s1', 30, 300)
    app1_s0 = Service('app1_s0', 40, 400)
    app2_s0 = Service('app2_s0', 100, 1000) # Butuh resource besar
    app2_s1 = Service('app2_s1', 60, 600)   # Butuh resource besar

    sal_map = {
        'app0': [app0_s0, app0_s1], # Deadline paling cepat
        'app1': [app1_s0],
        'app2': [app2_s0, app2_s1]  # Deadline paling lambat
    }

    # ARL (Application Requests List)
    arl_map = {
        'app0': ['req0_app0', 'req1_app0'],
        'app1': ['req0_app1'],
        'app2': ['req0_app2']
    }
    
    # Info Home Community untuk Requester
    # (Ini akan digunakan oleh fungsi `search_home_community_for_requester`)
    requester_home_map = {
        'req0_app0': 'comm0',
        'req1_app0': 'comm0', # Request lain untuk app0, home community sama
        'req0_app1': 'comm1',
        'req0_app2': 'comm0'  # Request app2 dari comm0
    }

    RANK_THRESHOLD = 0.7 # Contoh threshold

    # Bersihkan existing_placements_global sebelum run
    existing_placements_global.clear()

    print("--- Running Algorithm 3: Application Placement ---")
    final_placement_matrix = algorithm_3_application_placement(
        ranked_comm_map,
        sal_map,
        arl_map,
        communities_dev_map,
        RANK_THRESHOLD,
        requester_home_map
    )
    print("-" * 30)

    print("--- Final Placement Matrix ---")
    if not final_placement_matrix:
        print("No applications were placed.")
    for app_id, service_placements in final_placement_matrix.items():
        print(f"Application: {app_id}")
        for service_id, dev_id in service_placements.items():
            print(f"  Service: {service_id} -> Device: {dev_id}")
    print("-" * 30)

    print("--- Existing Placements (AppId, CommId) ---")
    print(existing_placements_global)
    print("-" * 30)

    print("--- Final Device Resources ---")
    for comm_id, devices in communities_dev_map.items():
        print(f"Community: {comm_id}")
        for dev in devices:
            print(f"  Device: {dev.id}, CPU Avail: {dev.cpu_available}, RAM Avail: {dev.ram_available}")