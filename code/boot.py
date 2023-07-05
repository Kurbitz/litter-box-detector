# boot.py -- run on boot-up
import gc  # Garbage collector
import urequests  # Used for HTTP requests
import utime  # Used to get the current time
from machine import reset  # Used to reset the board
import network  # Used to connect to the network
import ntptime  # Used to set the time
from lib import config  # Used to get the network credentials


def connect_to_network():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("connecting to network...")
        sta_if.active(True)
        sta_if.connect(config.SSID, config.WPA2_KEY)
        while not sta_if.isconnected():
            pass
    print("Network config", sta_if.ifconfig())


# TODO: Add a way to check if the network is connected
def http_get_test(url="http://detectportal.firefox.com/") -> bool:
    response = urequests.get(url)
    print(response.text)
    return response.status_code == 200


gc.collect()
connect_to_network()
try:
    if not http_get_test():
        raise OSError
except OSError:
    print("OSError: Failed to connect to the internet")
    reset()

ntptime.settime()
print("Time:", utime.localtime())
