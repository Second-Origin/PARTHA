from os import *
import importlib

module = importlib.import_module("json")
setattr(module, "custom", 1)
value = getattr(module, "custom")
