import requests
import os
import pandas as pd
import time
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the API token from the environment variables
API_TOKEN = os.getenv('FR24_API')

# Check if the API token is available
if not API_TOKEN:
    print("Error: FR24_API token not found in the .env file.")
    exit()

# Define the endpoint URL and headers
BASE_URL = 'https://fr24api.flightradar24.com/api'
headers = {
    'Accept': 'application/json',
    'Accept-Version': 'v1',
    'Authorization': f'Bearer {API_TOKEN}'
}

# Define the bounding box for the Arctic region (north of ~80 degrees latitude)
# Order: north, south, west, east
arctic_bounds = "90.0,80.0,-180.0,180.0"

# Throttling parameters
MAX_RETRIES = 5
BASE_BACKOFF_TIME = 10  # seconds
MAX_BACKOFF_TIME = 60  # maximum backoff time in seconds


def make_api_request(url, params, headers, max_retries=MAX_RETRIES):
    """Make an API request with throttling and exponential backoff"""
    retry_count = 0

    while retry_count <= max_retries:
        try:
            response = requests.get(url=url, params=params, headers=headers)

            # If request was successful, return the response
            if response.status_code == 200:
                return response.json()

            # Handle rate limiting (429 Too Many Requests)
            if response.status_code == 429:
                retry_count += 1

                if retry_count > max_retries:
                    print(f"Maximum retries ({max_retries}) exceeded. Giving up.")
                    break

                # Calculate backoff time with exponential backoff and jitter
                backoff_time = min(MAX_BACKOFF_TIME, BASE_BACKOFF_TIME * (2 ** (retry_count - 1)))
                # Add jitter to prevent synchronized retries
                jitter = random.uniform(0, 0.1 * backoff_time)
                backoff_time += jitter

                print(
                    f"Rate limited (429). Retry {retry_count}/{max_retries}. Waiting for {backoff_time:.2f} seconds...")
                time.sleep(backoff_time)
                continue

            # Handle other errors
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            retry_count += 1

            if retry_count > max_retries:
                print(f"Maximum retries ({max_retries}) exceeded. Giving up.")
                return {"data": []}

            # Use backoff for connection errors too
            backoff_time = min(MAX_BACKOFF_TIME, BASE_BACKOFF_TIME * (2 ** (retry_count - 1)))
            jitter = random.uniform(0, 0.1 * backoff_time)
            backoff_time += jitter

            print(f"Connection error. Retry {retry_count}/{max_retries}. Waiting for {backoff_time:.2f} seconds...")
            time.sleep(backoff_time)

    # If we got here without returning, something went wrong
    return {"data": []}


# Calculate the time range (now to 24 hours ago)
end_time = datetime.now()
start_time = end_time - timedelta(hours=24)

# Initialize a dictionary to store flight paths
# Key: fr24_id, Value: list of position dictionaries
all_flight_paths = {}

# Current timestamp to iterate through the 24-hour period
current_time = start_time

# Process in 15-minute increments
while current_time <= end_time:
    unix_timestamp = int(current_time.timestamp())
    print(f"Fetching flights at: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Prepare request parameters
    params = {
        'bounds': arctic_bounds,
        'timestamp': unix_timestamp,
        'limit': 1000
    }

    # Make the API request with throttling
    result = make_api_request(
        url=BASE_URL + '/historic/flight-positions/light',
        params=params,
        headers=headers
    )

    if 'data' in result:
        flights_data = result.get('data', [])
    else:
        flights_data = []

    if flights_data:
        print(f"Found {len(flights_data)} flights at this timestamp")

        # Process each flight
        for flight in flights_data:
            fr24_id = flight.get('fr24_id')

            if not fr24_id:
                continue  # Skip if no fr24_id

            # Copy the flight data as is
            position_data = flight.copy()

            # Add a standardized timestamp for our records
            position_data['query_time'] = current_time.strftime('%Y-%m-%d %H:%M:%S')
            position_data['query_unix_timestamp'] = unix_timestamp

            # Add to our collection
            if fr24_id not in all_flight_paths:
                all_flight_paths[fr24_id] = []

            all_flight_paths[fr24_id].append(position_data)

    else:
        print(f"No flights found at this timestamp")

    # Move to next 15-minute increment
    current_time += timedelta(minutes=15)

    # Add a small delay between requests to be gentle on the API
    time.sleep(1)

# Convert the collected flight paths to a DataFrame
all_positions = []
for fr24_id, positions in all_flight_paths.items():
    all_positions.extend(positions)

if all_positions:
    flights_df = pd.DataFrame(all_positions)
    print(f"\nSuccessfully captured {len(all_flight_paths)} unique flights with complete paths")
    print(f"Total position records: {len(all_positions)}")
    print(flights_df.head())  # Display the first few rows

    # Save to CSV if needed
    flights_df.to_csv('arctic_flights_last_24h.csv', index=False)
    print("Data saved to 'arctic_flights_last_24h.csv'")

    # Optional: Create a more organized version with one flight per row and path as a list
    flight_summaries = []
    for fr24_id, positions in all_flight_paths.items():
        # Get callsign from first position
        callsign = positions[0].get('callsign')

        # Extract only lat/lon pairs for path
        path = [(p.get('lat'), p.get('lon')) for p in positions]

        # Get min and max timestamps to see time range of flight
        timestamps = [datetime.fromisoformat(p.get('timestamp').replace('Z', '+00:00'))
                      for p in positions if 'timestamp' in p and p.get('timestamp')]
        min_time = min(timestamps) if timestamps else None
        max_time = max(timestamps) if timestamps else None

        flight_summaries.append({
            'fr24_id': fr24_id,
            'callsign': callsign,
            'position_count': len(positions),
            'first_seen': min_time,
            'last_seen': max_time,
            'flight_path': path
        })

    summaries_df = pd.DataFrame(flight_summaries)
    print("\nFlight summaries:")
    print(summaries_df.head())
    summaries_df.to_csv('arctic_flights_summaries.csv', index=False)
else:
    print("\nNo flight data found for the specified period and region.")