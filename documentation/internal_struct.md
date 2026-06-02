### hardware layout:

## FS 0.96/Landscape
```
 +----------------------------------------------------------------+
 +0 xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx 160+
 +y                                                               +
 +y                                                               + ###########
 +y                                                               + ########
 +y                                                               + ########
 +y                                                               + ###########
 +y                                                               +
 +80                                                              +
 +----------------------------------------------------------------+
```

## FS V1/Landscape
```
 +----------------------------------------------+
 +0 xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx 480+
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +y                                             +
 +320                                           +
 +----------------------------------------------+
```

### internal data structure:

hass.data[weact_display]["devices"][serial_number]

| Tupel                     | Data Type  | Default Value | Sensor/Attribute         | Description                                                |
|---------------------------|------------|---------------|--------------------------|------------------------------------------------------------|
| << state >>               | String     | initializing  |                          | [initializing\|port error\|timeout error\|ready\|busy]     |
| online                    | Boolean    |               |                          | for device state                                           |
| serial_port               | String     |               |                          | Serial Port description from HA                            |
| model                     | String     |               | model                    |                                                            |
| serial_number             | String     |               | serial_number            | part of the sensors name and unique ID                     |
| brightness                | Integer    | None          | brightness*              |                                                            |
| width                     | Integer    | None          | width                    |                                                            |
| height                    | Integer    | None          | height                   |                                                            |
| orientation_value         | Integer    | None          | dbg_orientation_value*** | [0\|1\|2\|3]                                               |
|                           | String     | None          | orientation*             | [portrait\|portrait reverse\|landscape\|landscape reverse] |
| clock_mode                | String     | idle          | clock_mode*              | [idle\|analog\|digital\|rheinturm]                         |
| clock_handle              | Function   | None          |                          | stores the handle that is called periodically              |
| clock_select_entity       | Function   | None          |                          | relation to reflect the clock_mode into select entity      |
| screencare                | Boolean    | True          | screencare*              | random pixels at 03:37? [False\|True]                      |
| screencare_target         | DateTime   | None          | next_screencare          | only if screencare is enabled                              |
| background_color          | Tupel      | [0, 0, 0]     | background_color*        |                                                            |
| humidity                  | Integer    | None          | humidity**               |                                                            |
| fastlz                    | Boolean    | False         | dbg_fastlz***            |                                                            |
| temperature               | Integer    | None          | temperature**            |                                                            |
|                           | String     | °C            | temperature_unit**       |                                                            |
| device_path               | String     |               | dbg_dev_path***          | friendly name from serial port                             |
| start_time                | DateTime   | init D/T      | dbg_start_time***        |                                                            |
| who_am_i                  | String     | None          | dbg_who_am_i***          |                                                            |
| firmware_version          | String     | None          | dbg_firmware_version***  |                                                            |
| humiture                  | Boolean    | False         | dbg_humiture***          | Humiture Sensor available? [False\|True]                   |
| entry_id                  | String     | None          | dbg_entry_id***          |                                                            |
| device_id                 | String     | None          | dbg_device_id***         |                                                            |
| lock                      | Function   | function      |                          | used for while an image is being send, avoids collisions   |
| shadow                    | Image Data | 0x000000...   |                          | width * height * 3, the BMP itself                         |

\* also available as seperate entity
** only available as separate entity if humiture sensor is also available
*** only available if debug mode is set


hass.data[weact_display]["serial_map"][entry_id] --> aktuell deaktiviert da ungenutzt
| Tupel                     | Data Type  | Default Value | Sensor/Attribute           | Description                     |
|---------------------------|------------|---------------|----------------------------|---------------------------------|
| serial_number             | String     | None          | dbg_lookup_entry2serial*** | for serial lookup from entry_id |


hass.data[weact_display]["device_id_map"][device_id]
| Tupel                     | Data Type  | Default Value | Sensor/Attribute | Description                      |
|---------------------------|------------|---------------|------------------|----------------------------------|
| serial_number             | String     | None          |                  | for serial lookup from device_id |


entry.data.
| Tupel                     | since version | Data Type  | Example           | Description                              |
|---------------------------|---------------|------------|-------------------|------------------------------------------|
| entry_id                  | 0.6.0         | String     |                   |                                          |
| device_path               | 0.6.0         | String     |                   |                                          |
| serial_number             | 0.6.0         | String     | 987321654s12      |                                          |
| model                     | 0.6.0         | String     | FS 0.96 Inch      |                                          |
| setup_dt                  | 0.6.1         | String     | 20260502T11:46:00 |                                          |
| setup_version             | 0.6.1         | String     | 0.6.1             |                                          |


entry.options.
| Tupel             | since version | Data Type | Default   | Description                     |
|-------------------|---------------|-----------|-----------|---------------------------------|
| entry_id          | 0.6.0         | String    |           |                                 |
| orientation_value | 0.5.5         | String    | 2         |                                 |
| background_color  | 0.5.5         | Tupel     | (0, 0, 0) |                                 |
| brightness        | 0.6.0         | String    | 7         |                                 |
| screencare        | 0.6.0         | Boolean   | True      | [True/False]                    |
| fastlz            | 0.6.3         | Boolean   | False     | [True/False] actually unused    |


### Orientation Settings:
```
 +--------------------+    
 +Portrait Reverse = 1+    
 +                    +    
 +                    +    
 +                    +    +---------------------------+
 +                    +    +   Landscape Reverse = 3   +
 +2                  3+    +1                         0+
 +                    +    +       Landscape = 2       +
 +                    +    +---------------------------+
 +                    +    
 +                    +    
 +    Portrait = 0    +    
 +--------------------+    
```
| Orientation        | Value | Rot. |
|--------------------|-------|------|
| PORTRAIT           | 0     |    0 |
| PORTRAIT_REVERSE   | 1     | -180 |
| LANDSCAPE          | 2     |  -90 |
| LANDSCAPE_REVERSE  | 3     | -270 |
| ROTATE (not impl.) | 5     |      |


### vorhandenes Bild anhand der alten und der neuen Orientierung mehrmals um -90° drehen:

 old |  90 | 270 |  0  | 180        old | 0 | 1 | 2 | 3
 new ------------------------       new ----------------
  90 |  -  |  2  |  3  |  1           0 | - | 2 | 3 | 1
 270 |  2  |  -  |  1  |  3           1 | 2 | - | 1 | 3
   0 |  1  |  3  |  -  |  2           2 | 1 | 3 | - | 2
 180 |  3  |  1  |  2  |  -           3 | 3 | 1 | 2 | -

resulting array-table since 0.6.2
ORIENTATION_CONVERSION_MAP[old][new]:
[[0,2,1,3],
 [2,0,3,1],
 [3,1,0,2],
 [1,3,2,0]]

ich glaube das hier ist falsch, 0.6.0 bis 0.6.1:
[[0,2,3,1],
 [2,0,1,3],
 [1,3,0,2],
 [3,1,2,0]]


