##
## Regression tests
##

import argparse
import shlex
import os
import re
import shutil
import sys

from MrPackMod import config 
from MrPackMod import download
from MrPackMod import info 
from MrPackMod.install import export_compilers,cmake_options,\
    open_logfile,close_logfile
from MrPackMod import modulefile
from MrPackMod import names 
from process import process_execute, process_initiate, process_terminate,\
    create_dir,ensure_dir,\
    nonzero_keyword, echo_string,trace_string,error_abort

#
# Parse the options with argparse
#
def parse_command( test_options,**kwargs ) -> dict:
    parser = argparse.ArgumentParser\
        ( prog="mpm_cmake_tester",
          description="CMake based tester for MrPackMod regression tests",
          add_help=True )
    # cmake
    parser.add_argument( '-r',"--run", action='store_true', default=False )
    # existence
    parser.add_argument( '-l',"--ldd", action='store_true', default=False )
    parser.add_argument( "-d","--dir" )
    # universal
    parser.add_argument( '-i','--title',default="some cmake test" )
    parser.add_argument( 'program', nargs=1, help=f"program.c" )

    argument_list = shlex.split( f"{test_options}" )
    arguments  = parser.parse_args( argument_list )

    # cmake test
    do_run     = arguments.run
    
    # existence test
    dir        = arguments.dir
    ldd        = arguments.ldd
    # always
    test_title = arguments.title
    program    = arguments.program[0]
    print( f"Test: {test_title}, program: {program}, run: {do_run}" )
    return { "program":program, "title":test_title,
             "do_run":do_run, # cmake tests
             "ldd":ldd, "dir":dir, # existence test
             }

def load_compiler_and_mpi_and_package( process=None,**kwargs ):
    # load the compiler since this is a fresh process
    _,compiler,compilerversion,_,mpi,mpiversion = names.family_names( **kwargs )
    process_execute\
        ( f"module load {compiler}/{compilerversion}",**kwargs,process=process )
    if kwargs.get("MODE")=="mpi":
        process_execute\
            ( f"module load {mpi}/{mpiversion}",**kwargs,process=process )
    # load the package that we are testing
    package,packageversion =  names.package_names( **kwargs )
    process_execute\
        ( f"module load {package}/{packageversion}",**kwargs,process=process )

def start_test_stage( name,stage,logdir,chdir=None,**kwargs ):
    logfile = open_logfile( f"{name}_{stage}",kwargs,dir=logdir,terminal=None ) # note dict
    shell = process_initiate( **kwargs )
    output = { "logfile":logfile,"terminal":None,"process":shell, }
    if chdir:
        process_execute( f"cd {chdir}",**kwargs,**output )
    load_compiler_and_mpi_and_package( **kwargs,**output )
    return output

def do_existence_test( test_options,**kwargs ) -> tuple[list[str],list[str]]:
    failure : list[str] = []; success : list[str] = []
    parsed_options : dict = parse_command( test_options,**kwargs )
    try :
        program = parsed_options["program"]
        ldd     = parsed_options["ldd"]
        dirtype = parsed_options["dirtype"]
    except KeyError:
        error_abort( "Did not find program/ldd/dirtype",**kwargs )

    package,_ = names.package_names( **kwargs )
    dir_variable = f"TACC_{package.upper()}_{dir.upper()}"
    if directory := nonzero_keyword( dir_variable,**kwargs ):
        msg : str = f"Variable {dir_variable} set to {directory}"
        success.append( msg )
        trace_string( msg,**kwargs,terminal=None )
        if not os.path.isdir( directory ):
            msg = f"Directory {directory} does not exist"
            failure.append( msg )
            trace_string( msg,**kwargs,terminal=None )
    else:
        msg = f"Variable {dir_variable} not set"
        failure.append( msg )
        trace_string( msg,**kwargs,terminal=None )
    return success,failure

def do_cmake_test( test_options,**kwargs ) -> tuple[list[str],list[str]]:
    failure = []; success = []
    parsed_options : dict = parse_command( test_options,**kwargs )
    try :
        program = parsed_options["program"]
        title   = parsed_options["title"]
        do_run  = parsed_options["do_run"]
    except KeyError:
        error_abort( "Did not find program/title/do_run",**kwargs )

    name,ext = re.search( r'^(.+)\.(.+)$',program ).groups()
    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )

    #
    # compilation
    #
    output = start_test_stage( name,"compile",logdir,chdir=builddir,**kwargs )
    # set up for cmake/make
    compiler_exports = export_compilers( **kwargs )
    cmakeflags = cmake_options( **kwargs )
    process_execute\
        ( f"{compiler_exports} && cmake -D PROJECTNAME={name} {cmakeflags} ../{ext}",
          **kwargs,**output )
    process_execute( f"make", **kwargs,**output )
    # terminate this stage
    process_terminate( output["process"],**kwargs )
    if os.path.exists( name ):
        success.append( f"Executable <<{name}>> created" )
    else:
        failure.append( f"Failed to create executable <<{name}>>" )
    close_logfile( output["logfile"],kwargs )

    #
    # execution
    #
    output = start_test_stage( name,"exec",logdir,chdir=builddir,**kwargs )
    # are library dependencies satisfied
    process_execute( f"ldd {name}",**kwargs,**output )
    # run!
    if do_run:
        process_execute( f"./{name}",**kwargs,**output )
    # end of this stage
    process_terminate( output["process"],**kwargs )
    close_logfile( output["logfile"],kwargs )

    return success,failure

def do_tests( **kwargs ):
    #
    # existence tests
    # we make one big logfile
    #
    package,_ = names.package_names( **kwargs )
    logdir : str = ensure_dir( "logfiles",**kwargs )
    logfile = open_logfile( f"{package}_existence",kwargs,dir=logdir,terminal=None ) # note dict
    if tests := kwargs.get( "EXISTENCETEST" ):
        for test in tests:
            success,failure = do_existence_test( test,**kwargs )
            for s in success:
                echo_string( s,**kwargs )
            for f in failure:
                echo_string( f,**kwargs )
    close_logfile( logfile,kwargs )
    #
    # cmake tests
    # each makes their own logfile
    #
    if tests := kwargs.get( "CMAKETEST" ):
        for test in tests:
            success,failure = do_cmake_test( test,**kwargs )
            for s in success:
                echo_string( s,**kwargs )
            for f in failure:
                echo_string( f,**kwargs )
