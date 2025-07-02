from yafs.population import Population
from yafs.distribution import exponentialDistribution


class JSONPopulation(Population):
    def __init__(self, json, iteration,**kwargs):
        super(JSONPopulation, self).__init__(**kwargs)
        self.data = json
        self.it = iteration


    def initial_allocation(self, sim, app_name):
            # Deploy sources berdasarkan data user
            for item in self.data["sources"]:
                if item["app"] == app_name:
                    idtopo = item["id_resource"]
                    lambd = item["lambda"]
                    message_name = item["message"]
                    
                    app = sim.apps[app_name]
                    msg = app.get_message(message_name)
                    
                    if msg is None:
                        continue
                    
                    seed = item["id_resource"]*1000+item["lambda"]+self.it
                    dDistribution = exponentialDistribution(name="Exp", lambd=lambd, seed=seed)

                    # Deploy source dengan message yang tepat
                    idsrc = sim.deploy_source(app_name, id_node=idtopo, msg=msg, distribution=dDistribution)



