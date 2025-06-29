import random

class Service:
    def __init__(self, name, ram, ipt, packet_size):
        self.name = name
        self.ram = ram
        self.ipt = ipt
        self.packet_size = packet_size

    def to_dict(self):
        return {
            "name": self.name,
            "RAM": self.ram,
            "IPT": self.ipt,
            "packet_size": self.packet_size
        }

class Application:
    def __init__(self, deadline, services):
        self.deadline = deadline
        self.services = services  # list of Service

    def to_dict_list(self):
        return [svc.to_dict() for svc in self.services]

def generate_random_application():
    deadline = random.randint(2600, 6600)
    num_services = random.randint(2, 10)
    services = []
    for i in range(num_services):
        ram = random.randint(1, 6)
        ipt = random.randint(1, 6)
        packet_size = random.randint(1_500_000, 4_500_000)
        services.append(Service(f"Service_{i+1}", ram, ipt, packet_size))
    return Application(deadline, services)