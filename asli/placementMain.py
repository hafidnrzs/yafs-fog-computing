import random
import experimentConfiguration
import myConfig
import ILPoptimization
import CNoptimization
import FSPCNoptimization
#import GAoptimization

# ****************************************************************************************************

# inizializations and set up

# ****************************************************************************************************
random.seed(8)

ILP_optimization = True
Communityoptimization = True
FSPCN_optimization = True
#GeneticOptimization = True


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

if ILP_optimization:
    ilp_ = ILPoptimization.ILP(ec, cnf_)
    service2DevicePlacementMatrixILP = ilp_.solve()

#########################
#    GRAPH PARTITION OPTIMIZATION
#########################

if Communityoptimization:
    cno_ = CNoptimization.CNoptimization(ec, cnf_)
    service2DevicePlacementMatrixCN = cno_.solve()

#########################
#    FSPCN OPTIMIZATION
#########################

if FSPCN_optimization:
    fspcn_ = FSPCNoptimization.FSPCNoptimization(ec, cnf_)
    service2DevicePlacementMatrixCN = fspcn_.solve()  

#########################
#    GA OPTIMIZATION
#########################

#if GeneticOptimization:
#    ga_ = GAoptimization.GAoptimization(ec, cnf_)
#    service2DevicePlacementMatrixCN = ga_.solve()
    

