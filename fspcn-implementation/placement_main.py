import random
import experiment_configuration
import my_config
import CN_optimization
import ILP_optimization

#
# Initialization and set up
#
random.seed(8)
generate_plots = True

ILPOptimization = False
CommunityOptimization = False
GAOptimization = True

config = my_config.MyConfig()
ec = experiment_configuration.ExperimentConfiguration(config)
ec.load_configuration(config.my_configuration)

ec.network_generation()
ec.app_generation()
ec.user_generation()

#
# Graph Partition Optimization
#

if CommunityOptimization:
    cno_ = CN_optimization.CNoptimization(ec, config)
    service_to_device_placement_matrix_CN = cno_.solve()

#
# ILP Optimization
#

if ILPOptimization:
    ilp_ = ILP_optimization.ILP(ec, config)
    service_to_device_placement_matrix_ILP = ilp_.solve()

#
# GA Optimization
#
if GAOptimization:
    # TODO - Implementasi Genetic Algorithm dari paper FSPCN
    pass
