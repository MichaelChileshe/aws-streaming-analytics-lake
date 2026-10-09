"""The Mvelaphanda fleet: 300 trucks, 4 depots, one GPS ping per truck every 5 seconds.

Shared by the live simulator (sim.py, pings into Kinesis) and the history generator
(backfill.py, the legacy hourly JSON export in S3), so both produce the same records.

A ping is one JSON object on one line:
  truck_id, depot, event_ms (UTC epoch milliseconds), lat, lon, speed_kmh, heading,
  engine_on, fuel_pct, driver_id, driver_phone
driver_id and driver_phone are the personal information (POPIA) that analysts must not see.
The phone numbers are fake by construction: +27 000 000 xxx is not a real South African number.
"""
import math
import random

# depot: (latitude, longitude, how many trucks, operating radius in km)
DEPOTS = {
    "PTA": (-25.7479, 28.2293, 120, 120.0),  # Pretoria (head office)
    "JHB": (-26.2041, 28.0473, 90, 100.0),   # Johannesburg
    "PLK": (-23.9045, 29.4689, 45, 150.0),   # Polokwane
    "BFN": (-29.0852, 26.1596, 45, 150.0),   # Bloemfontein
}
SPEED_LIMIT_KMH = 80.0       # heavy vehicles (over 9 t) in South Africa: 80 km/h
PING_SECONDS = 5
KM_PER_DEG_LAT = 111.32


class Truck:
    __slots__ = ("truck_id", "depot", "driver_id", "driver_phone", "risky", "offset_ms",
                 "home_lat", "home_lon", "radius_km", "lat", "lon", "heading", "speed",
                 "target", "target_left_s", "stop_left_s", "fuel", "rng")

    def __init__(self, n, depot, risky, seed):
        self.truck_id = f"MV-{n:04d}"
        self.depot = depot
        self.driver_id = f"DRV-{n:04d}"
        self.driver_phone = f"+27 000 000 {n:03d}"
        self.risky = risky
        self.offset_ms = (n * 997) % (PING_SECONDS * 1000)   # trucks ping at different moments
        lat, lon, _, radius = DEPOTS[depot]
        self.home_lat, self.home_lon, self.radius_km = lat, lon, radius
        self.rng = random.Random(seed)
        self.park_at_depot()
        self.fuel = 60.0 + self.rng.random() * 35.0

    def park_at_depot(self):
        r = self.rng
        self.lat = self.home_lat + r.uniform(-0.02, 0.02)
        self.lon = self.home_lon + r.uniform(-0.02, 0.02)
        self.heading = r.uniform(0, 360)
        self.speed = 0.0
        self.target = 0.0
        self.target_left_s = 0
        self.stop_left_s = 0

    def step(self, driving, dt=PING_SECONDS):
        """Move the truck forward dt seconds. driving=False: parked, engine off."""
        r = self.rng
        if not driving:
            self.speed = 0.0
            return False
        if self.stop_left_s > 0:                     # delivery, traffic, loading
            self.stop_left_s -= dt
            self.speed = max(0.0, self.speed - 25.0)
            return True
        if r.random() < 0.0015:
            self.stop_left_s = r.randint(30, 600)
        self.target_left_s -= dt
        if self.target_left_s <= 0:                  # a new road, a new cruising speed
            mean = 86.0 if self.risky else 64.0
            self.target = min(118.0, max(25.0, r.gauss(mean, 8.0)))
            self.target_left_s = r.randint(60, 300)
        self.speed += (self.target - self.speed) * 0.25 + r.gauss(0.0, 1.5)
        self.speed = min(120.0, max(0.0, self.speed))
        # steer: drift, and head home when outside the depot's radius
        dlat_km = (self.lat - self.home_lat) * KM_PER_DEG_LAT
        dlon_km = (self.lon - self.home_lon) * KM_PER_DEG_LAT * math.cos(math.radians(self.home_lat))
        if math.hypot(dlat_km, dlon_km) > self.radius_km:
            home = math.degrees(math.atan2(-dlon_km, -dlat_km)) % 360
            self.heading = (home + r.gauss(0.0, 10.0)) % 360
        else:
            self.heading = (self.heading + r.gauss(0.0, 4.0)) % 360
        km = self.speed * dt / 3600.0
        h = math.radians(self.heading)
        self.lat += km * math.cos(h) / KM_PER_DEG_LAT
        self.lon += km * math.sin(h) / (KM_PER_DEG_LAT * math.cos(math.radians(self.lat)))
        self.fuel -= km * 0.0875                      # about 35 l/100 km from a 400 l tank
        if self.fuel < 12.0:
            self.fuel = 95.0                          # refuelled
        return True

    def json(self, event_ms, engine_on):
        """One ping as a JSON line (hand-built: the history generator writes tens of millions)."""
        return (f'{{"truck_id":"{self.truck_id}","depot":"{self.depot}","event_ms":{event_ms},'
                f'"lat":{self.lat:.5f},"lon":{self.lon:.5f},"speed_kmh":{self.speed:.1f},'
                f'"heading":{int(self.heading)},"engine_on":{"true" if engine_on else "false"},'
                f'"fuel_pct":{self.fuel:.1f},"driver_id":"{self.driver_id}",'
                f'"driver_phone":"{self.driver_phone}"}}')


def make_fleet(seed=25, salt=0):
    """The same 300 trucks every time: ids, depots, drivers and the risky drivers are fixed.
    salt changes only how they drive (each day of history gets its own salt)."""
    r = random.Random(seed)
    trucks, n = [], 0
    for depot, (_, _, count, _) in DEPOTS.items():
        for _ in range(count):
            n += 1
            trucks.append(Truck(n, depot, risky=r.random() < 0.08, seed=(seed * 1000003 + n) * 7919 + salt))
    return trucks


def shift_hours(truck_index, day_seed):
    """History only: when a truck is on the road that day, in UTC hours (SAST = UTC+2).
    Most trucks start between 03:00 and 05:00 UTC (05:00-07:00 SAST) and drive 9-12 hours."""
    r = random.Random(day_seed * 1000 + truck_index)
    start = 3.0 + r.random() * 2.0
    return start, start + 9.0 + r.random() * 3.0
