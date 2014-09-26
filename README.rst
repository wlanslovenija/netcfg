netcfg
======

Simple network bridge configuration for Docker containers. It is similar in functionality
to the pipework_ script, but has persistent configuration and  can automatically configure
networking when containers are started.

.. _pipework: https://github.com/jpetazzo/pipework

Installation
------------

Netcfg can be installed via pip::

  $ pip install netcfg

Usage
-----

After installation, there are two parts to netcfg. First, a daemon process must be launched
with root privileges and given access to the Docker IPC socket::

  $ netcfg daemon

By default, netcfg stores configuration under `/var/lib/netcfg/netcfg.json`, but this location
may be overriden by using the `--config` command-line argument. After the daemon is running
in the background, one can setup netcfg configuration by calling the `netcfg` script.

First, one should define one or more networks::

  $ netcfg create foo0 bridge

The first argument specifies the network name and the other specifies the network type. Currently
only networks with type `bridge` are supported, but netcfg implements different network types as
modules so new ones could be added.

Then, we can attach networks to one or more containers::

  $ netcfg attach my_container_a foo0 --address 10.42.0.1/24
  $ netcfg attach my_container_b foo0 --address 10.42.0.2/24

Currently only static addressing can be configured (IPv4 and IPv6 are supported) and multiple
addresses may be specified. In case one only wants an address-less L2 veth device, no address
argument should be given.

Existing configuration can be shown by using::

  $ netcfg show
  {
    "containers": {
      "my_container_a": {
        "name": "my_container_a",
        "networks": {
          "foo0": {
            "address": [
              "10.42.0.1/24"
            ]
          }
        }
      },
      "my_container_b": {
        "name": "my_container_b",
        "networks": {
          "foo0": {
            "address": [
              "10.42.0.2/24"
            ]
          }
        }
      }
    },
    "networks": {
      "foo0": {
        "destroy_on_stop": false,
        "name": "foo0",
        "type": "bridge"
      }
    }
  }

If the containers are running, networks will be configured immediately. Otherwise, networks will
be configured when the named containers are started.
