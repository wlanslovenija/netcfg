import contextlib
import os
import subprocess


class NetworkConfigurationError(Exception):
    pass


class Network(object):
    """
    Base class for network implementations.
    """

    def __init__(self, name, destroy_on_stop=False):
        """
        Class constructor.

        :param name: Network name
        """

        self.name = name
        self.destroy_on_stop = destroy_on_stop
        self.containers = set()

    def serialize(self):
        """
        Prepares configuration so it is suitable for serialization into
        JSON (without complex types).
        """

        return {
            'name': self.name,
            'type': self.get_type(),
            'destroy_on_stop': self.destroy_on_stop,
        }

    @classmethod
    def deserialize(cls, data):
        """
        Deserializes configuration from data returned by a previous call to
        `serialize`.

        :param data: Serialized data returned by `serialize`
        """

        return {
            'name': data['name'],
            'destroy_on_stop': data['destroy_on_stop'],
        }

    def attach(self, container):
        """
        Attaches this network to a container. Note that calling this method will
        only update the configuration but will not apply it.

        :param container: Container instance to attach
        """

        self.containers.add(container)

    def detach(self, container):
        """
        Detaches this network from a container. Note that calling this method will
        only update the configuration but will not apply it.

        :param container: Container instance to attach
        """

        self.containers.remove(container)

    def get_type(self):
        """
        Returns the network type.
        """

        raise NotImplementedError

    def validate(self, netcfg):
        """
        Validates network configuration. Should raise `NetworkConfigurationError` on
        errors.

        :param netcfg: Network configuration
        """

        pass

    def apply(self, container, netcfg=None, detach=False):
        """
        Applies network configuration to a running container.

        :param container: Container instance
        """

        raise NotImplementedError

    @contextlib.contextmanager
    def network_namespace(self, container):
        """
        Context manager for network namespaces.
        """

        # Create network namespace
        netns = container.get_netns()
        netns_dir = '/var/run/netns'

        try:
            os.makedirs(netns_dir)
        except OSError:
            pass

        try:
            os.unlink(os.path.join(netns_dir, netns))
        except OSError:
            pass

        try:
            os.symlink(os.path.join('/proc', netns, 'ns/net'), os.path.join(netns_dir, netns))
        except OSError:
            pass

        try:
            yield netns
        finally:
            # Cleanup network namespace
            try:
                os.unlink(os.path.join(netns_dir, netns))
            except OSError:
                pass

    def execute(self, command, errors=True):
        """
        Executes a shell command.

        :param errors: Should an exception be raised on non-zero return code
        """

        try:
            subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError:
            if not errors:
                return

            raise
