import networkx as nx
import operator
import json
import random


class ExperimentConfiguration:
    def __init__(self, _config):
        # Initialize with default values, will be overridden by load_configuration
        self.TOTAL_APP_NUMBER = 10
        
        # CLOUD PARAMETERS (high capacity)
        self.CLOUD_CAPACITY = 9999999999999999  # MB RAM
        self.CLOUD_SPEED = 10000  # INSTR x MS
        self.CLOUD_BW = 125000  # BYTES / MS --> 1000 Mbits/s
        self.CLOUD_PR = 1  # MS
        
        # NETWORK PARAMETERS (sesuai tabel)
        self.PERCENTAGE_GATEWAYS = 0.25  # 25% FG gateways
        self.FUNC_PROPAGATION_TIME = "random.randint(3,5)"  # 3-5 ms
        self.FUNC_BANDWIDTH = "random.randint(6*10**6,6*10**7)"  # 6×10⁶-6×10⁷ bit/s
        self.FUNC_NETWORK_GENERATION = "nx.barabasi_albert_graph(n=100, m=2)"  # 100 fog nodes
        
        # NODE PARAMETERS (sesuai tabel)
        self.FUNC_NODE_RESOURECES = "random.randint(10,25)"  # 10-25 MB RAM
        self.FUNC_NODE_SPEED = "random.randint(100,1000)"  # 100-1000 inst/ms
        self.FUNC_NODE_TB = "random.uniform(0.2,100)"  # 0.2-100 TB storage
        
        # APPLICATION PARAMETERS (sesuai tabel)
        self.FUNC_APP_GENERATION = "nx.gn_graph(random.randint(2,10))"  # 2-10 services
        self.FUNC_SERVICE_INSTR = "random.randint(20000,60000)"  # service instructions
        self.FUNC_SERVICE_MESSAGE_SIZE = "random.randint(1500000,4500000)"  # 1.5M-4.5M bytes
        self.FUNC_SERVICE_RESOURCES = "random.randint(1,6)"  # service resources
        self.FUNC_APP_DEADLINE = "random.randint(2600,6600)"  # 2600-6600 ms
        
        # USER PARAMETERS
        self.FUNC_REQUEST_PROB = "random.random()/4"  # app popularity
        self.FUNC_USER_REQ_RAT = "random.randint(200,1000)"  # user request rate

        self.config = _config

    def user_generation(self):
        """
        Menghasilkan permintaan pengguna untuk aplikasi dan menulis konfigurasi ke file JSON.

        Metode ini melakukan operasi berikut:
        1. Membuat sekumpulan permintaan pengguna untuk setiap aplikasi berdasarkan probabilitas permintaan yang dikonfigurasi
        2. Memastikan bahwa setiap aplikasi memiliki setidaknya satu permintaan pengguna
        3. Menetapkan tingkat permintaan (lambda) ke setiap pengguna berdasarkan fungsi yang dikonfigurasi
        4. Menyimpan informasi pengguna dan perangkat gateway terkait
        5. Menulis konfigurasi pengguna ke 'usersDefinition.json' di folder data

        Permintaan pengguna yang dihasilkan mencakup:
        - ID Aplikasi
        - Tipe pesan
        - ID Sumber Daya (perangkat gateway)
        - Tingkat permintaan (lambda)

        Returns:
            None

        Efek samping:
            - Mengisi self.my_users dengan konfigurasi pengguna
            - Mengisi self.app_requests dengan set perangkat gateway untuk setiap aplikasi
            - Membuat file JSON dengan konfigurasi pengguna
        """

        # Initialize variabel untuk menyimpan data
        user_json = {}

        self.my_users = list()
        self.app_requests = list()

        # Iterasi sebanyak jumlah aplikasi yang ditentukan pada konfigurasi
        for i in range(0, self.TOTAL_APP_NUMBER):
            user_request_list = set()
            prob_of_requested = eval(self.FUNC_REQUEST_PROB)
            at_least_one_allocated = False

            # Iterasi semua gateway device
            # Dengan probabilitas acak, tentukan kalau gateway tersebut request aplikasi i
            for j in self.gateway_devices:
                if random.random() < prob_of_requested:
                    my_one_user = {}
                    my_one_user["app"] = str(i)
                    my_one_user["message"] = "M.USER.APP." + str(i)
                    my_one_user["id_resource"] = j
                    my_one_user["lambda"] = eval(self.FUNC_USER_REQ_RAT)
                    user_request_list.add(j)
                    self.my_users.append(my_one_user)
                    at_least_one_allocated = True

            # Memastikan setidaknya satu workload (user request) dialokasikan ke setiap aplikasi
            if not at_least_one_allocated:
                j = random.randint(0, len(self.gateway_devices) - 1)
                my_one_user = {}
                my_one_user["app"] = str(i)
                my_one_user["message"] = "M.USER.APP." + str(i)
                my_one_user["id_resource"] = j
                my_one_user["lambda"] = eval(self.FUNC_USER_REQ_RAT)
                user_request_list.add(j)
                self.my_users.append(my_one_user)

            self.app_requests.append(user_request_list)

        # Export data workload request aplikasi (untuk Population) ke file JSON
        user_json["sources"] = self.my_users

        file = open(self.config.data_folder + "/usersDefinition.json", "w")
        file.write(json.dumps(user_json))
        file.close()

    def app_generation(self):
        """
        Menghasilkan aplikasi, layanan, dan sumber daya terkait berdasarkan parameter konfigurasi.

        Fungsi ini:
        - Membuat aplikasi berdasarkan fungsi generator yang dikonfigurasi
        - Menetapkan sumber daya ke layanan
        - Membangun konektivitas antar layanan
        - Mengatur aliran pesan antar layanan
        - Menghitung total MIPS (Million Instructions Per Second) untuk setiap aplikasi
        - Mendefinisikan batas waktu aplikasi
        - Menyimpan definisi aplikasi yang dihasilkan ke file JSON

        Fungsi ini mengisi beberapa variabel instance:
        - number_of_services: Jumlah total layanan di semua aplikasi
        - apps: Daftar graf aplikasi
        - app_deadlines: Dictionary yang memetakan ID aplikasi ke batas waktunya
        - app_resources: Daftar kebutuhan sumber daya untuk setiap aplikasi
        - app_source_services: Daftar ID layanan sumber untuk setiap aplikasi
        - app_source_messages: Daftar pesan awal untuk setiap aplikasi
        - app_total_MIPS: Daftar kebutuhan komputasi total untuk setiap aplikasi
        - map_service_to_apps: Pemetaan layanan ke aplikasi mereka
        - map_service_id_to_service_name: Pemetaan ID layanan ke nama mereka
        - service_resources: Dictionary kebutuhan sumber daya untuk setiap layanan
        """

        # Inisialisasi variabel untuk menyimpan data
        self.number_of_services = 0
        self.apps = list()
        self.app_deadlines = {}
        self.app_resources = list()
        self.app_source_services = list()
        self.app_source_messages = list()
        self.app_total_MIPS = list()
        self.map_service_to_apps = list()
        self.map_service_id_to_service_name = list()

        app_json = list()
        self.service_resources = {}

        # Iterasi sebanyak jumlah aplikasi yang ditentukan pada konfigurasi
        for i in range(0, self.TOTAL_APP_NUMBER):
            my_app = {}
            APP = eval(self.FUNC_APP_GENERATION)

            # Beri label graf aplikasi
            my_labels = {}

            for n in range(0, len(APP.nodes)):
                my_labels[n] = str(n)

            if self.config.graphic_terminal:
                nx.draw(APP, labels=my_labels)

            # Reverse edge direction
            _edge_lists = list()

            for m in APP.edges:
                _edge_lists.append(m)
            for m in _edge_lists:
                APP.remove_edge(m[0], m[1])
                APP.add_edge(m[1], m[0])

            if self.config.graphic_terminal:
                nx.draw(APP, labels=my_labels)

            # Relabel node ID, mulai dari number_of_services dan increment untuk tiap node
            mapping = dict(
                zip(
                    APP.nodes(),
                    range(
                        self.number_of_services,
                        self.number_of_services + len(APP.nodes),
                    ),
                )
            )
            APP = nx.relabel_nodes(APP, mapping)

            # Update variabel jumlah total layanan
            self.number_of_services = self.number_of_services + len(APP.nodes)
            self.apps.append(APP)

            # Alokasi sumber daya pada node (MB RAM)
            for j in APP.nodes:
                self.service_resources[j] = eval(self.FUNC_SERVICE_RESOURCES)
            self.app_resources.append(self.service_resources)

            # Topological analysis pada directed acyclic graph (DAG)
            # mengurutkan dependency dulu sebelum layanan yang bergantung padanya
            topologic_order = list(nx.topological_sort(APP))
            source = topologic_order[0]

            self.app_source_services.append(source)

            # Terapkan properti pada aplikasi (node dan edges)
            # app_deadlines[i]=eval(FUNC_APP_DEADLINE)
            self.app_deadlines[i] = self.my_deadlines[i]
            my_app["id"] = i
            my_app["name"] = str(i)
            my_app["deadline"] = self.app_deadlines[i]

            my_app["module"] = list()

            edge_number = 0
            my_app["message"] = list()

            my_app["transmission"] = list()

            total_MIPS = 0

            # Iterasi semua nodes dan terapkan properti (id, name, RAM, type="MODULE") ke "module"
            for n in APP.nodes:
                self.map_service_to_apps.append(str(i))
                self.map_service_id_to_service_name.append(str(i) + "_" + str(n))
                my_node = {}
                my_node["id"] = n
                my_node["name"] = str(i) + "_" + str(n)
                my_node["RAM"] = self.service_resources[n]
                my_node["type"] = "MODULE"

                # Jika module merupakan source/node pertama di aplikasi, maka:
                # - Buat entry Message
                # - Tetapkan kebutuhan sumber daya (CPU & Message size)
                # - Terapkan "transmission" khusus untuk source
                if source == n:
                    my_edge = {}
                    my_edge["id"] = edge_number
                    edge_number = edge_number + 1
                    my_edge["name"] = "M.USER.APP." + str(i)
                    my_edge["s"] = "None"
                    my_edge["d"] = str(i) + "_" + str(n)
                    my_edge["instructions"] = eval(self.FUNC_SERVICE_INSTR)
                    total_MIPS = total_MIPS + my_edge["instructions"]
                    my_edge["bytes"] = eval(self.FUNC_SERVICE_MESSAGE_SIZE)
                    my_app["message"].append(my_edge)
                    self.app_source_messages.append(my_edge)
                    if self.config.verbose_log:
                        # print("ADD MESSAGE SOURCE")
                        pass
                    for o in APP.edges:
                        if o[0] == source:
                            my_transmissions = {}
                            my_transmissions["module"] = str(i) + "_" + str(source)
                            my_transmissions["message_in"] = "M.USER.APP." + str(i)
                            my_transmissions["message_out"] = (
                                str(i) + "_(" + str(o[0]) + "-" + str(o[1]) + ")"
                            )
                            my_app["transmission"].append(my_transmissions)

                my_app["module"].append(my_node)

            # Iterasi semua edges dan terapkan properti ke "message"
            for n in APP.edges:
                my_edge = {}
                my_edge["id"] = edge_number
                edge_number = edge_number + 1
                my_edge["name"] = str(i) + "_(" + str(n[0]) + "-" + str(n[1]) + ")"
                my_edge["s"] = str(i) + "_" + str(n[0])
                my_edge["d"] = str(i) + "_" + str(n[1])
                my_edge["instructions"] = eval(self.FUNC_SERVICE_INSTR)
                total_MIPS = total_MIPS + my_edge["instructions"]
                my_edge["bytes"] = eval(self.FUNC_SERVICE_MESSAGE_SIZE)
                my_app["message"].append(my_edge)
                dest_node = n[1]
                for o in APP.edges:
                    if o[0] == dest_node:
                        my_transmissions = {}
                        my_transmissions["module"] = str(i) + "_" + str(n[1])
                        my_transmissions["message_in"] = (
                            str(i) + "_(" + str(n[0]) + "-" + str(n[1]) + ")"
                        )
                        my_transmissions["message_out"] = (
                            str(i) + "_(" + str(o[0]) + "-" + str(o[1]) + ")"
                        )
                        my_app["transmission"].append(my_transmissions)

            # Konfigurasi untuk "transmission": module apa, apa pesan masuk dan pesan keluarnya
            for n in APP.nodes:
                outgoing_edges = False
                for m in APP.edges:
                    if m[0] == n:
                        outgoing_edges = True
                        break
                # Jika tidak ada outgoing edge atau node terakhir pada graf, maka atur ulang "transmission"
                if not outgoing_edges:
                    for m in APP.edges:
                        if m[1] == n:
                            my_transmissions = {}
                            my_transmissions["module"] = str(i) + "_" + str(n)
                            my_transmissions["message_in"] = (
                                str(i) + "_(" + str(m[0]) + "-" + str(m[1]) + ")"
                            )
                            my_app["transmission"].append(my_transmissions)

            self.app_total_MIPS.append(total_MIPS)

            app_json.append(my_app)

        # Export aplikasi yang dihasilkan ke file JSON
        file = open(self.config.data_folder + "/appDefinition.json", "w")
        file.write(json.dumps(app_json))
        file.close()

    def network_generation(self):
        """
        Menghasilkan topologi jaringan untuk simulasi fog computing dengan konektivitas cloud.
        
        Struktur jaringan:
        - 3 Cloud Servers (cloud_server)
        - 5% CFG Nodes (CFG) 
        - 70% Fog Nodes (fog)
        - 25% Edge Fog Nodes (FG)
        
        Total: 103 nodes (3 cloud + 100 fog network)
        """
        # Generate base network with 100 fog nodes
        base_network = eval(self.FUNC_NETWORK_GENERATION)
        
        # Create new network graph
        self.G = nx.Graph()
        
        # Calculate node distribution for 100 fog nodes
        total_fog_nodes = len(base_network.nodes())
        cfg_count = max(1, int(0.05 * total_fog_nodes))  # 5% CFG
        fg_count = int(0.25 * total_fog_nodes)           # 25% FG  
        fog_count = total_fog_nodes - cfg_count - fg_count  # 70% Fog
        cloud_count = 3  # 3 Cloud servers
        
        print(f"[NETWORK] Generating topology:")
        print(f"  - Cloud Servers: {cloud_count}")
        print(f"  - CFG Nodes: {cfg_count}")
        print(f"  - Fog Nodes: {fog_count}")
        print(f"  - FG Nodes: {fg_count}")
        print(f"  - Total: {cloud_count + cfg_count + fog_count + fg_count}")
        
        # Add all base network nodes and edges to new graph
        self.G.add_nodes_from(base_network.nodes())
        self.G.add_edges_from(base_network.edges())
        
        # Add 3 cloud servers (separate from fog network)
        cloud_nodes = []
        for i in range(cloud_count):
            cloud_id = total_fog_nodes + i
            cloud_nodes.append(cloud_id)
            self.G.add_node(cloud_id)
            
        # Assign types to fog network nodes (nodes 0 to total_fog_nodes-1)
        fog_nodes = list(range(total_fog_nodes))
        random.shuffle(fog_nodes)  # Randomize assignment
        
        # Assign node attributes for fog nodes
        for i, node in enumerate(fog_nodes):
            if i < cfg_count:
                self.G.nodes[node]['type'] = 'CFG'
                self.G.nodes[node]['level'] = 'fog'
            elif i < cfg_count + fog_count:
                self.G.nodes[node]['type'] = 'fog'
                self.G.nodes[node]['level'] = 'fog'
            else:
                self.G.nodes[node]['type'] = 'FG'
                self.G.nodes[node]['level'] = 'fog'
        
        # Assign cloud node attributes
        for cloud_id in cloud_nodes:
            self.G.nodes[cloud_id]['type'] = 'cloud_server'
            self.G.nodes[cloud_id]['level'] = 'cloud'
        
        # Debug: Print node type assignment
        print(f"[DEBUG] Node assignment completed:")
        type_counts = {}
        for node in self.G.nodes():
            node_data = self.G.nodes[node]
            node_type = node_data.get('type', 'unknown')
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        for node_type, count in type_counts.items():
            print(f"  - {node_type}: {count}")
        
        # Connect cloud servers to high-centrality fog nodes
        if len(fog_nodes) > 0:
            # Calculate centrality for fog nodes only
            fog_subgraph = self.G.subgraph(fog_nodes)
            if len(fog_subgraph.nodes()) > 0:
                centrality = nx.betweenness_centrality(fog_subgraph)
                top_fog_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
                  # Connect each cloud to top centrality fog nodes
                for i, cloud_id in enumerate(cloud_nodes):
                    if i < len(top_fog_nodes):
                        fog_node = top_fog_nodes[i][0]
                        self.G.add_edge(cloud_id, fog_node)
        
        if self.config.graphic_terminal:
            nx.draw(self.G)

        self.devices = list()

        # Siapkan penerapan atribut ke node dan edge
        self.node_resources = {}
        self.node_free_resources = {}
        self.node_speed = {}
        self.node_storage = {}
        for i in self.G.nodes:
            if i in cloud_nodes:
                # Cloud nodes have high capacity
                self.node_resources[i] = self.CLOUD_CAPACITY
                self.node_speed[i] = self.CLOUD_SPEED
                self.node_storage[i] = 999  # High storage for cloud
            else:
                # Fog nodes have limited resources
                self.node_resources[i] = eval(self.FUNC_NODE_RESOURECES)
                self.node_speed[i] = eval(self.FUNC_NODE_SPEED)
                self.node_storage[i] = eval(self.FUNC_NODE_TB)

        for e in self.G.edges:
            if e[0] in cloud_nodes or e[1] in cloud_nodes:
                # Cloud-fog connections
                self.G[e[0]][e[1]]["PR"] = self.CLOUD_PR
                self.G[e[0]][e[1]]["BW"] = self.CLOUD_BW
            else:
                # Regular fog-fog connections
                self.G[e[0]][e[1]]["PR"] = eval(self.FUNC_PROPAGATION_TIME)
                self.G[e[0]][e[1]]["BW"] = eval(self.FUNC_BANDWIDTH)

        net_json = {}

        # Menetapkan sumber daya komputasi (RAM, instruction per time, storage) ke setiap node
        for i in self.G.nodes:
            my_node = {}
            my_node["id"] = i
            my_node["RAM"] = self.node_resources[i]
            my_node["IPT"] = self.node_speed[i]
            my_node["TB"] = self.node_storage[i]
            # Add type information for devices
            if i in cloud_nodes:
                my_node["type"] = "CLOUD"
            self.devices.append(my_node)

        # Menetapkan properti jaringan (propagation time, bandwidth) ke setiap edge
        my_edges = list()
        for e in self.G.edges:
            my_link = {}
            my_link["s"] = e[0]
            my_link["d"] = e[1]
            my_link["PR"] = self.G[e[0]][e[1]]["PR"]
            my_link["BW"] = self.G[e[0]][e[1]]["BW"]
            my_edges.append(my_link)

        # Menghitung nilai betweenness centrality dari setiap node untuk mengidentifikasi node paling sentral
        # node penting yang banyak dilalui sebagai jalur
        centrality_values_no_ordered = nx.betweenness_centrality(
            self.G, weight="weight"
        )

        # Urutkan betweeness centrality dari yang tertinggi
        centrality_values = sorted(
            centrality_values_no_ordered.items(),
            key=operator.itemgetter(1),
            reverse=True,
        )
        # centrality_values = [[key_node, centrality_value], ...]

        # Menentukan cloud gateway device berdasarkan nilai centrality tertinggi
        self.gateway_devices = set()
        self.cloud_gateway_devices = set()

        # Ambil nilai betweeness centrality tertinggi
        highest_centrality = centrality_values[0][1]

        # TODO - Atur Cloud-Fog-Gateway menjadi 5% alih-alih hanya ambil betweeness centrality tertinggi
        # - Cek device mana yang punya nilai centrality tertinggi
        # - Lalu tambahkan device tersebut ke cloud_gateway_devices
        for device in centrality_values:
            if device[1] == highest_centrality:
                self.cloud_gateway_devices.add(device[0])

        # Menentukan gateway device berdasarkan persentase node dengan centrality terendah

        # mencari indeks awal untuk gateway device
        initial_idx = int((1 - self.PERCENTAGE_GATEWAYS) * len(fog_nodes))

        # karena centrality sudah diurutkan dari tertinggi ke terendah
        # maka indeks awal (misal 75) sampai jumlah node (misal 100)
        # adalah node dengan centrality terendah yang akan menjadi gateway device
        for id_dev in range(initial_idx, len(fog_nodes)):
            self.gateway_devices.add(centrality_values[id_dev][0])

        # Set cloud_id untuk kompatibilitas dengan kode lain
        self.cloud_id = cloud_nodes[0]  # Use first cloud node as main cloud

        # Membuat koneksi antara cloud gateway device dan cloud node
        for cloud_gateway in self.cloud_gateway_devices:
            my_link = {}
            my_link["s"] = cloud_gateway
            my_link["d"] = self.cloud_id
            my_link["PR"] = self.CLOUD_PR
            my_link["BW"] = self.CLOUD_BW

            my_edges.append(my_link)

        # Export definisi jaringan lengkap ke file JSON
        net_json["entity"] = self.devices
        net_json["link"] = my_edges

        file = open(self.config.data_folder + "/networkDefinition.json", "w")
        file.write(json.dumps(net_json))
        file.close()

    def load_configuration(self, my_configuration):
        # Configuration for the IEEE IoT journal experiment
        if my_configuration == "iotjournal":
            # CLOUD
            self.CLOUD_CAPACITY = 9999999999999999  # MB RAM
            self.CLOUD_SPEED = 10000  # INSTR x MS
            self.CLOUD_BW = 125000  # BYTES / MS --> 1000 Mbits/s
            self.CLOUD_PR = 1  # MS

            # NETWORK
            self.PERCENTAGE_GATEWAYS = 0.25
            self.FUNC_PROPAGATION_TIME = "random.randint(5,5)"  # MS
            self.FUNC_BANDWIDTH = "random.randint(75000,75000)"  # BYTES / MS
            self.FUNC_NETWORK_GENERATION = "nx.barabasi_albert_graph(n=100, m=2)"  # algorithm for the generation of the network topology
            self.FUNC_NODE_RESOURECES = "random.randint(10,25)"  # MB RAM   random distribution for the resources of the fog devices
            self.FUNC_NODE_SPEED = "random.randint(100,1000)"  # INTS / MS   random distribution for the speed of the fog devices

            # APP and SERVICES
            self.TOTAL_APP_NUMBER = 20
            self.FUNC_APP_GENERATION = "nx.gn_graph(random.randint(2,10))"  # algorithm for the generation of the random applications
            self.FUNC_SERVICE_INSTR = "random.randint(20000,60000)"  # INSTR --> Taking into account node speed this gives us between 200 and 600 MS
            self.FUNC_SERVICE_MESSAGE_SIZE = "random.randint(1500000,4500000)"  # BYTES and taking into account net bandwidth gives us between 20 and 60 MS
            self.FUNC_SERVICE_RESOURCES = "random.randint(1,6)"  # MB of RAM consumed by the service, taking into account node_resources and appgeneration, we have approximately 1 app per node or about 10 services
            self.FUNC_APP_DEADLINE = "random.randint(2600,6600)"  # MS

            # USERS and IoT DEVICES
            self.FUNC_REQUEST_PROB = "random.random()/4"  # App popularity. Threshold that determines the probability that a device has requests associated with an app. The threshold is for each app
            self.FUNC_USER_REQ_RAT = "random.randint(200,1000)"  # MS

            self.my_deadlines = [
                487203.22,
                487203.22,
                487203.22,
                474.51,
                302.05,
                831.04,
                793.26,
                1582.21,
                2214.64,
                374046.40,
                420476.14,
                2464.69,
                97999.14,
                2159.73,
                915.16,
                1659.97,
                1059.97,
                322898.56,
                1817.51,
                406034.73,
            ]

        # Configuration for FSPCN paper - SESUAI TABEL PARAMETER
        if my_configuration == "fspcn":
            # CLOUD PARAMETERS
            self.CLOUD_CAPACITY = 9999999999999999  # MB RAM (unlimited)
            self.CLOUD_SPEED = 10000  # INSTR x MS (high speed)
            self.CLOUD_BW = 125000  # BYTES / MS --> 1000 Mbits/s
            self.CLOUD_PR = 1  # MS (low latency)

            # NETWORK PARAMETERS - SESUAI TABEL
            self.PERCENTAGE_GATEWAYS = 0.25  # 25% FG nodes as gateways
            self.FUNC_PROPAGATION_TIME = "random.randint(3,5)"  # 3-5 MS (sesuai tabel PD)
            self.FUNC_BANDWIDTH = "random.randint(6*10**6,6*10**7)"  # 6×10⁶-6×10⁷ BIT/S (sesuai tabel BW)
            self.FUNC_NETWORK_GENERATION = "nx.barabasi_albert_graph(n=100, m=2)"  # 100 fog nodes (sesuai tabel)
            
            # NODE PARAMETERS - SESUAI TABEL  
            self.FUNC_NODE_RESOURECES = "random.randint(10,25)"  # 10-25 MB RAM (sesuai tabel)
            self.FUNC_NODE_SPEED = "random.randint(100,1000)"  # 100-1000 INST/MS (sesuai tabel IPT)
            self.FUNC_NODE_TB = "random.uniform(0.2,100)"  # 0.2-100 TB storage (sesuai tabel TB)

            # APPLICATION PARAMETERS - SESUAI TABEL
            self.TOTAL_APP_NUMBER = 10  # 10 applications
            self.FUNC_APP_GENERATION = "nx.gn_graph(random.randint(2,10))"  # 2-10 services per app (sesuai tabel)
            self.FUNC_SERVICE_INSTR = "random.randint(20000,60000)"  # service processing requirements
            self.FUNC_SERVICE_MESSAGE_SIZE = "random.randint(1500000,4500000)"  # 1.5M-4.5M bytes packet size (sesuai tabel)
            self.FUNC_SERVICE_RESOURCES = "random.randint(1,6)"  # service resource consumption
            self.FUNC_APP_DEADLINE = "random.randint(2600,6600)"  # 2600-6600 MS deadline (sesuai tabel)

            # USER PARAMETERS
            self.FUNC_REQUEST_PROB = "random.random()/4"  # app popularity probability
            self.FUNC_USER_REQ_RAT = "random.randint(200,1000)"  # user request rate MS

            # Predefined deadlines for consistent experiments
            self.my_deadlines = [
                487203.22, 487203.22, 487203.22, 474.51, 302.05,
                831.04, 793.26, 1582.21, 2214.64, 374046.40,
                420476.14, 2464.69, 97999.14, 2159.73, 915.16,
                1659.97, 1059.97, 322898.56, 1817.51, 406034.73,
            ]
