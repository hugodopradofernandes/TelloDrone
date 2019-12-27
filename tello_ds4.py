#!/usr/bin/python
###--------------------------------------------------------------
###IMPORTS

import time
import re
import numpy as np
import cv2
import pygame
from djitellopy import Tello #https://github.com/damiafuentes/DJITelloPy

from pygame.locals import *
from pygame import display, joystick, event, key, freetype
#from pygame import QUIT, JOYAXISMOTION, JOYBALLMOTION, JOYHATMOTION, JOYBUTTONUP, JOYBUTTONDOWN

###--------------------------------------------------------------
###VARS

# Default speed of the drone (Keyboard)
S = 60
# Frames per second of the pygame window display
FPS = 25

# Set joystick d-pad (hat) coordinates
h = {
	(0,0):  'c',
	(1,0):  'E', (1,1):   'NE', (0,1):  'N', (-1,1): 'NW',
	(-1,0): 'W', (-1,-1): 'SW', (0,-1): 'S', (1,-1): 'SE'
}

# set joystick axis decimal precision
P = 2 # precision

# Global stat variables
drone_stat = ''
drone_ext_stat = ''
np_commad_hist = np.array([[0, 0, 0, 0]])

###--------------------------------------------------------------
###FUNCTIONS DECLARATION

class FrontEnd(object):
    """ Maintains the Tello display and moves it through the keyboard keys.
        Press escape key to quit.
        The controls are:
            - T: Takeoff
            - L: Land
            - Arrow keys: Forward, backward, left and right.
            - A and D: Counter clockwise and clockwise rotations
            - W and S: Up and down.
            - P: Emergency - Shutdown propellers
            - Y: Display extended stats while pressed
            - H: Display the history commands
            - G: Resets to 0 the history commands
            - J: Execute the history commands and cleans history when finish
            ** History commands work only after a takeoff
            
        Joystick (DS4 used on tests):
            - D-Pad:        Flip on selected direction
            - R1:           Takeoff
            - L1:           Land
            - L2:           Up
            - R2:           Down
            - L Stick:      Forwards/Backwards,Left/Right
            - R Stick:      Rotate/UP/Down
            - Triangle:     Display extended stats while pressed
            - X:            Display the history commands
            - Circle:       Resets to 0 the history commands
            - Square:       Execute the history commands and cleans history when finish
            ** History commands work only after a takeoff
    """

    def __init__(self):
        # Init pygame
        pygame.init()

        # Creat pygame window
        pygame.display.set_caption("Tello video stream")
        self.screen = pygame.display.set_mode([960, 720])

        # Init Tello object that interacts with the Tello drone
        self.tello = Tello()

        # Drone velocities between -100~100
        self.for_back_velocity = 0
        self.left_right_velocity = 0
        self.up_down_velocity = 0
        self.yaw_velocity = 0
        self.speed = 10

        self.send_rc_control = False
        self.zero_rc_control = 0
        self.zero_axis = 0

        # Create update timer
        pygame.time.set_timer(pygame.USEREVENT + 1, 50)

        # Init Josystick
        display.init()
        joystick.init()
        for i in range(joystick.get_count()):
            joystick.Joystick(i).init()

#-------------------
#RUN FUNCTION
    def run(self):

        if not self.tello.connect():
            print("Tello not connected")
            return

        if not self.tello.set_speed(self.speed):
            print("Not set speed to lowest possible")
            return

        # In case streaming is on. This happens when we quit this program without the escape key.
        if not self.tello.streamoff():
            print("Could not stop video stream")
            return

        if not self.tello.streamon():
            print("Could not start video stream")
            return

        frame_read = self.tello.get_frame_read()
        
        ##Trigger an event to be used to fetch drone stats
        GETSTATS, t = pygame.USEREVENT+2, 10000
        pygame.time.set_timer(GETSTATS, t)
        global drone_ext_stat

        #-------------------
        # Getting inputs - KEYS and JOYSTICK
        should_stop = False
        while not should_stop:

            for event in pygame.event.get():
                #-------------------
                #TIMED EACH FRAME EVENTS
                if event.type == pygame.USEREVENT + 1:
                    self.update()
                elif event.type == pygame.QUIT:
                    should_stop = True
                #-------------------
                #KEYBOARD EVENTS
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        should_stop = True
                    else:
                        self.keydown(event.key)
                elif event.type == pygame.KEYUP:
                    self.keyup(event.key)
                #-------------------
                #JOYSTICK EVENTS
                if event.type == JOYAXISMOTION:
                    #Joystick axis needs to stop sending 0.00 values when not used after 5 attempts
                    if event.value != 0.0:
                        self.joystick_axis(event.axis, round(event.value, P))
                        self.zero_axis = 0
                    else:
                        if self.zero_axis <= 5:
                            self.joystick_axis(event.axis, round(event.value, P))
                            self.zero_axis += 1
                #elif event.type == JOYBALLMOTION: print ('js', event.joy, 'ball', event.ball, round(event.rel, P)) #not used with DS4
                elif event.type == JOYHATMOTION: self.joystick_hat(h[event.value])
                elif event.type == JOYBUTTONUP: self.joystick_button_up(event.button)
                elif event.type == JOYBUTTONDOWN: self.joystick_button_down(event.button)
                #-------------------
                #TIMED EVENTS
                if event.type == GETSTATS:
                    try:
                        drone_stat = self.get_stats()
                    except:
                        drone_stat = '0'

            if frame_read.stopped:
                frame_read.stop()
                break

            #-------------------
            #FRAME/SCREEN UPDATE
            self.screen.fill([0, 0, 0])
            try:
                frame = cv2.cvtColor(frame_read.frame, cv2.COLOR_BGR2RGB)
            except:
                pass
            frame = np.rot90(frame)
            frame = np.flipud(frame)
            frame = pygame.surfarray.make_surface(frame)
            gamefont = freetype.Font('/usr/share/fonts/gnu-free/FreeSans.ttf', 20)
            try:
                if drone_stat:
                    gamefont.render_to(frame, (10,10), drone_stat + drone_ext_stat, (255, 255, 255))
            except:
                drone_stat = 'No data'
                drone_ext_stat = ''
            self.screen.blit(frame, (0, 0))
            pygame.display.update()
            
            time.sleep(1 / FPS)

        # Call it always before finishing. To deallocate resources.
        self.tello.end()
#-------------------
#EVENTS FUNCTIONS JOYSTICK
    def joystick_hat(self, coord):
        """ Update velocities based on d-pad input
        Arguments:
            coordinates: pygame event.hat, h[event.value]
        """
        if coord == 'N':  # set forward velocity
            try:
                self.tello.flip('f')
            except Exception:
                pass
        elif coord == 'S':  # set backward velocity
            try:
                self.tello.flip('b')
            except Exception:
                pass
        elif coord == 'W':  # set backward velocity
            try:
                self.tello.flip('l')
            except Exception:
                pass
        elif coord == 'E':  # set backward velocity
            try:
                self.tello.flip('r')
            except Exception:
                pass

    def joystick_axis(self, axis, value):
        """ Update velocities based on joystick analog axis input (-1.00 to 1.00)
        Arguments:
            coordinates: pygame event.axis, round(event.value, P)
        """
        if axis == 0:  # left/right left analog
            self.left_right_velocity = int(value * 100)
        elif axis == 1:  # up/down left analog
            self.for_back_velocity = int(value * -100)
        elif axis == 3:  # left/right right analog
            self.yaw_velocity = int(value * 100)
        elif axis == 4:  # left/right right analog
            self.up_down_velocity = int(value * -100)

        #L2/R2 commands must have a tweak to set speed = 0 when less than -0.50 
        elif axis == 2:  # L2 analog
            if value < -0.50:
                self.up_down_velocity = 0
            else:
                self.up_down_velocity = int((1 + value) * -50)
        elif axis == 5:  # R2 analog
            if value < -0.50:
                self.up_down_velocity = 0
            else:
                self.up_down_velocity = int((1 + value) * 50)

    def joystick_button_down(self, button):
        """ Update velocities based on joystick button press
        Arguments:
            coordinates: pygame event.button
        """
        if button == 2:  # Triangle/X
            self.get_ext_stat()

    def joystick_button_up(self, button):
        """ Update velocities based on joystick button released
        Arguments:
            coordinates: pygame event.button
        """
        if button == 4:  # left/right left analog
            try:
                self.tello.land()
                self.send_rc_control = False
            except Exception:
                pass
        elif button == 5:  # left/right left analog
            try:
                self.tello.takeoff()
                self.send_rc_control = True
            except Exception:
                pass
        elif button == 6:  # left/right left analog
            self.up_down_velocity = 0
        elif button == 7:  # left/right left analog
            self.up_down_velocity = 0
        elif button == 2:  # Triangle/X
            global drone_ext_stat
            drone_ext_stat = ''
        #History Handling
        elif button == 0:  # X/B
            self.history('display')
        elif button == 3:  # Square/Y
            self.history('apply')
        elif button == 1:  # Circle/A
            self.history('reset')
#-------------------
#EVENTS FUNCTIONS KEYBOARD
    def keydown(self, key):
        """ Update velocities based on key pressed
        Arguments:
            key: pygame key
        """
        if key == pygame.K_UP:  # set forward velocity
            self.for_back_velocity = S
        elif key == pygame.K_DOWN:  # set backward velocity
            self.for_back_velocity = -S
        elif key == pygame.K_LEFT:  # set left velocity
            self.left_right_velocity = -S
        elif key == pygame.K_RIGHT:  # set right velocity
            self.left_right_velocity = S
        elif key == pygame.K_w:  # set up velocity
            self.up_down_velocity = S
        elif key == pygame.K_s:  # set down velocity
            self.up_down_velocity = -S
        elif key == pygame.K_a:  # set yaw counter clockwise velocity
            self.yaw_velocity = -S
        elif key == pygame.K_d:  # set yaw clockwise velocity
            self.yaw_velocity = S
        elif key == pygame.K_y:  # Extended status clear
            self.get_ext_stat()
        #History Handling
        elif key == pygame.K_h:  # Display History
            self.history('display')
        elif key == pygame.K_j:  # Execute History
            self.history('apply')
        elif key == pygame.K_g:  # Clear History
            self.history('reset')

    def keyup(self, key):
        """ Update velocities based on key released
        Arguments:
            key: pygame key
        """
        if key == pygame.K_UP or key == pygame.K_DOWN:  # set zero forward/backward velocity
            self.for_back_velocity = 0
        elif key == pygame.K_LEFT or key == pygame.K_RIGHT:  # set zero left/right velocity
            self.left_right_velocity = 0
        elif key == pygame.K_w or key == pygame.K_s:  # set zero up/down velocity
            self.up_down_velocity = 0
        elif key == pygame.K_a or key == pygame.K_d:  # set zero yaw velocity
            self.yaw_velocity = 0
        elif key == pygame.K_t:  # takeoff
            try:
                self.tello.takeoff()
                self.send_rc_control = True
            except Exception:
                pass
        elif key == pygame.K_l:  # land
            try:
                self.tello.land()
                self.send_rc_control = False
            except Exception:
                pass
        elif key == pygame.K_p:  # Emergency - turn off propellers
            self.tello.emergency()
            self.send_rc_control = False
        elif key == pygame.K_y:  # Extended status clear
            global drone_ext_stat
            drone_ext_stat = ''
#-------------------
#Extended stats display
    def get_stats(self):
        # declare drone Stats
        battery_stat = '0'
        drone_stat = 'No data'

        # get drone_stats
        battery_stat = str(self.tello.get_battery())
        battery_stat = re.sub('[^A-Za-z0-9]+', '',  battery_stat)
        drone_stat = 'Battery: '+battery_stat+'%'
        return drone_stat
    
    def get_ext_stat(self):
        # declare drone extended Stats
        temp_stat = '0'
        height_stat = '0'
        flight_stat = '0'
        speed_stat = '0'
        barometer_stat = '0'
        global drone_ext_stat
        drone_ext_stat = ''

        # get drone extended Stats
        temp_stat = str(self.tello.get_temperature())
        temp_stat = re.sub('[^A-Za-z0-9~]+', '',  temp_stat)
        height_stat = str(self.tello.get_height())
        height_stat = re.sub('[^A-Za-z0-9]+', '',  height_stat)
        flight_stat = str(self.tello.get_flight_time())
        flight_stat = re.sub('[^A-Za-z0-9]+', '',  flight_stat)
        speed_stat = str(self.tello.get_speed())
        speed_stat = re.sub('[^A-Za-z0-9]+', '',  speed_stat)
        barometer_stat = str(self.tello.get_barometer())
        barometer_stat = re.sub('[^A-Za-z0-9.]+', '',  barometer_stat)
        drone_ext_stat = ' T: '+temp_stat+'°C H: '+height_stat+' t:'+flight_stat+' S: '+speed_stat+'cm/s Bar:'+barometer_stat+'cm'
#-------------------
#History
    def history(self, parameter):
        global np_commad_hist
        if parameter == 'apply':
            if self.send_rc_control:
                print('Applying history!')
                self.send_rc_control = False
                for row in np_commad_hist[::-1]:
                    reverse_row = row * -1
                    #print('command:', row, '| negative:', reverse_row)
                    self.tello.send_rc_control(int(reverse_row[0]),int(reverse_row[1]),int(reverse_row[2]),int(reverse_row[3]))
                    time.sleep(0.05)
                np_commad_hist = np.array([[0, 0, 0, 0]])
                self.send_rc_control = True
                print('History applied and cleared')
            else:
                print('takeoff first!!')
        elif parameter == 'reset':
            np_commad_hist = np.array([[0, 0, 0, 0]])
            print('History cleared')
        elif parameter == 'display':
            print('Reversed command list:')
            for row in np_commad_hist[::-1]:
                reverse_row = row * -1
                print('command:', row, '| negative:', reverse_row)
#-------------------
#RC Commands each frame if send_rc_control is True
    def update(self):
        """ Update routine. Send velocities to Tello."""
        if self.send_rc_control:
            #Run 0,0,0,0 rc commands only 5 times if repeated
            newrow = np.array([self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity]) #get values from rc command
            if (newrow == 0).all():
                if self.zero_rc_control <= 5:
                    self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)
                    self.zero_rc_control += 1
                else:
                    print (newrow, self.zero_rc_control)
            else:
                self.tello.send_rc_control(self.left_right_velocity, self.for_back_velocity, self.up_down_velocity, self.yaw_velocity)
                self.zero_rc_control = 0
            #Storing rc command history
            global np_commad_hist
            if not (newrow == 0).all():
                np_commad_hist = np.vstack([np_commad_hist, newrow])

###--------------------------------------------------------------
###MAIN
def main():
    frontend = FrontEnd()

    # run frontend
    frontend.run()

if __name__ == '__main__':
    main()
