# TelloDrone
Code for Tello Drone

---------------------------------------------------
## tello_ds4.py:

- Dependencies:
numpy
cv2 (cv2 depends on ffmpeg)
pygame
djitellopy (https://github.com/damiafuentes/DJITelloPy)

When running this, a new window will open displaying Drone stream and battery status.
Commands:

        Press escape key to quit.
        The controls are:
            - T: Takeoff
            - L: Land
            - Arrow keys: Forward, backward, left and right.
            - A and D: Counter clockwise and clockwise rotations
            - W and S: Up and down.
            - P: Emergency- Shutdown propellers            
            
        Joystick (DS4 used on tests):
            - D-Pad:        Flip on selected direction
            - R1:           Takeoff
            - L1:           Land
            - L2:           Up
            - R2:           Down
            - L Stick:      Forwards/Backwards,Left/Right
            - R Stick:      Rotate/UP/Down
            - Triangle:     Display extended stats
            - X:            Display the history commands
            - Circle:       Resets to 0 the history commands
            - Square:       Execute the history commands and cleans history when finish
            ** History commands work only after a takeoff
            
---------------------------------------------------            
