import networkx as nx
import operator
import json
import random


class ExperimentConfiguration:
    def __init__(self, _config):
        self.TOTAL_APP_NUMBER = 1
        self.CLOUD_CAPACITY = 9999999999999999
        self.CLOUD_SPEED = 9999
        self.CLOUD_BW = 999
        self.CLOUD_PR = 99
        self.PERCENTAGE_GATEWAYS = 0.2
        self.FUNC_PROPAGATION_TIME = "random.randint(10,10)"
        self.FUNC_BANDWIDTH = "random.randint(100,100)"
        self.FUNC_SERVICE_INSTR = "random.randint(100,100)"
        self.FUNC_SERVICE_MESSAGE_SIZE = "random.randint(500,500)"
        self.FUNC_NETWORK_GENERATION = "nx.barbell_graph(5, 1)"
        self.FUNC_NODE_RESOURECES = "random.randint(1,1)"
        self.FUNC_NODE_SPEED = "random.randint(100,1000)"
        self.FUNC_NODE_TB = "random.uniform(10,10)"
        self.FUNC_APP_GENERATION = "nx.gn_graph(random.randint(2,3))"
        self.FUNC_REQUEST_PROB = "random.random()/4"
        self.FUNC_REQUEST_PROB = "1.0"
        self.FUNC_SERVICE_RESOURCES = "10"
        self.FUNC_APP_DEADLINE = "(random.random()*4)"
        self.FUNC_USER_REQ_RAT = "random.random()"

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

        Metode ini membuat graf jaringan, menetapkan sumber daya ke node, menghitung betweenness
        centrality untuk mengidentifikasi gateway device, dan mengekspor konfigurasi jaringan ke JSON.

        Metode ini melakukan operasi berikut:
        1. Menghasilkan graf jaringan menggunakan fungsi network generation yang dikonfigurasi
        2. Menetapkan sumber daya komputasi (RAM, processing speed, storage) ke setiap node
        3. Menetapkan properti jaringan (propagation time, bandwidth) ke setiap edge
        4. Menghitung betweenness centrality untuk mengidentifikasi node yang paling sentral
        5. Menentukan cloud gateway device berdasarkan nilai centrality tertinggi
        6. Menentukan gateway device reguler berdasarkan persentase node dengan centrality terendah
        7. Menambahkan cloud node dengan sumber daya berkapasitas tinggi
        8. Membuat koneksi antara cloud gateway device dan cloud node
        9. Mengekspor definisi jaringan lengkap ke file JSON

        Attributes Modified:
            G (networkx.Graph): Graf jaringan yang dihasilkan
            devices (list): Daftar semua network device dengan propertinya
            node_resources (dict): Alokasi RAM untuk setiap node
            node_free_resources (dict): Sumber daya yang tersedia untuk setiap node
            node_speed (dict): Kecepatan pemrosesan (IPT) untuk setiap node
            node_storage (dict): Kapasitas storage (TB) untuk setiap node
            gateway_devices (set): Set ID node yang ditentukan sebagai gateway device
            cloud_gateway_devices (set): Set ID node dengan koneksi cloud langsung
            cloud_id (int): Identifier unik untuk cloud node

        Side Effects:
            - Membuat visualisasi jaringan jika graphic_terminal diaktifkan
            - Menulis konfigurasi jaringan ke file 'networkDefinition.json'
            - Mencetak informasi device sebelum penambahan cloud node

        Note:
            Pemilihan cloud gateway saat ini hanya menggunakan node dengan centrality tertinggi.
            Ada komentar TODO yang menunjukkan implementasi masa depan harus menggunakan 5% dari node
            alih-alih hanya nilai centrality tertinggi.
        """
        self.G = eval(self.FUNC_NETWORK_GENERATION)
        if self.config.graphic_terminal:
            nx.draw(self.G)

        self.devices = list()

        # Siapkan penerapan atribut ke node dan edge
        self.node_resources = {}
        self.node_free_resources = {}
        self.node_speed = {}
        self.node_storage = {}
        for i in self.G.nodes:
            self.node_resources[i] = eval(self.FUNC_NODE_RESOURECES)
            self.node_speed[i] = eval(self.FUNC_NODE_SPEED)
            self.node_storage[i] = eval(self.FUNC_NODE_TB)

        for e in self.G.edges:
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
        initial_idx = int((1 - self.PERCENTAGE_GATEWAYS) * len(self.G.nodes))

        # karena centrality sudah diurutkan dari tertinggi ke terendah
        # maka indeks awal (misal 75) sampai jumlah node (misal 100)
        # adalah node dengan centrality terendah yang akan menjadi gateway device
        for id_dev in range(initial_idx, len(self.G.nodes)):
            self.gateway_devices.add(centrality_values[id_dev][0])

        # Menambahkan cloud node dengan sumber daya berkapasitas tinggi
        self.cloud_id = len(self.G.nodes)
        my_node = {}
        my_node["id"] = self.cloud_id
        my_node["RAM"] = self.CLOUD_CAPACITY
        my_node["IPT"] = self.CLOUD_SPEED
        my_node["type"] = "CLOUD"
        self.devices.append(my_node)

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

        # Configuration for FSPCN paper
        if my_configuration == "fspcn":
            # CLOUD
            self.CLOUD_CAPACITY = 9999999999999999  # MB RAM
            self.CLOUD_SPEED = 10000  # INSTR x MS
            self.CLOUD_BW = 125000  # BYTES / MS --> 1000 Mbits/s
            self.CLOUD_PR = 1  # MS

            # NETWORK
            self.PERCENTAGE_GATEWAYS = 0.25
            self.FUNC_PROPAGATION_TIME = "random.randint(3,5)"  # MS
            # TODO - Cek ulang satuan dari bandwidth (bit/s atau bytes/ms)
            self.FUNC_BANDWIDTH = "random.randint(6*10**6,6*10**7)"  # BIT / S
            self.FUNC_NETWORK_GENERATION = "nx.barabasi_albert_graph(n=100, m=2)"  # algorithm for the generation of the network topology
            self.FUNC_NODE_RESOURECES = "random.randint(10,25)"  # MB RAM   random distribution for the resources of the fog devices
            self.FUNC_NODE_SPEED = "random.randint(100,1000)"  # INTS / MS   random distribution for the speed of the fog devices
            self.FUNC_NODE_TB = "random.uniform(0.2,100)"  # TB  random distribution for storage of the fog devices

            # APP and SERVICES
            self.TOTAL_APP_NUMBER = 10
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
