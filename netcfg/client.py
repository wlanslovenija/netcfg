import json
import zmq


class Client(object):
    """
    Netcfg client API.
    """

    def __init__(self, ipc_socket_path):
        """
        Class constructor.

        :param socket: Path to netcfg socket
        """

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect('ipc://%s' % ipc_socket_path)

    def _method(self, method, **kwargs):
        """
        Helper method for calling netcfg RPC methods.
        """

        request = kwargs
        request['method'] = method
        self.socket.send(json.dumps(request))
        return json.loads(self.socket.recv())

    def get_config(self):
        """
        Returns the current netcfg configuration.
        """

        return self._method('get_config')

    def set_config(self, config):
        """
        Overwrites the current netcfg configuration.
        """

        return self._method('set_config', config=config)

    def flush(self):
        """
        Clear network configuration.
        """

        return self._method('flush')

    def create_network(self, type, name, destroy_on_stop=False, **kwargs):
        """
        Creates a new network.
        """

        return self._method(
            'create_network',
            type=type,
            name=name,
            destroy_on_stop=destroy_on_stop,
            config=kwargs,
        )

    def attach(self, container, network, **kwargs):
        """
        Attaches a network to a container.

        :param container: Container identifier
        :param network: Network identifier
        """

        return self._method(
            'attach',
            container=container,
            network=network,
            config=kwargs,
        )

    def detach(self, container, network):
        """
        Detaches a network from a container.

        :param container: Container identifier
        :param network: Network identifier
        """

        return self._method(
            'detach',
            container=container,
            network=network,
        )
