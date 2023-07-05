SSID = "CHANGE_ME"  # Network SSID
WPA2_KEY = "CHANGE_ME"  # Network password

MQTT_BROKER = "CHANGE_ME"  # MQTT broker address
MQTT_USER = "CHANGE_ME"  # MQTT username, remove if not needed
MQTT_PASSWORD = "CHANGE_ME"  # MQTT password, remove if not needed

TOPIC_PREFIX = "esp8266"  # MQTT topic prefix, change if needed

# InfluxDB token used for authentication
INFLUXDB_TOKEN = "CHANGE_ME"
# InfluxDB Query API URL with the organization ID
# Should look something like this: http://example.org:8086/api/v2/query?orgID=1a1a1a1a1a1a1a1a
INFLUX_DB_API_QUERY_URL = "CHANGE_ME"

# Time in seconds after which the LED is turned on to warn the user the litter box needs cleaning
LED_WARNING_THRESHOLD = 3600  # Default: 1 hour = 3600 seconds

# Time in seconds between measurements
SLEEP_TIME = 15  # Default: 15 seconds
# Time in milliseconds to detect a long press
LONG_PRESS_TIME = 2000  # Default: 2 seconds = 2000 milliseconds

# Time in milliseconds after which the LCD backlight is turned off
LCD_BACKLIGHT_TIMEOUT = 10000  # Default: 10 seconds = 10000 milliseconds

# Time in seconds after which the cleaning process is stopped automatically
CLEANING_TIMEOUT = 300  # Default: 5 minutes
