
import random
import experimentConfiguration
import myConfig
import ILPoptimization
import CNoptimization
import WCNoptimization
import GAoptimization

# import FSPCNoptimization


# ****************************************************************************************************

# inizializations and set up

# ****************************************************************************************************

random.seed(8)

ILP_optimization = True
Communityoptimization = True
WCN_optimization = True
FSPCN_optimization = False
GA_optimization = True
# MOLP_optimization = False

cnf_ = myConfig.myConfig()
ec = experimentConfiguration.experimentConfiguration(cnf_)

# Men-generate JSON file dari 2 file konfig sebelumnya (myConfig, exsperimentConfiguration)
ec.loadConfiguration(cnf_.myConfiguration_)
ec.networkGeneration()
ec.appGeneration()
ec.userGeneration()

#########################
#    ILP OPTIMIZATION
#########################

# if ILP_optimization:
#     ilp_ = ILPoptimization.ILP(ec, cnf_)
#     service2DevicePlacementMatrixILP = ilp_.solve()

#########################
#    MOLP OPTIMIZATION
#########################

# if MOLP_optimization:
#     molp_ = MOLPoptimization.MOLP(ec, cnf_)
#     service2DevicePlacementMatrixMOLP = molp_.solve()

#########################
#    GRAPH PARTITION OPTIMIZATION
# #########################

if Communityoptimization:
    cno_ = CNoptimization.CNoptimization(ec, cnf_)
    service2DevicePlacementMatrixCN = cno_.solve()

#########################
#     Weighted Greedy Heuristic OPTIMIZATION
#########################

if WCN_optimization:
    wcn_ = WCNoptimization.WCNoptimization(ec, cnf_)
    service2DevicePlacementMatrixCN = wcn_.solve()

#########################
#    FSPCN OPTIMIZATION
#########################

# if FSPCN_optimization:
#     fspcn_ = FSPCNoptimization.FSPCNoptimization(ec, cnf_)
#     service2DevicePlacementMatrixCN = fspcn_.solve()  

########################
#    GA OPTIMIZATION
########################

if GA_optimization:
   ga_ = GAoptimization.GAoptimization(ec, cnf_)
   service2DevicePlacementMatrixCN = ga_.solve()
    

