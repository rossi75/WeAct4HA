
# WeAct Display for Homeassistant

## Overview
provides a simple interface for the WeAct Display FS V1 0.96"

## sources
https://sourceforge.net/projects/weact-studio-system-monitor/files/Doc/WeAct%20Studio%20Display%20Communication%20protocol_v1.1.xlsx/download

## features
- display initialization
- color test on script init, finishes with black screen
- 

## restrictions
- searches for any weact display, but takes only the first one, whichever it is...
- new send actions only overwrite the specified area, they do not delete the whole screen. To clear the screen or area, first blank it with the background color
- display uses RGB565 ! ALWAYS use RGB888, as we calculate it ourself to RGB565
- landscape only, 160 width, 80 heigth
- actually no border for rectangle

# changelog

## V0.2.5 - 05.11.2025
- drawing a rectangle works

## V0.2.4 - 04.11.2025
- analog clock is working fine, moving every minute
- stop service to stop any clocks
- drawing circle and elipse
- all clock related routines outsourced into clock.py
- all services now with a well actions UI

## V0.2.1 - 31.10.2025
- clock is done. how to loop? How to deactivate (servicecommand or any action?)

## V0.2.0 - 30.10.2025
- hello world is being displayed fine: RGB565 / landscape
- show icon (size, colour, bg_colour, x, y, rotation) (does not work actually)
- parts of the analog clock even working

## V0.1.8 - 28.10.2025
- brightness can be set via slider

## V0.1.5 - 26.10.2025
- send random-coloured picture

## V0.1.2 - 25.10.2025
- reset display
- show init screen

## V0.1.0 - 24.10.2025
- communication for full size one color is working

### ToDo
- write text instead of random pixels
- frame for rectangle
- frame for text
- function for send simple commands
- color test finishes with Testbild
- start digital clock (later with offset +- for hours)
- send_picture from file (pos, size, orientation, shift, ...)
- send icon
- draw triangle
- qr code
- multicolor code
- Rheinturm-Uhr
- detect-loop 10 sec
- do not crash at startup with no display detected
- write into memory first, hence upload the whole memory onto the display
- parameter for supressing direct upload the whole memory for all draw functions and any clock


