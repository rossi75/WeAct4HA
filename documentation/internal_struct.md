### internal structure:

hass.data[weact_display][serial_number]

| Tupel               | Data Type  | Default Value | Sensor/Attribute         | Description                                                |
|---------------------|------------|---------------|--------------------------|------------------------------------------------------------|
| << state >>         | String     | initializing  |                          | [initializing\|port error\|timeout error\|ready\|busy]     |
| online              | Boolean    |               |                          | for device state                                                           |
| serial_port         | String     |               |                          | Serial Port description from HA                            |
| model               | String     |               | model                    |                                                            |
| serial_number       | String     |               | serial_number            | part of the sensors name and unique ID                     |
| brightness          | Integer    | None          | brightness*              |                                                            |
| width               | Integer    | None          | width                    |                                                            |
| height              | Integer    | None          | height                   |                                                            |
|                     | String     | None          | orientation*             | [Portrait\|Portrait Reverse\|Landscape\|Landscape Reverse] |
| clock_mode          | String     | idle          | clock_mode*              | [idle\|analog\|digital\|rheinturm]                         |
| clock_handle        | Function   | None          |                          | stores the handle that is called periodically              |
| clock_select_entity | Function   | None          |                          | relation to reflect the clock_mode into select entity      |
| humidity            | Integer    | None          | humidity**               |                                                            |
| temperature         | Integer    | None          | temperature**            |                                                            |
|                     | String     | °C            | temperature_unit**       |                                                            |
| port                | String     |               | dbg_port***              | friendly name from serial port                             |
| source              | String     | None          | dbg_source***            | [user\|import\|usb]                                        |
| start_time          | DateTime   | init D/T      | dbg_start_time***        |                                                            |
| who_am_i            | String     | None          | dbg_who_am_i***          |                                                            |
| firmware_version    | String     | None          | dbg_firmware_version***  |                                                            |
| humiture            | Boolean    | False         | dbg_humiture***          | Humiture Sensor available? [False\|True]                   |
| orientation_value   | Integer    | None          | dbg_orientation_value*** | [0\|1\|2\|3]                                               |
| device_id           | String     | None          | dbg_device_id***         |                                                            |
| entry_id            | String     | None          | dbg_entry_id***          |                                                            |
| lock                | Function   | function      |                          | used for while an image is being send, avoids collisions   |
| shadow              | Image Data | 0x000000...   |                          | width * height * 3, the BMP itself                         |

\* also available as seperate entity
** only available as separate entity if humiture sensor is also available
*** (later) only if debug mode is set


### Orientation Settings:

| Orientation       | Value |
|-------------------|-------|
| PORTRAIT          | 0     |
| PORTRAIT_REVERSE  | 1     |
| LANDSCAPE         | 2     |
| LANDSCAPE_REVERSE | 3     |
| ROTATE            | 5     |
