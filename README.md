# google-maps-prometheus

## Description

This simple Python script calculates the commute time between two geo coordinates using the Google Maps API (called distance matrix API) and exposes the time via Prometheus.

## Requirements
- The API Key for a Google Cloud project with the API "distance matrix" enabled
- Docker

## Build & Run

Build the docker image

    docker build -t commute-tracker:latest .
    
Run the docker image

    
    docker run -d -p 8000:8000 -e GOOGLE_API_KEY="YOU_KEY" --name commute-tracker commute-tracker:latest          
    
    
## Prometheus Metrics

The script exposes the following metrics:

* `commute_time_seconds_to_b3`: Commute time in seconds from EKZ to B3.
* `commute_time_seconds_to_ekz`: Commute time in seconds from B3 to EKZ.
