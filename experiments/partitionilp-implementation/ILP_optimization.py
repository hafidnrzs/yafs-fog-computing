#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Copyright 2018 Carlos Guerrero, Isaac Lera.
Created on Tue May 22 15:58:58 2018
@authors:
    Carlos Guerrero
    carlos ( dot ) guerrero  uib ( dot ) es
    Isaac Lera
    isaac ( dot ) lera  uib ( dot ) es
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.


This program has been implemented for the research presented in the
article "Availability-aware Service Placement Policy in Fog Computing
Based on Graph Partitions" and submitted for evaluation to the "IEEE
IoT Journal".
"""

import pulp
import itertools
import copy
import networkx as nx
import operator
import time
import json


class ILP:
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        self.networkdistances = {}
        self.nodeResUseILP = list()

        # deviceId: total usage resources
        self.nodeBussyResourcesILP = {}

        # (centrality,resources):occurrences
        self.statisticsCentralityResourcesILP = {}

        self.myServicesResources = {}

        # (deadline,shortestdistance):occurrences
        self.statisticsDistanceDeadlineILP = {}

        # (service,deadline):occurrences
        self.statisticsServiceInstancesILP = {}

        # distance:numberOfuserThatRequest
        self.statisticsDistancesRequestILP = {}

        # nodeid:numberOfuserThatRequest
        self.statisticsNodesRequestILP = {}

        # (nodeid,serviceId):ocurrences
        self.statisticsNodesServicesILP = {}

    def writeStatisticsAllocationILP(self, clientId, servId, devId):
        if not devId == self.ec.cloud_id:
            appId = int(self.ec.map_service_to_apps[servId])

            dist_ = nx.shortest_path_length(
                self.ec.G, source=clientId, target=devId, weight="weight"
            )

            mykey_ = dist_
            if mykey_ in self.statisticsDistancesRequestILP:
                self.statisticsDistancesRequestILP[mykey_] = (
                    self.statisticsDistancesRequestILP[mykey_] + 1
                )
            else:
                self.statisticsDistancesRequestILP[mykey_] = 1

            mykey_ = devId
            if mykey_ in self.statisticsNodesRequestILP:
                self.statisticsNodesRequestILP[mykey_] = (
                    self.statisticsNodesRequestILP[mykey_] + 1
                )
            else:
                self.statisticsNodesRequestILP[mykey_] = 1

            mykey_ = (devId, servId)
            if mykey_ in self.statisticsNodesServicesILP:
                self.statisticsNodesServicesILP[mykey_] = (
                    self.statisticsNodesServicesILP[mykey_] + 1
                )
            else:
                self.statisticsNodesServicesILP[mykey_] = 1

            mykey_ = (self.ec.app_deadlines[appId], dist_)
            if mykey_ in self.statisticsDistanceDeadlineILP:
                self.statisticsDistanceDeadlineILP[mykey_] = (
                    self.statisticsDistanceDeadlineILP[mykey_] + 1
                )
            else:
                self.statisticsDistanceDeadlineILP[mykey_] = 1

            mykey_ = (servId, self.ec.app_deadlines[appId])
            if mykey_ in self.statisticsServiceInstancesILP:
                self.statisticsServiceInstancesILP[mykey_] = (
                    self.statisticsServiceInstancesILP[mykey_] + 1
                )
            else:
                self.statisticsServiceInstancesILP[mykey_] = 1

    def calculateNodeUsage(self, service2DevicePlacementMatrix):
        nodeResUse = list()
        nodeNumServ = list()

        for i in service2DevicePlacementMatrix[0]:
            nodeResUse.append(0.0)
            nodeNumServ.append(0)

        for idServ in range(0, len(service2DevicePlacementMatrix)):
            for idDev in range(0, len(service2DevicePlacementMatrix[idServ])):
                if service2DevicePlacementMatrix[idServ][idDev] == 1:
                    nodeNumServ[idDev] = nodeNumServ[idDev] + 1
                    nodeResUse[idDev] = (
                        nodeResUse[idDev] + self.ec.service_resources[idServ]
                    )

        for idDev in range(0, len(service2DevicePlacementMatrix[0])):
            nodeResUse[idDev] = nodeResUse[idDev] / self.ec.node_resources[idDev]

        nodeResUse = sorted(nodeResUse)
        nodeNumServ = sorted(nodeNumServ)

        return nodeResUse, nodeNumServ

    def normalizeStatisticsDevicesILP(self):
        for i in self.nodeBussyResourcesILP.items():
            devId = i[0]
            mypercentageResources_ = float(self.nodeBussyResourcesILP[devId]) / float(
                self.ec.node_resources[devId]
            )
            mycentralityValues_ = self.centralityValuesNoOrdered[devId]
            mykey_ = (mycentralityValues_, mypercentageResources_)
            if mykey_ in self.statisticsCentralityResourcesILP:
                self.statisticsCentralityResourcesILP[mykey_] = (
                    self.statisticsCentralityResourcesILP[mykey_] + 1
                )
            else:
                self.statisticsCentralityResourcesILP[mykey_] = 1

    def writeStatisticsDevicesILP(self, servId, devId):
        #
        if not devId == self.ec.cloud_id:
            mykey_ = devId
            if mykey_ in self.nodeBussyResourcesILP:
                self.nodeBussyResourcesILP[mykey_] = self.nodeBussyResourcesILP[
                    mykey_
                ] + float(self.myServicesResources[servId])
            else:
                self.nodeBussyResourcesILP[mykey_] = float(
                    self.myServicesResources[servId]
                )

    def networkDelay(self, i):
        processTime = 0.0
        # processTime = mips_ / float(devices[devId]['IPT']) # time to execute all the services of the application
        netTime = self.networkdistances[
            (i[0][0], i[1])
        ]  # network latency between the device and the user
        return processTime + netTime

    def solve(self):
        t = time.time()

        self.service2DevicePlacementMatrixILP = [
            [0 for j in range(len(self.ec.G.nodes))]
            for i in range(self.ec.number_of_services)
        ]

        self.centralityValuesNoOrdered = nx.betweenness_centrality(
            self.ec.G, weight="weight"
        )

        print("Starting ILP optimization....")

        fognodes = list()
        for i in self.ec.G.nodes:
            fognodes.append(i)
        fognodes.append(self.ec.cloud_id)

        for myapp in self.ec.app_resources:
            for i in myapp.items():
                self.myServicesResources[i[0]] = i[1]

        myDevices = {}

        for i, v in enumerate(self.ec.devices):
            myDevices[i] = copy.copy(v)

        userServices = list()
        allTheGtws = set()

        numIoTDevices = 0

        for i, gtwList in enumerate(self.ec.app_requests):
            for gtwId in gtwList:
                numIoTDevices = numIoTDevices + 1
                for servId in self.ec.apps[i].nodes:
                    userServices.append((gtwId, servId))
                    allTheGtws.add(gtwId)

        for gtwId in allTheGtws:
            for devId in self.ec.G.nodes:
                self.networkdistances[(gtwId, devId)] = nx.shortest_path_length(
                    self.ec.G, source=gtwId, target=devId, weight="weight"
                )
            self.networkdistances[(gtwId, self.ec.cloud_id)] = 999999999999999999.9

        assignCombinations = list(itertools.product(userServices, fognodes))

        sortedAppsDeadlines = sorted(
            self.ec.app_deadlines.items(), key=operator.itemgetter(1)
        )

        allAlloc = {}
        myAllocationList = list()
        servicesInCloud = 0
        servicesInFog = 0

        ##### Model
        ## Problem

        for appToAllocate in sortedAppsDeadlines:
            appId = appToAllocate[0]

            problem = pulp.LpProblem("fog_app:" + str(appId), pulp.LpMinimize)
            ## Variables

            assignCombinationsForApp = list()
            for aComb in assignCombinations:
                if int(self.ec.map_service_to_apps[aComb[0][1]]) == appId:
                    assignCombinationsForApp.append(aComb)

            userServicesForApp = list()
            for uServ in userServices:
                if int(self.ec.map_service_to_apps[uServ[1]]) == appId:
                    userServicesForApp.append(uServ)

            UserServiceDevAssignment = {
                comb: pulp.LpVariable(
                    "sa_%i_%i_%i" % (comb[0][0], comb[0][1], comb[1]), cat="Binary"
                )
                for comb in assignCombinationsForApp
            }

            ## Objective

            problem += (
                pulp.lpSum(
                    [
                        (UserServiceDevAssignment[i] * self.networkDelay(i))
                        for i in assignCombinationsForApp
                    ]
                ),
                "Objective",
            )

            # Constraints

            # at least one service instantiated for each user
            for usrservId in userServicesForApp:
                problem += (
                    pulp.lpSum(
                        [
                            (UserServiceDevAssignment[(usrservId, devId)])
                            for devId in fognodes
                        ]
                    )
                    == 1,
                    "TaskAssignmentLowerBound_" + str(usrservId),
                )

            # allocated services less resources than available

            for devId in fognodes:
                problem += (
                    pulp.lpSum(
                        [
                            (
                                UserServiceDevAssignment[(usrservId, devId)]
                                * self.myServicesResources[usrservId[1]]
                            )
                            for usrservId in userServicesForApp
                        ]
                    )
                    <= myDevices[devId]["RAM"],
                    "DeviceCapacity_" + str(devId),
                )
            #    problem += sum([(UserServiceDevAssignment[(usrservId,devId)]* myServicesResources[usrservId[1]] ) for usrservId in userServices])> -1.0, 'DeviceCapacity_' +str(devId)

            #        print "************"
            #        print "Number of nodes (myDevices): "+str(len(myDevices))
            #        print "Number of services (myServicesResources): "+str(len(myServicesResources))
            #        print "Number of gateways (allTheGtws): "+str(len(allTheGtws))
            #        print "Number of IoT devices (numIoTDevices): "+str(numIoTDevices)
            #        print "Number of IoT devices X services (userServicesForApp): "+str(len(userServicesForApp))
            #        print "Number of ILP variables (assignCombinationsForApp): "+str(len(assignCombinationsForApp))
            #        print "************"

            #        print "Solving the problem..."
            problem.solve()

            #        print "The ILP finished in status "+str(problem.status)

            if problem.status == pulp.LpStatusOptimal:
                for i in assignCombinationsForApp:
                    if UserServiceDevAssignment[i].value() > 0.0:
                        if self.cnf.verbose_log:
                            print("-------")
                            print(i)
                            print(UserServiceDevAssignment[i].value())
                        #                    assignResult = UserServiceDevAssignment[i].value()
                        myAllocation = {}
                        if i[1] == self.ec.cloud_id:
                            servicesInCloud = servicesInCloud + 1
                        else:
                            servicesInFog = servicesInFog + 1
                            myAllocation["app"] = self.ec.map_service_to_apps[i[0][1]]
                            myAllocation["module_name"] = (
                                self.ec.map_service_id_to_service_name[i[0][1]]
                            )
                            myAllocation["id_resource"] = i[1]
                            myAllocationList.append(myAllocation)
                            self.writeStatisticsAllocationILP(
                                i[0][0], i[0][1], i[1]
                            )  # clientId, serviceId,devId
                            self.writeStatisticsDevicesILP(
                                i[0][1], i[1]
                            )  # serviceId,devId
                            myDevices[i[1]]["RAM"] = (
                                myDevices[i[1]]["RAM"]
                                - self.myServicesResources[i[0][1]]
                            )
                            self.service2DevicePlacementMatrixILP[i[0][1]][i[1]] = (
                                1  # serviceId,devId
                            )

        for idServ in range(self.ec.number_of_services):
            myAllocation = {}
            myAllocation["app"] = self.ec.map_service_to_apps[idServ]
            myAllocation["module_name"] = self.ec.map_service_id_to_service_name[idServ]
            myAllocation["id_resource"] = self.ec.cloud_id
            myAllocationList.append(myAllocation)
            servicesInCloud = servicesInCloud + 1

        self.nodeResUseILP, self.nodeNumServILP = self.calculateNodeUsage(
            self.service2DevicePlacementMatrixILP
        )

        self.normalizeStatisticsDevicesILP()

        print(
            "Number of services in cloud (ILP) (servicesInCloud): "
            + str(servicesInCloud)
        )
        print("Number of services in fog (ILP) (servicesInFog): " + str(servicesInFog))

        allAlloc["initialAllocation"] = myAllocationList

        file = open(self.cnf.data_folder + "/allocDefinitionILP.json", "w")
        file.write(json.dumps(allAlloc))
        file.close()

        print(str(time.time() - t) + " time for ILP-based optimization")

        return self.service2DevicePlacementMatrixILP
