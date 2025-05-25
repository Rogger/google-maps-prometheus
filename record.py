#!/usr/bin/env python3
import os, time, sys
from datetime import datetime, timedelta
import googlemaps
from prometheus_client import start_http_server, Gauge
from pytz import timezone

# CONFIGURATION
API_KEY = os.getenv("GOOGLE_API_KEY")
CET = timezone('Europe/Vienna')
B3 = "47.2990727660121, 11.580466819738952" #B3
EKZ_WEST = "47.26437541170264, 11.375077185225967" #EKZ West
TRINS = "47.084296044327736, 11.420916988822645" #Trins
PROMETHEUS_PORT = 8000

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
    now = datetime.now(CET)
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

def get_next_run_time():
    now = datetime.now(CET)
    
    # Night hours (20:00 - 05:59): Run on the hour (:00)
    if now.hour >= 20 or now.hour < 6:
        # Calculate the next hour. If it's 20:30, next is 21:00. If 05:30, next is 06:00.
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
    # Day hours (06:00 - 19:59): Run every 15 minutes (:00, :15, :30, :45)
    else:        
        # Determine the next 15-minute interval
        current_minute = now.minute
        if current_minute < 15:
            next_run = now.replace(minute=15, second=0, microsecond=0)
        elif current_minute < 30:
            next_run = now.replace(minute=30, second=0, microsecond=0)
        elif current_minute < 45:
            next_run = now.replace(minute=45, second=0, microsecond=0)
        else: # current_minute >= 45, go to next hour's :00
            next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    return next_run

if __name__ == "__main__":
    start_http_server(PROMETHEUS_PORT)
    print(f"Prometheus endpoint started on port {PROMETHEUS_PORT}")

    while True:
        next_scheduled_run = get_next_run_time()
        sleep_duration = (next_scheduled_run - datetime.now(CET)).total_seconds()
            
        if sleep_duration > 0:
            print(f"[{datetime.now(CET)}] Next update scheduled for: {next_scheduled_run.strftime('%Y-%m-%d %H:%M:%S')}. Sleeping for {int(sleep_duration)} seconds.")
            sys.stdout.flush()
            time.sleep(sleep_duration)
        
        # Now it's time to run the update
        update_commute_time()
