# PySystemFan

The not so overkill fan manager.

PySystemFan assigns several thermometers (accessed through hwmon interface in `/sys` or using `smarctl` for harddrives) to each fan and regulates its speed so that all of the temperatures are at or below a specified setpoint.
If your system has too powerful fan for the heat it generates (minimum fan speed is too much cooling for the set temperature and no fan is not enough cooling), this software can also prevent fan from frequently stopping and starting by exponentially increasing (up to a limit) time it waits before the fan is stopped.
As a side effect of `smartctl` based drive temperature measurements PySystemFan also has to spin down drives in case of inactivity instead of relying on the HDD firmware, because my WD reds counted temperature polling as access (this is optional).

PySystemFan not 100% finished yet, but it works already.
It's being tested (as in running 24/7 for the last few months) in a small NAS system built in [my custom case](https://github.com/bluecube/nas-case).
Exponential fan-off backoff is still being tweaked, the other features seem to be working well.
What's missing is mostly in the front end and packaging departments.

PySystemFan is written in python 3 with no dependencies outside standard library.
`smartctl` and `hdparm` commands are needed to measure temperatures of harddrives and to spin them down.
The code is Linux specific now, but should be reasonably simple to extend to other unixes (as long as the OS has a way to measure temperature and control a fan).

Feedback is appreciated :-).
