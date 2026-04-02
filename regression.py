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
    create_dir,ensure_dir

#
# Parse the options with argparse
#
def parse_command( test_options,**kwargs ):
    parser = argparse.ArgumentParser\
        ( prog="mpm_cmake_tester",
          description="CMake based tester for MrPackMod regression tests",
          add_help=True )
    parser.add_argument( '-i','--title',default="some cmake test" )
    parser.add_argument( '-r',"--run", action='store_true', default=False )
    parser.add_argument( 'program', nargs=1, help=f"program.c" )

    argument_list = shlex.split( f"{test_options}" )
    #print( argument_list )
    arguments  = parser.parse_args( argument_list )
    test_title = arguments.title
    do_run     = arguments.run
    program    = arguments.program[0]
    print( f"title: {test_title}, program: {program}, run: {do_run}" )
    return program,test_title,do_run

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

def do_cmake_test( test_options,**kwargs ) -> None:
    program,title,do_run = parse_command( test_options,**kwargs )
    name,ext = re.search( r'^(.+)\.(.+)$',program ).groups()
    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )
    failure = []; success = []

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
    if tests := kwargs.get( "CMAKETEST" ):
        for test in tests:
            do_cmake_test( test,**kwargs )
            
