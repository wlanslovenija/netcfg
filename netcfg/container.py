

class Container(object):
    """
    Container settings descriptor.
    """

    def __init__(self, config, name):
        """
        Class constructor.

        :param config: Configuration instance
        :param name: Container name
        """

        self.config = config
        self.name = name
        self.networks = {}

    @property
    def is_running(self):
        """
        Checkes whether this Docker container is currently running.
        """

        try:
            cfg = self.config.get_docker_client().inspect_container(self.name)
            return cfg['State']['Running']
        except:
            # TODO: We should not catch all the exceptions here
            return False

    def get_netns(self):
        """
        Returns the network namespace (PID) of this container. If the container is
        not running, returns None.
        """

        try:
            cfg = self.config.get_docker_client().inspect_container(self.name)
            if not cfg['State']['Running']:
                return None

            return str(cfg['State']['Pid'])
        except:
            # TODO: We should not catch all the exceptions here
            return None

    def serialize(self):
        """
        Prepares configuration so it is suitable for serialization into
        JSON (without complex types).
        """

        return {
            'name': self.name,
            'networks': {net.name: cfg for net, cfg in self.networks.items()},
        }

    @classmethod
    def deserialize(cls, data, cfg):
        """
        Deserializes configuration from data returned by a previous call to
        `serialize`.

        :param data: Serialized data returned by `serialize`
        :return: Deserialized Container instance
        """

        container = Container(cfg, data['name'])
        for netname, netcfg in data['networks'].items():
            try:
                net = cfg.networks[netname]
            except KeyError:
                raise KeyError("Deserialization of container '%s' failed." % container.name)

            container.attach(net, netcfg)

        return container

    def attach(self, network, netcfg):
        """
        Attaches a network to this container. In case the container is running,
        the configuration is also applied.

        :param network: Network to attach
        :param netcfg: Network-specific configuration
        """

        network.validate(netcfg)
        self.networks[network] = netcfg
        network.attach(self)

        if self.is_running:
            network.apply(self, netcfg)

    def detach(self, network):
        """
        Detaches a network from this container. In case the container is running,
        the configuration is also applied.

        :param network: Network to detach
        """

        if network not in self.networks:
            raise KeyError("Container '%s' is not attached to network '%s'!" % (self.name, network.name))

        network.detach(self)
        netcfg = self.networks[network]
        del self.networks[network]

        if self.is_running:
            network.apply(self, netcfg, detach=True)

    def apply(self, detach=False):
        """
        Applies container configuration.
        """

        for network, netcfg in self.networks.items():
            network.apply(self, netcfg, detach=detach)
