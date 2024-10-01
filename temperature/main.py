import network
import socket
from time import sleep
from machine import Pin
import machine
from wlan import SSID, PASSWORD
from dht import DHT11 # Import the DHT11 module in order to interact with the DHT11 sensor


# Set up the DHT11 sensor on Pin 26
dht_pin = Pin(26, Pin.OUT, Pin.PULL_DOWN)
dht_sensor = DHT11(dht_pin)


def connect():
    """
    Connect the device to a WLAN using the provided SSID and password.

    Returns:
        str: The IP address assigned to the device.
    """
    # Create WLAN object in station mode
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Static IP configuration
    # The first IP that appears will be the one set for microcontroller in the WLAN
    wlan.ifconfig(('192.168.1.250', '255.255.255.0', '192.168.1.1', '212.230.135.1'))
    # Connect to the WLAN using credentials from 'wlan.py'
    wlan.connect(SSID, PASSWORD)

    # Wait until connected
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        sleep(1)
    print(wlan.ifconfig())
    ip = wlan.ifconfig()[0] # Get the assigned IP address

    return ip
    

def open_socket(ip):
    """
    Open a socket for communication.

    Args:
        ip (str): The IP address of the device.

    Returns:
        socket: The opened socket for communication.
    """
    address = (ip, 80) # IP address and port for the socket
    connection = socket.socket() # Create a new socket
    connection.bind(address) # Bind the socket to the address
    connection.listen(1) # Listen for incoming connections

    return connection


def status_code_set(status_code):
    """
    Generate HTTP status response based on the given status code.

    Args:
        status_code (int): The HTTP status code (200, 400, 405, 500).

    Returns:
        str: The corresponding HTTP status response.
    """
    if status_code == 200:
        status_send = "HTTP/1.0 200 OK\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
    elif status_code == 400:
        status_send = "HTTP/1.0 400 Bad Request\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
    elif status_code == 405:
        status_send = "HTTP/1.0 405 Method Not Allowed\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
    elif status_code == 500:
        status_send = "HTTP/1.0 500 Internal Server Error\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"

    return status_send


def request_data_extractor(request):
    """
    Extract the HTTP method, endpoint, and parameters from the request.

    Args:
        request (str): The raw HTTP request string.

    Returns:
        tuple: (method, endpoint, parameters) extracted from the request.
    """
    request = request.split()
    method = request[0][2:] # Extract the HTTP method (e.g., GET, POST)    
    request = request[1].split("/")
    request = request[1].split("?")
    endpoint = request[0] # Extract the endpoint

    # Extract parameters (if any)
    if len(request) == 1:
        parameters = None
    else:
        parameters = request[1]
    
    return method, endpoint, parameters


def check_dht(method):
    """
    Handles the 'check_dht' endpoint, which returns the temperature and humidity data from the DHT11 sensor.

    Args:
        method (str): The HTTP method (only accepts 'GET').

    Returns:
        status_code (int): The HTTP status code (200, 405, 500).
        data_send (bool): Flag indicating whether to send the sensor data in the response.
        data (str): The JSON-formatted string containing temperature and humidity data, if successful.
    """
    if method == 'GET':
        try:
            # Format the temperature and humidity data into a JSON string
            data = '{"temperature": ' + str(dht_sensor.temperature) + ', "humidity": ' + str(dht_sensor.humidity) + '}'
            data_send = True
            status_code = 200 # OK status
        except Exception as e:
            print(e) # Print error message if the sensor reading fails
            data_send = False
            status_code = 500 # Internal Server Error if the sensor fails
            data = None
    else:
        status_code = 405 # Method not allowed (only GET allowed)
        data_send = False
        data = None
    
    return status_code, data_send, data
        

def serve(connection):
    """
    Start a web server to handle client requests for obtaining the status of the sensor.

    Args:
        connection (socket): The socket connection to handle.
    """
    data_send = False
    while True:
        client = connection.accept()[0] # Accept a client connection
        request = client.recv(1024) # Receive the request
        request = str(request)
        print(request)
        try:
            method, endpoint, parameters = request_data_extractor(request) # Extract request details
        except:
            endpoint = None    
        
        # Route the request to the appropriate handler based on the endpoint
        if endpoint == 'check_dht':
            status_code, data_send, data = check_dht(method)

        else:
            status_code = 400 # Bad request for invalid endpoints

        # Send HTTP response status
        client.send(status_code_set(status_code))
        
        # Send data if needed
        if data_send == True:
            client.send(data)
            data_send = False
        
        client.close()  


# Main code execution
try:
    ip = connect() # Connect to the WLAN and get IP address
    connection = open_socket(ip) # Open socket for communication
    serve(connection) # Start serving requests
except KeyboardInterrupt:
    machine.reset() # Reset the device if interrupted

