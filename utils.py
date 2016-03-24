"""Utils.py: contains basic functions reused in various contexts in other modules"""
__author__ = 'JGJeffryes'

from rdkit.Chem import AllChem
import hashlib
from os import path

def convert_sets_to_lists(obj):
    """Recursively converts dictionaries that contain sets to lists"""
    if isinstance(obj, set):
        try:
            obj = sorted(list(obj), key=lambda x: len(x))  # this brings short names to the top of the list
        except TypeError:
            obj = list(obj)
    elif isinstance(obj, dict):
        for key in obj:
            obj[key] = convert_sets_to_lists(obj[key])
    return obj

def get_dotted_field(input_dict, accessor_string):
    """Gets data from a dictionary using a dotted accessor-string"""
    current_data = input_dict
    for chunk in accessor_string.split('.'):
        current_data = current_data.get(chunk, {})
    return current_data

def save_dotted_field(accessor_string, data):
    """Gets data from a dictionary using a dotted accessor-string"""
    for chunk in accessor_string.split('.')[::-1]:
        data = {chunk: data}
    return data

def memoize(f):
    """ Memoization decorator for a function taking one or more arguments. """
    class memodict(dict):
        def __getitem__(self, *key):
            return dict.__getitem__(self, key)

        def __missing__(self, key):
            ret = self[key] = f(*key)
            return ret
    return memodict().__getitem__

def prevent_overwrite(write_path):
    """
    Prevents overwrite of existing output files by appending "_new" when needed
    :param write_path: potential write path
    :type write_path: string
    :return:
    :rtype:
    """
    while path.exists(write_path):
        sp = write_path.split('.')
        if len(sp) > 1:
            sp[-2] += '_new'
            write_path = '.'.join(sp)
        else:
            write_path += '_new'
    return write_path

def dict_merge(finaldict, sourcedict):
    """Merges two dictionaries using sets to avoid duplication of values"""
    for key, val in sourcedict.items():
        if (key in finaldict) and isinstance(finaldict[key], list):
            finaldict[key] = set(finaldict[key])
        if isinstance(val, list):
            if key in finaldict:
                finaldict[key].update(val)
            else:
                finaldict[key] = set(val)
        elif isinstance(val, str):
            if key in finaldict:
                finaldict[key].update(val)
            else:
                finaldict[key] = set(val)
                finaldict[key].update(val)
        elif isinstance(val, float):
            if key not in finaldict:
                finaldict[key] = val
        elif isinstance(val, dict):
            if not key in finaldict:
                finaldict[key] = {}
            dict_merge(finaldict[key], val)

def do_profile(func):
    from line_profiler import LineProfiler

    def profiled_func(*args, **kwargs):
        try:
            profiler = LineProfiler()
            profiler.add_function(func)
            profiler.enable_by_count()
            return func(*args, **kwargs)
        finally:
            profiler.print_stats()
    return profiled_func