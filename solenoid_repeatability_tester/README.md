# solenoid_repeatability_tester
 Rough and ready code to test the drawing machine solendoids repeatability. 

 Given problems with some drawing machines pen lift occasionally failing to lift, resulting in unexpected lines drawn, this is some rough and ready code to test how reliable the solenoid pen lift really is.

 Its meant to run on the existing controller. Can either replace the existing firmware or could be another controller board that gets plugged in temporarily.

 It should use the existing pen lift connector (J10) connected to the solenoid controller board. The X Limit Switch connector (J5) gets connected to an optical endstop that is positioned below the pen lift. A tab attached to the pen lift mechanism should pass through the optical endstop to register the activation.
 Failed activations are determined by not detecting the triggered endstop within a certain time (will need to test this out on a real machine and see what works best to avoid false positives).

 The results are logged to both the SD card in a 'test.txt' file and to the serial port.

 The solendoid is triggered at random intervals as defined by trigger delay. (minTriggerDelay/maxTriggerDelay). The fastest we can trigger the solenoid is about 10Hz or every 20ms.

 The endstop activation wait time defines how long to wait until we should expect the endstop to register the penlift to first occur and then how long we should continue to wait before we are certain the pen lift has failed. (minSenseTime/maxSenseTime)
