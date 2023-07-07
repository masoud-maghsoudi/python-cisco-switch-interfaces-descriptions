# About Script

# Aim

We want to automate the description setting on Cisco access switch user interfaces throughout the network.

# Mechanism:

This script is written in Python using [netmiko](https://github.com/ktbyers/netmiko) and [dnspython](https://github.com/rthalley/dnspython). Using specified **VLANs** for access users and the **switch** IP addresses in [configuration file](./config.yml) it filters out user interfaces and resolves the active IP address on the port via ARP cache of the corresponding **router** specified in the same configuration file and queries an IP reveres lookup from **Local DNS server** declared in configuration file. after formatting the resolved name it will be set on corresponding switch interface.

For disabled interfaces, we set _Disabled by Admin_ description.
For ports with more than active 1 MAC address, in the case that it has no description we set _Multi User_ description, otherwise we would not change the interface description, but list them all in a report file.

---
Github: https://github.com/masoud-maghsoudi

Email: masoud_maghsoudi@yahoo.com