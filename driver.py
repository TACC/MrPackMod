##
## Main driver function
##

import argparse
import os
import sys
from typing import Any

from MrPackMod import config 
from MrPackMod import download
from MrPackMod import info 
from MrPackMod import install
from MrPackMod import modulefile
from MrPackMod import names 
from MrPackMod.process import process_execute
from MrPackMod.tracing import echo_string
from MrPackMod.error import nonnull, nonzero_keyword, zero_keyword, abort_on_zero_keyword,\
    error_abort
from MrPackMod import regression

def do_config_tests( **kwargs: Any ) -> None:
    srcdir = names.srcdir_name( **kwargs )
    if not os.path.isdir(srcdir):
        echo_string( f"Warning: source directory {srcdir} does not exist",
                             **kwargs )
    modulefile.test_modules( **kwargs )

def screen_report_action( action: str, **kwargs: Any ) -> None:
    print( f"""
================================================================
====
==== Action: {action}
====
================================================================
    """)

def mpm( parser: argparse.ArgumentParser, **kwargs: Any ) -> None:
    arguments = parser.parse_args()
    configfile   = arguments.configuration
    dependencies = arguments.dependencies
    find_string  = arguments.find_string
    jcount       = arguments.jcount
    tracing      = arguments.trace
    command_arguments = arguments.args

    file_actions: str = kwargs.get( "file_actions" ) or ""
    build_actions: str = kwargs.get( "build_actions" ) or ""
    context_actions: str = kwargs.get( "context_actions" ) or ""
    package_actions: str = kwargs.get( "package_actions" ) or ""
    utility_actions: str = kwargs.get( "utility_actions" ) or ""
    
    ##
    ## what actions are we performing?
    ##
    actions = arguments.actions
    if len(actions)==0:
        parser.print_help(); sys.exit(0)
    if tracing:
        print( f"Actions: {actions}" )
    nowarn = any( [ action in [ "clean","configurelog","dependencies",
                                "actions", "url",
                                "listmodules", "modules", "public", "version",
                               ]
                    for action in actions ] ) \
                        or len(actions)==0 # help only

    configuration = config.read_config(configfile,tracing=tracing,nowarn=nowarn)
    # take care of jcount, dependencies, tracing
    # VLE this seems ad-hoc
    for arg,val in [ ["jcount",jcount], ["tracing",tracing], ["dependencies",dependencies], ]:
        configuration[arg] = val
    for action in actions:
        if tracing:
            print( f"Action: {action}" )
        # informative
        if action=="help":
            parser.print_help(); sys.exit(0)
        elif action=="actions":
            print( f"""file_actions: {file_actions}
build_actions   : {build_actions}
context_actions : {context_actions}
package_actions : {package_actions}
utility_actions : {utility_actions}
""" )
        # auxiliaries
        elif action=="dependencies":
            print( configuration['MODULES'] )
        elif action=="find_string":
            if args := nonnull( command_arguments ):
                srcdir = names.srcdir_name( **configuration )
                process_execute\
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
            do_config_tests( **configuration )
        elif action=="listmodules":
            if modulelist := configuration.get("MODULES"):
                print( modulelist )
        elif action=="url":
            if url := configuration.get("URL"): print( url )
            if url := configuration.get("CODEURL"): print( url )
            if url := configuration.get("DOCURL"): print( url )
        elif action=="version":
            v = configuration["PACKAGEVERSION"]
            if nonnull(v):
                print( v )
            else : print( "default" )
        # download stuff
        elif action=="download":
            download.download_from_url( **configuration )
        elif action in [ "unpack", "untar", ]:
            srcdir_local = names.srcdir_local_name( **configuration )
            download.unpack_from_url( srcdir=srcdir_local,**configuration )
        elif action=="retar":
            download.retar_to_standard_name( **configuration )
        elif action=="clone":
            download.clone_from_url( **configuration )
        elif action=="pull":
            download.pull_from_url( **configuration )
        # build stuff
        elif action in [ "install", "configure", "build", "module", "public", ]:
            do_config_tests( **configuration )
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
            if action in [ "install", "module", ] and zero_keyword( "NOMODULE",**kwargs ):
                install.write_module_file( **configuration )
            if action in [ "install", "public", ]:
                install.public_installation( **configuration )
                if zero_keyword( "NOMODULE",**kwargs ):
                    install.public_module( **configuration )
        elif action=="clean":
            os.system( "rm -rf *~ *.log logfiles *.out build* __pycache__ .mypy_cache" )
        elif action=="regression":
            screen_report_action(action,**configuration)
            do_config_tests( **configuration,no_home=True )
            regression.do_tests\
                ( match=arguments.match,filter=arguments.filter,**configuration )
        else:
            if action in build_actions+context_actions+package_actions+utility_actions:
                error_abort( f"Action promised in help but not implemented: {action}", **configuration )
            else:
                error_abort( f"Unknown action: {action}",**configuration )
                
