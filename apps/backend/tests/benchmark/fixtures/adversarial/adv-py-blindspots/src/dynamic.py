from os import *
import importlib

module = importlib.import_module("json")
importlib.custom = 1
value = getattr(module, "custom")
