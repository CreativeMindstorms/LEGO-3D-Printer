#!/usr/bin/env pybricks-micropython
from pybricks.parameters import Stop, Button
from pybricks.tools import wait
from printer import Printer

# Create a printer object
# This object is used to control the printer
printer = Printer(verbose=0, font_size=25)

# Main loop
while True:

    # Visual feedback
    printer.draw_centered_text("Y+", line=-2)
    printer.draw_centered_text("X-             X+", False)
    printer.draw_centered_text("Y-", False, +2)
    
    # X-Y mode
    while True:

        # Wait for button press
        while not printer.ev3.buttons.pressed(): wait(10)
        pressed_buttons = printer.ev3.buttons.pressed()
        
        # Move X motor based on button press
        if Button.LEFT in pressed_buttons:
            printer.x_motor.dc(-100)
            while printer.ev3.buttons.pressed(): wait(10)
            printer.x_motor.brake()
        elif Button.RIGHT in pressed_buttons:
            printer.x_motor.dc(100)
            while printer.ev3.buttons.pressed(): wait(10)
            printer.x_motor.brake()
        
        # Move Y motor based on button press
        if Button.UP in pressed_buttons:
            printer.y_motor.dc(100)
            while printer.ev3.buttons.pressed(): wait(10)
            printer.y_motor.brake()
        elif Button.DOWN in pressed_buttons:
            printer.y_motor.dc(-100)
            while printer.ev3.buttons.pressed(): wait(10)
            printer.y_motor.brake()

        # Switch to E-Z mode if CENTER button is pressed
        if Button.CENTER in pressed_buttons:
            while printer.ev3.buttons.pressed(): wait(10)
            break

    # Visual feedback
    printer.draw_centered_text("Z+", line=-2)
    printer.draw_centered_text("E-             E+", False)
    printer.draw_centered_text("Z-", False, +2)

    # E-Z mode
    while True:
        # Wait for button press
        while not printer.ev3.buttons.pressed(): wait(10)
        pressed_buttons = printer.ev3.buttons.pressed()
        
        # Move E motor based on button press
        if Button.LEFT in pressed_buttons:
            printer.e_motor.run_until_stalled(500, then=Stop.HOLD, duty_limit=40)
            while printer.ev3.buttons.pressed(): wait(10)
        elif Button.RIGHT in pressed_buttons:
            printer.e_motor.run_until_stalled(-500, then=Stop.BRAKE, duty_limit=40)
            while printer.ev3.buttons.pressed(): wait(10)
        
        # Move Z motor based on button press
        if Button.UP in pressed_buttons:
            printer.z_motor.dc(100)
            while printer.ev3.buttons.pressed(): wait(10)
            printer.z_motor.brake()
        elif Button.DOWN in pressed_buttons:
            printer.z_motor.dc(-100)
            while printer.ev3.buttons.pressed(): wait(10)
            printer.z_motor.brake()

        # Switch to X-Y mode if CENTER button is pressed
        if Button.CENTER in pressed_buttons:
            while printer.ev3.buttons.pressed(): wait(10)
            break