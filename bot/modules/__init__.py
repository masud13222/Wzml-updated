#!/usr/bin/env python3
from os import path as ospath, listdir
from importlib import import_module
import logging

# Get all python files in the modules directory
all_modules = sorted([
    f[:-3] for f in listdir(ospath.dirname(__file__))
    if f.endswith(".py") and not f.startswith("__")
])

# Import each module
for module in all_modules:
    try:
        import_module(f".{module}", __package__)
        logging.info(f"Successfully imported module {module}")
    except Exception as e:
        logging.error(f"Error importing module {module}: {str(e)}")
