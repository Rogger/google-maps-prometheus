#!/usr/bin/env python3
import os, csv, time
from datetime import datetime
import googlemaps
from prometheus_client import start_http_server, Gauge

# CONFIGURATION
API_KEY = os.getenv("GOOGLE_API_KEY")
B3 = "47.2990727660121, 11.580466819738952" #B3
EKZ_WEST = "47.26437541170264, 11.375077185225967" #EKZ West
TRINS = "47.084296044327736, 11.420916988822645" #Trins
PROMETHEUS_PORT = 8000
REFRESH_INTERVAL = 15 * 60  # 15 minutes

# initialize client
gmaps = googlemaps.Client(key=API_KEY)

# Create a Prometheus Gauge metric to store the commute time
commute_time_seconds_to_b3 = Gauge('commute_time_seconds_to_b3', 'Commute time in seconds from EKZ to B3')
commute_time_seconds_to_ekz = Gauge('commute_time_seconds_to_ekz', 'Commute time in seconds from EKZ to B3')
commute_time_seconds_trins_to_b3 = Gauge('commute_time_seconds_trins_to_b3', 'Commute time in seconds from Trins to B3')
commute_time_seconds_b3_to_trins = Gauge('commute_time_seconds_b3_to_trins', 'Commute time in seconds from B3 to Trins')


def get_travel_time(orig, dest):
    # departure_time="now" makes Google return traffic-aware duration
    resp = gmaps.distance_matrix(orig, dest, mode="driving", departure_time="now")
    elem = resp["rows"][0]["elements"][0]
    if elem["status"] != "OK":
        return None
    # duration_in_traffic is in seconds
    return elem["duration_in_traffic"]["value"]
        
def update_commute_time():
    now = datetime.now()
    secs_b3_to_ekz = get_travel_time(B3, EKZ_WEST)
    if secs_b3_to_ekz is not None:
        commute_time_seconds_to_ekz.set(secs_b3_to_ekz)
        print(f"[{now}] B3 -> EKZ West: {secs_b3_to_ekz} seconds")
    else:
        print(f"[{now}] ERROR: could not fetch travel time")
        
        
    secs_ekz_to_b3 = get_travel_time(EKZ_WEST, B3)
    if secs_ekz_to_b3 is not None:
        commute_time_seconds_to_b3.set(secs_ekz_to_b3)
        print(f"[{now}] EKZ West -> B3: {secs_ekz_to_b3} seconds")
    else:
        print(f"[{now}] ERROR: could not fetch travel time")
        
    secs_trins_to_b3 = get_travel_time(TRINS, B3)
    if secs_trins_to_b3 is not None:
        commute_time_seconds_trins_to_b3.set(secs_trins_to_b3)
        print(f"[{now}] Trins -> B3: {secs_trins_to_b3} seconds")
    else:
        print(f"[{now}] ERROR: could not fetch travel time")
        
    secs_b3_to_trins = get_travel_time(B3, TRINS)
    if secs_b3_to_trins is not None:
        commute_time_seconds_b3_to_trins.set(secs_b3_to_trins)
        print(f"[{now}] B3 -> Trins: {secs_b3_to_trins} seconds")
    else:
        print(f"[{now}] ERROR: could not fetch travel time")

def get_sleep_interval():
    now = datetime.now()
    hour = now.hour
    # Between 20:00 and 06:00 (night hours) - update every hour
    if hour >= 20 or hour < 6:
        return 60 * 60  # 1 hour
    else:
        return 15 * 60  # 15 minutes

if __name__ == "__main__":
    start_http_server(PROMETHEUS_PORT)
    print(f"Prometheus endpoint started on port {PROMETHEUS_PORT}")

    while True:
        update_commute_time()
        sleep_interval = get_sleep_interval()
        time.sleep(sleep_interval)

