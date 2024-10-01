from machine import Pin, ADC, PWM, reset
import network
import socket
import _thread
from wlan import SSID, PASSWORD
from time import sleep
from neopixel import Neopixel # Import the Neopixel module in order to interact with the RGB Matrix


def set_matrix(red, green, blue, brightness):
    """
    Sets the color and brightness of the LED matrix.

    Args:
        red (int): Red color intensity (0-255).
        green (int): Green color intensity (0-255).
        blue (int): Blue color intensity (0-255).
        brightness (int): Brightness value (0-255).
    """
    global last_values

    # If all colors are zero, store the previous values before turning off
    if red == 0 and green == 0 and blue == 0:
        values = matrix.get_pixel(1)
        last_values = [values[0], values[1], values[2], matrix.brightnessvalue]

    # Set the LED matrix with new color and brightness
    matrix.fill((red, green, blue))
    matrix.brightness(brightness)
    matrix.show()


def check_values(red, green, blue, brightness):
    """
    Validates whether the red, green, blue, and brightness values are within the valid range (0-255).

    Args:
        red (int): Red color intensity.
        green (int): Green color intensity.
        blue (int): Blue color intensity.
        brightness (int): Brightness value.

    Returns:
        bool: True if all values are valid, False otherwise.
    """
    # Check if RGB and brightness values are within valid range
    if red > 255 or red < 0 or green > 255 or green < 0 or blue > 255 \
        or blue < 0 or brightness > 255 or brightness < 0:
        return False
    else:
        return True
    

# Define the number of LEDs and the pin connected to the matrix
num_leds = 64
pin_matrix = 0

# Initialize the RGB LED matrix
matrix = Neopixel(num_leds, 0, pin_matrix, "GRB")

# Set a default tuple of values for the init
last_values = [255,0,0,10]

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
    wlan.ifconfig(('192.168.1.252', '255.255.255.0', '192.168.1.1', '212.230.135.1'))
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
    method = request[0][2:]  # Extract the HTTP method (e.g., GET, POST) 
    request = request[1].split("/")
    request = request[1].split("?")
    endpoint = request[0] # Extract the endpoint

    # Extract parameters (if any)
    if len(request) == 1:
        parameters = None
    else:
        parameters = request[1]
    
    return method, endpoint, parameters

def change_color(method, parameters):
    """
    Handles the 'change_color' endpoint to update the LED matrix color and brightness.

    Args:
        method (str): The HTTP method (only accepts 'POST').
        parameters (str): The query parameters containing red, green, blue, and brightness values.

    Returns:
        status_code (int): The HTTP status code (200, 400, or 405).
    """
    if method == "POST":
        try:
            parameters = parameters.split("&") # Split parameters by "&"
            values = {}
            for parameter in parameters:
                key, value = parameter.split("=")
                values[key] = int(value)

            red = values['red']
            green = values['green']
            blue = values['blue']
            brightness = values['brightness']

            # Check if the values are valid
            if check_values(red, green, blue, brightness) == True:
                status_code = 200 # OK status
                set_matrix(red, green, blue, brightness)
            else:
                status_code = 400 # Bad request for invalid status

        except:
            status_code = 400 # Bad request if an error occurs
    else:
        status_code = 405 # Method not allowed (only POST allowed)

    return status_code


def check_status(method):
    """
    Handles the 'check_status' endpoint to return the current color and brightness of the LED matrix.

    Args:
        method (str): The HTTP method (only accepts 'GET').

    Returns:
        status_code (int): The HTTP status code (200 or 405).
        data_send (bool): Whether data should be sent in the response.
        data (str): The JSON-formatted string containing the current RGB values and brightness.
    """
    if method == "GET":
        data_send = True
        values = matrix.get_pixel(1)

        # Format the color and brightness into a JSON string
        data = '{"red": ' + str(values[0]) + ', "green": ' + str(values[1]) + ', "blue": ' + str(values[2]) + ', "brightness": ' + str(matrix.brightnessvalue) + '}'
        status_code = 200 # OK status
    else:
        status_code = 405 # Method not allowed (only POST allowed)
        data_send = False
        data = None
    
    return status_code, data_send, data

 
def serve(connection):
    """
    Start a web server to handle client requests for controlling the RGB Matrix.

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
        if endpoint == 'change_color':
            status_code = change_color(method,parameters)
        
        elif endpoint == 'check_status':
            status_code, data_send, data = check_status(method)
            
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
    Task to toggle the RGB Matrix status between on and off using a physical button press.
    """

    old_value_button = 0
    button = Pin(16, Pin.IN) # Initialize push button on Pin 16 as input

    while True:
        new_value_button = button.value() # Read button state

        # Detect button press (from 0 to 1)
        if old_value_button == 0 and new_value_button == 1:
            spLock.acquire()
            # Get actual values of the matrix, if all 0 it means it is off
            values = matrix.get_pixel(1)
            if values[0] == 0 and values[1] == 0 and values[2] == 0:
                set_matrix(last_values[0], last_values[1], last_values[2], last_values[3]) #T urn on
            else:
                set_matrix(0,0,0,matrix.brightnessvalue) # Turn off
            spLock.release()

        old_value_button = new_value_button


# Main code execution
try:
    _thread.start_new_thread(button_task, ()) # Start button task in a new thread
    ip = connect() # Connect to the WLAN and get IP address
    connection = open_socket(ip) # Open socket for communication
    serve(connection) # Start serving requests
except KeyboardInterrupt:
    reset() # Reset the device if interrupted






