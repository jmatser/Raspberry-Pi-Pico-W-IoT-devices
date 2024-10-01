import network
import socket
from time import sleep
from machine import Pin
import machine
import _thread
from wlan import SSID, PASSWORD

# Initialize LED on Pin 15 and turn it off initially
led = Pin(15, Pin.OUT)
led.off()

# Thread synchronization lock
spLock = _thread.allocate_lock()


def connect():
    """
    Connect the device to the WLAN using the specified SSID and password.

    Returns:
        str: The IP address assigned to the device.
    """
    # Create WLAN object in station mode
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Static IP configuration
    # The first IP that appears will be the one set for microcontroller in the WLAN
    wlan.ifconfig(('192.168.1.254', '255.255.255.0', '192.168.1.1', '212.230.135.1'))
    # Connect to the WLAN using credentials from 'wlan.py'
    wlan.connect(SSID, PASSWORD)
    
    # Wait until connected to the network
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        sleep(1)

    # Print and return the device's IP configuration
    print(wlan.ifconfig())
    ip = wlan.ifconfig()[0]
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
    Generate the HTTP status response based on the given status code.

    Args:
        status_code (int): The status code (e.g., 200, 400, 405).

    Returns:
        str: The corresponding HTTP status response.
    """
    if status_code == 200:
        status_send = "HTTP/1.0 200 OK\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
    elif status_code == 400:
        status_send = "HTTP/1.0 400 Bad Request\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
    elif status_code == 405:
        status_send = "HTTP/1.0 405 Method Not Allowed\r\nContent-type: text/html\r\nAccess-Control-Allow-Origin: *\r\n\r\n"

    return status_send


def request_data_extractor(request):
    """
    Extract the HTTP method, endpoint, and parameters from the incoming request.

    Args:
        request (str): The raw HTTP request string.

    Returns:
        tuple: (method, endpoint, parameters) extracted from the request.
    """
    request = request.split()
    method = request[0][2:] # Extract HTTP method (GET, POST, etc.)      
    request = request[1].split("/")
    request = request[1].split("?")
    endpoint = request[0] # Extract endpoint

    # Extract parameters (if any)
    if len(request) == 1:
        parameters = None
    else:
        parameters = request[1]
    
    return method, endpoint, parameters


def change_status(method, parameters):
    """
    Changes the LED status (on or off) based on the HTTP method and parameters provided.

    Args:
        method (str): The HTTP method (only accepts 'POST').
        parameters (str): The parameters containing the desired LED status ('on' or 'off').

    Returns:
        status_code (int): The HTTP status code (200, 400, or 405).
    """
    if method == 'POST':
        try:
            parameters = parameters.split("&") # Split parameters by "&"
            found = False
            for parameter in parameters:
                key, value = parameter.split("=")
                if key == "status":
                    status = value
                    found = True
            if found == False:
                status = None
                status_code = 400 # Bad Request

            # Change LED status based on 'status' parameter
            if status == 'on':
                led.on()
                status_code = 200 # OK status
            elif status == 'off':
                led.off()
                status_code = 200 # OK status
            else:
                status_code = 400 # Bad Request
        except:
            status_code = 400 # Bad Request
    else:
        status_code = 405 # Method Not Allowed (only POST is allowed)

    return status_code


def toggle(method):
    """
    Toggles the current state of the LED.

    Args:
        method (str): The HTTP method (only accepts 'POST').

    Returns:
        status_code (int): The HTTP status code (200 or 405).
    """
    if method == 'POST':
        led.toggle() # Toggle the LED state
        status_code = 200 # OK status
    else:
        status_code = 405 # Method Not Allowed (only GET is allowed)

    return status_code


def check_status(method):
    """
    Checks the current state of the LED (on or off).

    Args:
        method (str): The HTTP method (only accepts 'GET').

    Returns:
        status_code (int): The HTTP status code (200 or 405).
        data_send (bool): Whether data should be sent in the response.
        data (str): The current LED status (1 for on, 0 for off).
    """
    if method == 'GET':
        status = led.value() # Get the LED status
        data_send = True
        data = str(status)
        status_code = 200 # OK status
    else:
        status_code = 405 # Method Not Allowed (only GET is allowed)
        data_send = False
        data = None
    
    return status_code, data_send, data



def serve(connection):
    """
    Start a web server to handle client requests for controlling the LED.

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
        if endpoint == 'change_status':
            status_code = change_status(method, parameters)

        elif endpoint == 'toggle':
            status_code = toggle(method)
        
        elif endpoint == 'check_status':
            status_code, data_send, data = check_status(method)
            
        else:
            status_code = 400 # Bad Request for invalid endpoints

        spLock.release() # Release the lock

        # Send HTTP status code
        client.send(status_code_set(status_code))
        
        # Send data if needed
        if data_send == True:
            client.send(data)
            data_send = False
        
        client.close()
        

def button_task():
    """
    Task to toggle the LED status using a physical button press.
    """
    global led
    old_value_button = 0
    button = Pin(16, Pin.IN) # Initialize push button on Pin 16 as input
    while True:
        new_value_button = button.value() # Read button state
        
        # Detect button press (from 0 to 1)
        if old_value_button == 0 and new_value_button == 1:
            spLock.acquire()
            led.toggle() # Toggle LED status
            spLock.release()
        
        old_value_button = new_value_button
        

# Main code execution
try:
    _thread.start_new_thread(button_task, ()) # Start button task in a new thread
    ip = connect() # Connect to the WLAN and get IP address
    connection = open_socket(ip) # Open socket for communication
    serve(connection) # Start serving requests
except KeyboardInterrupt:
    machine.reset() # Reset the device if interrupted