# WeAct4HA
provides an integration in home assistant for the Display FS 0.96" (others may follow)


# WeAct Display for Homeassistant

## Overview
provides 

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

# changelog

## V0.2.1 - 31.10.2025
- clock is done. how to loop? How to deactivate (servicecommand or any action?)

## V0.2.0 - 30.10.2025
- hello world is being displayed fine: RGB565 / landscape
- show icon (size, colour, bg_colour, x, y, rotation)
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
- color test finishes with Testbild
- set digital clock (later with offset +- for hours)
- set analog clock (later with offset +- for hours)
- send_picture (pos)
- send_text (pos, size, font, align, color, bg_color, orientation)
- qr code
- draw line
- draw circle
- draw square
- draw triangle
- Rheinturm-Uhr
- detect-loop 10 sec
- do not crash at startup if no display detected


