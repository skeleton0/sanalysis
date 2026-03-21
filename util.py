import math
from io import StringIO
from dataclasses import dataclass

@dataclass(frozen=True)
class Sector:
    time: float
    trace: [(float, float)]

@dataclass(frozen=True)
class SectorPlan:
    p1: (float, float)
    p2: (float, float)

def _point_between(pos1, pos2) -> tuple[float, float]:
    """
    Returns a point along the straight line (in lat/lon space) between two coordinates.

    Author: Grok
    """
    lat = pos1[0] + 0.5 * (pos2[0] - pos1[0])
    lon = pos1[1] + 0.5 * (pos2[1] - pos1[1])
    return (lat, lon)

def _distance(pos1, pos2):
    """
    Fast flat-Earth approximation — error typically < 0.3–0.8 m at 500 m distance

    Author: Grok
    """
    # Average latitude for better cosine value
    avg_lat = (pos1[0] + pos2[0]) / 2

    # metres per degree
    dy = 111_111 * (pos2[0] - pos1[0])              # north-south
    dx = 111_111 * math.cos(math.radians(avg_lat)) * (pos2[1] - pos1[1])  # east-west

    dist = math.hypot(dx, dy)
    #print(f"Distance: {dist}")
    return dist

def _sector_valid(trace: [(float, float)], sec1: SectorPlan, sec2: SectorPlan) -> bool:
    """Check if first and last trace coordinates deviate from the
    sector plan's start and end coordinates by `threshold` m or more, respectively.
    """
    threshold = 40
    pb1 = _point_between(sec1.p1, sec1.p2)
    pb2 = _point_between(sec2.p1, sec2.p2)
    return _distance(pb1, trace[0]) < threshold and \
           _distance(pb2, trace[-1]) < threshold

def parse_files(files):
    tracks = dict()

    def skip_until(f, prefix):
        for line in f:
            if line.startswith(prefix):
                return True
        return False

    for file in files:
        print(f"Parsing {file.name}")
        f = StringIO(file.getvalue().decode("utf-8"))
        # Find track name
        for line in f:
            if line.startswith("#S="):
                track_name = line.removeprefix("#S=").rstrip("= \r\n")
                break
        else:
            print("Failed to find track name")
            continue

        # Skip <trackplan> tag
        next(f)

        # Parse track plan (if we don't have it already)
        if track_name not in tracks:
            trackplan = []
            for line in f:
                if line.strip() == "</trackplan>":
                    break
                coords = line.split(',')
                trackplan.append(SectorPlan((float(coords[1]), float(coords[2])), (float(coords[3]), float(coords[4]))))
        else:
            trackplan = tracks[track_name]['trackplan']

        if not skip_until(f, "<timer"):
            print("Failed to find timer section")
            continue

        # Parse timer section
        sector_data = []
        lap_speed = []
        for line in f:
            line = line.split(',')
            match len(line):
                case 2:
                    sector_num = int(line[0].removeprefix('#'))
                    mins, secs = line[1].split(':')
                    sector_data.append({'sector_num': sector_num - 1,
                                        'time': int(mins) * 60 + float(secs),
                                        'avg': 0,
                                        'top': 0,
                                  })
                case 6:
                    s = sector_data[-1]
                    if s['sector_num'] == len(trackplan) - 1:
                        s['avg'] = int(line[0])
                        s['top'] = int(line[1])
                case _:
                    break

        # Skip <trace> tag
        next(f)

        # Parse trace section
        trace = []
        for line in f:
            if line.strip() == "</trace>":
                break
            line = line.split(',')
            trace.append((float(line[0]), float(line[1])))

        # Compile sector times, trace data and speed data into laps
        bad_sectors = 0
        laps = []
        lap_sectors = [None] * len(trackplan)
        prev_t = 0
        for sdatum in sector_data:
            sdelta = sdatum['time'] - prev_t
            strace = trace[int(prev_t * 10) : int(sdatum['time'] * 10)]
            prev_t = sdatum['time']
            snum = sdatum['sector_num']

            if _sector_valid(strace, trackplan[snum-1], trackplan[snum]):
                lap_sectors[snum] = Sector(sdelta, strace)
            else:
                print(f"Invalid sector: {file.name}, {len(laps) + 1}, S{snum + 1}")
                bad_sectors += 1

            if snum == len(trackplan) - 1:
                # Final sector; construct lap
                lap = {'sectors': lap_sectors,
                       'avg': sdatum['avg'],
                       'top': sdatum['top'],
                       'laptime': None,
                       }

                # Calulate laptime
                if None not in lap_sectors:
                    lap['laptime'] = sum([s.time for s in lap_sectors])

                laps.append(lap)

                # Clear sector list
                lap_sectors = [None] * len(trackplan)

        # Handle any unfinished lap
        if any(lap_sectors):
            lap = {'sectors': lap_sectors,
                   'avg': None,
                   'top': None,
                   'laptime': None}

            # Add speed data
            if (final_sector := lap_sectors[-1]) is not None:
                lap['avg'] = final_sector['avg']
                lap['top'] = final_sector['top']

            laps.append(lap)

        # Append processed data
        trackdata = tracks.setdefault(track_name, {'trackplan': trackplan,
                                                   'bad_sectors': 0,
                                                   'laps': dict()})
        trackdata['bad_sectors'] += bad_sectors
        for i, lap in enumerate(laps):
            trackdata['laps'][(file.name, i)] = lap

    return tracks

