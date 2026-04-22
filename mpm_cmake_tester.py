#! /usr/bin/env python3

import sys
import argparse

parser = argparse.ArgumentParser\
    ( prog="mpm_cmake_tester",
      description="CMake based tester for MrPackMod regression tests",
      add_help=True )
parser.add_argument( '-i','--title',action='store_true',default="some cmake test" )
parser.add_argument( 'program', nargs='1', help=f"program.c" )

arguments = parser.parse_args()
title     = arguments.title
program   = arguments.program
