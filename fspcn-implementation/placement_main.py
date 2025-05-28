import random
import experiment_configuration
import my_config
import CN_optimization

#
# Initialization and set up
#
random.seed(8)
verbose_log = False
generate_plots = True

CommunityOptimization = True

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
    service_to_device_placement_matrix = cno_.solve()
