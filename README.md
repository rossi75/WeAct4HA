# WeAct4HA
provides an integration in home assistant for the Display FS 0.96 Inch and FS V1

## Overview
provides a simple interface for the WeAct Display FS V1 and FS 0.96 Inch with various routines to access the display. If more displays will come up, we can simply add a new model into models.py. The display itself needs to be connected directly via USB to the host PC. Not tested on virtual machines.

## features
- registers as device
- auto-discovery at startup (nope, due to config-flow, not anymore possible since 0.6.0)
- Integration entity available with sensors and some little options (clock, brightness, orientation, background color)
- color test on startup/script init, finishes with background color
- display initialization
- service for manual color test, finishes with black screen
- service for random pixels
- service for orientation
- service to write some text
- service to draw lines
- service to draw squares
- service to draw circles
- service for brightness
- service to draw a progress bar
- service to show an analog clock
- service to show a digital clock
- service to draw an icon
- reads temperature and humidity from displays supported
- entity to set brightness via slider, writing back to persistent store since 0.6.1
- entity to set clock-mode via selector
- entity to set orientation via selector, writing back to persistent store since 0.6.1
- service to draw a triangle
- service to draw a bmp onto the screen, including downsizing
- config-flow compatible
- entity to set background color via rgb-selector, writing back to persistent store since 0.6.1


## restrictions
- any draw/write actions only overwrite the specified area, they do not delete the whole screen. To clear the screen
  or area, draw a rectangle with the desired background color on the whole screen
- display uses RGB565 ! ALWAYS use RGB888, as we calculate it ourself to RGB565

## known issues
- digital clock in portrait orientation uses wrong coordinates (!! need to fix !!) --> __init__.py, bei set_orientation() muss das Bild neu definiert und gezeichnet werden
- analog clock in portrait orientation results in shit (!! need to fix !!) --> same as before
- does not save the orientation for each display (need to enhance it anytime) --> set a startup orientation and background
- if display is newly connected, HA needs a restart to reflect the clock-mode accurate (need to fix)
- display is being recognized only if plugged in at HA startup (maybe I will fix it anytime)
- integration does not start up if NO display is being recognized (maybe I will fix it anytime)
- cannot change clock-mode immediately once after once, need to await the next minute cycle before any further change
  (maybe I will fix it anytime)


## see also:
- changelog: https://github.com/rossi75/WeAct4HA/blob/main/documentation/changelog.md
- next steps: https://github.com/rossi75/WeAct4HA/blob/main/documentation/ToDo.md
- internal struct: https://github.com/rossi75/WeAct4HA/blob/main/documentation/internal_struct.md
- next steps: https://github.com/rossi75/WeAct4HA/blob/main/documentation/notes.md



