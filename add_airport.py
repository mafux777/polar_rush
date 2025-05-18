import requests
import os
import pandas as pd
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

airports = pd.read_csv('world-airports.csv')
airports = airports.loc[(airports.icao_code.notna())&(airports.iata_code.notna())].set_index('icao_code')
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

# Throttling parameters
MAX_RETRIES = 5
BASE_BACKOFF_TIME = 10  # seconds
MAX_BACKOFF_TIME = 60  # maximum backoff time in seconds
BATCH_SIZE = 15  # Process 15 flight IDs in a single API call


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
            print(f"API error: {response.status_code} - {response.text}")
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

my_flights = []

def get_flight_details_batch(flight_ids):
    """Get origin and destination airports for a batch of flight IDs"""
    # Join flight IDs with commas for the API
    flight_ids_str = ",".join(flight_ids)

    params = {
        'flight_ids': flight_ids_str,
    }

    # Make the API request
    result = make_api_request(
        url=BASE_URL + '/flight-summary/light',
        params=params,
        headers=headers
    )

    # Process the response
    flights_data = result.get('data', [])

    for flight in flights_data:
        flight_id =flight['fr24_id']
        if((flight.get('orig_icao')) and (flight.get('dest_icao'))):
            # Extract details
            try:
                details = {
                    'id': flight_id,
                    'callsign': flight['callsign'],
                    'origin': flight['orig_icao'],
                    'ori_iata': airports.loc[flight['orig_icao'], 'iata_code'],
                    'dest_iata': airports.loc[flight['dest_icao'], 'iata_code'],
                    'destination': flight['dest_icao'],
                }
                my_flights.append(details)
            except:
                print(f"Flight details error: {flight}")


def main():
    # Load the flight summaries
    print("Loading flight summaries from arctic_flights_summaries.csv...")
    try:
        summaries_df = pd.read_csv('arctic_flights_summaries.csv')
        print(f"Loaded {len(summaries_df)} flight summaries.")
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return

    # Get unique flight IDs, removing any None/NaN values
    unique_flight_ids = summaries_df['fr24_id'].dropna().unique().tolist()
    print(f"Found {len(unique_flight_ids)} unique flight IDs to process.")

    # Process flight IDs in batches
    total_batches = (len(unique_flight_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min((batch_idx + 1) * BATCH_SIZE, len(unique_flight_ids))
        batch_flight_ids = unique_flight_ids[start_idx:end_idx]

        print(f"Processing batch {batch_idx + 1}/{total_batches} with {len(batch_flight_ids)} flight IDs...")
        print(f"Flight IDs in this batch: {', '.join(batch_flight_ids)}")

        # Get details for all flight IDs in the batch with a single API call
        get_flight_details_batch(batch_flight_ids)

        # Add a delay between batches to be kind to the API
        if batch_idx < total_batches - 1:
            sleep_time = random.uniform(5, 6)
            print(f"Batch complete. Waiting {sleep_time:.2f} seconds before next batch...")
            time.sleep(sleep_time)

    # Convert flight details to DataFrame
    if my_flights:
        details_df = pd.DataFrame(my_flights)
        print(f"Retrieved details for {len(details_df)} flight IDs.")

        # Merge with original data
        # We'll use a left join to keep all original flight data
        enhanced_df = pd.merge(
            summaries_df,
            details_df,
            on='callsign',
            how='left'
        )

        # Save the enhanced data
        output_file = 'arctic_flights_enhanced.csv'
        enhanced_df.to_csv(output_file, index=False)
        print(f"Enhanced data saved to {output_file}")

        # Display a preview
        print("\nPreview of enhanced data:")
        preview_columns = ['flight_id', 'callsign', 'origin', 'destination', 'aircraft_type', 'airline',
                           'position_count']
        print(enhanced_df[preview_columns].head())
    else:
        print("No flight details were retrieved.")


if __name__ == "__main__":
    main()