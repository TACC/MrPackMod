#! /usr/bin/env python3

import os
import sys
if sys.version_info<(3,9,0):
    raise Exception("MrPackMod requires at least Python 3.9")

args = sys.argv
import argparse
parser = argparse.ArgumentParser\
    ( prog="MrPackMod",
      description="Package installer with LMod support",
      add_help=True )
parser.add_argument( '-j','--jcount',default='6' )
parser.add_argument( '-t','--trace',action='store_true',default=False )
parser.add_argument( '-c','--configuration',default="Configuration")
parser.add_argument( '-d','--dependencies',action='store_true',default=False )
parser.add_argument( '-f','--find_string',action='store_true',default=False )
parser.add_argument( '-A','--args',default="" )
file_actions    = "download unpack retar clone pull"
build_actions = "configure build module public"
context_actions = "dependencies listmodules test"
package_actions = "version url configurelog logfiles"
utility_actions = "actions clean regression"
parser.add_argument( 'actions', nargs='*', help=f"File: {file_actions}, Package: {package_actions}, Build: {build_actions}, Context: {context_actions}, Utility: {utility_actions}, install=configure+build+module" )

from MrPackMod import driver

driver.mpm( parser,
            file_actions=file_actions,
            build_actions=build_actions,
            context_actions=context_actions,
            package_actions=package_actions,
            utility_actions=utility_actions,
           )
