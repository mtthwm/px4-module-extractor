# import argparse

# parser = argparse.ArgumentParser(
#     prog="PX4 Module Extractor",  
#     description="Returns a list of all the modules used by a given PX4 configuration"
# )

# parser.add_argument("-v", "")

import os
from typing import List, Any, Dict, Callable
import re

def find_scripts (dirname: str, identifier: str = "#!/bin/sh"):
    script_names: List[str] = []

    for filename in os.listdir(dirname):
        filepath = os.path.join(dirname, filename)
        if os.path.isfile(filepath):
            with open(filepath, "r") as file:
                if file.readline().strip() == identifier:
                    script_names.append(filepath)

    return script_names

class ParserState:
    skip = False
    indentation_level = 0
    last_executed_indentation_level = 0

class StatementHandler:
    def execute (self, match: re.Match, state: ParserState) -> None:
        pass
    
    def unconditional (self, match: re.Match, state: ParserState) -> None:
        pass

def parse_script (filepath: str, statement_handlers: Dict[str, StatementHandler]):
    state = ParserState()
    with open(filepath, "r") as file:
        for raw_line in file:
            line = raw_line.strip()

            if not line:
                continue # skip whitespace

            if line.startswith("#"):
                continue # skip comments

            for pattern in statement_handlers.keys():
                reg_compiled = re.compile(pattern)
                reg_match = re.search(reg_compiled, line)
                if reg_match:
                    statement_handlers[pattern].unconditional(reg_match, state)
                    if not state.skip:
                        statement_handlers[pattern].execute(reg_match, state)
                    break

def infer_type (str_val: str) -> float | str:
    try:
        return float(str_val)
    except:
        pass

    return str_val

def main ():
    # Configurable Parameters
    px4_dir = "/home/matt/Src/PX4-Autopilot/"
    is_posix = False
    board_vendor = "raspberrypi"
    board_model = "pico"
    airframe = "4901_crazyflie21"
    vehicle="mc" #balloon, fw, uuv, mc, etc.

    # Useful Globals
    build_dir = os.path.join(px4_dir, "build")
    init_scripts_dir = os.path.join(px4_dir, f"ROMFS/px4fmu_common/init.d{".posix" if is_posix else ""}")
    boards_dir = os.path.join(px4_dir, "boards")

    # Parser vars/functions
    set_params = {}
    started_mods = set()

    class handle_set_param (StatementHandler):
        def execute (self, match: re.Match[str], state: ParserState):
            param_name = match.group("param_name")
            param_val = match.group("param_val")
            set_params[param_name] = infer_type(param_val)

    class handle_set_default_param (StatementHandler):
        def execute (self, match: re.Match[str], state: ParserState):
            param_name = match.group("param_name")
            param_val = match.group("param_val")
            if not set_params.get(param_name, False):
                set_params[param_name] = infer_type(param_val)

    class handle_start_module (StatementHandler):
        def execute (self, match: re.Match[str], state: ParserState):
            module_name = match.group("module_name")
            started_mods.add(module_name)

    class handle_if (StatementHandler):
        def unconditional(self, match: re.Match, state: ParserState) -> None:
            state.indentation_level += 1

        def _comparison (self, match: re.Match[str]) -> bool:
            op = match.group("operator")
            param_name = match.group("param_name")
            param_val = infer_type(match.group("param_val"))

            if not set_params.get(param_name, False):
                return False

            if op == "greater":
                return set_params[param_name] > param_val
            elif op == "compare":
                return set_params[param_name] == param_val
            
            return False

        def _resolve_condition (self, condition: str) -> bool:
            condition_handlers = {
                r"^param (?P<operator>(greater)|(compare))\s(.+\s)*(?P<param_name>\w+)\s(?P<param_val>\w+)$": self._comparison,
            }

            for pattern in condition_handlers:
                m = re.search(re.compile(pattern), condition)
                if m:
                    return condition_handlers[pattern](m)
                
            return False

        def execute (self, match: re.Match[str], state: ParserState):
            result = self._resolve_condition(match.group("condition")) # TODO: Try to infer this value

            if not result:
                state.skip = True
                state.last_executed_indentation_level = state.indentation_level - 1

    class handle_else (StatementHandler):
        def unconditional(self, match: re.Match, state: ParserState) -> None:
            state.skip = not state.skip

    class handle_fi (StatementHandler):
        def unconditional(self, match: re.Match, state: ParserState) -> None:
            state.indentation_level -= 1

            if state.skip and (state.indentation_level == state.last_executed_indentation_level):
                state.skip = False

    class handle_script_execution (StatementHandler):
        def execute(self, match: re.Match, state: ParserState) -> None:
            filepath = os.path.join(init_scripts_dir, match.group("filename"))
            if os.path.exists(filepath):
                parse_script(filepath, handlers)


    handlers = {
        r"^param set (?P<param_name>\w+)\s(?P<param_val>\w+).*$": handle_set_param(),
        r"^param set-default (?P<param_name>\w+)\s(?P<param_val>\w+).*$": handle_set_default_param(),
        r"^(?P<module_name>\w+)\sstart.*$": handle_start_module(),
        r"^if (?P<condition>.+)$": handle_if(),
        r"^fi$": handle_fi(),
        r"^else$": handle_else(),
        r"^\.\s(.+\/)+(?P<filename>.+)$": handle_script_execution(),
    }

    # Step 1: Find the initialization scripts for the board we are using and add their parameters/started modules
    board_dir = os.path.join(boards_dir, board_vendor, board_model, "init")
    board_init_scripts = find_scripts(board_dir)

    for script in board_init_scripts:
        parse_script(script, handlers)

    # Step 2: rcS script 
    rcSFile = os.path.join(init_scripts_dir, "rcS")
    parse_script(rcSFile, handlers)

    # Step 3: Vehicle type-specific initialization files
    vehicle_scripts = find_scripts(init_scripts_dir)
    
    for script in vehicle_scripts:
        if re.match(rf"rc.({vehicle})\w+", os.path.basename(script)):
            parse_script(script, handlers)

    print(",".join(started_mods))
    print()
    print(set_params)


if __name__ == "__main__":
    main()