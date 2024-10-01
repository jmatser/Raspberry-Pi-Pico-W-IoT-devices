import network
import socket
from time import sleep
from machine import Pin, PWM
import machine
import _thread
from wlan import SSID, PASSWORD


# Initialize the fan control (Pin 14) and set it to OFF
fan = Pin(14, Pin.OUT)
fan.off()

# Initialize PWM for controlling fan speed (Pin 16)
fan_speed = PWM(Pin(16))
fan_speed.freq(60) # Set PWM frequency to 50Hz

# Thread synchronization lock
spLock = _thread.allocate_lock()


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
    wlan.ifconfig(('192.168.1.251', '255.255.255.0', '192.168.1.1', '212.230.135.1'))
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


def change_status_fan(method, parameters):
    """
    Change the status of the fan (on/off) based on the request.

    Args:
        method (str): The HTTP method used (should be 'POST').
        parameters (str): The parameters provided in the request.

    Returns:
        int: The corresponding HTTP status code.
    """
    if method == 'POST':
        try:
            parameters = parameters.split("&") # Split parameters by "&"
            found = False
            for parameter in parameters:
                key, value = parameter.split("=")
                if key == "status":
                    status = value # Extract the status (on/off)
                    found = True
            if found == False:
                status = None
                status_code = 400 # Bad request if status not found
            if status == 'on':
                fan.on() # Turn the fan ON
                status_code = 200 # OK status
            elif status == 'off':
                fan.off() # Turn the fan OFF
                status_code = 200 # OK status
            else:
                status_code = 400 # Bad request for invalid status
        except:
            status_code = 400 # Bad request if an error occurs
    else:
        status_code = 405 # Method not allowed (only POST allowed)

    return status_code


def toggle_fan(method):
    """
    Toggle the fan status (on/off) when requested.

    Args:
        method (str): The HTTP method used (should be 'POST').

    Returns:
        int: The corresponding HTTP status code.
    """
    if method == 'POST':
        fan.toggle() # Toggle fan status
        status_code = 200 # OK status
    else:
        status_code = 405 # Method not allowed (only POST allowed)

    return status_code


def check_status_fan(method):
    """
    Check the current status of the fan and return it.

    Args:
        method (str): The HTTP method used (should be 'GET').

    Returns:
        tuple: (status_code, data_send, data) where status_code is HTTP status, 
               data_send is a flag if data should be sent, and data is the fan status.
    """
    if method == 'GET':
        status = fan.value() # Get fan status (on/off)
        data_send = True
        data = str(status) # Convert fan status to string
        status_code = 200 # OK status
    else:
        status_code = 405 # Method not allowed (only GET allowed)
        data_send = False
        data = None
    
    return status_code, data_send, data
        

def serve(connection):
    """
    Start a web server to handle client requests for controlling the fan.

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
        
        spLock.acquire() # Lock to avoid race conditions

        # Route the request to the appropriate handler based on the endpoint
        if endpoint == 'change_status_fan':
            status_code = change_status_fan(method, parameters)

        elif endpoint == 'toggle_fan':
            status_code = toggle_fan(method)
        
        elif endpoint == 'check_status_fan':
            status_code, data_send, data = check_status_fan(method)

        else:
            status_code = 400 # Bad request for invalid endpoints

        spLock.release() # Release the lock

        # Send HTTP response status
        client.send(status_code_set(status_code))
        
        # Send data if needed
        if data_send == True:
            client.send(data)
            data_send = False
        
        client.close() # Close the client connection
        

def button_task():
    """
    Task to toggle fan status using a physical button press.
    """

    global fan
    old_value_button = 0
    button = Pin(12, Pin.IN) # Initialize push button on Pin 12 as input

    while True:
        new_value_button = button.value() # Read button state
        
        # Detect button press (from 0 to 1)
        if old_value_button == 0 and new_value_button == 1:
            spLock.acquire()
            fan.toggle() # Toggle fan status
            spLock.release()
            print("BUTTON Status: ", fan.value())
            
        old_value_button = new_value_button


# Main code execution
try:
    _thread.start_new_thread(button_task, ()) # Start button task in a new thread
    ip = connect() # Connect to the WLAN and get IP address
    connection = open_socket(ip) # Open socket for communication
    serve(connection) # Start serving requests
except KeyboardInterrupt:
    machine.reset() # Reset the device if interrupted