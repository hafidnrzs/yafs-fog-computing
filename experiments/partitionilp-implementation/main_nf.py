"""

This example

@author: Isaac Lera & Carlos Guerrero

"""

import json

from yafs.core_old import Sim
from yafs.application import Application, Message
from yafs.topology_old import Topology
from yafs.placement import JSONPlacement, JSONPlacementOnCloud
from yafs.distribution import *
import numpy as np

from yafs.utils import fractional_selectivity

from selection_multipleDeploys import DeviceSpeedAwareRouting
from jsonPopulation import JSONPopulation

import time
import random


def create_applications_from_json(data):
    """
    Membuat dictionary dari objek Application berdasarkan data JSON.

    Fungsi ini mem-parsing data JSON yang berisi definisi aplikasi dan membangun
    objek Application dengan modul, pesan, dan konfigurasi service yang terkait.

    Args:
        data (list): Sebuah list dari dictionary, dimana setiap dictionary merepresentasikan
                    konfigurasi aplikasi yang berisi:
                    - name (str): Nama aplikasi
                    - module (list): List dari definisi modul dengan nama dan kebutuhan RAM
                    - message (list): List dari definisi pesan dengan nama, source, destination,
                                     instructions, dan bytes
                    - transmission (list): List dari konfigurasi transmisi yang mendefinisikan bagaimana modul memproses pesan

    Returns:
        dict: Sebuah dictionary yang memetakan nama aplikasi ke objek Application yang sesuai.
              Setiap objek Application dikonfigurasi lengkap dengan:
              - Module (termasuk default "None" source module)
              - Message (dengan source message yang diidentifikasi secara otomatis)
              - Service module dengan hubungan pemrosesan pesan

    Note:
        - Fungsi secara otomatis menambahkan default source module dengan tipe TYPE_SOURCE
        - Message dengan source "None" diperlakukan sebagai source message
        - Service module dapat memiliki konfigurasi message output yang opsional
        - Menggunakan fractional_selectivity untuk konfigurasi service module
    """
    applications = {}
    for app in data:
        a = Application(name=app["name"])
        modules = [{"None": {"Type": Application.TYPE_SOURCE}}]
        for module in app["module"]:
            modules.append(
                {
                    module["name"]: {
                        "RAM": module["RAM"],
                        "Type": Application.TYPE_MODULE,
                    }
                }
            )
        a.set_modules(modules)

        ms = {}
        for message in app["message"]:
            # print "Creando mensaje: %s" %message["name"]
            ms[message["name"]] = Message(
                message["name"],
                message["s"],
                message["d"],
                instructions=message["instructions"],
                bytes=message["bytes"],
            )
            if message["s"] == "None":
                a.add_source_messages(ms[message["name"]])

        # print "Total mensajes creados %i" %len(ms.keys())
        for idx, message in enumerate(app["transmission"]):
            if "message_out" in message.keys():
                a.add_service_module(
                    message["module"],
                    ms[message["message_in"]],
                    ms[message["message_out"]],
                    fractional_selectivity,
                    threshold=1.0,
                )
            else:
                a.add_service_module(message["module"], ms[message["message_in"]])

        applications[app["name"]] = a

    return applications


###
# Thanks to this function, the user can control about the elemination of the nodes according with the modules deployed (see also DynamicFailuresOnNodes example)
###
"""
It returns the software modules (a list of identifiers of DES process) deployed on this node
"""


def getProcessFromThatNode(sim, node_to_remove):
    """
    Mengambil semua proses DES (Discrete Event Simulation) yang dialokasikan ke node tertentu.

    Fungsi ini memeriksa apakah node yang diberikan memiliki proses DES yang dialokasikan padanya dan
    mengembalikan list semua ID proses yang terkait dengan node tersebut.

    Args:
        sim: Objek simulation yang berisi dictionary alokasi
        node_to_remove: Identifier dari node yang akan diperiksa untuk proses yang dialokasikan

    Returns:
        tuple: Sebuah tuple yang berisi:
            - list: List dari ID proses DES yang dialokasikan ke node (kosong jika tidak ada)
            - bool: True jika node memiliki proses yang dialokasikan, False jika sebaliknya
    """
    if node_to_remove in sim.alloc_DES.values():
        DES = []
        # This node can have multiples DES processes on itself
        for k, v in sim.alloc_DES.items():
            if v == node_to_remove:
                DES.append(k)
        return DES, True
    else:
        return [], False


"""
It controls the elimination of a node
"""
idxFControl = 0


def failureControl(sim, filelog, ids):
    """
    Mengontrol kegagalan node dalam simulasi dengan menghapus node dan menghentikan proses terkait.

    Fungsi ini mensimulasikan kegagalan node dengan secara sistematis menghapus node dari topology
    simulasi dan menghentikan semua proses yang berjalan pada node tersebut. Fungsi ini mencatat
    event kegagalan dan menangani pembersihan proses DES (Discrete Event Simulation) terkait.

    Args:
        sim: Objek simulation yang berisi topology dan method manajemen proses
        filelog: File handle untuk mencatat event kegagalan dengan ID node, module, dan timestamp
        ids: List dari ID node yang dapat dihapus selama simulasi kegagalan

    Global Variables:
        idxFControl: Counter index global untuk melacak node mana yang akan dihapus selanjutnya dari list ids

    Behavior:
        - Jika lebih dari satu node ada dalam topology, menghapus node berikutnya dari list ids
        - Mengambil dan menghentikan semua proses DES yang berjalan pada target node
        - Mencatat event kegagalan dengan ID node, module yang deployed, dan waktu simulasi saat ini
        - Menangani IndexError dengan baik ketika semua node dalam list ids telah diproses
        - Menghentikan simulasi jika hanya satu node yang tersisa dalam topology

    Side Effects:
        - Memodifikasi topology simulasi dengan menghapus node
        - Menghentikan proses yang berjalan terkait dengan node yang dihapus
        - Menulis data event kegagalan ke file log
        - Dapat menghentikan seluruh simulasi ketika node yang tersisa tidak mencukupi
    """
    global idxFControl
    nodes = list(sim.topology.G.nodes())
    if len(nodes) > 1:
        try:
            node_to_remove = ids[idxFControl]
            idxFControl += 1

            keys_DES, someModuleDeployed = getProcessFromThatNode(sim, node_to_remove)

            # print "\n\nRemoving node: %i, Total nodes: %i" % (node_to_remove, len(nodes))
            # print "\tStopping some DES processes: %s\n\n"%keys_DES
            filelog.write(
                "%i,%s,%d\n" % (node_to_remove, someModuleDeployed, sim.env.now)
            )

            ##Print some information:
            # for des in keys_DES:
            #     if des in sim.alloc_source.keys():
            #         print "Removing a Gtw/User entity\t"*4

            sim.remove_node(node_to_remove)
            for key in keys_DES:
                sim.stop_process(key)
        except IndexError:
            None

    else:
        sim.stop = True  ## We stop the simulation


def main(simulated_time, experimento, ilpPath, it):
    """
    Fungsi utama untuk menjalankan simulasi fog computing dengan YAFS framework.

    Fungsi ini melakukan setup dan eksekusi simulasi lengkap yang mencakup:
    - Loading topology network dari file JSON
    - Membuat aplikasi dari definisi JSON
    - Menerapkan algoritma placement untuk alokasi resource
    - Setup population untuk simulasi user
    - Menjalankan simulasi dengan selector routing algorithm

    Args:
        simulated_time (int): Waktu simulasi dalam detik yang akan dijalankan
        experimento (str): Path ke direktori experiment yang berisi file konfigurasi
        ilpPath (str): Identifier untuk file allocation definition yang akan digunakan
        it (int): Nomor iterasi untuk eksperimen yang sedang berjalan

    Returns:
        None: Fungsi ini tidak mengembalikan nilai, tetapi menghasilkan file hasil
              simulasi di direktori yang ditentukan

    File Dependencies:
        - {experimento}networkDefinition.json: Definisi topology network
        - {experimento}appDefinition.json: Definisi aplikasi yang akan di-deploy
        - {experimento}allocDefinition{ilpPath}.json: Definisi allocation placement
        - {experimento}usersDefinition.json: Definisi population user

    Output Files:
        - network.gexf: File topology network dalam format GEXF
        - Results_{ilpPath}_{stop_time}_{it}/: Direktori hasil simulasi

    Note:
        Fungsi ini menggunakan DeviceSpeedAwareRouting sebagai selector algorithm
        dan menjalankan simulasi untuk setiap aplikasi secara terpisah dengan
        population yang sesuai.
    """
    """
    TOPOLOGY from a json
    """
    t = Topology()
    dataNetwork = json.load(open(experimento + "networkDefinition.json"))
    t.load(dataNetwork)
    t.write("network.gexf")

    """
    APPLICATION
    """
    dataApp = json.load(open(experimento + "appDefinition.json"))
    apps = create_applications_from_json(dataApp)
    # for app in apps:
    #  print apps[app]

    """
    PLACEMENT algorithm
    """
    placementJson = json.load(open(experimento + "allocDefinition%s.json" % ilpPath))
    placement = JSONPlacement(name="Placement", json=placementJson)

    ### Placement histogram

    # listDevices =[]
    # for item in placementJson["initialAllocation"]:
    #     listDevices.append(item["id_resource"])
    # import matplotlib.pyplot as plt
    # print listDevices
    # print np.histogram(listDevices,bins=range(101))
    # plt.hist(listDevices, bins=100)  # arguments are passed to np.histogram
    # plt.title("Placement Histogram")
    # plt.show()
    ## exit()
    """
    POPULATION algorithm
    """
    dataPopulation = json.load(open(experimento + "usersDefinition.json"))
    pop = JSONPopulation(name="Statical", json=dataPopulation, iteration=it)

    """
    SELECTOR algorithm
    """
    selectorPath = DeviceSpeedAwareRouting()

    """
    SIMULATION ENGINE
    """

    stop_time = simulated_time
    s = Sim(
        t,
        default_results_path=experimento
        + "Results_%s_%i_%i" % (ilpPath, stop_time, it),
    )

    """
    Failure process
    """
    # time_shift = 10000
    # distribution = deterministicDistributionStartPoint(name="Deterministic", time=time_shift,start=10000)
    # failurefilelog = open(experimento+"Failure_%s_%i.csv" % (ilpPath,stop_time),"w")
    # failurefilelog.write("node, module, time\n")
    # idCloud = t.find_IDs({"type": "CLOUD"})[0] #[0] -> In this study there is only one CLOUD DEVICE
    # centrality = np.load(pathExperimento+"centrality.npy")
    # randomValues = np.load(pathExperimento+"random.npy")
    # # s.deploy_monitor("Failure Generation", failureControl, distribution,sim=s,filelog=failurefilelog,ids=centrality)
    # s.deploy_monitor("Failure Generation", failureControl, distribution,sim=s,filelog=failurefilelog,ids=randomValues)

    # For each deployment the user - population have to contain only its specific sources
    for aName in apps.keys():
        print("Deploying app: ", aName)
        pop_app = JSONPopulation(name="Statical_%s" % aName, json={}, iteration=it)
        data = []
        for element in pop.data["sources"]:
            if element["app"] == aName:
                data.append(element)
        pop_app.data["sources"] = data

        s.deploy_app(apps[aName], placement, pop_app, selectorPath)

    s.run(
        stop_time, test_initial_deploy=False, show_progress_monitor=False
    )  # TEST to TRUE

    ## Enrouting information
    # print "Values"
    # print selectorPath.cache.values()

    # failurefilelog.close()

    # #CHECKS
    # print s.topology.G.nodes
    # s.print_debug_assignaments()


if __name__ == "__main__":
    # import logging.config
    import os

    pathExperimento = "data/"
    # pathExperimento = "exp_rev/"
    # pathExperimento = "/home/uib/src/YAFS/src/examples/PartitionILPPlacement/exp_rev/"

    print(os.getcwd())
    # logging.config.fileConfig(os.getcwd()+'/logging.ini')
    # for i in range(50):
    #     start_time = time.time()
    #     random.seed(i)
    #     np.random.seed(i)
    #     # 1000000
    #     print("Running Partition")
    #     main(simulated_time=1000000, experimento=pathExperimento, ilpPath="", it=i)
    #     print("\n--- %s seconds ---" % (time.time() - start_time))
    #     start_time = time.time()
    #     print("Running: ILP ")
    #     main(simulated_time=1000000, experimento=pathExperimento, ilpPath="ILP", it=i)
    #     print("\n--- %s seconds ---" % (time.time() - start_time))

    start_time = time.time()
    random.seed(42)
    np.random.seed(42)
    # 1000000
    print("Running Partition")
    main(simulated_time=1000000, experimento=pathExperimento, ilpPath="", it=0)
    print("\n--- %s seconds ---" % (time.time() - start_time))
    start_time = time.time()
    print("Running: ILP ")
    main(simulated_time=1000000, experimento=pathExperimento, ilpPath="ILP", it=0)
    print("\n--- %s seconds ---" % (time.time() - start_time))

    print("Simulation Done")
