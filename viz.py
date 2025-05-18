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
flights_df = pd.read_csv('arctic_flights_summaries.csv')

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

# Add circular polar boundary
def add_circular_boundary(ax):
    theta = np.linspace(0, 2 * np.pi, 100)
    center, radius = [0.5, 0.5], 0.5
    verts = np.vstack([np.sin(theta), np.cos(theta)]).T
    circle = mpath.Path(verts * radius + center)
    ax.set_boundary(circle, transform=ax.transAxes)

# Set up figure and projection
fig = plt.figure(figsize=(12, 12))
ax = plt.axes(projection=ccrs.NorthPolarStereo(central_longitude=0))
ax.set_extent([-180, 180, 70, 90], ccrs.PlateCarree())
add_circular_boundary(ax)

# Map features
ax.add_feature(cfeature.COASTLINE.with_scale('110m'))
ax.add_feature(cfeature.BORDERS.with_scale('110m'), linestyle=':')
ax.add_feature(cfeature.LAND.with_scale('110m'), facecolor='lightgray', alpha=0.5)
ax.add_feature(cfeature.OCEAN.with_scale('110m'), facecolor='lightblue', alpha=0.5)

# Add latitude markers
for lat in [75, 80, 85]:
    ax.text(180, lat, f'{lat}°N', transform=ccrs.PlateCarree(),
            ha='center', va='center')
    circle = plt.Circle((0, 0), radius=90 - lat,
                        transform=ccrs.PlateCarree(),
                        fill=False, linestyle='--', color='gray', alpha=0.5)
    ax.add_patch(circle)

# Airline color mapping
airlines = {}
for _, flight in flights_df.iterrows():
    callsign = flight['callsign']
    if callsign and len(callsign) >= 3:
        airline_code = callsign[:3]
        if airline_code not in airlines:
            airlines[airline_code] = len(airlines)

cmap = plt.cm.tab20
colors = [cmap(i % 20) for i in range(len(airlines))]

# Plot flights
for _, flight in flights_df.iterrows():
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
plt.title('Arctic Flight Paths (May 17–18, 2025)', fontsize=16)

# Airline legend
from matplotlib.lines import Line2D
legend_elements = [Line2D([0], [0], color=colors[idx], lw=2, label=airline)
                   for airline, idx in airlines.items()]
ax.legend(handles=legend_elements, loc='lower left', bbox_to_anchor=(0.1, 0.1),
          title="Airlines", frameon=True, framealpha=0.8)

# Explanatory text
plt.figtext(0.15, 0.05, 'Green dots: Entry points', fontsize=10, color='green')
plt.figtext(0.45, 0.05, 'Red dots: Exit points', fontsize=10, color='red')

plt.tight_layout()
plt.savefig('arctic_flights_map_with_callsigns.png', dpi=300, bbox_inches='tight')
plt.show()