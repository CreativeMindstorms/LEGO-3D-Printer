from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, TouchSensor
from pybricks.parameters import Port, Stop, Direction, Button
from pybricks.media.ev3dev import Font
from pybricks.tools import wait
from math import sqrt

class Printer:
    """
    A class to manage the printer's display and control its motors and sensors.
    This class provides methods to initialize the printer, control the motors, handle user input, and manage the printer's state.
    It uses the Pybricks library to interface with the EV3 brick and its components.
    The printer has motors for X, Y, Z axes and an extruder, as well as touch sensors for homing the axes.
    The class also provides methods to display messages on the EV3 screen and handle user interactions.
    """
    # Define log levels
    LOG_ERROR = 0
    LOG_WARN = 0
    LOG_INFO = 1
    LOG_DEBUG = 2

    def __init__(self, verbose: int = 0, font_size: int = 15):
        """
        Initializes the Printer.
        Sets up the motors, sensors, and display for the printer.

        Args:
            verbose (int):   An integer for verbosity level (0=Errors/Warn, 1=Info, 2=Debug).
                             Defaults to 0 (no debug output).
            font_size (int): An integer for the font size to be used on the display.
                             Defaults to 15.
        """
        # --- Define motor variables ---

        # Printing speed (G1)
        self.xy_speed = 90
        self.z_speed = 1000
        self.e_speed = 500

        # Maximum speed multiplier for XY motors
        # This is used for rapid movements (G0)
        self.max_xy_speed_multiplier = 3

        # Millimeters per degree of rotation for each axis
        # These values are used to convert the values in the gcode file from millimeters to degrees
        self.x_mm_per_degree = 4/45
        self.y_mm_per_degree = 4/45
        self.z_mm_per_degree = 8/45

        # Axis limits in millimeters
        # These values are used to determine the presenting position of the printer (finished print)
        self.y_limit = 141
        self.z_limit = 152

        # Multiplier for acceleration
        # This is used to increase the acceleration of the motors and achieve more linear movements
        # This ensures consistent extrusion and better print quality
        acceleration_multiplier = 5

        # Multiplier for target tolerances
        # This is used to decrease the requirements for the code to know when the motors are done moving
        # A higher value means new commands can be sent sooner, leading to less blobbing at ends of lines and more continuous movement
        # A lower value means that the motors really have to stop (stand still) at each target destination before the next command is sent
        target_tolerance_multiplier = 2

        # --- End of motor variables ---

        # Define wait time for priming the extruder in seconds
        # This is the time the printer will wait after priming the extruder before starting the print
        # It is used to allow the nozzle to heat up
        self.wait_time = 35

        # Initialize parameters
        self.font_size = font_size
        self.verbose = verbose

        # Initialize ev3 brick
        self.ev3 = EV3Brick()

        # Initialize motors and sensors
        self.x_motor = Motor(Port.A, Direction.CLOCKWISE, gears=[20, 28])
        self.y_motor = Motor(Port.B, Direction.COUNTERCLOCKWISE, gears=[24, 40])
        self.z_motor = Motor(Port.C, Direction.COUNTERCLOCKWISE, gears=[[12,20],[1, 24]])
        self.e_motor = Motor(Port.D, Direction.COUNTERCLOCKWISE)

        self.x_sensor = TouchSensor(Port.S1)
        self.y_sensor = TouchSensor(Port.S2)
        self.z_sensor = TouchSensor(Port.S3)

        # Debug messages for motor limits and target tolerances
        self._log(Printer.LOG_DEBUG, "Initial Max XY-motors speed and acceleration, given gears: X{}, Y{}".format(self.x_motor.control.limits()[:2],self.y_motor.control.limits()[:2]))
        self._log(Printer.LOG_DEBUG, "Initial Max Z-motor speed and acceleration, given gears: {}".format(self.z_motor.control.limits()[:2]))
        self._log(Printer.LOG_DEBUG, "Initial Max E-motor speed, given gears: {}".format(self.e_motor.control.limits()))
        self._log(Printer.LOG_DEBUG, "Initial X Target tolerances: {}".format(self.x_motor.control.target_tolerances()))
        self._log(Printer.LOG_DEBUG, "Initial Y Target tolerances: {}".format(self.y_motor.control.target_tolerances()))

        # Set motor speed and acceleration limits
        x_speed,x_acc,x_act = self.x_motor.control.limits()
        y_speed,y_acc,y_act = self.y_motor.control.limits()
        new_speed = min(x_speed, y_speed)
        new_acc = min(x_acc, y_acc) * acceleration_multiplier
        self.x_motor.control.limits(new_speed, new_acc, x_act)
        self.y_motor.control.limits(new_speed, new_acc, y_act)

        # Adjust target tolerances
        _,tolerance = self.x_motor.control.target_tolerances()
        self.x_motor.control.target_tolerances(self.xy_speed, tolerance*target_tolerance_multiplier)
        _,tolerance = self.y_motor.control.target_tolerances()
        self.y_motor.control.target_tolerances(self.xy_speed, tolerance*target_tolerance_multiplier)

        # Debug messages for updated motor limits and target tolerances
        self._log(Printer.LOG_DEBUG, "Updated Max XY-motors speed and acceleration, given gears: X{}, Y{}".format(self.x_motor.control.limits()[:2],self.y_motor.control.limits()[:2]))
        self._log(Printer.LOG_DEBUG, "Updated Max Z-motor speed and acceleration, given gears: {}".format(self.z_motor.control.limits()[:2]))
        self._log(Printer.LOG_DEBUG, "Updated Max E-motor speed, given gears: {}".format(self.e_motor.control.limits()))
        self._log(Printer.LOG_DEBUG, "Updated X Target tolerances: {}".format(self.x_motor.control.target_tolerances()))
        self._log(Printer.LOG_DEBUG, "Updated Y Target tolerances: {}".format(self.y_motor.control.target_tolerances()))

        # Initialize display
        self.screen = self.ev3.screen
        self.font = Font(size=self.font_size, bold=False)
        self.screen.set_font(self.font)

        # Initialize printer state
        self.extruding = False

        # Start with a clear screen
        self.screen.clear()

        # Debug message for initialization
        self._log(Printer.LOG_INFO, "Printer initialized.")

    def _log(self, level, message):
        """Internal logging function based on verbosity level (prints to stdout)."""
        if self.verbose >= level:
            print(message)

    def file_selector(self, available_files: list):
        """
        Displays a file selector on the EV3 screen for G-code files.
        Lists and selects G-code files from a specific directory using the display and buttons.

        Args:
            available_files (list): A list of G-code files to display and select from.
        """
        def draw_file(file_name: str):
            """Helper function to draw the selected file name on the screen."""
            self.draw_centered_text("Select file:", line=-2)
            self.draw_centered_text(file_name, False)

        selected_file_index = 0
        draw_file(available_files[selected_file_index])
        while True:
            # Wait for button press
            while not self.ev3.buttons.pressed(): wait(100)
            pressed_buttons = self.ev3.buttons.pressed()
            
            if Button.LEFT in pressed_buttons:
                # Move to the previous file
                selected_file_index = (selected_file_index - 1) % len(available_files)
                draw_file(available_files[selected_file_index])
                while self.ev3.buttons.pressed(): wait(100)
            elif Button.RIGHT in pressed_buttons:
                # Move to the next file
                selected_file_index = (selected_file_index + 1) % len(available_files)
                draw_file(available_files[selected_file_index])
                while self.ev3.buttons.pressed(): wait(100)
            elif Button.CENTER in pressed_buttons:
                # Select the current file
                self.draw_centered_text("Selected:", line=-2)
                self.draw_centered_text(available_files[selected_file_index], False)
                self.ev3.speaker.beep(750, 50)
                wait(50)
                self.ev3.speaker.beep(1000, 50)
                while self.ev3.buttons.pressed(): wait(100)
                return selected_file_index

    def draw_centered_text(self, text: str, do_clear: bool = True, line: int = 0):
        """
        Clears the screen and draws the provided text string centered
        both horizontally and vertically on the EV3 display.

        Args:
            text (str): The string message to display.
            do_clear (bool): A boolean indicating whether to clear the screen before drawing.
                    Defaults to True.
            line (int): The line number to display the text on
                    Negative is above center, positive is below center.
        """
        # 1. Clear the screen before drawing new text
        if do_clear: self.screen.clear()

        # 2. Get screen dimensions
        screen_width = self.screen.width  # Typically 178 pixels
        screen_height = self.screen.height # Typically 128 pixels

        # 3. Calculate text dimensions using the current font
        try:
            text_width_pixels = self.font.text_width(text)
        except Exception as e:
            self._log(Printer.LOG_WARN, "Warning: Could not get text dimensions: {}".format(e))
            text_width_pixels = len(text) * 8 # Rough estimate

        # 4. Calculate top-left coordinates (x, y) for centering
        x = (screen_width - text_width_pixels) // 2
        y = (screen_height - self.font_size) // 2 + (line * self.font_size)

        # Ensure coordinates are not negative (e.g., if text is too wide)
        x = max(0, x)
        y = max(0, y)

        # 5. Draw the text at the calculated position
        self.screen.draw_text(x, y, text)
        self._log(Printer.LOG_DEBUG, "Drew text: '{}' at ({}, {})".format(text, x, y))

    def _start_extruding(self):
        """
        Starts the extruder.
        """
        # Run the extruder motor against the extruder button until it is stalled
        self.e_motor.run_until_stalled(self.e_speed, then=Stop.HOLD, duty_limit=40)

        # Wait for the button press to be registered
        wait(450)

    def _stop_extruding(self):
        """
        Stops the extruder.
        """
        # Run the extruder motor away from the extruder button until it is stalled
        self.e_motor.run_until_stalled(-self.e_speed, then=Stop.BRAKE, duty_limit=40)

    def extrude(self, extrude: bool):
        """
        Controls the extruder state (extruding or retracting).

        Args:
            extrude (bool): A boolean indicating whether to extrude or retract.
        """

        # Only start extruding if previously not extruding
        if extrude and not self.extruding:
            self._log(Printer.LOG_INFO, "  -> Starting Extruding...")
            self.extruding = True
            self._start_extruding()

        # Only stop extruding if previously extruding
        elif not extrude and self.extruding:
            self._log(Printer.LOG_INFO, "  -> Stopping Extruding...")
            self.extruding = False
            self._stop_extruding()

    @staticmethod
    def _calculate_velocity_components(current_x, current_y, target_x, target_y, target_speed):
        """
        Calculates the x and y velocity components to move towards a target
        at a constant speed.

        Args:
            current_x: The current x-coordinate.
            current_y: The current y-coordinate.
            target_x: The target x-coordinate.
            target_y: The target y-coordinate.
            target_speed: The desired constant speed.

        Returns:
            A tuple (vx, vy) representing the velocity components.
            Returns (0, 0) if already at the target.
        """
        # Calculate the difference in coordinates
        dx = target_x - current_x
        dy = target_y - current_y

        # Calculate the distance to the target
        distance = sqrt(dx*dx + dy*dy)

        # If the distance is very small, return (0, 0) to indicate no movement needed
        if distance < 0.05:
            return (0.0, 0.0)

        # Normalize the direction vector and scale by speed
        inv_distance = 1.0 / distance
        vx = dx * inv_distance * target_speed
        vy = dy * inv_distance * target_speed

        # If the speed is very small, set it to 0
        if abs(dx) < 0.05: vx = 0
        if abs(dy) < 0.05: vy = 0

        # Return the velocity components
        return (vx, vy)

    def move(self, x: float, y: float, z: float, prev_x: float, prev_y: float, prev_z: float, command: str = "G1"):
        """
        Moves the printer to the specified coordinates (x, y, z).

        Args:
            x (float): Target X coordinate.
            y (float): Target Y coordinate.
            z (float): Target Z coordinate.
            prev_x (float): Previous X coordinate.
            prev_y (float): Previous Y coordinate.
            prev_z (float): Previous Z coordinate.
            command (str): The G-code command (G0 or G1). Defaults to "G1".
        """
        # Debugging output
        self._log(Printer.LOG_INFO, "  -> Target (mm): ({:.3f}, {:.3f}, {:.3f})".format(x, y, z))

        # Determine motor speeds
        if command == "G1": x_speed, y_speed = self._calculate_velocity_components(prev_x, prev_y, x, y, self.xy_speed)
        elif command == "G0": x_speed, y_speed = self._calculate_velocity_components(prev_x, prev_y, x, y, self.xy_speed*self.max_xy_speed_multiplier)

        # Convert to degrees
        x = int(x / self.x_mm_per_degree)
        y = int(y / self.y_mm_per_degree)
        z = int(z / self.z_mm_per_degree)

        # Log the calculated values
        self._log(Printer.LOG_DEBUG, "  -> Calculated speeds (degrees/s): (X:{:.3f}, Y:{:.3f})".format(x_speed, y_speed))
        self._log(Printer.LOG_DEBUG, "  -> Target (degrees): ({:.3f}, {:.3f}, {:.3f})".format(x, y, z))

        # If the target Z is higher than the previous Z, move up first
        if z > prev_z:
            self.z_motor.run_target(self.z_speed, z, then=Stop.BRAKE, wait=True)

        # Wait for motors to finish previous tasks
        while not (self.x_motor.control.done() and self.y_motor.control.done()) and not Button.CENTER in self.ev3.buttons.pressed(): wait(5)

        # Move in XY plane if the movement is significant
        if abs(x_speed) > 2 and abs(self.x_motor.angle()-x) > 2:
            self._log(Printer.LOG_DEBUG, "    -> Moving X-axis to {} degrees.".format(x))
            self.x_motor.run_target(x_speed, x, then=Stop.HOLD, wait=False)
        if abs(y_speed) > 2 and abs(self.y_motor.angle()-y) > 2:
            self._log(Printer.LOG_DEBUG, "    -> Moving Y-axis to {} degrees.".format(y))
            self.y_motor.run_target(y_speed, y, then=Stop.HOLD, wait=False)

        # If the target Z is lower than the previous Z, move down last
        if z < prev_z:
            self.z_motor.run_target(self.z_speed, z, then=Stop.BRAKE, wait=True)

    def prime_extruder(self):
        """
        Opens a selection menu for the user to prime the extruder.
        Also primes the extruder if the user confirms.
        """
        # Prompt the user to prime the extruder
        self.draw_centered_text("Is the pen ready?", line=-1)
        self.draw_centered_text("YES            NO", False, 1)

        # Wait for button press
        while not self.ev3.buttons.pressed(): wait(100)

        # Prime the extruder if the user presses the right button
        if Button.RIGHT in self.ev3.buttons.pressed():
            self._log(Printer.LOG_INFO, "  -> Priming Extruder...")

            # Press the extruder button once
            self._start_extruding()
            self._stop_extruding()

            # Wait for 35 seconds to prime the extruder, updating the display with the countdown
            for i in range(self.wait_time):
                self.draw_centered_text("Heating Nozzle...", line=-1)
                self.draw_centered_text("{} seconds left".format(self.wait_time - i), False, 1)
                wait(1000)
                if Button.CENTER in self.ev3.buttons.pressed():
                    break
        
        # Ensure the extruder is turned off if the user presses any other button
        else:
            self._stop_extruding()

        # Visual feedback for priming completion
        self._log(Printer.LOG_DEBUG, "  -> Extruder primed.")
        self.draw_centered_text("Extruder primed.")
        wait(1000)
        self.screen.clear()

    def home(self):
        """
        Resets the printer's position to the home coordinates (0, 0, 0) using touch sensors.
        """
        # After touching the sensors, the Z-axis is offset to a position above the print area first
        # After this, the X and Y axis are offset, after which the Z-axis is offset down onto the print area
        # The following values can be adjusted to fit the printer's design
        # The values are in degrees and the Z-axis ends up at (Z_offset_up + Z_offset_down)
        Z_offset_up = 18
        X_offset = 290
        Y_offset = 0
        Z_offset_down = -11.25

        # Display a message indicating the start of the homing sequence
        self._log(Printer.LOG_INFO, "  -> Executing Homing Sequence...")
        self.draw_centered_text("Homing axes...")

        # This is the sequence used for both the X and Y axes
        def home_xy(motor, sensor):

            # Move towards the sensor
            motor.run(-2.5 * self.xy_speed)

            # Wait until the sensor is pressed
            while not sensor.pressed():
                wait(5)

            # Move back a little for a second touch
            motor.brake()
            motor.run_angle(self.xy_speed, 45, then=Stop.BRAKE, wait=True)

            # Move towards the sensor again, slowly
            motor.run(-0.5 * self.xy_speed)

            # Wait until the sensor is pressed
            while not sensor.pressed():
                wait(5)

            # Stop the motor
            motor.hold()

        # A function to move the motor to a specific offset, which is the zero position
        def offset(motor, offset: int, speed = self.xy_speed):
            # Move the motor to the offset position only if necessary
            if offset != 0:
                motor.run_angle(speed, offset, then=Stop.HOLD, wait=True)
                wait(500)

            # Reset the motor angle to zero
            motor.reset_angle(0)
            motor.stop()
        
        # This is the sequence used for the Z axis
        def home_z(motor, sensor):

            # Move towards the sensor
            motor.run(-self.z_speed)

            # Wait until the sensor is pressed
            while not sensor.pressed():
                wait(5)

            # Move back a little for a second touch
            motor.brake()
            motor.run_angle(self.z_speed, 8, then=Stop.BRAKE, wait=True)

            # Move towards the sensor again, slowly
            motor.run(-0.25 * self.z_speed)

            # Wait until the sensor is pressed
            while not sensor.pressed():
                wait(5)
            
            # Stop the motor
            motor.hold()
        
        # Execute the homing sequence for each axis
        home_xy(self.x_motor, self.x_sensor)
        home_xy(self.y_motor, self.y_sensor)
        home_z(self.z_motor, self.z_sensor)

        # Offset the motors to their zero positions
        offset(self.z_motor, Z_offset_up, self.z_speed)
        offset(self.x_motor, X_offset)
        self._log(Printer.LOG_DEBUG, "  -> X-axis homed.")
        offset(self.y_motor, Y_offset)
        self._log(Printer.LOG_DEBUG, "  -> Y-axis homed.")
        offset(self.z_motor, Z_offset_down, self.z_speed)
        self._log(Printer.LOG_DEBUG, "  -> Z-axis homed.")

        # Debugging output
        self._log(Printer.LOG_DEBUG, "  -> Positions reset to (0.0, 0.0, 0.0).")
    
    def present_print(self):
        """
        Moves the z-axis to a position above the print area and moves the bed forward.
        Displays a message indicating that the print is complete.
        """
        # Stop the motors
        self.x_motor.brake()
        self.y_motor.brake()
        self.z_motor.brake()

        # Display a message and make a sound indicating the end of the print
        self.draw_centered_text("Print complete!", line = -1)
        self.ev3.speaker.beep(750, 50)
        wait(50)
        self.ev3.speaker.beep(1000, 50)

        # Move the Z-axis 10mm up to a position above the print, but within the limits
        z_position = min(self.z_motor.angle() + (10 / self.z_mm_per_degree), self.z_limit / self.z_mm_per_degree)
        self.z_motor.run_target(self.z_speed, z_position, then=Stop.BRAKE, wait=True)
        self._log(Printer.LOG_DEBUG, "  -> Moved Z-axis to {} degrees.".format(z_position))
        self._log(Printer.LOG_DEBUG, "  -> Moved Z-axis to {} mm.".format(z_position * self.z_mm_per_degree))

        # Move the X-axis to its zero position
        self.x_motor.run_target(self.max_xy_speed_multiplier * self.xy_speed, 0, then=Stop.BRAKE, wait=True)
        self._log(Printer.LOG_DEBUG, "  -> Moved X-axis")

        # Move the Y-axis to its limit position
        self.y_motor.run_target(self.max_xy_speed_multiplier * self.xy_speed, self.y_limit / self.y_mm_per_degree, then=Stop.BRAKE, wait=True)
        self._log(Printer.LOG_DEBUG, "  -> Moved Y-axis")

        # Wait for the user to press a button to exit
        self.draw_centered_text("Press any button to exit.", False, 1)
        while not self.ev3.buttons.pressed(): wait(100)
        self.screen.clear()