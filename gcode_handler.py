import os

class GCodeProcessor:
    """
    Handles finding G-code files and parsing actionable commands (G0, G1)
    for a MicroPython-based EV3 3D printer with a simple ON/OFF extruder (3D pen),
    assuming M82 absolute extrusion mode.
    Parses all G0/G1 commands, indicating if extrusion occurred during that specific move.
    Includes parameters present in the G-code line (X, Y, Z).
    G92 E commands are processed internally to track extrusion state but not returned.
    Looks within a 'models' subdirectory relative to the script's execution directory.
    Includes verbosity levels for logging to standard output.
    """
    # Define log levels
    LOG_ERROR = 0
    LOG_WARN = 0
    LOG_INFO = 1
    LOG_DEBUG = 2

    def __init__(self, models_subdir: str = 'models', gcode_extension: str = '.gcode', verbose: int = 1):
        """
        Initializes the GCodeProcessor. Verifies the 'models' directory exists.

        Args:
            models_subdir (str): The name of the subdirectory containing G-code files. Defaults to 'models'.
            gcode_extension (str): The file extension to look for. Defaults to '.gcode'.
            verbose (int): Logging verbosity level (0=Errors/Warn, 1=Info, 2=Debug). Defaults to 1.
        """

        # Initialize instance variables
        self.gcode_extension = gcode_extension.lower()
        self.models_dir = models_subdir
        self.models_dir_valid = False
        self.verbose = verbose

        # Initial state for extrusion tracking
        self.last_e_value = 0.0

        # Debugging output
        self._log(GCodeProcessor.LOG_DEBUG, "Looking for '{}' files in subdirectory: '{}' (relative to CWD)".format(self.gcode_extension, self.models_dir))

        # Check if the models directory exists and is valid
        if self._is_directory(self.models_dir):
            self._log(GCodeProcessor.LOG_DEBUG, "'{}' directory found and verified.".format(self.models_dir))
            self.models_dir_valid = True
        else:
            self._log(GCodeProcessor.LOG_ERROR, "Models directory '{}' is not valid. Please check path and permissions.".format(self.models_dir))
            self._log(GCodeProcessor.LOG_ERROR, "Please ensure a subdirectory named '{}' exists...".format(self.models_dir))
            self.models_dir_valid = False

        # Debugging output
        self._log(GCodeProcessor.LOG_INFO, "GCodeProcessor initialized.")

    def _log(self, level, message):
        """Internal logging function based on verbosity level."""

        # Print messages if verbosity level is sufficient
        if self.verbose >= level:
            print(message)

    def _is_directory(self, path):
        """Checks if a path points to a directory using os.stat."""
        try:
            stat_info = os.stat(path)
            return (stat_info[0] & 0o170000) == 0o040000
        except OSError as e:
            self._log(GCodeProcessor.LOG_ERROR, "Error accessing path '{}': {}".format(path, e))
            return False

    def _is_file(self, path):
        """Checks if a path points to a regular file using os.stat."""
        try:
            stat_info = os.stat(path)
            is_file = (stat_info[0] & 0o170000) == 0o100000
            if not is_file:
               self._log(GCodeProcessor.LOG_DEBUG, "Debug: Path '{}' exists but is not a regular file.".format(path))
            return is_file
        except OSError as e:
            self._log(GCodeProcessor.LOG_ERROR, "Error accessing path '{}' to check file status: {}".format(path, e))
            return False

    def find_gcode_files(self):
        """Scans the 'models' subdirectory for files with the .gcode extension."""

        # Check if the models directory is valid
        if not self.models_dir_valid: return []

        # Start with an empty list of G-code files
        gcode_files = []
        self._log(GCodeProcessor.LOG_DEBUG, "Scanning directory: {}...".format(self.models_dir))

        # Attempt to list files in the models directory
        try:
            items = os.listdir(self.models_dir)
            self._log(GCodeProcessor.LOG_DEBUG, "Items found: {}".format(items))

            # Go over every file in the directory
            for item in items:
                full_path = item if self.models_dir == '.' else self.models_dir + '/' + item
                
                # Check if the item ends with the G-code extension and is a valid file
                if item.lower().endswith(self.gcode_extension) and self._is_file(full_path):
                    self._log(GCodeProcessor.LOG_DEBUG, "  -> Match found: {}".format(item))

                    # If it is a valid G-code file, add it to the list
                    gcode_files.append(item)
        
        # Handle any errors that occur during directory scanning
        except OSError as e:
            self._log(GCodeProcessor.LOG_ERROR, "Error scanning directory '{}': {}".format(self.models_dir, e))
            return []

        # Debugging output
        if not gcode_files: self._log(GCodeProcessor.LOG_INFO, "No '{}' files found.".format(self.gcode_extension))
        else: self._log(GCodeProcessor.LOG_INFO, "Found {} G-code file(s).".format(len(gcode_files)))

        # Return the list of G-code files found
        return gcode_files

    def parse_line(self, gcode_line, line_number: int = 0):
        """
        Parses a single line of G-code, returning actionable commands (G0, G1).
        For G0/G1, includes only X, Y, Z parameters present in the line along with extrusion status for that move.
        G92 E commands update internal state but are not returned.

        Args:
            gcode_line (str): The raw line of text from the G-code file.
            line_number (int): The line number in the G-code file (for logging). Defaults to 0.

        Returns:
            dict: A dictionary describing the command if it's G0 or G1.
                  The dictionary contains:
                  - 'command': The G-code command ('G0' or 'G1').
                  - 'extruding': A boolean indicating if extrusion is happening (True/False).
                  - 'x': The X coordinate (if present).
                  - 'y': The Y coordinate (if present).
                  - 'z': The Z coordinate (if present).
                  The dictionary may look like:
                      {'command': str, 'extruding': Bool, 'x': float?, 'y': float?, 'z': float?}
            None: If the line is empty, a comment, G92, or any other unhandled command.
        """

        # Debugging output
        self._log(GCodeProcessor.LOG_DEBUG, "Parsing line: '{}'".format(gcode_line.strip()))

        # Clean the line and check for empty lines/comments
        if ';' in gcode_line: gcode_line = gcode_line.split(';', 1)[0]
        cleaned_line = gcode_line.strip()

        # Ignore empty lines or comments
        if not cleaned_line: return None

        # Parse command and parameters
        parts = cleaned_line.split()
        if not parts: return None

        # Extract the command and parameters into a dictionary
        command = parts[0].upper()
        raw_params = {}
        try:
            for part in parts[1:]:
                part = part.strip()
                if len(part) >= 2:
                    param_code = part[0].upper()
                    if 'A' <= param_code <= 'Z':
                        param_value = float(part[1:])
                        raw_params[param_code] = param_value
                        self._log(GCodeProcessor.LOG_DEBUG,"  -> Parsed raw param: {} = {}".format(param_code, param_value))

        # Handle any parsing errors
        # This may happen if the G-code line is malformed or contains unexpected characters
        # For example, if a parameter is not a number or is missing
        except ValueError as e:
            self._log(GCodeProcessor.LOG_WARN, "Warning: Value parse error in '{}'. Error: {}. Skipping part.".format(cleaned_line, e))

        # Handle movement commands (G0, G1)
        if command in ('G0', 'G1'):
            
            # Initialize dictionary with mandatory fields
            # The actual extrusion state will be determined later
            parsed_data = {
                'command': command,
                'extruding': False
            }

            # Add X, Y, Z only if they exist in the command line
            if 'X' in raw_params: parsed_data['X'] = raw_params['X']
            if 'Y' in raw_params: parsed_data['Y'] = raw_params['Y']
            if 'Z' in raw_params: parsed_data['Z'] = raw_params['Z']

            # Get the E value from the command line if it exists
            current_e = raw_params.get('E', None)
            if current_e is not None:
                
                # Extrusion happens if E is present and greater than the last E value
                if current_e > self.last_e_value:
                    parsed_data['extruding'] = True
                    
                    # Update the last E value to this new bigger value
                    self.last_e_value = current_e

                    # Debugging output
                    self._log(GCodeProcessor.LOG_DEBUG,"  -> Extrusion detected: {} (last E: {})".format(current_e, self.last_e_value))

            # Debugging output
            self._log(GCodeProcessor.LOG_DEBUG,"  -> Parsed G0/G1 Data: {}".format(parsed_data))

            # Return the parsed data
            return parsed_data

        # Handle G92 command (set position)
        elif command == 'G92':

            # Get the E value from the command line if it exists
            new_e = raw_params.get('E', None)
            if new_e is not None:

                # Debugging output
                self._log(GCodeProcessor.LOG_INFO,"  Line {}: RESET -> G:92 E:{}".format(line_number, new_e))
                self._log(GCodeProcessor.LOG_DEBUG,"  -> Resetting internal E tracker...".format(line_number, new_e))

                # Update the last E value to this new value
                self.last_e_value = new_e

            # Do nothing if E is not present
            else:
                 self._log(GCodeProcessor.LOG_DEBUG,"  Line {}: Parsed empty G92 (non-E params).".format(line_number))

            # Do not return G92
            return None

        # If the command is not G0, G1, or G92, None is returned
        else:
            self._log(GCodeProcessor.LOG_DEBUG,"  -> Skipping unhandled/non-actionable command: {}".format(command))
            return None
