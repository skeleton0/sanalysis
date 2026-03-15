from io import StringIO
from dataclasses import dataclass

@dataclass(frozen=True)
class Sector:
    time: float
    trace: [(float, float)]

@dataclass(frozen=True)
class Track:
    name: str
    sectors: int

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

        # Parse sector count
        sector_count = int(next(f).strip().removeprefix("<trackplan #sectors=").rstrip('>'))

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
                    sector = int(line[0].removeprefix('#'))
                    mins, secs = line[1].split(':')
                    sector_data.append({'sector': sector - 1,
                                        'time': int(mins) * 60 + float(secs),
                                        'avg': 0,
                                        'top': 0,
                                  })
                case 6:
                    s = sector_data[-1]
                    if s['sector'] == sector_count - 1:
                        s['avg'] = int(line[0])
                        s['top'] = int(line[1])
                case _:
                    break

        # Parse trace section

        next(f) # Skip <trace> tag
        trace = []
        for line in f:
            line = line.split(',')
            if len(line) != 11:
                break
            trace.append((float(line[0]), float(line[1])))

        # Compile sector times, trace data and speed data into laps
        laps = []
        lap_sectors = [None] * sector_count
        prev_t = 0
        for sdatum in sector_data:
            sdelta = sdatum['time'] - prev_t
            strace = trace[int(prev_t * 10) : int(sdatum['time'] * 10)]
            prev_t = sdatum['time']
            lap_sectors[sdatum['sector']] = Sector(sdelta, strace)
            if sdatum['sector'] == sector_count - 1:
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
                lap_sectors = [None] * sector_count

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
        track_laps = tracks.setdefault(Track(track_name, sector_count), dict())
        for i, lap in enumerate(laps):
            track_laps[(file.name, i)] = lap

    return tracks

