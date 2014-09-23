
from . import bridge


def get_class_for_type(network_type):
    """
    Returns a network class based on a given type string.

    :param network_type: Network type string
    """

    if network_type == 'bridge':
        return bridge.BridgeNetwork

    raise ValueError("Network type '%s' is not supported." % network_type)
