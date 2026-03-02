# WeAct4HA
provides an integration in home assistant for the Display FS 0.96 Inch and FS V1

## Overview
provides a simple interface for the WeAct Display FS V1 and FS 0.96 Inch with various routines to access the display. If more displays will come up, we can simply add a new model into models.py

## features
- registers as device
- auto-discovery at startup
- Integration entity available with sensors and some little commands (self test, clock)
- color test on startup/script init, finishes with black screen
- manual color test, finishes with black screen
- display initialization
- random pixels
- write some text
- draw lines
- draw squares
- draw circles
- draw a progress bar
- show an analog clock
- show a digital clock
- draws an icon
- reads temperature and humidity from displays supported
- set brightness via slider
- set clock-mode via selector
- set orientation via selector
- draw a triangle
- draw a bmp onto the screen, including downsizing


## restrictions
- new draw/write actions only overwrite the specified area, they do not delete the whole screen. To clear the screen
  or area, first blank it with the background color
- display uses RGB565 ! ALWAYS use RGB888, as we calculate it ourself to RGB565
- display is being recognized only if plugged in at HA startup (maybe I will fix it anytime)
- integration does not start up if NO display is being recognized (maybe I will fix it anytime)


## see also:
- changelog: https://github.com/rossi75/WeAct4HA/blob/main/documentation/changelog.md
- next steps: https://github.com/rossi75/WeAct4HA/blob/main/documentation/ToDo.md
- internal struct: https://github.com/rossi75/WeAct4HA/blob/main/documentation/internal_struct.md
- next steps: https://github.com/rossi75/WeAct4HA/blob/main/documentation/notes.md



