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
from MrPackMod import install
from MrPackMod import modules
from MrPackMod import names 
from process import process_execute, process_initiate, process_terminate

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

#
# Set up a build dir for cmake
#
def make_build_dir( **kwargs ) -> str:
    builddir : str = "build"
    try:
        shutil.rmtree(builddir)
    except FileNotFoundError: pass
    os.makedirs(builddir,exist_ok=True)
    return builddir

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

def do_cmake_test( test_options,**kwargs ):
    program,title,do_run = parse_command( test_options,**kwargs )
    name,ext = re.search( r'^(.+)\.(.+)$',program ).groups()

    shell = process_initiate( **kwargs )
    builddir : str = make_build_dir( **kwargs )
    process_execute( f"cd {builddir}",**kwargs,process=shell )

    # module loads
    load_compiler_and_mpi_and_package( **kwargs,process=shell )

    # set up the cmake command
    compiler_exports = install.export_compilers( **kwargs )
    cmakeflags = install.cmake_options( **kwargs )
    process_execute\
        ( f"{compiler_exports} && cmake -D PROJECTNAME={name} {cmakeflags} ../{ext}",
          **kwargs,process=shell )
    process_execute( f"make",**kwargs,process=shell )
    if do_run:
        process_execute( f"./{name}",**kwargs,process=shell )
    process_terminate( shell,**kwargs )
    

def do_tests( **kwargs ):
    if tests := kwargs.get( "CMAKETEST" ):
        for test in tests:
            do_cmake_test( test,**kwargs )
            
