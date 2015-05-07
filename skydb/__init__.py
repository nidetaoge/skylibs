import os
from os import listdir
from os.path import abspath, isdir, join
import fnmatch
import datetime

import numpy as np

from envmap import EnvironmentMap
from hdrtools import sunutils


class SkyDB:
    def __init__(self, path):
        """Creates a SkyDB.
        The path should contain folders named by YYYYMMDD (ie. 20130619 for June 19th 2013).
        These folders should contain folders named by HHMMSS (ie. 102639 for 10h26 39s).
        Inside these folders should a file named envmap.exr be located.
        """
        p = abspath(path)
        self.intervals_dates = [join(p, f) for f in listdir(p) if isdir(join(p, f))]
        self.intervals = list(map(SkyInterval, self.intervals_dates))


class SkyInterval:
    def __init__(self, path):
        """Represent an interval, usually a day.
        The path should contain folders named by HHMMSS (ie. 102639 for 10h26 39s).
        """
        self.path =  path
        matches = []
        for root, dirnames, filenames in os.walk(path):
            for filename in fnmatch.filter(filenames, 'envmap.exr'):
                matches.append(join(root, filename))

        self.probes = list(map(SkyProbe, matches))
        self.reftimes = [datetime.datetime(year=1, 
                                            month=1, 
                                            day=1,
                                            hour=int(probe.time[:2]),
                                            minute=int(probe.time[2:4]),
                                            second=int(probe.time[4:6])) for probe in self.probes]
        if len(self.probes) > 0:
            self.sun_visibility = sum(1 for x in self.probes if x.sun_visible) / len(self.probes)
        else:
            self.sun_visibility = 0

    @property
    def date(self):
        return os.path.normpath(self.path).split(os.sep)[-1]

    def closestProbe(self, hours, minutes=0, seconds=0):
        """
        Return the SkyProbe object closest to the requested time.
        TODO : check for day change (if we ask for 6:00 AM and the probe sequence
            only begins at 7:00 PM and ends at 9:00 PM, then 9:00 PM is actually
            closer than 7:00 PM and will be wrongly selected; not a big deal but...)
        """
        cmpdate = datetime.datetime(year=1, month=1, day=1, hour=hours, minute=minutes, second=seconds)
        idx = np.argmin([np.abs((cmpdate - t).total_seconds()) for t in self.reftimes])
        return self.probes[idx]


class SkyProbe:
    def __init__(self, path, format_='angular'):
        """Represent an environment map among an interval."""
        self.path = path
        self.envmap = EnvironmentMap(path, format_)

    @property
    def sun_visible(self):
        return self.envmap.data.max() > 5000

    @property
    def mean_light_vector(self):
        raise NotImplementedError()

    @property
    def time(self):
        return os.path.normpath(self.path).split(os.sep)[-2]

    @property
    def pictureHDR(self):
        return self.envmap.data

    @property
    def sun_position(self):
        return sunutils.sunPosFromEnvmap(self.envmap)

    # ToneMapping operators. Returns unsigned 8-bit result.
    def tmoReinhard2002(self, scale=700):
        """Performs the Reinhard 2002 operator as described in
        Reinhard, Erik, et al. "Photographic tone reproduction for digital
        images." ACM Transactions on Graphics (TOG). Vol. 21. No. 3. ACM, 2002.
        """
        return np.clip(scale * self.envmap.data / (1. + self.envmap.data), 0., 255.).astype('uint8')

    def tmoGamma(self, gamma, scale=1):
        """Performs a gamma compression: scale*V^(1/gamma) ."""
        data = self.envmap.data - self.envmap.data.min()
        return np.clip(scale * np.power(data, 1./gamma), 0., 255.).astype('uint8')