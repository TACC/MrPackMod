#! /usr/bin/env python3

import argparse
import os
import sys
from typing import Any

if sys.version_info < (3, 9, 0):
    raise Exception("MrPackMod requires at least Python 3.9")

parser: argparse.ArgumentParser = argparse.ArgumentParser\
    ( prog="MrPackMod",
      description="Package installer with LMod support",
      add_help=True )
parser.add_argument( '-j','--jcount',default='6' )
parser.add_argument( '-t','--trace',action='store_true',default=False )
parser.add_argument( '-c','--configuration',default="Configuration")
# VLE what does this do?
parser.add_argument( '-d','--dependencies',action='store_true',default=False )
parser.add_argument( '-f','--find_string',action='store_true',default=False )
# display configuration variable, action=show
parser.add_argument( '-v','--var',default='none')
parser.add_argument( '--filter',default="" )
parser.add_argument( '--match',default="" )
# VLE what does this do?
parser.add_argument( '-A','--args',default="" )
##
## what actions do we support?
##
file_actions: str = "download unpack retar clone pull"
build_actions: str = "configure build module public"
context_actions: str = "dependencies listmodules test"
package_actions: str = "version url configurelog logfiles"
utility_actions: str = "actions clean regression"
parser.add_argument( 'actions', nargs='*', help=f"File: {file_actions}, Package: {package_actions}, Build: {build_actions}, Context: {context_actions}, Utility: {utility_actions}, install=configure+build+module" )

from MrPackMod import driver

driver.mpm( parser,
            file_actions=file_actions,
            build_actions=build_actions,
            context_actions=context_actions,
            package_actions=package_actions,
            utility_actions=utility_actions,
           )
