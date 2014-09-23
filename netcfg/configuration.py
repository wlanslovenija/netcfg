import docker

from . import container
from . import network


class Configuration(object):
    """
    Netcfg configuration store.
    """

    def __init__(self, docker_socket_path):
        """
        Class constructor.

        :param docker_socket_path: Path to Docker socket
        """

        self.docker_client = docker.Client(
            base_url='unix:/%s' % docker_socket_path,
            version='1.12',
            timeout=10
        )
        self.networks = {}
        self.containers = {}

    def get_docker_client(self):
        """
        Returns an instance of the Docker client that can be used to invoke
        Docker RPCs.
        """

        return self.docker_client

    def add_network(self, network_type, **kwargs):
        """
        Creates a new network or returns an existing one if a network with
        the same name already exists.

        :param network_type: Network type
        :return: Network instance of the specific type
        """

        net_cls = network.get_class_for_type(network_type)
        net = net_cls(**kwargs)
        if net.name in self.networks:
            return self.networks[net.name], False

        self.networks[net.name] = net
        return net, True

    def get_network(self, name):
        """
        Returns a network instance by its name.
        """

        return self.networks[name]

    def add_container(self, name):
        """
        Creates a new container or returns an existing one if a container with
        the same name already exists.

        :param name: Container name
        :return: Container instance
        """

        if name in self.containers:
            return self.containers[name]

        cont = container.Container(self, name)
        self.containers[name] = cont
        return cont

    def get_container(self, name):
        """
        Returns a container instance by its name.
        """

        return self.containers[name]

    def apply(self):
        """
        Applies complete configuration to running containers.
        """

        for ctr in self.containers.values():
            if ctr.is_running:
                ctr.apply()

    def serialize(self):
        """
        Prepares configuration so it is suitable for serialization into
        JSON (without complex types).
        """

        return {
            'networks': {k: v.serialize() for k, v in self.networks.items()},
            'containers': {k: v.serialize() for k, v in self.containers.items()},
        }

    def deserialize(self, data):
        """
        Deserializes configuration from data returned by a previous call to
        `serialize` and stores it in the current configuration object.

        :param data: Serialized data returned by `serialize`
        """

        self.networks = {}
        self.containers = {}
        for netname, netcfg in data['networks'].items():
            net_cls = network.get_class_for_type(netcfg['type'])
            self.networks[netname] = net_cls(**net_cls.deserialize(netcfg))

        self.containers = {k: container.Container.deserialize(v, self) for k, v in data['containers'].items()}
