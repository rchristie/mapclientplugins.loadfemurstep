
'''
MAP Client Plugin
'''

__version__ = '0.1.0'
__author__ = 'Hugh Sorby, Richard Cristie'
__stepname__ = 'Load Femur'
__location__ = 'https://github.com/rchristie/mapclientplugins.loadfemurstep/archive/master.zip'

# import class that derives itself from the step mountpoint.
from mapclientplugins.loadfemurstep import step

# Import the resource file when the module is loaded,
# this enables the framework to use the step icon.
from . import resources_rc