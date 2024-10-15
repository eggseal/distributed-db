import logging as console
import re
import sys
import requests

def validate_action(action: str) -> bool:
    """
    Validate the action format. The action must start with a '/' and contain only alphanumeric characters or underscores.
    Parameters:
    - action (str): The action string to validate.
    """
    return bool(re.match(r'^/[a-zA-Z]+$', action))

def validate_index(index: str) -> bool:
    """
    Validate the index format. The index must be a valid number.
    Parameters:
    - index (str): The index string to validate.
    """
    return index.isdigit() and int(index) >= 0

def extract_components(cmd: list[str], host: str, port: int):
    """
    Extract and validate components from the command.
    Parameters:
    - cmd (list[str]): The command line arguments.
    - host (str): The host address.
    - port (int): The port number.
    Returns:
    - tuple: A tuple containing the origin, headers, and data.
    """
    try:
        action, index = cmd[:2]
        if not validate_action(action):
            raise ValueError(f"Invalid action format: '{action}'. Must start with '/' and contain only alphanumeric characters or underscores.")
        if not validate_index(index):
            raise ValueError(f"Invalid index: '{index}'. Must be a number.")

        message = " ".join(cmd[2:])
        origin = f'http://{host}:{port}'
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]

        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        data = {'action': action, 'index': index, 'message': message}
        return (origin, headers, data)
    except ValueError as ve:
        console.error(f"Error in input: {ve}")
        raise

def send_command(cmd: list[str], host: str, port: int):
    """
    Send a command to the specified host and port.
    Parameters:
    - cmd (list[str]): The command line arguments.
    - host (str): The host address.
    - port (int): The port number.
    """
    try:
        origin, headers, data = extract_components(cmd, host, port)
        console.info(f'Request to {origin}: {data}')

        if data['action'] == '/write':
            response = requests.post(origin, headers=headers, json=data)
        elif data['action'] == '/read':
            response = requests.get(origin, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported action: {data['action']}")

        response.raise_for_status()  # Raise an error for bad HTTP response
        console.info(f"Response: {response.status_code} - {response.text}")
    except requests.RequestException as req_err:
        console.error(f"Request failed: {req_err}")
    except ValueError as ve:
        console.error(f"Error in action handling: {ve}")
    except Exception as e:
        console.error(f"Unexpected error: {e}")

def main(argc: int, argv: list[str]):
    """
    Main entry point of the application. Parses command line arguments and handles command input.
    Parameters:
    - argc (int): Argument count.
    - argv (list[str]): Argument list.
    - Exits the program with an error message if the arguments are invalid.
    """
    try:
        host_idx = argv.index('-h') + 1
        port_idx = argv.index('-p') + 1
        comm_idx = argv.index('--cmd') + 1
        comm_end = comm_idx + 2
        host, port = argv[host_idx], int(argv[port_idx])
    except (ValueError, IndexError) as err:
        console.error(f'Argument error: {err}. Expected format: python client.py -h <host> -p <port> --cmd /<action> <index> "<message>"')
        sys.exit(1)

    # Request once if the command is on args
    if comm_end <= argc:
        send_command(argv[comm_idx:], host, port)
        return
    # Infinitely ask for the command and send it on a loop otherwise
    while True:
        try:
            cmd = input('cmd: ').split(' ')
            if len(cmd) < 2:
                console.error('Missing args. Expected format: /action index "message"')
                continue
            send_command(cmd, host, port)
        except KeyboardInterrupt:
            console.info("Exiting...")
            break
        except Exception as e:
            console.error(f"Unexpected error: {e}")
            continue

if __name__ == "__main__":
    """
    Examples sys.argv:
    - python client.py -h http://192.168.100.102 -p 8000 --cmd /write 1 "Hey Jhony"
    - python client.py -h localhost -p 5000 --cmd /read 1
    - python client.py -h localhost -p 5000 --cmd
    """
    console.basicConfig(level=console.INFO)
    main(len(sys.argv), sys.argv)
