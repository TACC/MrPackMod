##
## Regression tests
##

import argparse
import shlex
import os
import re
import sys

from MrPackMod import config 
from MrPackMod import download
from MrPackMod import info 
from MrPackMod import install
from MrPackMod import modules
from MrPackMod import names 
from process import process_execute, process_initiate, process_terminate

def do_cmake_test( test_options,**kwargs ):
    #
    # parse the options with argparse
    #
    parser = argparse.ArgumentParser\
        ( prog="mpm_cmake_tester",
          description="CMake based tester for MrPackMod regression tests",
          add_help=True )
    parser.add_argument( '-i','--title',default="some cmake test" )
    parser.add_argument( 'program', nargs=1, help=f"program.c" )

    argument_list = shlex.split( f"{test_options}" )
    #print( argument_list )
    arguments = parser.parse_args( argument_list )
    title     = arguments.title
    program   = arguments.program[0]
    print( f"title: {title}, program: {program}" )
    name,ext = re.search( r'^(.+)\.(.+)$',program ).groups()

    shell = process_initiate( **kwargs )
    process_execute\
        ( f"rm -rf build && mkdir build && cd build && cmake -D PROJECTNAME={name} ../{ext}",
          **kwargs,process=shell )
    process_terminate( shell,**kwargs )
    

def do_tests( **kwargs ):
    if tests := kwargs.get( "CMAKETEST" ):
        for test in tests:
            do_cmake_test( test,**kwargs )
            
