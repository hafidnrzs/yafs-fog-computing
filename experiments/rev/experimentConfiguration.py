#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  2 11:52:43 2018

@author: carlos
"""

import networkx as nx
import time
import operator
import copy
import json
import random


class experimentConfiguration:
    def __init__(self, cnf_):
        # Default tiny configuration
        self.TOTALNUMBEROFAPPS = 1
        self.CLOUDCAPACITY = 9999999999999999
        self.CLOUDSPEED = 9999
        self.CLOUDBW = 999
        self.CLOUDPR = 99
        self.PERCENTATGEOFGATEWAYS = 0.2
        self.PERCENTAGEOFCLOUDGATEWAYS = (
            0.05  # Default percentage of nodes that are cloud gateways
        )
        self.func_PROPAGATIONTIME = "random.randint(10,10)"
        self.func_BANDWITDH = "random.randint(100,100)"
        self.func_SERVICEINSTR = "random.randint(100,100)"
        self.func_SERVICEMESSAGESIZE = "random.randint(500,500)"
        self.func_NETWORKGENERATION = "nx.barbell_graph(5, 1)"  # algorithm for the generation of the network topology
        self.func_NODERESOURECES = "random.randint(1,1)"  # random distribution for the resources of the fog devices
        self.func_NODESPEED = "random.randint(100,1000)"  # random distribution for the speed of the fog devices
        self.func_APPGENERATION = "nx.gn_graph(random.randint(2,3))"  # algorithm for the generation of the random applications
        self.func_REQUESTPROB = "random.random()/4"  # Popularidad de la app. threshold que determina la probabilidad de que un dispositivo tenga asociado peticiones a una app. tle threshold es para cada ap
        self.func_REQUESTPROB = "1.0"  # Popularidad de la app. threshold que determina la probabilidad de que un dispositivo tenga asociado peticiones a una app. tle threshold es para cada ap
        self.func_SERVICERESOURCES = "10"
        self.func_APPDEADLINE = "(random.random()*4)"
        self.func_USERREQRAT = "random.random()"

        self.cnf = cnf_

    def userGeneration(self):
        # ****************************************************************************************************
        # generation of the IoT devices (users)
        # ****************************************************************************************************

        userJson = {}

        self.myUsers = list()

        self.appsRequests = list()
        for i in range(0, self.TOTALNUMBEROFAPPS):
            userRequestList = set()
            probOfRequested = eval(self.func_REQUESTPROB)
            atLeastOneAllocated = False
            for j in self.gatewaysDevices:
                if random.random() < probOfRequested:
                    myOneUser = {}
                    myOneUser["app"] = str(i)
                    myOneUser["message"] = "M.USER.APP." + str(i)
                    myOneUser["id_resource"] = j
                    myOneUser["lambda"] = eval(self.func_USERREQRAT)
                    userRequestList.add(j)
                    self.myUsers.append(myOneUser)
                    atLeastOneAllocated = True
            if not atLeastOneAllocated:
                j = random.choice(list(self.gatewaysDevices))
                myOneUser = {}
                myOneUser["app"] = str(i)
                myOneUser["message"] = "M.USER.APP." + str(i)
                myOneUser["id_resource"] = j
                myOneUser["lambda"] = eval(self.func_USERREQRAT)
                userRequestList.add(j)
                self.myUsers.append(myOneUser)
            self.appsRequests.append(userRequestList)

        userJson["sources"] = self.myUsers

        file = open(self.cnf.resultFolder + "/usersDefinition.json", "w")
        print(
            "Users definition generated in",
            self.cnf.resultFolder + "/usersDefinition.json",
        )
        file.write(json.dumps(userJson))
        file.close()

    def appGeneration(self):
        # ****************************************************************************************************
        # application generation
        # ****************************************************************************************************

        self.numberOfServices = 0
        self.apps = list()
        self.appsDeadlines = {}
        self.appsResources = list()
        self.appsSourceService = list()
        self.appsSourceMessage = list()
        self.appsTotalMIPS = list()
        self.mapService2App = list()
        self.mapServiceId2ServiceName = list()

        appJson = list()
        self.servicesResources = {}

        for i in range(0, self.TOTALNUMBEROFAPPS):
            myApp = {}
            APP = eval(self.func_APPGENERATION)

            mylabels = {}

            for n in range(0, len(APP.nodes)):
                mylabels[n] = str(n)

            if self.cnf.graphicTerminal:
                nx.draw(APP, labels=mylabels)

            edgeList_ = list()

            for m in APP.edges:
                edgeList_.append(m)
            for m in edgeList_:
                APP.remove_edge(m[0], m[1])
                APP.add_edge(m[1], m[0])

            if self.cnf.graphicTerminal:
                nx.draw(APP, labels=mylabels)

            mapping = dict(
                zip(
                    APP.nodes(),
                    range(
                        self.numberOfServices, self.numberOfServices + len(APP.nodes)
                    ),
                )
            )
            APP = nx.relabel_nodes(APP, mapping)

            self.numberOfServices = self.numberOfServices + len(APP.nodes)
            self.apps.append(APP)
            for j in APP.nodes:
                self.servicesResources[j] = eval(self.func_SERVICERESOURCES)
            self.appsResources.append(self.servicesResources)

            topologicorder_ = list(nx.topological_sort(APP))
            source = topologicorder_[0]

            self.appsSourceService.append(source)

            # appsDeadlines[i]=eval(func_APPDEADLINE)
            # self.appsDeadlines[i] = self.myDeadlines[i]
            self.appsDeadlines[i] = eval(self.func_APPDEADLINE)
            myApp["id"] = i
            myApp["name"] = str(i)
            myApp["deadline"] = self.appsDeadlines[i]

            myApp["module"] = list()

            edgeNumber = 0
            myApp["message"] = list()

            myApp["transmission"] = list()

            totalMIPS = 0

            for n in APP.nodes:
                self.mapService2App.append(str(i))
                self.mapServiceId2ServiceName.append(str(i) + "_" + str(n))
                myNode = {}
                myNode["id"] = n
                myNode["name"] = str(i) + "_" + str(n)
                myNode["RAM"] = self.servicesResources[n]
                myNode["type"] = "MODULE"
                if source == n:
                    myEdge = {}
                    myEdge["id"] = edgeNumber
                    edgeNumber = edgeNumber + 1
                    myEdge["name"] = "M.USER.APP." + str(i)
                    myEdge["s"] = "None"
                    myEdge["d"] = str(i) + "_" + str(n)
                    myEdge["instructions"] = eval(self.func_SERVICEINSTR)
                    totalMIPS = totalMIPS + myEdge["instructions"]
                    myEdge["bytes"] = eval(self.func_SERVICEMESSAGESIZE)
                    myApp["message"].append(myEdge)
                    self.appsSourceMessage.append(myEdge)
                    if self.cnf.verbose_log:
                        print("AÑADO MENSAGE SOURCE")
                    for o in APP.edges:
                        if o[0] == source:
                            myTransmission = {}
                            myTransmission["module"] = str(i) + "_" + str(source)
                            myTransmission["message_in"] = "M.USER.APP." + str(i)
                            myTransmission["message_out"] = (
                                str(i) + "_(" + str(o[0]) + "-" + str(o[1]) + ")"
                            )
                            myApp["transmission"].append(myTransmission)

                myApp["module"].append(myNode)

            for n in APP.edges:
                myEdge = {}
                myEdge["id"] = edgeNumber
                edgeNumber = edgeNumber + 1
                myEdge["name"] = str(i) + "_(" + str(n[0]) + "-" + str(n[1]) + ")"
                myEdge["s"] = str(i) + "_" + str(n[0])
                myEdge["d"] = str(i) + "_" + str(n[1])
                myEdge["instructions"] = eval(self.func_SERVICEINSTR)
                totalMIPS = totalMIPS + myEdge["instructions"]
                myEdge["bytes"] = eval(self.func_SERVICEMESSAGESIZE)
                myApp["message"].append(myEdge)
                destNode = n[1]
                for o in APP.edges:
                    if o[0] == destNode:
                        myTransmission = {}
                        myTransmission["module"] = str(i) + "_" + str(n[1])
                        myTransmission["message_in"] = (
                            str(i) + "_(" + str(n[0]) + "-" + str(n[1]) + ")"
                        )
                        myTransmission["message_out"] = (
                            str(i) + "_(" + str(o[0]) + "-" + str(o[1]) + ")"
                        )
                        myApp["transmission"].append(myTransmission)

            for n in APP.nodes:
                outgoingEdges = False
                for m in APP.edges:
                    if m[0] == n:
                        outgoingEdges = True
                        break
                if not outgoingEdges:
                    for m in APP.edges:
                        if m[1] == n:
                            myTransmission = {}
                            myTransmission["module"] = str(i) + "_" + str(n)
                            myTransmission["message_in"] = (
                                str(i) + "_(" + str(m[0]) + "-" + str(m[1]) + ")"
                            )
                            myApp["transmission"].append(myTransmission)

            self.appsTotalMIPS.append(totalMIPS)

            appJson.append(myApp)

        file = open(self.cnf.resultFolder + "/appDefinition.json", "w")
        print(
            "Application definition generated in",
            self.cnf.resultFolder + "/appDefinition.json",
        )
        file.write(json.dumps(appJson))
        file.close()

    def networkGeneration(self):
        # ****************************************************************************************************
        # generation of the network topology
        # ****************************************************************************************************

        # TOPOLOGY GENERATION

        self.G = eval(self.func_NETWORKGENERATION)
        # G = nx.barbell_graph(5, 1)
        if self.cnf.graphicTerminal:
            nx.draw(self.G)

        self.devices = list()

        self.nodeResources = {}
        self.nodeFreeResources = {}
        self.nodeSpeed = {}
        for i in self.G.nodes:
            self.nodeResources[i] = eval(self.func_NODERESOURECES)
            self.nodeSpeed[i] = eval(self.func_NODESPEED)

        for e in self.G.edges:
            self.G[e[0]][e[1]]["PR"] = eval(self.func_PROPAGATIONTIME)
            self.G[e[0]][e[1]]["BW"] = eval(self.func_BANDWITDH)

        # JSON EXPORT

        netJson = {}

        for i in self.G.nodes:
            myNode = {}
            myNode["id"] = i
            myNode["RAM"] = self.nodeResources[i]
            myNode["IPT"] = self.nodeSpeed[i]
            self.devices.append(myNode)

        myEdges = list()
        for e in self.G.edges:
            myLink = {}
            myLink["s"] = e[0]
            myLink["d"] = e[1]
            myLink["PR"] = self.G[e[0]][e[1]]["PR"]
            myLink["BW"] = self.G[e[0]][e[1]]["BW"]

            myEdges.append(myLink)

        centralityValuesNoOrdered = nx.betweenness_centrality(self.G, weight="weight")
        centralityValues = sorted(
            centralityValuesNoOrdered.items(), key=operator.itemgetter(1), reverse=True
        )

        self.gatewaysDevices = set()
        self.cloudgatewaysDevices = set()

        # Calculate number of cloud gateways based on percentage
        # Cloud gateways are the nodes with highest centrality that connect directly to cloud
        numCloudGateways = max(
            1, int(self.PERCENTAGEOFCLOUDGATEWAYS * len(self.G.nodes))
        )

        # Select top nodes with HIGHEST centrality as cloud gateways
        for i in range(numCloudGateways):
            if i < len(centralityValues):
                self.cloudgatewaysDevices.add(centralityValues[i][0])

        # Select regular gateways from LOWEST centrality nodes (bottom 25%)
        # Calculate how many nodes to select from the bottom
        numGateways = int(self.PERCENTATGEOFGATEWAYS * len(self.G.nodes))

        # Select from the end of the list (lowest centrality values)
        for idDev in range(len(centralityValues) - numGateways, len(centralityValues)):
            if idDev >= 0:  # Safety check
                self.gatewaysDevices.add(centralityValues[idDev][0])

        self.cloudId = len(self.G.nodes)
        myNode = {}
        myNode["id"] = self.cloudId
        myNode["RAM"] = self.CLOUDCAPACITY
        myNode["IPT"] = self.CLOUDSPEED
        myNode["type"] = "CLOUD"
        self.devices.append(myNode)

        for cloudGtw in self.cloudgatewaysDevices:
            myLink = {}
            myLink["s"] = cloudGtw
            myLink["d"] = self.cloudId
            myLink["PR"] = self.CLOUDPR
            myLink["BW"] = self.CLOUDBW

            myEdges.append(myLink)

        netJson["entity"] = self.devices
        netJson["link"] = myEdges

        file = open(self.cnf.resultFolder + "/networkDefinition.json", "w")
        print(
            "Network definition generated in",
            self.cnf.resultFolder + "/networkDefinition.json",
        )
        file.write(json.dumps(netJson))
        file.close()

    def loadConfiguration(self, myConfiguration_):
        # Configuration for the IEEE IoT journal experiments
        if myConfiguration_ == "iotjournal":
            # CLOUD
            self.CLOUDCAPACITY = 9999999999999999  # MB RAM
            self.CLOUDSPEED = 10000  # INSTR x MS
            self.CLOUDBW = 125000  # BYTES / MS --> 1000 Mbits/s
            self.CLOUDPR = 1  # MS

            # NETWORK
            self.PERCENTATGEOFGATEWAYS = 0.25
            self.PERCENTAGEOFCLOUDGATEWAYS = 0.05
            self.func_PROPAGATIONTIME = "random.randint(5,5)"  # MS
            self.func_BANDWITDH = "random.randint(75000,75000)"  # BYTES / MS
            self.func_NETWORKGENERATION = "nx.barabasi_albert_graph(n=100, m=2)"  # algorithm for the generation of the network topology
            self.func_NODERESOURECES = "random.randint(10,25)"  # MB RAM #random distribution for the resources of the fog devices
            self.func_NODESPEED = "random.randint(100,1000)"  # INTS / MS #random distribution for the speed of the fog devices

            # APP and SERVICES
            self.TOTALNUMBEROFAPPS = 80
            self.func_APPGENERATION = "nx.gn_graph(random.randint(2,10))"  # algorithm for the generation of the random applications
            self.func_SERVICEINSTR = "random.randint(20000,60000)"  # INSTR --> teniedno en cuenta nodespped esto nos da entre 200 y 600 MS
            self.func_SERVICEMESSAGESIZE = "random.randint(1500000,4500000)"  # BYTES y teniendo en cuenta net bandwidth nos da entre 20 y 60 MS
            self.func_SERVICERESOURCES = "random.randint(1,6)"  # MB de ram que consume el servicio, teniendo en cuenta noderesources y appgeneration tenemos que nos caben aprox 1 app por nodo o unos 10 servicios
            self.func_APPDEADLINE = "random.randint(2600,6600)"  # MS

            # USERS and IoT DEVICES
            self.func_REQUESTPROB = "random.random()/4"  # Popularidad de la app. threshold que determina la probabilidad de que un dispositivo tenga asociado peticiones a una app. tle threshold es para cada ap
            self.func_USERREQRAT = "random.randint(200,1000)"  # MS

            # self.myDeadlines = [
            #     487203.22,
            #     487203.22,
            #     487203.22,
            #     474.51,
            #     302.05,
            #     831.04,
            #     793.26,
            #     1582.21,
            #     2214.64,
            #     374046.40,
            #     420476.14,
            #     2464.69,
            #     97999.14,
            #     2159.73,
            #     915.16,
            #     1659.97,
            #     1059.97,
            #     322898.56,
            #     1817.51,
            #     406034.73,
            # ]
