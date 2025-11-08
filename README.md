# WeAct4HA
provides an integration in home assistant for the Display FS 0.96" (others may follow)

## Overview
provides a simple interface for the WeAct Display FS V1 0.96" with various routines to access the display

## sources
https://sourceforge.net/projects/weact-studio-system-monitor/files/Doc/WeAct%20Studio%20Display%20Communication%20protocol_v1.1.xlsx/download

## features
- display initialization
- color test on script init, finishes with black screen
- draw squares
- draw circles
- show an analog clock
- write some text

## restrictions
- searches for any weact display, but takes only the first one, whichever it is...
- new send actions only overwrite the specified area, they do not delete the whole screen. To clear the screen or area, first blank it with the background color
- display uses RGB565 ! ALWAYS use RGB888, as we calculate it ourself to RGB565
- landscape only, 160 width, 80 heigth

# changelog

## V0.2.8 - 08.11.2025
- rectangle is now without the line, found the issue for the line (double xe)
- prepared call for progress bar
- if no Y-End line is given for text, we will take the font-size
- text with a rotation of 90 or 270 degree is now displayed. But there is one more issue with the alignment then...
- all draw routines are saving (only !) its BMP to ../bmp/*

## V0.2.7 - 07.11.2025
- rectangle is now with frame, but why the heck is there a line in?
- text is now scalable
- text is now visible
- text with 90 or 270 degrees rotated results in a scramled image
- image save routine corrected
- global variable for IMAGE_PATH and CLOCK_REMOVE_HANDLE

## V0.2.6 - 06.11.2025
- preparations for progress bar
- all draw routines should save the image now as BMP, JPG and PNG

## V0.2.5 - 05.11.2025
- drawing a rectangle works, but no frame.... :(

## V0.2.4 - 04.11.2025
- analog clock is working fine, moving every minute
- stop service to stop any clocks
- drawing circle and elipse
- all clock related routines outsourced into clock.py
- all services now with a well actions UI in Home Assistant

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
- function for send simple commands
- color test finishes with Testbild
- start digital clock (later with offset +- for hours)
- send_picture from file (pos, size, orientation, shift, ...)
- send icon
- draw triangle
- qr code
- multicolor code (3D-Code/Ultracode)
- Rheinturm-Uhr
- detect-loop 10 sec
- do not crash at startup with no display detected
- write into memory first, hence upload the whole memory onto the display
- parameter for supressing direct upload the whole memory for all draw functions and any clock


