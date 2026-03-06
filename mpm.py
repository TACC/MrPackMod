#! /usr/bin/env python3

import os
import sys
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
file_actions    = "download unpack clone pull"
build_actions = "configure build module public"
context_actions = "dependencies listmodules test"
package_actions = "version url configurelog logfiles"
utility_actions = "clean"
parser.add_argument( 'actions', nargs='*', help=f"File: {file_actions}, Package: {package_actions}, Build: {build_actions}, Context: {context_actions}, Utility: {utility_actions}, install=configure+build+module" )

arguments = parser.parse_args()
configfile   = arguments.configuration
dependencies = arguments.dependencies
find_string  = arguments.find_string
jcount       = arguments.jcount
tracing      = arguments.trace
command_arguments = arguments.args

actions = arguments.actions
if tracing:
    print( f"Actions: {actions}" )

from MrPackMod import config 
from MrPackMod import download
from MrPackMod import info 
from MrPackMod import install
from MrPackMod import modules
from MrPackMod import names 
from MrPackMod import process

def usage():
    global parser
    parser.print_help()

def mpm( actions,**kwargs ):
    nowarn = any( [ action in [ "clean","configurelog","dependencies",
                                "url",
                                "listmodules", "modules", "version",]
                    for action in actions ] ) \
                        or len(actions)==0 # help only
    configuration = config.read_config(configfile,tracing=tracing,nowarn=nowarn)
    # take care of jcount, dependencies, tracing
    for arg,val in kwargs.items():
        configuration[arg] = val
    if len(actions)==0:
            usage(); sys.exit(0)
    for action in actions:
        if tracing:
            print( f"Action: {action}" )
        if action=="help":
            usage(); sys.exit(0)
        # auxiliaries
        elif action=="dependencies":
            print( configuration['MODULES'] )
        elif action=="find_string":
            if args := process.nonnull( command_arguments ):
                srcdir = names.srcdir_name( **configuration )
                process.process_execute\
                    ( f"find {srcdir} -type f -exec grep "+command_arguments+" {} \\; -print",
                      **configuration )
            else:
                echo_string( f"WARNING: find_string command needs --args",**configuration )
        elif action=="list":
            info.list_installations( **configuration )
        elif action=="logfiles":
            info.list_logfiles( **configuration )
        elif action=="configurelog":
            logfile = info.configurelog_name( **configuration,nowarn=True )
            print( logfile )
        elif action=="test":
            modules.test_modules( **configuration )
        elif action=="listmodules":
            if modulelist := configuration.get("MODULES"):
                print( modulelist )
        elif action=="url":
            if url := configuration.get("URL"): print( url )
            if url := configuration.get("CODEURL"): print( url )
            if url := configuration.get("DOCURL"): print( url )
        elif action=="version":
            print( configuration["PACKAGEVERSION"] )
        # download stuff
        elif action=="download":
            download.download_from_url( **configuration )
        elif action in [ "unpack", "untar", ]:
            srcdir_local = names.srcdir_local_name( **configuration )
            download.unpack_from_url( srcdir=srcdir_local,**configuration )
        elif action=="clone":
            download.clone_from_url( **configuration )
        # build stuff
        elif action in [ "install", "configure", "build", "module", ]:
            if action in [ "install", "configure", ]:
                if ( system := configuration["BUILDSYSTEM"].lower() ) == "cmake":
                    install.cmake_configure( **configuration )
                elif system == "autotools":
                    install.autotools_configure( **configuration )
                else: raise Exception( f"Can only configure for cmake and autotools, not: {system}" )
            if action in [ "install", "build", ]:
                if ( system := configuration["BUILDSYSTEM"].lower() ) == "cmake":
                    install.cmake_build( **configuration )
                elif system == "autotools":
                    install.autotools_build( **configuration )
                else: raise Exception( f"Can only build for cmake and autotools, not: {system}" )
            if action in [ "install", "module", ]:
                install.write_module_file( **configuration )
        elif action=="clean":
            os.system( "rm -f *~ *.log" )
        elif action=="public":
            install.public_installation( **configuration )
            install.public_module( **configuration )
        else:
            if action in build_actions+context_actions+package_actions+utility_actions:
                process.error_abort( f"Action promised in help but not implemented: {action}", **configuration )
            else:
                process.error_abort( f"Unknown action: {action}",**configuration )
                
mpm( actions,tracing=tracing,jcount=jcount,dependencies=dependencies )
