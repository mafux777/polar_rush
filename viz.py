import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import numpy as np
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os

# Disable SSL verification for Cartopy data downloads
os.environ['CARTOPY_IGNORE_CERTIFICATE'] = 'True'

# Set Cartopy cache directory to current directory if needed
# os.environ['CARTOPY_DATA_DIR'] = './cartopy_data'

# Read the flight data
flights_df = pd.read_csv('arctic_flights_summaries.csv')


# Convert flight paths from string representation to list of tuples
def parse_path(path_str):
    # Remove brackets and split by comma
    path_str = path_str.strip('[]')
    coordinates = []

    # Handle empty paths
    if not path_str:
        return coordinates

    # Split by ), ( to get individual coordinate pairs
    pairs = path_str.split('), (')
    for pair in pairs:
        # Clean up the pair string
        pair = pair.replace('(', '').replace(')', '')
        lat, lon = pair.split(',')
        coordinates.append((float(lat), float(lon)))

    return coordinates


# Apply the parsing function
flights_df['parsed_path'] = flights_df['flight_path'].apply(parse_path)


# Function to create a circular boundary for polar plots
def add_circular_boundary(ax):
    # Generate a circle in axes coordinates
    theta = np.linspace(0, 2 * np.pi, 100)
    center, radius = [0.5, 0.5], 0.5
    verts = np.vstack([np.sin(theta), np.cos(theta)]).T
    circle = mpath.Path(verts * radius + center)
    ax.set_boundary(circle, transform=ax.transAxes)


# Create figure and polar stereographic projection
fig = plt.figure(figsize=(12, 12))
ax = plt.axes(projection=ccrs.NorthPolarStereo(central_longitude=0))

# Set map extent (north of 70 degrees latitude)
ax.set_extent([-180, 180, 70, 90], ccrs.PlateCarree())

# Add circular boundary
add_circular_boundary(ax)

# Use lower resolution features that are included with Cartopy
ax.add_feature(cfeature.COASTLINE.with_scale('110m'))
ax.add_feature(cfeature.BORDERS.with_scale('110m'), linestyle=':')
ax.add_feature(cfeature.LAND.with_scale('110m'), facecolor='lightgray', alpha=0.5)
ax.add_feature(cfeature.OCEAN.with_scale('110m'), facecolor='lightblue', alpha=0.5)

# Add gridlines (without labels to avoid download issues)
gl = ax.gridlines(draw_labels=False, linewidth=1, color='gray', alpha=0.5, linestyle='--')

# Manually add latitude circles at 75, 80, and 85 degrees
for lat in [75, 80, 85]:
    ax.text(180, lat, f'{lat}°N', transform=ccrs.PlateCarree(),
            horizontalalignment='center', verticalalignment='center')
    circle = plt.Circle((0, 0), radius=90 - lat,
                        transform=ccrs.PlateCarree(),
                        fill=False, linestyle='--', color='gray', alpha=0.5)
    ax.add_patch(circle)

# Plot each flight path with color based on airline (first 3 letters of callsign)
airlines = {}
for _, flight in flights_df.iterrows():
    callsign = flight['callsign']
    if callsign and len(callsign) >= 3:
        airline_code = callsign[:3]
        if airline_code not in airlines:
            airlines[airline_code] = len(airlines)

# Create color map based on airline codes
cmap = plt.cm.tab20
colors = [cmap(i % 20) for i in range(len(airlines))]

# Plot each flight path
for _, flight in flights_df.iterrows():
    if len(flight['parsed_path']) > 0:
        # Extract lat/lon points
        lats, lons = zip(*flight['parsed_path'])

        # Determine line color based on airline
        callsign = flight['callsign']
        if callsign and len(callsign) >= 3:
            airline_code = callsign[:3]
            color = colors[airlines[airline_code]]
        else:
            color = 'gray'

        # Determine line thickness based on position count
        line_width = min(max(flight['position_count'] / 2, 1), 4)

        # Plot the flight path
        ax.plot(lons, lats,
                transform=ccrs.PlateCarree(),
                linewidth=line_width,
                alpha=0.7,
                color=color)

        # Add markers for departure and arrival points
        ax.plot(lons[0], lats[0], 'go', markersize=4, transform=ccrs.PlateCarree())  # Departure
        ax.plot(lons[-1], lats[-1], 'ro', markersize=4, transform=ccrs.PlateCarree())  # Arrival

# Add title
plt.title('Arctic Flight Paths (May 17-18, 2025)', fontsize=16)

# Add airline legend
legend_elements = []
for airline, idx in airlines.items():
    from matplotlib.lines import Line2D

    legend_elements.append(Line2D([0], [0], color=colors[idx], lw=2, label=airline))

# Add the legend in a location that doesn't overlap with the plot
ax.legend(handles=legend_elements, loc='lower left', bbox_to_anchor=(0.1, 0.1),
          title="Airlines", frameon=True, framealpha=0.8)

# Add explanatory text for entry/exit points
plt.figtext(0.15, 0.05, 'Green dots: Entry points', fontsize=10, color='green')
plt.figtext(0.45, 0.05, 'Red dots: Exit points', fontsize=10, color='red')

plt.tight_layout()
plt.savefig('arctic_flights_map.png', dpi=300, bbox_inches='tight')
plt.show()