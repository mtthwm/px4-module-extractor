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
    airframe = ""

    # Useful Globals
    build_dir = os.path.join(px4_dir, "build")
    init_scripts_dir = os.path.join(px4_dir, f"ROMFS/px4fmu_common/init.d{".posix" if is_posix else ""}")
    boards_dir = os.path.join(px4_dir, "boards")
    params_set = {}

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
            if not params_set.get(param_name, False):
                set_params[param_name] = infer_type(param_val)

    class handle_start_module (StatementHandler):
        def execute (self, match: re.Match[str], state: ParserState):
            module_name = match.group("module_name")
            started_mods.add(module_name)

    class handle_if (StatementHandler):
        def unconditional(self, match: re.Match, state: ParserState) -> None:
            state.indentation_level += 1

        def execute (self, match: re.Match[str], state: ParserState):
            result = False # TODO: Try to infer this value

            if not result:
                state.skip = True
                state.last_executed_indentation_level = state.indentation_level - 1

    class handle_fi (StatementHandler):
        def unconditional(self, match: re.Match, state: ParserState) -> None:
            state.indentation_level -= 1

            if state.skip and (state.indentation_level == state.last_executed_indentation_level):
                state.skip = False


    handlers = {
        r"^param set (?P<param_name>\w+)\s(?P<param_val>\w+).*$": handle_set_param(),
        r"^param set-default (?P<param_name>\w+)\s(?P<param_val>\w+).*$": handle_set_default_param(),
        r"^(?P<module_name>\w+)\sstart.*$": handle_start_module(),
        r"^if (?P<condition>.+)$": handle_if(),
        r"^fi$": handle_fi(),
    }

    # Step 1: Find the initialization scripts for the board we are using and add their parameters/started modules
    init_dir = os.path.join(boards_dir, board_vendor, board_model, "init")
    init_scripts = find_scripts(init_dir)

    for script in init_scripts:
        parse_script(script, handlers)

    # Step 2: rcS script 
    rcSFile = os.path.join(init_scripts_dir, "rcS")
    parse_script(rcSFile, handlers)

    print(started_mods)
    print()
    print(set_params)


    # mod_start_reg = re.compile(r"^(?P<module>\w+) start$")
    # mod_start_match = re.search(mod_start_reg, "px4_mod start")

    # if mod_start_match:
    #     print(mod_start_match.group("module"))


if __name__ == "__main__":
    main()