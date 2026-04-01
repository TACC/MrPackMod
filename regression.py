##
## Regression tests
##

import os
import sys

from MrPackMod import config 
from MrPackMod import download
from MrPackMod import info 
from MrPackMod import install
from MrPackMod import modules
from MrPackMod import names 
from MrPackMod import process

def do_cmake_test( test_options,**kwargs ):
    print( f"cmake test: {test_options}" )

def do_tests( **kwargs ):
    if tests := kwargs.get( "CMAKETEST" ):
        for test in tests:
            do_cmake_test( test,**kwargs )
            
