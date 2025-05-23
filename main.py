#!/usr/bin/env pybricks-micropython

from pybricks.parameters import Button
from pybricks.tools import wait

# Module imports
from gcode_handler import GCodeProcessor
from printer import Printer

# Verbosity controls how much information is printed to the console
# 0 = Only errors
# 1 = Basic output
# 2 = Detailed output
VERBOSE = 0

# Initialize the GCodeProcessor and Printer classes
# The GCodeProcessor handles the parsing of G-code files
# The Printer class handles the physical printing process
processor = GCodeProcessor(verbose=VERBOSE)
printer = Printer(verbose=VERBOSE)

# Get the list of G-code files in the models directory
# The models directory is set in the GCodeProcessor class
available_files = processor.find_gcode_files()
if available_files:
    if VERBOSE > 0:
        print("\nAvailable G-code files:")
        for i, file_name in enumerate(available_files): print("{}: {}".format(i + 1, file_name))
        print()

    # Display available files on the EV3 screen in a selection menu
    if len(available_files) > 0:
        selected_file_index = printer.file_selector(available_files)
    
    # If no files are found, exit
    else:
        if VERBOSE > 0: print("No files found.")
        printer.draw_centered_text("No files found.")
        printer.ev3.speaker.beep()
        while not printer.ev3.buttons.pressed(): wait(100)
        exit()

    # If a file is selected, process it
    if 0 <= selected_file_index < len(available_files):
        selected_file = available_files[selected_file_index]
        if VERBOSE > 0: print("\nSelected file: {}".format(selected_file))
        full_path = selected_file if processor.models_dir == '.' else processor.models_dir + '/' + selected_file

        # Try reading the G-code file
        # If there is an error reading the file, exit
        try:
            with open(full_path, 'r') as f:
                lines = f.readlines()
        except OSError as e:
            print("\nError reading file '{}': {}".format(full_path, e))
            exit()

        # Initialize printer state
        current_x, current_y, current_z = 0.0, 0.0, 0.0

        # Prompt to prime the extruder
        printer.prime_extruder()

        # Auto Home
        printer.home()
        current_x, current_y, current_z = 0.0, 0.0, 0.0

        # Initialize main loop to print the G-code file
        line_count = 0
        total_lines = len(lines)
        printer.draw_centered_text("Printing...", line=-1)
        printer.draw_centered_text("{}%".format(int(line_count/total_lines*100)), False, 1)

        # Loop through each line of the G-code file
        # The line count is used to track the progress of the print
        for line in lines:
            line_count += 1

            # Stop the program if the center button is pressed
            if printer.ev3.buttons.pressed() == [Button.CENTER]:
                printer.draw_centered_text("Stopped.")
                printer.ev3.speaker.beep()
                while printer.ev3.buttons.pressed():
                    wait(100)
                break

            # Parse the line using the GCodeProcessor
            # The parsed output contains the command and parameters
            # Valid commands are G0 and G1 (movement commands)
            # G92 commands are handled by the GCodeProcessor but not returned (they are useful to determine whether to extrude or not)
            parsed_output = processor.parse_line(line, line_count)

            # If the line is not empty and contains a valid command (G0/G1), execute it
            if parsed_output:

                # Retrieve the target coordinates and extrusion status
                # If the coordinates are not present, use the current position
                target_x = parsed_output.get('X', current_x)
                target_y = parsed_output.get('Y', current_y)
                target_z = parsed_output.get('Z', current_z)
                should_extrude = parsed_output['extruding'] # Always present

                # Debugging output
                if VERBOSE > 0:
                    print("  Line {}: MOVE -> ".format(line_count), end="")
                    if 'X' in parsed_output: print("X:{:.3f} ".format(target_x), end="")
                    if 'Y' in parsed_output: print("Y:{:.3f} ".format(target_y), end="")
                    if 'Z' in parsed_output: print("Z:{:.3f} ".format(target_z), end="")
                    print("Extruding:{}".format(should_extrude))

                # Control Extruder (Pen ON)
                if should_extrude: printer.extrude(should_extrude)

                # Move to the target position
                printer.move(target_x, target_y, target_z, current_x, current_y, current_z, command=parsed_output['command'])

                # Control Extruder (Pen OFF)
                if not should_extrude: printer.extrude(should_extrude)

                # Update current position state after move
                current_x = target_x
                current_y = target_y
                current_z = target_z

                # Update progress display only if not extruding, to avoid delays
                if not should_extrude:
                    printer.draw_centered_text("Printing...", line=-1)
                    printer.draw_centered_text("{}%".format(int(line_count/total_lines*100)), False, 1)                        
        
        # Ensure extruder is off after the print is finished
        printer.extrude(False)

        # Display completion message
        if VERBOSE > 0: print("\nFinished processing file '{}'.".format(selected_file))
        if VERBOSE > 1: print("Total lines read: {}/{}".format(line_count,total_lines))

        # Move the extruder out of the way
        printer.present_print()

    # If the file selection index is somehow invalid, print an error message
    else:
        print("\nError: Invalid file selection index.")