################################################################
#### driver.py
#### top level mpm function executing the commandline actions
################################################################

import argparse
import os
import pdb
import sys
from typing import Any,Optional

from MrPackMod.config import read_config,derived_setting_triggers
from MrPackMod import download
from MrPackMod import info 
from MrPackMod import install
from MrPackMod import names 
from MrPackMod.process import process_initiate,process_terminate,process_execute,\
    ensure_dir
from MrPackMod.basics  import echo_string,echo_warning,error_abort,\
    nonnull, nonzero_keyword, zero_keyword,\
    ModuleLoadStrategy
from MrPackMod.error   import abort_on_failure_result
from MrPackMod.testing import do_config_tests,report_success_failure
from MrPackMod import regression

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

    ##
    ## what actions are we performing?
    ##
    actions = arguments.actions
    if len(actions)==0:
        parser.print_help(); sys.exit(0)
    if tracing:
        print( f"Actions: {actions}" )
    configuration: dict[str, Any] = {
        'MODULES':"", 'mode':"seq",
        'PACKAGE':"all", 'PACKAGEVERSION':"",
        'tracing':tracing,
        'exports':[], # vars to set before cmake/configure call
        'unsets':[],  # vars that should not be set, like PETSC_DIR
        'logfiles':{}, # name,handle pairs
        'startdir':os.getcwd(), 
        'scriptdir':os.getcwd(), # VLE confusing name, abandon in favor of `startdir'?
        'nowarn' : any( [ action in [ "clean","configurelog","dependencies",
                                      "actions", "url", "show", "test",
                                      "listmodules", "modules", "public", "version",
                                     ]
                          for action in actions ] ) or len(actions)==0,
    }
    not_create_home : bool = any( [ a in actions for a in ["regression","version",] ] )
    read_config( configuration,configfile,
                 # test_stage mechanism is used here, but is missing some info
                 # so we set dummy values
                 no_home=not_create_home,PACKAGE="setup",PACKAGEVERSION="0.0"
                )
    # make sure we have triggered derived settings
    if not any( [ nonnull(configuration.get(key)) for key in derived_setting_triggers ] ):
        raise Exception( f"Need to have any of {derived_setting_triggers}" )
    # take care of jcount, dependencies, tracing
    # VLE this seems ad-hoc
    for arg,val in [ ["jcount",jcount], ["tracing",tracing], ["dependencies",dependencies], ]:
        configuration[arg] = val
    for action in actions:
        if tracing:
            print( f"Action: {action}" )
        if action=="help":
            parser.print_help(); sys.exit(0)
        mpm_action( action,arguments,**configuration )

def mpm_action( action : str,arguments,**configuration ) -> None:
    # what are the possible actions
    file_actions: str = configuration.get( "file_actions" ) or ""
    build_actions: str = configuration.get( "build_actions" ) or ""
    context_actions: str = configuration.get( "context_actions" ) or ""
    package_actions: str = configuration.get( "package_actions" ) or ""
    utility_actions: str = configuration.get( "utility_actions" ) or ""
    
    # informative
    if action=="actions":
        print( f"""\
file_actions: {file_actions}
build_actions   : {build_actions}
context_actions : {context_actions}
package_actions : {package_actions}
utility_actions : {utility_actions}
""" ) ; sys.exit(0)
    # Auxiliary actions
    elif action=="dependencies":
        print( configuration['MODULES'] )
    elif action=="find_string":
        if args := nonnull( arguments.args ):
            srcdir = names.srcdir_name( **configuration )
            process_execute\
                ( f"find {srcdir} -type f -exec grep "+arguments.args+" {} \\; -print",
                  **configuration )
        else:
            echo_string( f"WARNING: find_string command needs --args",**configuration )
    elif action=="package":
        print( configuration.get("PACKAGE","PACKAGE variable not set") )
    elif action=="list":
        info.list_installations( **configuration )
    elif action=="logfiles":
        info.list_logfiles( **configuration )
    elif action=="configurelog":
        logfile = info.configurelog_name( **configuration, )
        print( logfile )
    elif action=="show":
        displayvar : str = arguments.displayvar
        try:
            print( configuration[displayvar] )
        except:
            print( f"No configuration variable: {displayvar}" )
    elif action=="test":
        if not os.path.isdir( ( srcdir := names.srcdir_name( **configuration ) ) ):
            echo_warning( "Source directory {srcdir} does not exist (yet)",
                          **configuration )
        abort_on_failure_result(
            do_config_tests( installing=True,**configuration ),**configuration )
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
    elif action in [ "clone","pull" ]:
        download.clone_or_pull( **configuration,gitaction=action )
    # build stuff
    elif action=="install":
        for a in ["configure","build","module","public",]:
            mpm_action(a,arguments,**configuration)
    elif action in [ "configure", "build", "public", ]:
        # VLE the `install' action should really be a loop over recursive calls
        # to prevent corruption of the install options
        install_options : dict = {
            "immediate_output":True,
            "moduleloadstrategy":ModuleLoadStrategy.prerequisites
        }
        abort_on_failure_result(
            do_config_tests( **configuration ),**configuration )
        success : list[str] = []
        failure : list[str] = []
        if action=="configure":
            if not configure_action( **{ **configuration,**install_options } ):
                return
        elif action=="build":
            if not build_action( **{ **configuration,**install_options } ):
                return
            install_options["moduleloadstrategy"] = ModuleLoadStrategy.package
            install.post_install_actions(
                **{ **configuration,**install_options} )
        elif action=="public":
            install_options["moduleloadstrategy"] = ModuleLoadStrategy.package
            install.public_installation( 
                **{ **configuration,**install_options } )
            if zero_keyword( "NOMODULE",**configuration ):
                install.public_module( 
                    **{ **configuration,**install_options } )
    elif action=="module" and zero_keyword( "NOMODULE",**configuration ):
        install_options = {
            "immediate_output":False,
            # VLE we need to be able to get the version of prereqs
            # for dependency clauses. Do we also need to be able to
            # load the package itself?
            "moduleloadstrategy":ModuleLoadStrategy.prerequisites #package
        }
        success,failure = install.write_module_file(
            **{ **configuration,**install_options } )
        report_success_failure( success,failure )
    elif action=="clean":
        clean_targets : str = \
            "*~ a.out *.log logfiles mpmscripts* *.out build* __pycache__"
        if targets := nonzero_keyword( "CLEANTARGET",**configuration ):
            for t in targets:
                clean_targets += " "+t
            os.system( f"rm -rf {clean_targets}" )
    elif action=="regression":
        package : str = str( configuration.get("PACKAGE") ) # str only for mypy
        echo_warning( f"Need better test for package actually being loaded",**configuration )
        # if not loaded_module_version( package,**configuration ):
        #     error_abort( f"Module {package} needs to be loaded for regression testing",
        #                  **configuration )
        screen_report_action(action,**configuration)
        #do_config_tests( installing=False,**configuration,no_home=True )
        regression.do_tests\
            ( match=arguments.match,filter=arguments.filter,
              logdir="./logfiles",**configuration )
    else:
        if action in build_actions+context_actions+package_actions+utility_actions:
            error_abort( f"Action promised in help but not implemented: {action}", **configuration )
        else:
            error_abort( f"Unknown action: {action}",**configuration )
                
def configure_action( **kwargs : Any ) -> Optional[str]:
    if ( system := kwargs["BUILDSYSTEM"].lower() ) == "cmake":
        return install.cmake_configure( **kwargs )
    elif system == "autotools":
        return install.autotools_configure( **kwargs )
    elif system == "make":
        return install.make_configure( **kwargs )
    elif system == "petsc":
        return install.petsc_configure( **kwargs )
    else: raise Exception( f"Can only configure for cmake and autotools, not: {system}" )

def build_action( **kwargs : Any ) -> Optional[str]:
    if ( system := kwargs["BUILDSYSTEM"].lower() ) == "cmake":
        return install.cmake_build( **kwargs )
    elif system == "autotools":
        return install.autotools_build( **kwargs )
    elif system == "make":
        return install.make_build( **kwargs )
    elif system == "petsc":
        return install.petsc_build( **kwargs )
    else: raise Exception\
        ( f"Can only build for cmake/autotools/make, not: {system}" )
