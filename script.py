#!/usr/bin/env python3

import argparse
from netmiko import ConnectHandler
import time



def connect_to_dasan(hostname, username, password, enable_password, device_type='generic'):
    device = {
        'device_type': device_type,
        'host': hostname,
        'username': username,
        'password': password,
        'secret': enable_password,
        'session_log': 'session_log.txt'
    }
    try:
        connection = ConnectHandler(**device)
        # Timeout z uwagi na długi czas logowania 
        time.sleep(7)
        print("Connected to device")

        for _ in range(2):
            output = connection.send_command_timing("\n", read_timeout=10)
            time.sleep(0.1)

        output = connection.send_command_timing("en", read_timeout=10)
        print(f"Output after 'en' command: {output}")

        if "Password" in output or 'Password:' in output:
            output += connection.send_command_timing(enable_password, read_timeout=10)
            print(f"Output after sending enable password: {output}")
        else:
            output = connection.send_command_timing(enable_password, read_timeout=10)
            print(f"Output after forcing enable password: {output}")

        prompt = connection.find_prompt()
        print(f"Current prompt: {prompt}")

        if not prompt.strip().endswith('#'):
            print("Failed to enter enable mode.")
            connection.disconnect()
            return None

        print("Entered enable mode successfully.")
        command = f"terminal length 0"
        output = connection.send_command(command)
        return connection

    except Exception as e:
        print(f"Failed to connect to {hostname}: {e}")
        return None


def get_onu_model(connection, olt_id):
    command = f"sh onu model-name {olt_id}"
    output = connection.send_command(command)
    model_data = []
    lines = output.splitlines()[3:]
    for line in lines:
        parts = [part.strip() for part in line.split('|') if part.strip()]
        if len(parts) == 3:
            olt, onu, model = parts
            model_data.append({
                'OLT': olt,
                'ONU': onu,
                'Model': model
            })
    return model_data


def get_onu_firmware(connection, olt_id):
    command = f"sh onu firmware version {olt_id}"
    output = connection.send_command(command)
    firmware_data = []
    lines = output.splitlines()[4:]
    for line in lines:
        parts = [part.strip() for part in line.split('|') if part.strip()]
        if len(parts) == 5:
            olt, onu, status, os1, os2 = parts[0], parts[1], parts[2], parts[3], parts[4]
            running_os = 'OS1' if '(D)(R)' in os1 else 'OS2'
            firmware_data.append({
                'OLT': olt,
                'ONU': onu,
                'Status': status,
                'OS1': os1,
                'OS2': os2,
                'RunningOS': running_os
            })
    return firmware_data


def combine_data(model_data, firmware_data, model, current_version):
    combined_data = []
    for model_entry in model_data:
        for firmware_entry in firmware_data:
            if (model_entry['OLT'] == firmware_entry['OLT'] and
                model_entry['ONU'] == firmware_entry['ONU'] and
                model_entry['Model'] == model and
                (current_version in firmware_entry['OS1'] or current_version in firmware_entry['OS2']) and
                firmware_entry['Status'] != 'Commit Complete' and
                firmware_entry['Status'] != 'Download Wait' and
                firmware_entry['Status'] != 'Download Progress'):

                combined_data.append({
                    'OLT': model_entry['OLT'],
                    'ONU': model_entry['ONU'],
                    'Model': model_entry['Model'],
                    'Firmware': firmware_entry['OS1'] if firmware_entry['RunningOS'] == 'OS1' else firmware_entry['OS2'],
                    'RunningOS': firmware_entry['RunningOS']
                })
    return combined_data


def get_free_space(connection):
    command = "q df /dev/shm"
    output = connection.send_command(command)
    lines = output.splitlines()

    if len(lines) > 1:
        parts = lines[1].split()
        if len(parts) >= 4:
            available_kb = int(parts[3])
            available_mb = available_kb / 1024
            return available_mb
    return None


def list_firmware_files(connection):
    command = "sh onu firmware-list"
    output = connection.send_command(command)
    firmware_files = []
    lines = output.splitlines()[2:]
    for line in lines:
        parts = [part.strip() for part in line.split('|') if part.strip()]
        if len(parts) == 2:
            size, filename = parts
            firmware_files.append(filename)
    return firmware_files


def remove_firmware_files(connection, firmware_files):
    # Usuwam tylko dwa pierwsze elementy z listy
    for filename in firmware_files[:2]:
        command = f"remove onu firmware {filename}"
        output = connection.send_command(command)
        print(output)


def download_firmware(connection, ftp_host, file_name, ftp_user, ftp_password):
    cmd_list = [
        "copy ftp onu download",
        ftp_host,
        file_name,
        ftp_user,
        ftp_password,
        "\n"
    ]
    output = connection.send_multiline_timing(cmd_list)
    
    if "bytes download OK" in output and not "downloaded file deleted" in output:
        print("Firmware download completed successfully.")
        return True
    else:
        print("Firmware download failed.")
        return False


def upgrade_firmware(connection, olt_ids, combined_data, firmware_file, ftp_host, ftp_user, ftp_password, current_version, exclude_version=None):
    def version_matches(version, pattern):
        return version.startswith(pattern)

    for olt_id in olt_ids:
        if current_version.lower() == 'all':
            onu_list = [entry for entry in combined_data if entry['OLT'] == str(olt_id) and 
                        (exclude_version is None or entry['Firmware'] != exclude_version)]
        else:
            onu_list = [entry for entry in combined_data if entry['OLT'] == str(olt_id) and 
                        version_matches(entry['Firmware'], current_version) and
                        (exclude_version is None or entry['Firmware'] != exclude_version)]
        
        if not onu_list:
            print(f"No ONUs found for OLT port {olt_id} to upgrade.")
            continue

        # Sprawdzanie dostępności pliku firmware na konkretnym OLT
        firmware_files = list_firmware_files(connection)
        if firmware_file not in firmware_files:
            print(f"Firmware file {firmware_file} not found on OLT. Downloading...")
            if not download_firmware(connection, ftp_host, firmware_file, ftp_user, ftp_password):
                print("Retrying firmware download after removing existing firmware files.")
                remove_firmware_files(connection, firmware_files)
                if not download_firmware(connection, ftp_host, firmware_file, ftp_user, ftp_password):
                    print("Failed to download firmware after removing existing files. Skipping OLT.")
                    continue

        for onu_entry in onu_list:
            onu_id = onu_entry['ONU']
            current_firmware = onu_entry['Firmware']
            print(f"Upgrading ONU {onu_id} from version {current_firmware} to {firmware_file}")
            commands = [
                'conf t',
                'gpon',
                f'gpon-olt {olt_id}',
                f'onu upgrade {onu_id} {firmware_file}',
                'end'
            ]
            output = ''
            for command in commands:
                output += connection.send_command(command, expect_string=r'#', read_timeout=20)
            print(f"Upgrade output for OLT {olt_id}, ONU {onu_id}:\n{output}")


def list_reset_onu(connection, olt_ids):
    for olt_id in olt_ids:
        firmware_data = get_onu_firmware(connection, olt_id)
        onu_to_reset = [onu['ONU'] for onu in firmware_data if onu['Status'] == 'Commit Complete']
        
        if not onu_to_reset:
            print(f"No ONUs with status 'Commit Complete' found for OLT {olt_id}.")
        else:
            print(f"ONUs to reset for OLT {olt_id}: {', '.join(map(str, onu_to_reset))}")


def reset_onu(connection, olt_ids):
    for olt_id in olt_ids:
        firmware_data = get_onu_firmware(connection, olt_id)
        onu_to_reset = [onu['ONU'] for onu in firmware_data if onu['Status'] == 'Commit Complete']

        if not onu_to_reset:
            print(f"No ONUs with status 'Commit Complete' found for OLT {olt_id}.")
            continue

        for onu_id in onu_to_reset:
            commands = [
                'conf t',
                'gpon',
                f'gpon-olt {olt_id}',
                f'onu reset {onu_id}',
                'end'
            ]
            output = ''
            for command in commands:
                output += connection.send_command(command, expect_string=r'#', read_timeout=20)
            print(f"ONU {onu_id} reset command output for OLT {olt_id}:\n{output}")


def list_model_firmware(connection, olt_ids, model):
    for olt_id in olt_ids:
        model_data = get_onu_model(connection, olt_id)
        firmware_data = get_onu_firmware(connection, olt_id)
        for model_entry in model_data:
            if model_entry['Model'] == model:
                for firmware_entry in firmware_data:
                    if model_entry['OLT'] == firmware_entry['OLT'] and model_entry['ONU'] == firmware_entry['ONU']:
                        print(f"OLT: {model_entry['OLT']}, ONU: {model_entry['ONU']}, Model: {model_entry['Model']}, Firmware: {firmware_entry['OS1'] if firmware_entry['RunningOS'] == 'OS1' else firmware_entry['OS2']} (Running on {firmware_entry['RunningOS']})")

def parse_olt_ids(olt_ids_str):
    return [int(olt_id) for olt_id in olt_ids_str.split(',')]


def list_models(connection, olt_ids):
    all_models = set()
    for olt_id in olt_ids:
        model_data = get_onu_model(connection, olt_id)
        for model_entry in model_data:
            all_models.add(model_entry['Model'])
    
    print("Unique Models: ")
    for model in sorted(all_models):
        print(model)


def check_firmware_update_status(firmware_data):
    for entry in firmware_data:
        if "Download Progress" in entry['Status'] or "Download Wait" in entry['Status']:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description='Script to manage DASAN ONU firmware upgrade, reset, and firmware listing')
    
    parser.add_argument('hostname', help='IP address of the OLT')
    parser.add_argument('username', help='Username for OLT login')
    parser.add_argument('password', help='Password for OLT login')
    parser.add_argument('enable_password', help='Enable password for OLT login')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--reset', nargs='?', const='default', help='Reset ONUs with status "Commit Complete"')
    group.add_argument('--list-reset', nargs='?', const='default', help='List ONUs with status "Commit Complete"')
    group.add_argument('--firmware', nargs='?', const='default', help='List firmware versions for a specific model')
    group.add_argument('--upgrade', nargs='+', metavar=('model', 'firmware', 'current_version', 'exclude_version'), 
                       help='Upgrade firmware for specified ONU model. Use "all" for current_version to upgrade all versions. exclude_version is optional.')
    group.add_argument('--list-model', nargs='?', const='default', help='List unique models from specified OLT IDs')

    parser.add_argument('--oltid', help='OLT ID(s) to operate on, separated by commas if multiple')
    parser.add_argument('--model', help='ONU model to operate on')
    parser.add_argument('--ftp-host', help='FTP server host')
    parser.add_argument('--ftp-user', help='FTP server username')
    parser.add_argument('--ftp-password', help='FTP server password')
    
    args = parser.parse_args()

    if args.oltid:
        olt_ids = parse_olt_ids(args.oltid)
    else:
        olt_ids = []

    connection = connect_to_dasan(args.hostname, args.username, args.password, args.enable_password)

    if connection:
        try:
            if args.reset is not None:
                reset_onu(connection, olt_ids)
            elif args.list_reset is not None:
                list_reset_onu(connection, olt_ids)
            elif args.firmware is not None:
                if args.model:
                    list_model_firmware(connection, olt_ids, args.model)
                else:
                    print("Model must be specified with --firmware.")
            elif args.upgrade:
                if not all([args.ftp_host, args.ftp_user, args.ftp_password]):
                    print("FTP host, username, and password must be provided for upgrade.")
                    return
                
                if len(args.upgrade) < 3 or len(args.upgrade) > 4:
                    print("Incorrect number of arguments for --upgrade. Expected 3 or 4 arguments.")
                    return
                
                model, firmware, current_version = args.upgrade[:3]
                exclude_version = args.upgrade[3] if len(args.upgrade) == 4 else None
                
                model_data = []
                firmware_data = []
                
                for olt_id in olt_ids:
                    olt_firmware_data = get_onu_firmware(connection, olt_id)
                    olt_model_data = get_onu_model(connection, olt_id)
                    model_data.extend(olt_model_data)
                    firmware_data.extend(olt_firmware_data)
                
                if not model_data or not firmware_data:
                    print("No data available for the update. All OLTs are being skipped or there is no data.")
                    return
                
                combined_data = combine_data(model_data, firmware_data, model, current_version)
                
                for entry in combined_data:
                    print(f"OLT: {entry['OLT']}, ONU: {entry['ONU']}, Model: {entry['Model']}, Firmware: {entry['Firmware']} (Running on {entry['RunningOS']})")

                if check_firmware_update_status(firmware_data):
                    print("A firmware update from a previous run is currently in progress. Terminating script execution.")
                    return

                upgrade_firmware(connection, olt_ids, combined_data, firmware, args.ftp_host, args.ftp_user, args.ftp_password, current_version, exclude_version)
            
            elif args.list_model is not None:
                list_models(connection, olt_ids)
        
        finally:
            connection.disconnect()

if __name__ == "__main__":
    main()