import ssl
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# SSL workaround for environments with certificate issues
ssl._create_default_https_context = ssl._create_unverified_context

# Load the flight data
flights_df = pd.read_csv('arctic_flights_enhanced.csv')
flights_df = flights_df.loc[flights_df.callsign.notna()]

# Load airport data
airport_data = None
if os.path.exists('world-airports.csv'):
    try:
        airport_data = pd.read_csv('world-airports.csv')
        print(f"Loaded {len(airport_data)} airports from world-airports.csv")

        # Create lookup dictionary for IATA codes
        iata_lookup = {}
        for _, row in airport_data.iterrows():
            if pd.notna(row['iata_code']) and row['iata_code']:
                iata_lookup[row['iata_code']] = row
    except Exception as e:
        print(f"Could not load world-airports.csv: {e}")
else:
    print("Warning: world-airports.csv not found. Airport information will not be available.")


# Function to format airport name given an IATA code
def format_airport_name(iata_code):
    if not iata_code or pd.isna(iata_code) or airport_data is None:
        return "Unknown"

    # Try to find the airport by IATA code
    if iata_code in iata_lookup:
        airport = iata_lookup[iata_code]
        municipality = airport['municipality'] if pd.notna(airport['municipality']) else ''

        if municipality:
            return f"{municipality} ({iata_code})"
        else:
            airport_name = airport['name'] if pd.notna(airport['name']) else ''
            if airport_name:
                return f"{airport_name} ({iata_code})"

    # Return the code if we couldn't find/format a proper name
    return iata_code


# Convert flight paths from string to list of (lat, lon) tuples
def parse_path(path_str):
    path_str = path_str.strip('[]')
    coordinates = []
    if not path_str:
        return coordinates
    pairs = path_str.split('), (')
    for pair in pairs:
        pair = pair.replace('(', '').replace(')', '')
        lat, lon = pair.split(',')
        coordinates.append((float(lat), float(lon)))
    return coordinates


flights_df['parsed_path'] = flights_df['flight_path'].apply(parse_path)


# Count data points above 80° latitude for each flight
def count_points_above_80(path):
    return sum(1 for lat, lon in path if lat > 80)


flights_df['points_above_80'] = flights_df['parsed_path'].apply(count_points_above_80)

# Filter flights to only show those with at least 5 data points above 80° latitude
high_arctic_flights = flights_df[flights_df['points_above_80'] >= 5]

print(f"Total flights: {len(flights_df)}")
print(f"Flights with 5+ points above 80°N: {len(high_arctic_flights)}")


# Add circular polar boundary
def add_circular_boundary(ax):
    theta = np.linspace(0, 2 * np.pi, 100)
    center, radius = [0.5, 0.5], 0.75
    verts = np.vstack([np.sin(theta), np.cos(theta)]).T
    circle = mpath.Path(verts * radius + center)
    ax.set_boundary(circle, transform=ax.transAxes)


# Set up figure and projection
fig = plt.figure(figsize=(15, 15))
ax = plt.axes(projection=ccrs.NorthPolarStereo(central_longitude=0))
ax.set_extent([-180, 180, 70, 90], ccrs.PlateCarree())
add_circular_boundary(ax)

# Map features
ax.add_feature(cfeature.COASTLINE.with_scale('110m'))
ax.add_feature(cfeature.BORDERS.with_scale('110m'), linestyle=':')
ax.add_feature(cfeature.LAND.with_scale('110m'), facecolor='lightgray', alpha=0.5)
ax.add_feature(cfeature.OCEAN.with_scale('110m'), facecolor='lightblue', alpha=0.5)

# Add meridians (longitude lines) and parallels (latitude circles)
gl = ax.gridlines(crs=ccrs.PlateCarree(),
                  draw_labels=False,
                  linewidth=1,
                  color='gray',
                  alpha=0.5,
                  linestyle='--')

# Specify which lines you want: meridians and/or parallels
gl.xlocator = plt.MultipleLocator(30)  # meridians every 30°
gl.ylocator = plt.FixedLocator([70, 75, 80, 85])  # parallels

# Add latitude markers
for lat in [65, 70, 75, 80, 85]:
    ax.text(180, lat, f'{lat}°N', transform=ccrs.PlateCarree(),
            ha='center', va='center')
    circle = plt.Circle((0, 0), radius=90 - lat,
                        transform=ccrs.PlateCarree(),
                        fill=False, linestyle='--', color='gray', alpha=0.5)
    ax.add_patch(circle)

# Airline color mapping
airlines = {}
flight_origin_dest = {}  # Store origin and destination for each flight

# Process each flight to get origin/destination airports
for _, flight in high_arctic_flights.iterrows():
    callsign = flight['callsign']
    path = flight['parsed_path']

    if len(path) > 3:
        if callsign and len(callsign) >= 3:
            airline_code = callsign[:3]
            if airline_code not in airlines:
                airlines[airline_code] = len(airlines)

            # Get origin and destination IATA codes
            origin_iata = flight.get('ori_iata', None)
            dest_iata = flight.get('dest_iata', None)

            # Format the airport names
            origin_name = format_airport_name(origin_iata)
            dest_name = format_airport_name(dest_iata)

            # Store the origin and destination info
            flight_origin_dest[callsign] = (origin_name, dest_name)

cmap = plt.cm.tab20
colors = [cmap(i % 20) for i in range(len(airlines))]

# Plot flights
for _, flight in high_arctic_flights.iterrows():
    path = flight['parsed_path']
    if len(path) > 3:
        lats, lons = zip(*path)
        callsign = flight['callsign']
        if callsign and len(callsign) >= 3:
            airline_code = callsign[:3]
            color = colors[airlines[airline_code]]
        else:
            color = 'gray'
        line_width = min(max(flight['position_count'] / 2, 1), 4)

        ax.plot(lons, lats, transform=ccrs.PlateCarree(),
                linewidth=line_width, alpha=0.7, color=color)

        # Entry/exit points and labels
        ax.plot(lons[0], lats[0], 'go', markersize=4, transform=ccrs.PlateCarree())
        ax.plot(lons[-1], lats[-1], 'ro', markersize=4, transform=ccrs.PlateCarree())
        ax.text(lons[0], lats[0], callsign, transform=ccrs.PlateCarree(),
                fontsize=6, color='green', ha='right', va='bottom', alpha=0.8)
        ax.text(lons[-1], lats[-1], callsign, transform=ccrs.PlateCarree(),
                fontsize=6, color='red', ha='left', va='top', alpha=0.8)

# Add title
plt.suptitle('High Arctic Flight Paths (80°N+, May 17–18, 2025)', fontsize=18, y=0.95)

# Create custom legend for airlines with origin/destination info
from matplotlib.lines import Line2D

# Format origin/destination information
legend_elements = []
for airline, idx in airlines.items():
    # Find flights for this airline
    airline_flights = []
    for callsign, (origin_name, dest_name) in flight_origin_dest.items():
        if callsign[:3] == airline:
            airline_flights.append(f"{callsign}: {origin_name} → {dest_name}")

    # Add to legend with flight info
    flight_info = "\n".join(airline_flights[:5])  # Limit to first 5 flights if too many
    if len(airline_flights) > 5:
        flight_info += f"\n+ {len(airline_flights) - 5} more flights"

    legend_elements.append(Line2D([0], [0], color=colors[idx], lw=2,
                                  label=f"{airline} ({len(airline_flights)} flights)\n{flight_info}"))

# Position the legend in the upper right
ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.1, 1.05),
          title="Airlines (80°N+ Crossings)", frameon=True, framealpha=0.8)

# Explanatory text
plt.figtext(0.15, 0.05, 'Green dots: Entry points', fontsize=10, color='green')
plt.figtext(0.45, 0.05, 'Red dots: Exit points', fontsize=10, color='red')
plt.figtext(0.75, 0.05, 'Only showing flights with 5+ data points above 80°N', fontsize=10)

# Major northern airports with coordinates and labels
airports = {
    'Toronto (YYZ)': (43.6777, -79.6248),
    'Vancouver (YVR)': (49.1951, -123.1800),
    'Oslo (OSL)': (60.1976, 11.1004),
    'Saint Petersburg (LED)': (59.8003, 30.2625),
    'Reykjavík (KEF)': (63.9850, -22.6056),
    'Anchorage (ANC)': (61.1743, -149.9983),
    'Murmansk (MMK)': (68.7817, 32.7508),
    'Tromsø (TOS)': (69.6833, 18.9189),
    'Magadan (GDX)': (59.9100, 150.7200),
    'Yellowknife (YZF)': (62.4628, -114.4403),
    'Inuvik (YEV)': (68.3042, -133.4833),
    'Iqaluit (YFB)': (63.7564, -68.5558),
    'Resolute Bay (YRB)': (74.7169, -94.9694),
    'Longyearbyen (LYR)': (78.2461, 15.4656),
    'Petropavlovsk-Kamchatsky (PKC)': (53.1709, 158.4536),
    'New York (JFK)': (40.6413, -73.7781),
    'Tokyo (HND)': (35.5494, 139.7798),
    'Hong Kong (HKG)': (22.3080, 113.9185),
    'Beijing (PEK)': (40.0799, 116.6031),
    'Munich (MUC)': (48.3538, 11.7861),
    'Doha (DOH)': (25.2736, 51.6081)
}

# Display relevant airports
min_lat = 60  # Map cutoff

for name, (lat, lon) in airports.items():
    if lat >= min_lat:
        # Plot normally
        ax.plot(lon, lat, marker='^', color='blue', markersize=6,
                transform=ccrs.PlateCarree(), zorder=5)
        ax.text(lon, lat + 1, name, transform=ccrs.PlateCarree(),
                fontsize=7, color='blue', ha='center', va='bottom')
    else:
        ax.plot(lon, min_lat, marker='^', color='blue', markersize=6,
                transform=ccrs.PlateCarree(), zorder=5)

        # Determine flip and alignment
        if -180 < lon < 0:
            rotation = lon + 90
            ha = 'right'
        else:
            rotation = lon - 90
            ha = 'left'

        ax.text(lon, 60, f"{name}",
                fontsize=10, color='red',
                rotation=rotation,
                rotation_mode='anchor',
                ha=ha,
                va='center',
                transform=ccrs.PlateCarree(), )

plt.tight_layout()
plt.savefig('high_arctic_flights_map.png', dpi=300, bbox_inches='tight')
plt.show()