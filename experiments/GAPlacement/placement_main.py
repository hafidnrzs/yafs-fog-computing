import random
import experiment_configuration
import my_config
import GA_optimization

#
# Initialization and set up
#
random.seed(8)
generate_plots = True


GAOptimization = True

config = my_config.MyConfig()
ec = experiment_configuration.ExperimentConfiguration(config)
ec.load_configuration(config.my_configuration)

ec.network_generation()
ec.app_generation()
ec.user_generation()


#
# GA Optimization
#
if GAOptimization:
    ga_ = GA_optimization.GA(ec, config)
    service_to_device_placement_matrix_GA = ga_.solve()
