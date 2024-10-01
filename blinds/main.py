from machine import Pin, ADC, PWM, reset
import network
import socket
import _thread
from wlan import SSID, PASSWORD
from time import sleep


def set_position_blinds(percent):
    """
    Set the position of the blinds based on the given percentage.

    Args:
        percent (float): The percentage to set the blinds to (0 to 1.0).
    """
    global percentage
    max = 7700 # Maximum duty cycle for the servo (fully open)
    min = 1400 # Minimum duty cycle for the servo (fully closed)

    # Calculate the duty cycle based on the percentage
    duty = ((max - min) * percent) + min
    servo.duty_u16(int(duty)) # Set the duty cycle for the servo
    percentage = percent # Update the global percentage variable


# Initialize PWM for the servo motor connected to Pin 16
servo = PWM(Pin(16))
servo.freq(50) # Set PWM frequency to 50Hz for controlling the servo
servo.duty_u16(0)# Start with blinds closed (duty cycle = 0)

# Thread synchronization lock
spLock = _thread.allocate_lock()
percentage = 0 # Default blinds position (0%)


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
    wlan.ifconfig(('192.168.1.253', '255.255.255.0', '192.168.1.1', '212.230.135.1'))
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


def turn_blinds_percentage(method, parameters):
    """
    Process the 'turn_blinds_percentage' request to set blinds' position.

    Args:
        method (str): The HTTP method used (should be 'POST').
        parameters (str): The request parameters (percentage of blinds position).

    Returns:
        tuple: (status_code, percentage) where status_code is HTTP status and 
               percentage is the updated blinds position.
    """
    if method == 'POST':
        try:
            parameters = parameters.split("&") # Split parameters by "&"
            found = False

            for parameter in parameters:
                key, value = parameter.split("=")
                if key == "percentage":
                    percentage = int(value) # Extract the percentage value
                    print(percentage)
                    found = True
            if found == True:
                if percentage >= 0 and percentage <=100:
                    percentage = percentage/100 # Convert percentage to float (0 to 1)
                    set_position_blinds(percentage) # Set blinds' position
                    status_code = 200 # OK status
                else:
                    status_code = 400 # Bad Request
                    percentage = None
            else:
                status_code = 400 # Bad Request
                percentage = None
        except:
            status_code = 400 # Bad Request (invalid parameters)
            percentage = None
    else:
        status_code = 405 # Method Not Allowed (only POST is allowed)
        percentage = None
    
    return status_code, percentage


def check_status(method, percentage):
    """
    Process the 'check_status' request to return current blinds' position.

    Args:
        method (str): The HTTP method used (should be 'GET').
        percentage (float): The current position of the blinds.

    Returns:
        tuple: (status_code, data_send, data) where status_code is HTTP status, 
               data_send is a flag if data should be sent, and data is the blinds' position.
    """
    if method == 'GET':
        data_send = True
        data = str(percentage*100) # Convert percentage back to a string (0 to 100)
        status_code = 200 # OK status
    else:
        data_send = False
        data = None
        status_code = 405 # Method Not Allowed (only GET is allowed)

    return status_code, data_send, data


def serve(connection):
    """
    Start a web server to handle client requests and control blinds.

    Args:
        connection (socket): The socket connection to handle.
    """
    global percentage
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
        if endpoint == 'turn_blinds_percentage':
            status_code, new_percentage = turn_blinds_percentage(method, parameters)
            if new_percentage != None:
                percentage = new_percentage # Update global percentage
        
        elif endpoint == 'check_status':
            status_code, data_send, data = check_status(method, percentage)
        
        else:
            status_code = 400 # Bad Request for invalid endpoints

        spLock.release() # Release the lock
        
        # Send HTTP status code
        client.send(status_code_set(status_code))
        
        # Send data if needed
        if data_send == True:
            client.send(data)
            data_send = False
        
        client.close() # Close the client connection


def button_task():
    """
    Task to handle button press and adjust blinds position using a potentiometer.
    """

    old_value_button = 0
    potentiometer = ADC(Pin(26)) # Initialize potentiometer on Analog Pin 26
    button = Pin(18, Pin.IN) # Initialize push button on Pin 18 as input

    while True:
        new_value_button = button.value() # Read button state
        
        # Detect button press (from 0 to 1)
        if old_value_button == 0 and new_value_button == 1:
            spLock.acquire()
            percentage = float(potentiometer.read_u16())/65535 # Get percentage from potentiometer
            print(percentage)
            set_position_blinds(percentage) # Set blinds position
            spLock.release()
        old_value_button = new_value_button # Update button state



# Main code execution
try:
    _thread.start_new_thread(button_task, ()) # Start button task in a new thread
    ip = connect() # Connect to the WLAN and get IP address
    connection = open_socket(ip) # Open socket for communication
    serve(connection) # Start serving requests
except KeyboardInterrupt:
    reset() # Reset the device if interrupted





