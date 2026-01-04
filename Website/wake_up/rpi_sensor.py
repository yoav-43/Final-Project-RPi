import requests
import time
import random # Used to simulate sensor data

# -----------------------------------------------------------------
# !!! Update this URL to your site address after deploying to Heroku !!!
SERVER_URL = "https://wakeup-fbc50be37a8b.herokuapp.com/api/data"
# -----------------------------------------------------------------

DEVICE_ID = "rpi_living_room_01"

def get_fatigue_data():
    """
    This function simulates reading data from a sensor.
    In the real world, read EAR/PERCLOS data from the camera here.
    """
    # For example, return a random value between 0 and 1
    return round(random.uniform(0, 1), 2)

def send_data_to_server(fatigue_level):
    """
    Sends data to the cloud server.
    """
    data_to_send = {
        "device_id": DEVICE_ID,
        "fatigue": fatigue_level
    }
    
    print(f"Sending data: {data_to_send}")
    
    try:
        # Connection happens here (via phone hotspot)
        response = requests.post(SERVER_URL, json=data_to_send, timeout=10)
        
        if response.status_code == 201:
            print("Data sent successfully!")
        else:
            print(f"Failed to send data. Server responded with: {response.status_code}")
            print(f"Response body: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("[ERROR] Connection error. Is the hotspot active? Could not connect to server.")
    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out. Server or connection is slow.")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")

# Main loop of the Raspberry Pi
if __name__ == "__main__":
    print(f"Starting sensor client for device: {DEVICE_ID}")
    print(f"Target server: {SERVER_URL}")
    
    while True:
        # 1. Read data
        current_fatigue = get_fatigue_data()
        
        # 2. Send data
        send_data_to_server(current_fatigue)
        
        # 3. Wait 30 seconds
        print("Waiting for 30 seconds...")
        time.sleep(30)