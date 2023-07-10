"""Litterbox monitor program for ESP8266."""
import json
import utime
import urequests as requests
from machine import Pin, unique_id, reset, I2C, Timer
from micropython import const
from dht import DHT11
from umqtt.simple import MQTTClient
from ubinascii import hexlify
from lib import config, i2c_lcd


class SensorState:
    reset_detected: bool = False
    button_1_ticks: int = 0
    motion_last_timestamp: int = 0
    reset_last_timestamp: int = 0
    motion_detected = False


DEBOUNCE_MS = const(300)  # Debounce time for the button in milliseconds
I2C_ADDR = const(
    0x27
)  # I2C address of the LCD display, check with i2c.scan() if this doesn't work

CLIENT_ID = hexlify(unique_id())  # Unique ID of the ESP8266
led = Pin(2, Pin.OUT)  # LED on GPIO2
led.off()  # Turn off the LED

dht = DHT11(Pin(14))  # DHT11 sensor on GPIO14
pir = Pin(12, Pin.IN)  # PIR sensor on GPIO12

button_1 = Pin(13, Pin.IN)  # Button on GPIO13

sdaPin = Pin(4)  # I2C SDA pin
sclPin = Pin(5)  # I2C SCL pin
i2c = I2C(sda=sdaPin, scl=sclPin, freq=10000)  # Initialise I2C
lcd = i2c_lcd.I2cLcd(
    i2c=i2c, i2c_addr=I2C_ADDR, num_lines=2, num_columns=16
)  # Initialise LCD display

backlight_timer = Timer(1)  # Timer for turning off the LCD backlight after a short time
debounce_timer = Timer(2)  # Timer for debouncing the button

# Initialise the MQTT client
mqtt_client = MQTTClient(
    CLIENT_ID,
    config.MQTT_BROKER,
    keepalive=60,
    user=config.MQTT_USER,
    password=config.MQTT_PASSWORD,
)


def main():
    # On startup, display a startup message on the LCD.
    # This serves two purposes:
    # 1. It looks cool
    # 2. The PIR sensor is very sensitive on startup, and will trigger a lot of
    #   false positives. This gives the sensor time to settle.
    display_startup_message()

    # Try to connect to the MQTT broker. If it fails, reset the device.
    try:
        mqtt_client.connect()
    except Exception as ex:
        print("Error connecting to MQTT broker:", ex)
        reset_device()

    # Initialise the state object.
    state = SensorState()
    state.button_1_ticks = utime.ticks_ms()

    # Set up the interrupts for the PIR sensor and the button.
    pir.irq(trigger=Pin.IRQ_FALLING, handler=lambda _: pir_handler(state))
    button_1.irq(
        trigger=Pin.IRQ_RISING, handler=lambda _: button_trigger(state, button_1)
    )

    # Get the last motion and reset timestamps from InfluxDB
    # If the timestamps could not be retrieved, the timestamps are set to 0.
    (
        state.motion_last_timestamp,
        state.reset_last_timestamp,
    ) = get_timestamps_from_influxdb()

    if state.motion_last_timestamp == 0 or state.reset_last_timestamp == 0:
        print("Error getting timestamps from InfluxDB")
        raise OSError

    # Main loop:
    while True:
        # Read the DHT sensor
        dht.measure()

        # Publish the data to MQTT
        mqtt_publish(
            "litterbox",
            {
                "motion_detected": int(state.motion_detected),
                "reset_pressed": int(state.reset_detected),
                "temperature": dht.temperature(),
                "humidity": dht.humidity(),
            },
        )

        now = get_now()
        # We've handled the events, reset the variables to False.
        # Set the timestamps to the current time.
        if state.motion_detected:
            state.motion_last_timestamp = now
            state.motion_detected = False
        if state.reset_detected:
            state.reset_last_timestamp = now
            state.reset_detected = False

        display_status(state)
        # Sleep for a while to keep the CPU usage low.
        utime.sleep(config.SLEEP_TIME)


#
def display_status(state: SensorState):
    now = get_now()
    motion_delta = now - state.motion_last_timestamp
    reset_delta = now - state.reset_last_timestamp

    motion_delta_tuple = utime.gmtime(motion_delta)
    reset_delta_tuple = utime.gmtime(reset_delta)

    print("Motion delta:", motion_delta_tuple)
    print("Reset delta:", reset_delta_tuple)

    reset_delta_hours = reset_delta_tuple[3] + (reset_delta_tuple[2] - 1) * 24
    reset_delta_minutes = reset_delta_tuple[4]

    # If the litterbox has been cleaned more recently than it has been used,
    # display a message saying that the litterbox is clean.
    if motion_delta > reset_delta:
        lcd_print_line(0, "Litterbox clean")
        lcd_print_line(1, f"{reset_delta_hours}h {reset_delta_minutes}m ago")
    # If the litterbox has been used more recently than it has been cleaned,
    # display the time since the litterbox was last used and last cleaned.
    else:
        motion_delta_hours = motion_delta_tuple[3] + (motion_delta_tuple[2] - 1) * 24
        motion_delta_minutes = motion_delta_tuple[4]

        lcd_print_line(0, f"Cat: {motion_delta_hours}h {motion_delta_minutes}m")
        lcd_print_line(1, f"Clean: {reset_delta_hours}h {reset_delta_minutes}m")
        # If the litterbox has not been cleaned for a long time, turn on the LED
        # to warn the user that the litterbox needs to be cleaned.
        if (
            state.reset_last_timestamp < state.motion_last_timestamp
            and motion_delta > config.LED_WARNING_THRESHOLD
        ):
            led.on()
        else:
            led.off()


# Print a line of text to the LCD display.
# If the text is shorter than 16 characters, pad it with spaces.
def lcd_print_line(line: int, text: str):
    lcd.move_to(0, line)
    if len(text) < 16:
        text += " " * (16 - len(text))
    lcd.putstr(text)


# Get the last motion and reset timestamps from InfluxDB
# Returns a tuple of (motion_timestamp, reset_timestamp)
# If the timestamps could not be retrieved, returns (0, 0)
# TODO: Clean up this function
def get_timestamps_from_influxdb() -> tuple[int, int]:
    print("Getting timestamps from InfluxDB...")
    # These queries get the last entries in the database where motion was detected or the reset button was pressed.
    motion_query = 'from(bucket: "iot") |> range(start: -72h) |> filter(fn: (r) => r["mqtt"] == "esp8266/litterbox") |> filter(fn: (r) => r["host"] == "iot") |> filter(fn: (r) => r["_field"] == "motion_detected") |> filter(fn: (r) => r["_value"] == 1) |> last()'
    reset_query = 'from(bucket: "iot") |> range(start: -72h) |> filter(fn: (r) => r["mqtt"] == "esp8266/litterbox") |> filter(fn: (r) => r["host"] == "iot") |> filter(fn: (r) => r["_field"] == "reset_pressed") |> filter(fn: (r) => r["_value"] == 1) |> last()'

    # Headers for the HTTP request
    headers = {
        "Accept": "application/csv",  # We want the response in CSV format
        "Content-type": "application/vnd.flux",  # We are sending a Flux query
        "Authorization": f"Token {config.INFLUXDB_TOKEN}",  # We need to authenticate with InfluxDB
    }

    # Send the HTTP requests
    motion_response = requests.post(
        url=config.INFLUX_DB_API_QUERY_URL,
        headers=headers,
        data=motion_query,
        timeout=5,
    )
    reset_response = requests.post(
        url=config.INFLUX_DB_API_QUERY_URL,
        headers=headers,
        data=reset_query,
        timeout=5,
    )

    # If any of the requests failed, return (0, 0) (please give me monads in micropython)
    if motion_response.status_code != 200 or reset_response.status_code != 200:
        print("Error getting timestamps from InfluxDB:", motion_response.status_code)
        return (0, 0)

    print("Motion response:", motion_response.text)
    print("Reset response:", reset_response.text)

    # parase the csv responses
    motion_timestamp = influxdb_resonse_to_timestamp(motion_response.text)
    reset_timestamp = influxdb_resonse_to_timestamp(reset_response.text)

    print(f"Motion timestamp: {motion_timestamp} ({utime.gmtime(motion_timestamp)})")
    print(f"Reset timestamp: {reset_timestamp} ({utime.gmtime(reset_timestamp)})")

    return (motion_timestamp, reset_timestamp)


# Parse a CSV response from InfluxDB and return the timestamp
# This function is very fragile and will break if the response format changes.
def influxdb_resonse_to_timestamp(response: str) -> int:
    # Split the response into lines and get the first two lines
    response_lines = response.split("\r\n")[0:2]
    # Split the lines on commas and get the value of the "_time" field
    time_string = response_lines[1].split(",")[
        response_lines[0].split(",").index("_time")
    ]
    return time_string_to_timestamp(time_string)


# Convert a time string in the format "2021-05-01T12:00:00Z" to a timestamp
def time_string_to_timestamp(time_string: str) -> int:
    return utime.mktime(
        (
            int(time_string[0:4]),
            int(time_string[5:7]),
            int(time_string[8:10]),
            int(time_string[11:13]),
            int(time_string[14:16]),
            int(time_string[17:19]),
            0,
            0,
        )
    )


# Get the current time as a timestamp
def get_now() -> int:
    return int(utime.time())


# Display a startup message on the LCD display
def display_startup_message():
    lcd.backlight_on()
    lcd.clear()
    utime.sleep(1)
    lcd.putstr("Starting up")
    utime.sleep_ms(400)
    lcd.putstr(".")
    utime.sleep_ms(400)
    lcd.putstr(".")
    utime.sleep_ms(400)
    lcd.putstr(".")
    utime.sleep(3)
    lcd.clear()
    lcd.backlight_off()


# Publish a message to MQTT
# The message is a dictionary that is converted to JSON.
# The topic is prefixed with the TOPIC_PREFIX constant.
# The message is not retained by default.
def mqtt_publish(topic: str, message: dict[str, object], retain=False) -> None:
    payload = json.dumps(message)
    print(
        "Publishing:",
        payload,
        "to topic:",
        config.TOPIC_PREFIX + "/" + topic,
        "retain:",
        retain,
    )
    mqtt_client.publish(
        config.TOPIC_PREFIX + "/" + topic, payload.encode(), retain=retain
    )


# Called when the PIR sensor detects motion.
def pir_handler(state: SensorState):
    state.motion_detected = True
    print("Motion detected")


# Is called when the button is pressed and the IRQ is triggered.
def button_trigger(state: SensorState, button: Pin):
    # To prevent multiple triggers from a single button press, we check if the
    # button was pressed within the last DEBOUNCE_MS milliseconds.
    print(
        f"Button triggered, delta {utime.ticks_ms() - state.button_1_ticks + DEBOUNCE_MS}ms"
    )
    if utime.ticks_ms() < state.button_1_ticks + DEBOUNCE_MS:
        return
    state.button_1_ticks = utime.ticks_ms()

    debounce_timer.init(
        period=100,
        mode=Timer.ONE_SHOT,
        callback=lambda x: button_handler(
            timer=x,
            state=state,
            button=button,
            long_press_time=config.LONG_PRESS_TIME,
            short_press_callback=lambda _: short_press_handler(),
            long_press_callback=long_press_handler,
        ),
    )


# Called when the button is short pressed.
def short_press_handler():
    print("Short press handler called")
    lcd.backlight_on()
    backlight_timer.init(
        period=config.LCD_BACKLIGHT_TIMEOUT,
        mode=Timer.ONE_SHOT,
        callback=lambda _: lcd.backlight_off(),
    )


# Called when the button is long pressed.
def long_press_handler(state: SensorState):
    print("Long press handler called")
    lcd.backlight_on()
    lcd.clear()
    lcd.putstr("Cleaning mode!")
    # Wait for the button to be pressed again or for the timeout to expire.
    for _ in range(config.CLEANING_TIMEOUT):
        if button_1.value() == 1:
            break
        led.on()
        utime.sleep(1)
        led.off()
        utime.sleep(1)
    lcd.clear()
    lcd.putstr("Cleaning done!")
    state.reset_detected = True
    utime.sleep(5)


# Detects long and short button presses and calls the appropriate callback.
# The callback is passed the state object.
# TODO: Make a button class that encapsulates this functionality.
def button_handler(
    timer: Timer,
    state: SensorState,
    button: Pin,
    time_passed: int = 0,
    long_press_time=2000,
    short_press_callback=lambda x: None,
    long_press_callback=lambda x: None,
):
    print("Button handler called, time passed:", time_passed, "ms")
    if time_passed >= long_press_time:
        if button.value() == 0:
            print("Long press registered")
            long_press_callback(state)
            return
    elif button.value() == 0:
        print("Short press registered")
        short_press_callback(state)
        return
    state.button_1_ticks = utime.ticks_ms()
    timer.init(
        period=100,
        mode=Timer.ONE_SHOT,
        callback=lambda x: button_handler(
            timer=x,
            state=state,
            button=button,
            time_passed=time_passed + 100,
            long_press_time=long_press_time,
            short_press_callback=short_press_callback,
            long_press_callback=long_press_callback,
        ),
    )


def reset_device():
    print("Resetting...")
    lcd.clear()
    lcd.putstr("Resetting...")
    utime.sleep(5)
    reset()


# Start of program
if __name__ == "__main__":
    try:
        main()
    except OSError as e:
        print("Error: " + str(e))
        reset_device()
