import sys
import re
import os.path
from enum import Enum
from io import StringIO

import streamlit as st
import pandas as pd
import numpy as np

from util import Track, Sector, parse_files

TRACE_COLOURS = ['#ff4d6d', '#2de2e6', '#ffbd00', '#7cff6b', '#00c2ff']
laptime_ratings = {
        'Broadford': (60, 59),
        'Phillip Island': (102, 100),
        'Mac Park': (75, 73),
        }
def format_laptime(t):
    if t is None:
        return "None"
    mins = int(t / 60)
    secs = t % 60

    if mins > 0:
        return f"{mins}:{secs:06.3f}"
    else:
        return f"{secs:06.3f}"

if "initialised" not in st.session_state:
    st.session_state.tracks = dict()
    st.session_state.deleted_laps = dict()
    st.session_state.file_change = False

    st.session_state.initialised = True

def on_file_change():
    st.session_state.file_change = True

uploaded_files = st.file_uploader("Upload SA files", type="sa", accept_multiple_files=True, on_change=on_file_change)

if st.session_state.file_change:
    st.session_state.tracks = parse_files(uploaded_files)
    st.session_state.file_change = False

# Find the fastest sectors
fastest = dict()
for track, laps in st.session_state.tracks.items():
    fastest_lap = None
    fastest_sectors = [None] * track.sectors
    max_top_speed = (None, 0)
    for key, lap in laps.items():
        if lap['top'] is not None and lap['top'] > max_top_speed[1]:
            max_top_speed = (key, lap['top'])
        if key in st.session_state.deleted_laps.setdefault(track, set()):
            continue
        # Check fastest lap
        laptime = lap['laptime']
        if laptime is not None and (fastest_lap is None or laptime < fastest_lap[1]):
            fastest_lap = (key, laptime)

        # Check fastest sectors
        for s_no, sector in enumerate(lap['sectors']):
            if sector is not None:
                if fastest_sectors[s_no] is None:
                    fastest_sectors[s_no] = (key, sector.time)
                elif sector.time < fastest_sectors[s_no][1]:
                    fastest_sectors[s_no] = (key, sector.time)

    if None in fastest_sectors:
        print(f"Don't have times for all sectors for {track.name}")
        continue


    ideal_lap = sum([t for _, t in fastest_sectors])
    fastest_sectors.append(fastest_lap)
    fastest_sectors = [k for k, _ in fastest_sectors]
    fastest[track] = (max_top_speed, ideal_lap, fastest_sectors)
    continue

# Construct data for display
display_data = dict()
for track, fastest_data in fastest.items():
    # Create rows for fastest sector table
    fastest_sector_rows = []
    for lap_key in set(fastest_data[2]):
        lap = st.session_state.tracks[track][lap_key]
        fastest_sector_lap = {
            'File': lap_key[0],
            'Lap': lap_key[1] + 1,
            }

        # Add sectors
        for i, sector in enumerate(lap['sectors']):
            fastest_sector_lap[f'S{i+1}'] = None if sector is None else round(sector.time, 3)

        fastest_sector_lap['Laptime'] = format_laptime(lap['laptime'])
        fastest_sector_lap['Top speed (km/h)'] = str(lap['top']) if lap['top'] is not None else None 

        fastest_sector_rows.append(fastest_sector_lap)

    fastest_sector_rows.sort(key=lambda x: (x['File'], x['Lap']))

    # Create rows for trace map
    trace_rows = []
    for i, key in enumerate(fastest_data[2][:track.sectors]):
        for pos in st.session_state.tracks[track][key]['sectors'][i].trace:
            trace_rows.append((*pos, TRACE_COLOURS[i]))

    trace_dataframe = pd.DataFrame(trace_rows, columns=('lat', 'lon', 'colour'))

    # Add rating emoji to ideal lap
    rating = ''
    if track in laptime_ratings:
        if fastest_data[1] >= laptime_ratings[track][0]:
            rating = '🐢'
        elif fastest_data[1] >= laptime_ratings[track][1]:
            rating = '👍'
        else:
            rating = '🔥'

    display_data[track] = {'fastest_sector_rows': fastest_sector_rows,
                           'trace_dataframe': trace_dataframe,
                           'ideal_lap': format_laptime(fastest_data[1]),
                           'max_top_speed': fastest_data[0],
                           'rating_emoji': rating,
                           }

def on_change(track, key):
    rows = display_data[track]['fastest_sector_rows']
    for idx in getattr(st.session_state, key)['deleted_rows']:
        lap_key = (rows[idx]['File'], rows[idx]['Lap'] - 1)
        st.session_state.deleted_laps[track].add(lap_key)
    # We don't want the table do handle any deltas, we'll handle that
    getattr(st.session_state, key)['deleted_rows'] = []

# Display content

for track, dp in display_data.items():
    key = f"{track.name.replace(' ', '_')}{track.sectors}de"

    # Create column config
    column_config = {f"S{i}": st.column_config.NumberColumn(format="%.3f") for i in range(1, track.sectors + 1)}

    df = pd.DataFrame(dp['fastest_sector_rows']).style.highlight_min(subset=['Laptime'])

    for i in range(track.sectors):
        df = df.highlight_min(subset=[f'S{i+1}'], color=TRACE_COLOURS[i])

    with st.container():
        st.header(f"{track} — :rainbow[{dp['ideal_lap']}] {dp['rating_emoji']}", divider="blue")
        st.caption("Reference the map to check the sectors are correct. If you have a dodgy sector you can delete it by clicking the checkbox on the left side of the row, and the clicking the trash can at the top right of the table.")
        st.data_editor(df, hide_index=True, num_rows="delete", disabled=df.columns, on_change=on_change, key=key, args=[track, key], column_config=column_config)

        # Display top speed message
        top_speed = dp['max_top_speed']
        st.markdown(f"Highest speed reported was :orange[{top_speed[1]} km/h] — :grey[{top_speed[0][0]}, Lap {top_speed[0][1]}]")

        # Display map
        st.map(dp['trace_dataframe'], color="colour", size=1)
