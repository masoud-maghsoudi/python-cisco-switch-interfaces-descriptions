"""
   This script deploy configurateions declared in config.yml file on
   Cisco devices dclared in same config.yml file.

   Author: Masoud Maghsoudi
   Github: https://github.com/masoud-maghsoudi
   Email:  masoud_maghsoudi@yahoo.com
"""

import os
import csv
from datetime import datetime
from getpass import getpass
import openpyxl
from netmiko import ConnectHandler
from yaml import safe_load
from dns import resolver, reversename


def load_configuration() -> dict:
    """ Loads interface configuration from config.yml file

    Returns:
        dict: loaded parameters from config file
    """
    params = {}
    file_path = os.path.dirname(__file__)
    with open(os.path.join(file_path, "config.yml"), 'r', encoding="utf-8") as file:
        config = safe_load(file)
        params['router'] = sorted(config['router'])
        params['switch'] = sorted(config['switch_list'])
        params['user_vlan'] = sorted(config['user_vlan'])
        params['dns_servers'] = sorted(config['dns_server_list'])
        return params


def arp_table(device: str) -> dict:
    """arp_table function connects to a router and returns arp table of the router in dictionary

    Args:
        device (str): router IP address

    Returns:
        dict: router arp table
    """
    conn_handler = {
        'device_type': 'cisco_ios',
        'ip': device,
        'username': USERNAME,
        'password': PASSWORD
    }
    result = {}
    net_connect = ConnectHandler(**conn_handler)
    command = net_connect.send_command('show ip arp', use_textfsm=True)
    for entry in command:
        result[entry['mac']] = entry['address']
    return result


def mac_table(device: str, vlans: list) -> list:
    """mac_table function connects to switches and returns switch mac table
    for access ports with vlans defined in configuration file

    Args:
        device (str): switch IP address
        vlans (list): list of user vlans

    Returns:
        list: switch mac table for specified vlans
    """
    access_ports = []
    result = []
    conn_handler = {
        'device_type': 'cisco_ios',
        'ip': device,
        'username': USERNAME,
        'password': PASSWORD
    }
    net_connect = ConnectHandler(**conn_handler)
    command = net_connect.send_command(
        'show interfaces status', use_textfsm=True)
    for item in command:
        if item['vlan'] in vlans:
            access_ports.append(item['port'])
    for vlan in vlans:
        command = net_connect.send_command(
            f'show mac address-table vlan {vlan}', use_textfsm=True)
        for entry in command:
            # with this condition check we try to exclude textfsm parsing errors
            if not isinstance(entry, dict):
                continue
            if entry['vlan'] in vlans and entry['destination_port'][0] in access_ports:
                result.append(
                    (entry['destination_port'][0], entry['destination_address']))
    return sorted(result)


def ip_table(mac_tuple_list: list, arp_dict: dict) -> list:
    """ ip table function uses result of mac table of switches and arp table of
        routers to cunstruct a list consist of port, mac and ip address of
        active devices on the switch port

    Args:
        mac_tuple_list (list): MAC address table
        arp_dict (dict): router ARP table

    Returns:
        list: add IP address to corresponding MAC data
    """
    result = []
    for mac_tuple in mac_tuple_list:
        for key, value in arp_dict.items():
            if mac_tuple[1] == key:
                result.append((*mac_tuple, value))
            else:
                continue
    return result


def dns_query(mac_ip_tuple_list: list, dns_servers: list) -> list:
    """ This function queries the ip addresses and add the stripped form of
        associated "A" record to data structure

    Args:
        mac_ip_tuple_list (list): list of data including IP addresses
        dns_servers (list): nameservers used for DNS query

    Returns:
        list: adds corresponfing name resolved from DNS to data structure
    """
    result = []
    res = resolver.Resolver(configure=True)
    res.nameservers = dns_servers
    q_type = 'PTR'
    for mac_ip_tuple in mac_ip_tuple_list:
        q_addr = reversename.from_address(mac_ip_tuple[2])
        try:
            query = res.resolve(q_addr, q_type)[0]
        # DNS resovler raises an NXDOMAIN exception if could not find any answer for query
        except resolver.NXDOMAIN:
            result.append((*mac_ip_tuple, "DNS Not Found"))
        else:
            query_stripped = str(query).partition('.')[0]
            result.append((*mac_ip_tuple, query_stripped))
    return result


def backup_config(device: str) -> None:
    """ Backup running configuration to file

    Args:
        device (str): Device IP address
    """
    conn_handler = {
        'device_type': 'cisco_ios',
        'ip': device,
        'username': USERNAME,
        'password': PASSWORD
    }
    net_connect = ConnectHandler(**conn_handler)
    directory = "config_backup_files"
    if not os.path.isdir(directory):
        os.makedirs(directory)
    filename = f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-{conn_handler['ip']}-backup.config"
    with open(os.path.join(directory, filename), 'w', encoding="utf-8") as file:
        backup = net_connect.send_command("show running-config")
        file.write(backup)


def write_startup_config(device: str) -> None:
    """ Writes running-config to startup-config

    Args:
        device (str): Device IP address
    """
    conn_handler = {
        'device_type': 'cisco_ios',
        'ip': device,
        'username': USERNAME,
        'password': PASSWORD
    }
    net_connect = ConnectHandler(**conn_handler)
    command = net_connect.send_command('write memory')
    print(command)


def csv_report(data: dict) -> None:
    """ Generates CSV file from proccessed data

    Args:
        data (dict): Interface, MAC, IP, Name data of active users
                     on each switch
    """
    directory = "csv_reports"
    if not os.path.isdir(directory):
        os.makedirs(directory)
    file_name = f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}_switch_ports_report.csv"
    with open(os.path.join(directory, file_name), 'w', encoding="utf-8", newline='') as file:
        header_fields = ['Switch IP', 'Interface',
                         'MAC address', 'IP address', 'User']
        report_writer = csv.writer(file, delimiter=',')
        report_writer.writerow(header_fields)
        for key, values in data.items():
            for value in values:
                row = [key, *value]
                report_writer.writerow(row)
    print("CSV report generated succefully")


def xls_report(data: dict) -> None:
    """ Generates Excel file from proccessed data in Tabs

    Args:
        data (dict): Interface, MAC, IP, Name data of active users
                     on each switch
    """
    header_fields = ['Interface', 'MAC address', 'IP address', 'User']
    directory = "excel_reports"
    if not os.path.isdir(directory):
        os.makedirs(directory)
    file_name = f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}_switch_ports_report.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    workbook.remove(sheet)
    for key, value in data.items():
        sheet = workbook.create_sheet(key)
        sheet.append(header_fields)
        for row_data in value:
            sheet.append(row_data)
    workbook.save(filename=os.path.join(directory, file_name))
    print("Excel report generated succefully")


def write_descriptions(data: dict) -> None:
    """ Writes interface description for switch ports

    Args:
        data (dict): Interface, MAC, IP, Name data of active users
                     on each switch
    """
    for key, value in data.items():
        backup_config(key)
        conn_handler = {
            'device_type': 'cisco_ios',
            'ip': key,
            'username': USERNAME,
            'password': PASSWORD
        }
        net_connect = ConnectHandler(**conn_handler)
        for interface_data in value:
            interface_fullname = f'interface {interface_data[0]}'
            interface_description = f'description {interface_data[3]}'
            command = net_connect.send_config_set(
                [interface_fullname, interface_description])
            print(command)


# MAIN function
if __name__ == "__main__":

    NOTICE = """    ###############################################################################
    #                                                                             #
    #     NOTICE: You are changing the configration on Cisco devices based on     #
    #        configuration and devices declarted in config.yml file               #
    #                                                                             #
    #      Please do not proceed if you do not know the effects of deplying       #
    #                     configurations you are applying.                        #
    #                                                                             #
    ###############################################################################"""
    print(NOTICE)
    REPORT_TYPE = input(
        "Which type of report do you prefer? [xlsx/csv] (Default: xlsx)").strip()
    USERNAME = input("Please enter the username for devices: ").strip()
    PASSWORD = getpass(prompt="Please enter password for devices: ")

    CONFIGS = load_configuration()
    ARP = arp_table(CONFIGS['router'][0])
    switch_data = {}

    for switch in CONFIGS['switch']:
        switch_data[switch] = mac_table(switch, CONFIGS['user_vlan'])

    for switch in CONFIGS['switch']:
        switch_data[switch] = ip_table(switch_data[switch], ARP)

    for switch in CONFIGS['switch']:
        switch_data[switch] = dns_query(
            switch_data[switch], CONFIGS['dns_servers'])

    if REPORT_TYPE[0] in ('c', 'C'):
        csv_report(switch_data)
    else:
        xls_report(switch_data)

    WRTIE_DESC = input(
        "Do you want to configure user descriptions on switch ports? [y/n] (default=no) ").strip()
    if WRTIE_DESC[0] in ('y', 'Y'):
        write_descriptions(switch_data)
        SAVE_PROMPT = input(
            "Are you sure to write configuration on Start-up configuration? [y/n] (default=no) ").strip()
        if SAVE_PROMPT[0] in ('y', 'Y'):
            for switch_ip in switch_data:
                write_startup_config(switch_ip)
        else:
            print("Deplyed configurations has not been written on Startup configuration")
    else:
        pass
