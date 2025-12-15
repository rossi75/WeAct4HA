# WeAct4HA
provides an integration in home assistant for the Display FS 0.96 Inch and FS V1

## Overview
provides a simple interface for the WeAct Display FS V1 and FS 0.96 Inch with various routines to access the display. If more displays will come up, we can simply add a new model into models.py

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
- show a digital clock
- draws an icon

## restrictions
- new draw/write actions only overwrite the specified area, they do not delete the whole screen. To clear the screen
  or area, first blank it with the background color
- display uses RGB565 ! ALWAYS use RGB888, as we calculate it ourself to RGB565
- display is being recognized only if plugged in at HA startup
- integration does not start up if NO display is being recognized

# changelog

## V0.4.3 - 15.12.2025
- fixed icon with native code
- fixed services.yaml to allow x- and y-values to 479
- display lock activated while sending
- serial read without CPU blocking
- enabled logrotate for SVG, 100 files in CONST.PY, destination is ../icons/

## V0.4.2 - 30.11.-08.12.2025
- start humiture report after startup for reporting every 60 seconds, only if model supports it, native Bytes can
  be seen in debug, calculated values in logs, reflecting values into sensors attributes
- corrected orientation values
- moved initial display communication to post_startup(), integration startup now takes 0.05 seconds instead of ~5-8 seconds
- added attribute temperature_unit into sensor
- clock is now synchronized to seconds
- offset hours for analog and digital clock
- icon works, but is a bit scrappy.... will be fixed soon
- stabilized rectangle function
- CPU load +25% due to serial RX if FS V1 is connected, since 

## V0.4.1 - 27.11.2025
- corrected analog clock (the dot was the issue)
- corrected progress bar (missing last lines as big as the frame-width), no value, no rotation
- digital clock working, no rotation
- disabled hard-coded landscape mode [2], set as default at startup
- enabled logrotate for BMP, 100 files in CONST.PY, destination is ../bmp/
- brightness is set at startup (to 10)
- enabled temperature and humidity reading

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
- send_picture from file (pos, size, orientation, shift, ...)
- draw triangle
- barcode
- qr code
- Rheinturm-Uhr
- detect-loop every 20 sec
- do not crash at startup with no display detected
- function for send simple commands
- parameter for supressing direct upload the whole memory for all draw functions
- text rotation
- progress bar value
- progress bar rotate
- testbild
- bitmap
- digital clock rotate
- analog clock rotate

### internal structure:

hass.data[weact_display][serial_number]

| Instance          | Data Type | Default Value | Sensor/Attribute    | Description                                                |
|-------------------|-----------|---------------|---------------------|------------------------------------------------------------|
| << state >>       | String    | initializing  |                     | [initializing\|port error\|timeout error\|ready\|busy]     |
| serial_port       | String    |               |                     | Serial Port description from HA                            |
| port              | String    |               | port**              | friendly name from serial port                             |
| model             | String    |               | model               |                                                            |
| serial_number     | String    |               | serial_number       | part of the sensors name and unique ID                     |
| start_time        | Date Time | init D/T      | start_time**        |                                                            |
| width             | Integer   | None          | width               |                                                            |
| height            | Integer   | None          | height              |                                                            |
| orientation_value | Integer   | None          | orientation_value** | [0\|1\|2\|3]                                               |
| orientation       | String    | None          | orientation         | [Portrait\|Reverse Portrait\|landscape\|Reverse landscape] |
| humiture          | Boolean   | False         | humiture**          | Humiture Sensor available? [False\|True]                   |
| humidity          | Integer   | None          | humidity*           |                                                            |
| temperature       | Integer   | None          | temperature*        |                                                            |
| temperature_unit  | String    | °C            | temperature_unit*   |                                                            |
| clock_handle      | Function  | None          |                     |                                                            |
| clock_mode        | String    | idle          | clock_mode          | [idle\|analog\|digital\|rheinturm]                         |
| lock              | Function  | function      |                     | used for while an image is being send, avoids collisions   |
| shadow            | Image     | 0x000000...   |                     | width * height * 3, the BMP itself                         |

\* only available if humiture sensor is also available
** later only if debug mode is set at startup


### Orientation Settings:

| Orientation       | Value       |
|-------------------|-------------|
| PORTRAIT          | 0           |
| REVERSE_PORTRAIT  | 1           |
| LANDSCAPE         | 2           |
| REVERSE_LANDSCAPE | 3           |
| ROTATE            | 5           |
