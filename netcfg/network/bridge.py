import hashlib
import ipaddr
import logging
import os
import subprocess

from . import base

logger = logging.getLogger('netcfg.network.bridge')


class BridgeNetwork(base.Network):
    """
    Bridged network implementation.
    """

    def __repr__(self):
        return '<BridgeNetwork \'%s\'>' % self.name

    def get_type(self):
        """
        Returns the network type.
        """

        return 'bridge'

    def validate(self, netcfg):
        """
        Validates network configuration. Should raise `NetworkConfigurationError` on
        errors.

        :param netcfg: Network configuration
        """

        if netcfg is None:
            netcfg = {}

        # Configure addressing
        addresses = netcfg.get('address', None) or []
        if not isinstance(addresses, list):
            raise base.NetworkConfigurationError('Invalid address configuration.')
        else:
            for address in addresses:
                try:
                    ipaddr.IPNetwork(address)
                except ValueError:
                    raise base.NetworkConfigurationError('Invalid IPv4/IPv6 address: %s' % address)

    def apply(self, container, netcfg=None, detach=False):
        """
        Applies network configuration to a running container.

        :param container: Container instance
        """

        if netcfg is None:
            netcfg = {}

        if detach:
            logger.info("Detaching network configuration '%s' from container '%s'." % (self.name, container.name))
        else:
            logger.info("Applying network configuration '%s' to container '%s'." % (self.name, container.name))

            # Create a bridge if one does not yet exist
            if not os.path.isdir(os.path.join('/sys/class/net', self.name)):
                try:
                    self.execute('ip link add dev %s type bridge' % self.name)
                    self.execute('ip link set %s up' % self.name)
                except subprocess.CalledProcessError:
                    logger.error("Failed to create bridge '%s'!" % self.name)
                    self.execute('ip link delete %s' % self.name, errors=False)
                    return

            with self.network_namespace(container) as netns:
                veth_id = hashlib.md5(container.name + self.name + netns).hexdigest()
                veth_host = 've%s1' % veth_id[:7]
                veth_guest = 've%s2' % veth_id[:7]

                # Create veth interface pair
                try:
                    self.execute(
                        'ip link add name %s mtu 1500 type veth peer name %s mtu 1500' % (
                            veth_host, veth_guest
                        )
                    )
                except subprocess.CalledProcessError:
                    logger.error("Failed to create veth pair for network '%s', container '%s'!" % (
                        self.name, container.name))
                    return

                # Join host interface to the bridge and bring it up
                try:
                    self.execute('ip link set %s master %s' % (veth_host, self.name))
                    self.execute('ip link set %s up' % veth_host)
                except subprocess.CalledProcessError:
                    logger.error("Failed to join host interface '%s' into bridge '%s'!" % (
                        veth_host, self.name))
                    self.execute('ip link delete dev %s' % veth_host, errors=False)
                    return

                # Move guest interface into the container namespace and rename it
                ifname = netcfg.get('ifname', self.name)
                try:
                    self.execute('ip link set %s netns %s' % (veth_guest, netns))
                    self.execute('ip netns exec %s ip link set %s name %s' % (
                        netns, veth_guest, ifname
                    ))
                except subprocess.CalledProcessError:
                    logger.error("Failed to move guest interface '%s' into netns '%s'!" % (
                        veth_guest, netns))
                    self.execute('ip link delete dev %s' % veth_host, errors=False)
                    return

                # When requested, setup IP configuration
                for ip in netcfg.get('address', None) or []:
                    try:
                        self.execute('ip netns exec %s ip addr add %s dev %s' % (netns, ip, ifname))
                    except subprocess.CalledProcessError:
                        logger.warning("Unable to configure IP for guest interface '%s'." % ifname)

                # Bringe the guest device up
                try:
                    self.execute('ip netns exec %s ip link set %s up' % (netns, ifname))
                except subprocess.CalledProcessError:
                    logger.error("Failed to bring guest interface '%s' up!" % ifname)
                    self.execute('ip link delete dev %s' % veth_host, errors=False)
                    return
