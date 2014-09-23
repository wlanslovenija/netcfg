import docker
import json
import logging
import os
import threading
import time
import traceback
import zmq

from . import configuration
from .network import base as network_base

logger = logging.getLogger('netcfg.daemon')


class ErrorResponse(Exception):
    pass


class DockerSubscriber(threading.Thread):
    """
    Thread that subscribes to Docker events and forwards them to the
    netcfg main daemon thread.
    """

    def __init__(self, docker_socket_path, netcfg_socket):
        """
        Class constructor.

        :param docker_socket_path: Path to Docker socket
        :param netcfg_socket: ZMQ socket for communication with the main thread
        """

        self.client = docker.Client(
            base_url='unix:/%s' % docker_socket_path,
            version='1.12',
            timeout=10
        )
        self.socket = netcfg_socket
        super(DockerSubscriber, self).__init__()

    def run(self):
        """
        Thread entry point.
        """

        while True:
            try:
                # Forward all events to the main thread
                for event in self.client.events():
                    event = json.loads(event)
                    if event['status'] not in ('start', 'stop'):
                        continue

                    event['container'] = self.client.inspect_container(event['id'])
                    self.socket.send(json.dumps(event))
            except:
                logger.warning("Exception raised in docker subscriber thread:")
                logger.warning(traceback.format_exc())
                time.sleep(1)


class Daemon(object):
    """
    Netcfg daemon.
    """

    def __init__(self, ipc_socket_path, docker_socket_path, config_path):
        """
        Class constructor.

        :param ipc_socket_path: Path to IPC socket
        :param docker_socket_path: Path to Docker socket
        :param config_path: Path to netcfg configuration
        """

        self.context = zmq.Context()
        self.ipc_socket_path = ipc_socket_path
        self.docker_socket_path = docker_socket_path
        self.config_path = config_path
        self.config = configuration.Configuration(docker_socket_path)

    def start(self):
        """
        Starts the netcfg daemon.
        """

        # Prepare the docker subscriber
        socket_ds = self.context.socket(zmq.PAIR)
        socket_nc = self.context.socket(zmq.PAIR)
        socket_ds.bind('inproc://docker-subscriber')
        socket_nc.connect('inproc://docker-subscriber')
        docker_sub = DockerSubscriber(self.docker_socket_path, socket_ds)
        docker_sub.daemon = True
        docker_sub.start()

        # Bind the IPC socket
        socket_rpc = self.context.socket(zmq.REP)
        socket_rpc.bind('ipc://%s' % self.ipc_socket_path)

        # Wait for socket events
        poller = zmq.Poller()
        poller.register(socket_nc, zmq.POLLIN)
        poller.register(socket_rpc, zmq.POLLIN)

        # Load configuration
        try:
            os.makedirs(os.path.dirname(self.config_path))
        except OSError:
            pass

        try:
            with open(self.config_path, 'r') as f:
                self.config.deserialize(json.load(f))
        except IOError:
            self.save_config()

        # Attempt to first apply configuration for all running containers
        logger.info("Applying configuration to all running containers.")
        self.config.apply()

        while True:
            socks = dict(poller.poll())

            if socket_rpc in socks:
                msg = socket_rpc.recv()
                socket_rpc.send(self.process_rpc(msg))

            if socket_nc in socks:
                msg = socket_nc.recv()
                self.process_docker_event(msg)

    def save_config(self):
        """
        Saves current configuration.
        """

        with open(self.config_path, 'w') as f:
            json.dump(self.config.serialize(), f)

    def process_docker_event(self, msg):
        """
        Processes an event from the Docker daemon.

        :param msg: JSON serialized docker event
        """

        msg = json.loads(msg)
        container_id = msg['container']['Name'][1:]
        status = msg['status']

        logger.info("Got docker event '%s' for container '%s'." % (msg['status'], container_id))

        try:
            container = self.config.get_container(container_id)
        except KeyError:
            # Skip containers that have no network configuration in netcfg
            logger.info("No network configuration found for container '%s'." % container_id)
            return

        if status == 'start':
            container.apply()
        elif status == 'stop':
            container.apply(detach=True)

    def process_rpc(self, msg):
        """
        Processes a remote procedure call from netcfg CLI.

        :param msg: JSON serialized RPC message
        :return: JSON serialized RPC response
        """

        try:
            msg = json.loads(msg)
            if 'method' not in msg:
                raise ValueError

            if msg['method'] == 'create_network':
                network_type = msg['type']
                base_cfg = msg.get('config', {})
                base_cfg['name'] = msg['name']
                base_cfg['destroy_on_stop'] = msg['destroy_on_stop']

                try:
                    net, created = self.config.add_network(network_type, **base_cfg)
                except ValueError:
                    raise ErrorResponse('Unknown network type.')

                if created:
                    self.save_config()
                    response = {
                        'success': 'Network created.',
                        'network': net.serialize(),
                    }
                else:
                    response = {
                        'error': 'Network already exists.',
                        'network': net.serialize(),
                    }
            elif msg['method'] == 'attach':
                container_id = msg['container']
                network_id = msg['network']
                net_cfg = msg.get('config', {})

                # Obtain the network
                try:
                    net = self.config.get_network(network_id)
                except KeyError:
                    raise ErrorResponse('Network does not exist.')

                # Obtain or create the container
                container = self.config.add_container(container_id)
                try:
                    container.attach(net, net_cfg)
                    self.save_config()
                except network_base.NetworkConfigurationError, e:
                    raise ErrorResponse('Network configuration error: ' + e.message)

                response = {
                    'success': 'Network attached.',
                }
            elif msg['method'] == 'detach':
                container_id = msg['container']
                network_id = msg['network']

                # Obtain the network
                try:
                    net = self.config.get_network(network_id)
                except KeyError:
                    raise ErrorResponse('Network does not exist.')

                # Obtain the container
                try:
                    container = self.config.get_container(container_id)
                except KeyError:
                    raise ErrorResponse('Container does not exist.')

                try:
                    container.detach(net)
                    self.save_config()
                except KeyError, e:
                    raise ErrorResponse(e.message)

                response = {
                    'success': 'Network detached.',
                }
            elif msg['method'] == 'get_config':
                response = {
                    'config': self.config.serialize(),
                }
            elif msg['method'] == 'set_config':
                if 'config' not in msg or not isinstance(msg['config'], dict):
                    raise ValueError

                self.config = configuration.Configuration.deserialize(msg['config'])
                self.save_config()
            else:
                response = {
                    'error': 'Unknown method \'%s\'.' % msg['method']
                }
        except (ValueError, KeyError):
            response = {
                'error': 'Malformed message received.',
            }
        except ErrorResponse, e:
            response = {
                'error': e.message,
            }

        return json.dumps(response)
