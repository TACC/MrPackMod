##
## Regression tests
##

import argparse
import shlex
import os
import re
import pdb
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
    nonnull, nonzero_keyword, echo_string,trace_string,trace_var,error_abort,echo_warning

#
# Parse the options with argparse
#
def parse_command( test_options,**kwargs ) -> dict:
    parser = argparse.ArgumentParser\
        ( prog="mpm_cmake_tester",
          description="CMake based tester for MrPackMod regression tests",
          add_help=True )
    # running
    parser.add_argument( '-r',"--run", action='store_true', default=False )
    parser.add_argument( '--run_in_dir', action='store_true', default=False )
    parser.add_argument( '-a',"--run_args" )
    parser.add_argument( '-k','--keywords',default="" )
    parser.add_argument( '-p',"--run_prefix" )
    # existence
    parser.add_argument( '-l',"--ldd", action='store_true', default=False )
    parser.add_argument( "-d","--dir" )
    parser.add_argument( "-g","--grep" )
    # universal
    parser.add_argument( '-i','--title',default="some cmake test" )
    parser.add_argument( 'program', nargs=1, help=f"program.c" )

    argument_list = shlex.split( f"{test_options}" )
    arguments  = parser.parse_args( argument_list )
    #print( f"Test arguments: {arguments}" )

    parsed = {
        # running
        "do_run"     : arguments.run or arguments.run_in_dir,
        "run_in_dir" : arguments.run_in_dir,
        "run_args"   : arguments.run_args,
        "keywords"   : arguments.keywords,
        "run_prefix" : arguments.run_prefix,
        # existence test
        "dirtype"    : arguments.dir,
        "grep"       : arguments.grep,
        "ldd"        : arguments.ldd,
        # always
        "test_title" : arguments.title,
        "program"    : arguments.program[0],
    }
    print( f"Test: "+parsed["test_title"] )
    trace_string( f" .. parameters: {parsed}",**kwargs )
    return parsed

def load_compiler_and_mpi_and_package( process=None,**kwargs ):
    # load the compiler since this is a fresh process
    _,compiler,compilerversion,_,mpi,mpiversion = names.family_names( **kwargs )
    # disable terminal output unless otherwise specified
    process_execute\
        ( f"module load {compiler}/{compilerversion}",**kwargs,process=process )
    if kwargs.get("MODE")=="mpi":
        process_execute\
            ( f"module load {mpi}/{mpiversion}",**kwargs,process=process )
    # load the package that we are testing
    package,packageversion =  names.package_names( **kwargs )
    loadname = package
    if nonnull(packageversion): loadname = f"{loadname}/{packageversion}"
    process_execute\
        ( f"module load {loadname}",**kwargs,process=process )
    process_execute\
        ( f"module -t list 2>&1 | sort", **kwargs,process=process )

def start_test_stage( name,stage,logdir,kwargs,chdir=None,title=None ): # note dict
    # Create log file for this test stage, and add it to the stack of logfiles
    logfile = \
        open_logfile( f"{name}_{stage}",kwargs,dir=logdir,terminal=None ) # note dict
    # Create a process for the commands of this test stage
    shell = process_initiate( **kwargs )
    output = { "logfile":logfile, "logdir":logdir, "terminal":"suppress", "process":shell, }
    if title:
        process_execute( f"echo Test title: {title}",**kwargs,**output )
    if chdir:
        process_execute( f"cd {chdir}",**kwargs,**output )
    load_compiler_and_mpi_and_package( **kwargs,**output )
    return output

def end_test_stage( success,failure,kwargs,output ) -> tuple[list[str],list[str]]:
    process_terminate( output["process"],**kwargs,**output )
    close_logfile( output["logfile"],kwargs )
    success,failure = success_failure_in_logfile\
        ( output["logfile"],success=success,failure=failure,**kwargs )
    return success,failure

##
## Return directory, actual file name & name with LMOD variable unexpanded
##
def file_to_exist( package : str,dirtype : str,program : str,**kwargs ) -> tuple[str,str,str]:
    if dirtype in [ "dir","inc","lib","bin", ]:
        filedir : str = dir_variable(package,dirtype)
        filedir = f"${filedir}"
        file_to_test   : str = f"{filedir}/{program}"
        file_to_report : str = f"{filedir}/{program}"
    else:
        filedir = f"$TACC_{package.upper()}_DIR/{dirtype}"
        file_to_test   : str = f"{filedir}/{program}"
        file_to_report : str = f"{filedir}/{program}"
    return filedir,file_to_test,file_to_report

##
## Add process lines for testing file existence
##
def execute_file_to_exist( package : str,dirtype : str,program : str,**kwargs ) -> None:
    process = kwargs.get("process")
    process_execute\
        ( f"echo \"Investigate program: {program}, in var: {dirtype}\"",**kwargs )
    filedir,file_to_test,file_to_report = file_to_exist(package,dirtype,program,**kwargs)
    process_execute\
        ( f"""
if [ ! -z \"{filedir}\" -a -d \"{filedir}\" ] ; then 
    echo ' .. directory {filedir} exists' ; 
else 
    echo 'FAILURE: {filedir} does not exist' ; 
fi
        """,**kwargs )
    process_execute\
        ( f"""
if [ -f \"{file_to_test}\" ] ; then
    echo 'SUCCESS: file exists: <<{file_to_report}>> ' ; 
else
    echo 'FAILURE: file does not exist <<{file_to_report}>>' ; 
fi
        """,**kwargs )

##
## Add lines to a process for testing the existence of a file
## In case we grep something in that file, return the name of the grep file
##
def execute_grep( package,dirtype,program,**kwargs ) -> tuple[str,str]:
    _,file_to_test,file_to_report = file_to_exist( package,dirtype,program,**kwargs )
    # with directories in place, does the actual file exist?
    program_clean = re.sub( '/','',program )
    grep_output_file : str = f"{os.getcwd()}/{program_clean}_grep.out"
    process_execute\
        ( f"""
if [ -f \"{file_to_test}\" ] ; then
    grep \"{grep}\" {file_to_test} >{grep_output_file} 2>&1 ; 
fi
""",
          **kwargs, )
    return grep_output_file

def execute_cmake_script( program,ext,**kwargs ) -> None:
    compiler_exports = export_compilers( **kwargs )
    cmakeflags = cmake_options( **kwargs )
    process_execute\
        ( f"{compiler_exports} && cmake -D PROJECTNAME={program} {cmakeflags} ../{ext}",
          **kwargs )
    process_execute( f"make V=1", **kwargs )
    process_execute( f"""
if [ -f \"{program}\" ] ; then
    found=1 && echo SUCCESS: program created ; 
else
    found=0 && echo FAILURE: program not created ; 
fi
    """,**kwargs )

def execute_ldd_script( program,**kwargs ) -> None:
    lddout = "ldd.out"
    process_execute( f"rm -f {lddout}",**kwargs )
    process_execute( f"""
if [ -f \"{program}\" ] ; then
    ldd {program} 2>&1 | tee {lddout} ; 
else
    touch {lddout} ; 
fi
    """,**kwargs )
    process_execute( f"""
if [ -f \"{program}\" ] ; then
    notfound=$( grep \"not found\" {lddout} | wc -l ) && 
    if [ $notfound -eq 0 ] ; then
        echo \"SUCCESS: all libraries resolved\" ; 
    else
        echo \"FAILURE: $notfound references not found\" ; 
    fi ; 
fi
    """,**kwargs )

##
## Run a program
##
def execute_run_script( run_in_dir,filedir,run_prefix,run_args,program,**kwargs ) -> None:
    tracestring = f"run program={program}"
    if nonnull(run_in_dir):
        tracestring += f" in dir {run_in_dir}"
    if nonnull(run_args):
        tracestring += f" with args={run_args}"
    trace_string( tracestring,**kwargs )
    #breakpoint()
    if nonnull(run_in_dir):
        cmdline : str = f"cd {filedir} && "
    else:
        cmdline = ""
    if nonnull(run_prefix):
        cmdline += f"{run_prefix}{program}"
    else:
        cmdline += f"./{program}"
    if nonnull(run_args):
        cmdline += run_args
    trace_string( f"run cmdline: {cmdline}",**kwargs )
    logdir = kwargs["logdir"]
    runout = f"{logdir}/run.out"
    process_execute( f"""
{cmdline} >{runout} 2>&1 &&
if [ $? -eq 0 ] ; then 
    echo SUCCESS: running {program} ;
else
    echo FAILURE: running {program} ;
fi 
echo "Run output"
cat {runout}
    """,**kwargs )

def dir_variable( package,dirtype ) -> str:
    return f"TACC_{package.upper()}_{dirtype.upper()}"

def do_existence_test( test_options,**kwargs ) -> tuple[list[str],list[str]]:
    parsed_options : dict = parse_command( test_options,**kwargs )
    trace_string( f"Existence test options: {parsed_options}",**kwargs )
    try :
        title      = parsed_options["test_title"]
        program    = parsed_options["program"]
        dirtype    = parsed_options["dirtype"]
        grep       = parsed_options["grep"]
        ldd        = parsed_options["ldd"]
        do_run     = parsed_options["do_run"]
        run_in_dir = parsed_options["run_in_dir"]
        run_args   = parsed_options["run_args"]
        run_prefix = parsed_options["run_prefix"]
    except KeyError:
        error_abort( "Did not find program/grep/ldd/dirtype/do_run",**kwargs )

    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )
    success = []; failure = []

    #
    # existence
    #
    package,_ = names.package_names( **kwargs )
    # program can contain a path
    program_clean = re.sub( '/','',program )
    output = start_test_stage( program_clean,"exists",logdir,
                               kwargs,title=title,chdir=builddir, ) # note dict
    execute_file_to_exist( package,dirtype,program,**kwargs,**output )
    if nonnull(grep):
        grepfile : str = execute_grep( package,dirtype,program,**kwargs,**output )
    else: grepfile = ""
    process_terminate( output["process"],**kwargs,**output )
    close_logfile( output["logfile"],kwargs )
    success,failure = success_failure_in_logfile\
                      ( output["logfile"],success=success,failure=failure,
                        **kwargs,**output )
    if nonnull(grepfile):
        success = add_grep_lines( f"{grep_output_file}",success,**kwargs,**output )

    #
    # run and ldd
    #
    if do_run or ldd:
        filedir,file_to_test,file_to_report = \
            file_to_exist(package,dirtype,program,**kwargs,**output)
        output = start_test_stage( program_clean,"exec",logdir,
                                   kwargs,title=title,chdir=builddir, ) # dict!
        if ldd:
            # are library dependencies satisfied
            execute_ldd_script( file_to_test,**kwargs,**output )
        # run!
        if do_run:
            execute_run_script( run_in_dir,filedir,run_prefix,run_args,program,**kwargs,**output )
        process_terminate( output["process"],**kwargs,**output )
        close_logfile( output["logfile"],kwargs )
        success,failure = success_failure_in_logfile\
                          ( output["logfile"],success=success,failure=failure,
                            **kwargs,**output )
    return success,failure

def do_cmake_test( test_options,**kwargs ) -> tuple[list[str],list[str]]:
    failure : list[str] = []; success : list[str] = []
    parsed_options : dict = parse_command( test_options,**kwargs )
    try :
        program = parsed_options["program"]
        title   = parsed_options["test_title"]
        do_run  = parsed_options["do_run"]
    except KeyError:
        error_abort( "Did not find program/title/do_run",**kwargs )

    name,ext = re.search( r'^(.+)\.(.+)$',program ).groups()
    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )

    success : list[str] = []
    failure : list[str] = []

    #
    # Cmake & compile
    #
    output = start_test_stage( name,"compile",logdir,kwargs,chdir=builddir, ) # note dict
    execute_cmake_script( name,ext,**kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    #
    # Check library dependencies satisfied & run
    #
    output = start_test_stage( name,"exec",logdir,kwargs,chdir=builddir, ) # note dict
    execute_ldd_script( name,**kwargs,**output )
    if do_run:
        execute_run_script( name,**kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    return success,failure

def do_make_test( test_options,**kwargs ) -> tuple[list[str],list[str]]:
    failure : list[str] = []; success : list[str] = []
    parsed_options : dict = parse_command( test_options,**kwargs )
    try :
        program = parsed_options["program"]
        title   = parsed_options["test_title"]
        do_run  = parsed_options["do_run"]
    except KeyError:
        error_abort( "Did not find program/title/do_run",**kwargs )

    try:
        name,ext = re.search( r'^(.+)\.(.+)$',program ).groups()
    except:
        error_abort( f"program <<{program}>> can not be parsed as name.ext",**kwargs )
    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )

    #
    # compilation
    #
    output = start_test_stage( name,"compile",logdir,kwargs,chdir=builddir ) # note dict
    # set up for make
    compiler_exports = export_compilers( **kwargs,**output )
    cmakeflags = cmake_options( **kwargs )
    process_execute\
        ( f"{compiler_exports} && make -f ../{ext}/Makefile SRCDIR=../{ext} PROJECTNAME={name} {name}",
          **kwargs,**output )
    process_execute( f"make", **kwargs,**output )
    # terminate this stage
    process_terminate( output["process"],**kwargs,**output )
    close_logfile( output["logfile"],kwargs )
    if os.path.exists( f"{builddir}/{name}" ):
        success.append( f"executable <<{name}>> created" )
    else:
        failure.append( f"Failed to create executable <<{name}>>" )

    #
    # execution
    #
    output = start_test_stage( name,"exec",logdir,kwargs,chdir=builddir ) # note dict
    # are library dependencies satisfied
    process_execute( f"ldd {name}",**kwargs,**output )
    # run!
    if do_run:
        process_execute( f"./{name}",**kwargs,**output )
    # end of this stage
    process_terminate( output["process"],**kwargs,**output )
    close_logfile( output["logfile"],kwargs )

    return success,failure

def do_tests( **kwargs ):
    #
    # existence tests
    #
    if tests := kwargs.get( "EXISTENCETEST" ):
        for test in tests:
            success,failure = do_existence_test( test,**kwargs )
            for s in success:
                echo_string( f"    {s}",**kwargs, )
            for f in failure:
                echo_string( f"    ERROR: {f}",**kwargs, )
    #
    # cmake tests
    #
    if tests := kwargs.get( "CMAKETEST" ):
        for test in tests:
            success,failure = do_cmake_test( test,**kwargs )
            for s in success:
                echo_string( f"    {s}",**kwargs, )
            for f in failure:
                echo_string( f"    ERROR: {f}",**kwargs, )
    #
    # make tests
    #
    if tests := kwargs.get( "MAKETEST" ):
        for test in tests:
            success,failure = do_make_test( test,**kwargs )
            for s in success:
                echo_string( f"    {s}",**kwargs, )
            for f in failure:
                echo_string( f"    ERROR: {f}",**kwargs, )

##
## Grep for SUCCESS or FAILURE in a log file;
## add those messages to two list-of-strings variables
##
def success_failure_in_logfile( logoutput,**kwargs ) -> tuple[list[str],list[str]] :
    success : list[str] = kwargs.get( "success",[] )
    failure : list[str] = kwargs.get( "failure",[] )
    with open( logoutput,"r" ) as loglines:
        for line in loglines:
            if succ := re.match( r'SUCCESS: (.*)$',line ):
                msg : str = succ.groups()[0]
                trace_string( msg,**kwargs )
                success.append( msg )
            if fail := re.match( r'FAILURE: (.*)$',line ):
                msg = fail.groups()[0]
                trace_string( msg,**kwargs )
                failure.append( msg )
    return success,failure

##
## Lines from the grep file are added to success unconditionally
## This means it's up to the test to interpret these lines
## as containing the right thing or not
##
def add_grep_lines( grepfile,success : str,**kwargs ) -> str:
    try:
        with open( grepfile,"r" ) as grep_out:
            for line in grep_out.readlines():
                line = line.strip("\n")
                success.append( f"grep output: {line}" )
    except:
        echo_warning( f"Can not find grep file: {grepfile}",**kwargs )
        pass
    return success

