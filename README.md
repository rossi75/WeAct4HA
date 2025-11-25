# WeAct4HA
provides an integration in home assistant for the Display FS 0.96 Inch and FS V1

## Overview
provides a simple interface for the WeAct Display FS V1 and FS 0.96 Inch with various routines to access the display

## sources
https://sourceforge.net/projects/weact-studio-system-monitor/files/Doc/WeAct%20Studio%20Display%20Communication%20protocol_v1.1.xlsx/download

## features
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

## restrictions
- new send actions only overwrite the specified area, they do not delete the whole screen. To clear the screen or area, first blank it with the background color
- display uses RGB565 ! ALWAYS use RGB888, as we calculate it ourself to RGB565
- landscape only, 160 width, 80 heigth
- display is being recognized only if plugged in at HA startup

# changelog

## V0.4.0 - 20.-25.11.2025
- multiple display support, need to mandatory select the display entity for every command
- display entity ends now with serial number
- serial_number is the unique entity id
- display name is now with model and serial_number
- new structure for ONE sensor for each display with all attributes
- internal shadow picture in RGB888 for each display
- every time anything is drawn and the complete picture is being sent, the picture is being stored in ../bmp/[serial]_[time].bmp
- rectangle working
- circle working
- line working
- brightness working
- orientation not tested
- random bitmap working
- text partially working, no rotation
- progress bar partially working. no value, no rotate
- analog clock....... nope !
- digital clock not working
- QR code not working
- triangle not working
- icon not working
- testbild not working
- bitmap not working

## V0.3.0 - 16.11.2025
-  repaired clock

## V0.2.9 - 14.11.2025
- progress bar works 
- more details in attributes (humiture/width/height), preparations for multiple displays and rotate
- clock state now in attribute, not anymore as an additional entity. Reason is, if you have multiple displays,
  the will named *_2, *_3, etc, but the clock_state would have started its counting from the 1st you start the clock...

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
- start digital clock (later with offset +- for hours)
- send_picture from file (pos, size, orientation, shift, ...)
- send icon
- draw triangle
- strichcode
- qr code
- Rheinturm-Uhr
- detect-loop every 20 sec
- do not crash at startup with no display detected
- parameter for supressing direct upload the whole memory for all draw functions
- enable temperature and humidity reading


### structure:

hass.data[weact_display][serial_number]

| Instance      | Data Type | Default Value | Sensor/Attribute | Description                              |
|---------------|-----------|---------------|------------------|------------------------------------------|
| << state >>   | boolean   | false         |                  | [false\|initializing\|ready]             |
| serial_port   | string    |               |                  | Serial Port description from HA          |
| port          | string    |               | port**           | friendly name from serial port           |
| model         | string    |               | model            |                                          |
| serial_number | string    |               | serial_number    | part of the sensors name and unique ID   |
| start_time    | Date Time | init D/T      | start_time**     |                                          |
| width         | integer   | None          | width            |                                          |
| height        | integer   | None          | height           |                                          |
| orientation   | integer   | None          | orientation      | [0\|1\|2\|3]                             |
| humiture      | boolean   | false         | humiture**       | Humiture Sensor available? [false\|true] |
| temperature   | integer   | None          | temperature*     |                                          |
| humidity      | integer   | None          | humidity*        |                                          |
| clock_handle  | ???       | None          |                  |                                          |
| clock_mode    | string    | idle          | clock_mode       | [idle\|analog\|digital\|rheinturm]       |
| shadow        | Image()   | 0x000000...   |                  | width * height * 3, the BMP itself       |

\* only available if humiture sensor is also available
** later only in debug mode
