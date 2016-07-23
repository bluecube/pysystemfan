# PySystemFan
The overkill fan manager (Why? Because I can).

This branch is unfinished and contains the megalomaniac start of the project.
Maybe I will return to it some day.

This program controls fans in a linux system to minimize noise and maintain temperature limits (measured on ACPI and SMART thermometers).
Because simple proportional control or even PID controller are not good enough for me, this project will use [model predictive control](https://en.wikipedia.org/wiki/Model_predictive_control) to determine the fan speeds and an [extended Kalman filter](https://en.wikipedia.org/wiki/Extended_Kalman_filter) to identify the model parameters.
Also because querying harddrive temperature keeps my drives from spinning down, this program can handle spindowns if there is no IO (the idea comes from [hddfancontrol](https://github.com/desbma/hddfancontrol)).

Currently this is just work in progress, the EKF part sorta works, fans are stopped unless any of the temperatures exceeds the threshold, otherwise all of them run at full power.
There are some failsafes in place, so that the program probably won't burn down your computer), but don't count on it :-).

The code is being tested in a small NAS system built in [my custom case](https://github.com/bluecube/nas-case), which means that I deal with rather slow temperature changes.
It is questionable if this approach won't degrade from "mostly pointless" to "completely pointless" on systems with more power and higher working temperatures.
