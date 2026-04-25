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
from typing import Any

from MrPackMod import config 
from MrPackMod import download
from MrPackMod import info 
from MrPackMod.install import export_compilers,cmake_options
from MrPackMod import modulefile
from MrPackMod import names 
from MrPackMod.process import process_execute, process_initiate, \
    create_dir,ensure_dir
from MrPackMod.error   import isnull,nonnull, nonzero_keyword,error_abort
from MrPackMod.tracing import echo_string,trace_string,echo_warning,trace_var
from MrPackMod.testing import start_test_stage,end_test_stage,success_failure_in_logfile,\
    OutputDict

#
# Parse the options with argparse
#
def parse_command( test_options: str, **kwargs: Any ) -> dict[str, Any]:
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
        file_to_test   = f"{filedir}/{program}"
        file_to_report = f"{filedir}/{program}"
    return filedir,file_to_test,file_to_report

##
## Add process lines for testing file existence
##
def execute_file_to_exist(
    package: str,
    dirtype: str,
    program: str,
    **kwargs: Any,
) -> None:
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
def execute_grep(
    package: str,
    dirtype: str,
    program: str,
    grep: str,
    **kwargs: Any,
) -> str:
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

def execute_cmake_script( program: str, ext: str, **kwargs: Any ) -> None:
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

def execute_ldd_script( program: str, **kwargs: Any ) -> None:
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
def execute_run_script( program : str,run_config : dict,**kwargs ) -> None:
    tracestring : str = f"run program={program}"
    if nonnull( prefix := run_config["run_prefix"] ):
        cmdline :str = f"{prefix}{program}"
    else:
        cmdline = f"./{program}"
    if nonnull( run_config["run_in_dir"] ):
        dir = run_config["run_dir"]
        tracestring += f" in dir: {dir}"
        cmdline = f"cd {dir} && {cmdline}"
    if nonnull( args:=run_config["run_args"] ):
        tracestring += f" with args={args}"
        cmdline += args
    trace_string( tracestring,**kwargs )
    trace_string( f" .. cmdline: {cmdline}",**kwargs )
    logdir : str = kwargs["logdir"]
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

def dir_variable( package: str, dirtype: str ) -> str:
    return f"TACC_{package.upper()}_{dirtype.upper()}"

def get_run_configuration(
    parsed_options: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    run_params : list[str] = [
        "run_in_dir","run_args","run_prefix","do_run",
        ]
    run_config : dict = {}
    for p in run_params:
        try:
            run_config[p] = parsed_options[p]
        except:
            error_abort( f"Could not find run option <<{p}>> in parsed option",**kwargs )
    package,_   = names.package_names( **kwargs )
    dirtype     = parsed_options["dirtype"]
    program     = parsed_options["program"]
    filedir,_,_ = file_to_exist( package,dirtype,program,**kwargs )
    run_config["run_dir"] = filedir
    return run_config

def do_existence_test(
    test_options: str,
    **kwargs: Any,
) -> tuple[list[str], list[str]]:
    parsed_options : dict = parse_command( test_options,**kwargs )
    trace_string( f"Existence test options: {parsed_options}",**kwargs )
    run_config = get_run_configuration(parsed_options,**kwargs)
    try :
        title      = parsed_options["test_title"]
        program    = parsed_options["program"]
        dirtype    = parsed_options["dirtype"]
        grep       = parsed_options["grep"]
        ldd        = parsed_options["ldd"]
    except KeyError:
        error_abort( "Did not find program/grep/ldd/dirtype/do_run",**kwargs )

    logdir   : str       = ensure_dir( os.getcwd()+"/"+kwargs.get("logdir","logfiles") )
    builddir : str       = create_dir( "build",**kwargs )
    success  : list[str] = []
    failure  : list[str] = []

    #
    # existence
    #
    package,_ = names.package_names( **kwargs )
    # program can contain a path
    program_clean = re.sub( '/','',program )
    output : OutputDict = \
        start_test_stage( "exists",
                          kwargs, # note dict
                          title=title,chdir=builddir,
                          package=program_clean,
                          linedisplay=trace_string ) 
    execute_file_to_exist( package,dirtype,program,**kwargs,**output )
    if nonnull(grep):
        grepfile : str = execute_grep( package,dirtype,program,grep,**kwargs,**output )
    else: grepfile = ""
    success,failure = end_test_stage( success,failure,kwargs,output )
    if nonnull(grepfile):
        success = add_grep_lines( f"{grepfile}",success,**kwargs,**output )

    #
    # run and ldd
    #
    if ( do_run := run_config["do_run"] ) or ldd:
        filedir,file_to_test,file_to_report = \
            file_to_exist(package,dirtype,program,**kwargs,**output)
        output = \
            start_test_stage( "exec",kwargs, # dict!
                              package=program_clean,
                              title=title,chdir=builddir,
                              linedisplay=trace_string ) 
        if ldd:
            # are library dependencies satisfied
            execute_ldd_script( file_to_test,**kwargs,**output )
        # run!
        if do_run:
            execute_run_script( program,run_config,**kwargs,**output )
        success,failure = end_test_stage( success,failure,kwargs,output )
    return success,failure

def do_cmake_test(
    test_options: str,
    **kwargs: Any,
) -> tuple[list[str], list[str]]:

    parsed_options : dict = parse_command( test_options,**kwargs )
    run_config : dict = get_run_configuration( parsed_options,**kwargs )
    try :
        program = parsed_options["program"]
        title   = parsed_options["test_title"]
    except KeyError:
        error_abort( "Did not find program/title/do_run",**kwargs )

    if name_ext := re.search( r'^(.+)\.(.+)$',program ):
        name,ext = name_ext.groups()
    else:
        error_abort( f"Can not parse <<{program}>> as name.ext",**kwargs )
    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )

    success : list[str] = []
    failure : list[str] = []

    #
    # Cmake & compile
    #
    output : OutputDict = \
        start_test_stage( "compile",kwargs,logdir=logdir,chdir=builddir,package=name, ) # note dict
    execute_cmake_script( name,ext,**kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    #
    # Check library dependencies satisfied & run
    #
    output = start_test_stage( "exec",kwargs,logdir=logdir,chdir=builddir,package=name, )
    execute_ldd_script( name,**kwargs,**output )
    if nonnull( run_config["do_run"] ):
        execute_run_script( name,run_config,**kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    return success,failure

def do_make_test(
    test_options: str,
    **kwargs: Any,
) -> tuple[list[str], list[str]]:
    failure : list[str] = []; success : list[str] = []
    parsed_options : dict = parse_command( test_options,**kwargs )
    try :
        program = parsed_options["program"]
        title   = parsed_options["test_title"]
        do_run  = parsed_options["do_run"]
    except KeyError:
        error_abort( "Did not find program/title/do_run",**kwargs )

    if name_ext := re.search( r'^(.+)\.(.+)$',program ):
        name,ext = name_ext.groups()
    else:
        error_abort( f"program <<{program}>> can not be parsed as name.ext",**kwargs )
    logdir : str = ensure_dir( "logfiles",**kwargs )
    builddir : str = create_dir( "build",**kwargs )

    #
    # compilation
    #
    output : OutputDict = \
        start_test_stage( "compile",kwargs,logdir=logdir,chdir=builddir,package=name, ) # note dict
    # set up for make
    compiler_exports = export_compilers( **kwargs,**output )
    cmakeflags = cmake_options( **kwargs )
    process_execute\
        ( f"{compiler_exports} && make -f ../{ext}/Makefile SRCDIR=../{ext} PROJECTNAME={name} {name}",
          **kwargs,**output )
    process_execute( f"make", **kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )
    if os.path.exists( f"{builddir}/{name}" ):
        success.append( f"executable <<{name}>> created" )
    else:
        failure.append( f"Failed to create executable <<{name}>>" )

    #
    # execution
    #
    output = start_test_stage( "exec",kwargs,logdir=logdir,chdir=builddir,package=name, ) # note dict
    # are library dependencies satisfied
    process_execute( f"ldd {name}",**kwargs,**output )
    # run!
    if do_run:
        process_execute( f"./{name}",**kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    return success,failure

#
# If no filters and no matches, accept.
# If testname matches a filter, discard.
# Next, if testname maches a match, accept
# default case: reject
# 
def test_match( testname : str,matching : str,filtering : str,**kwargs ) -> bool:
    #breakpoint()
    if isnull(matching) and isnull(filtering):
        trace_string( f"Test: {testname} accepted by default",**kwargs )
        return True
    matches : list[str] = matching.lower().split(",")
    filters : list[str] = filtering.lower().split(",")
    for f in filters:
        if nonnull(f) and re.search(f,testname.lower()):
            trace_string( f"Test: {testname} rejected by filter: {f}",**kwargs )
            return False
    for m in matches:
        if nonnull(m) and re.search(m,testname.lower()):
            trace_string( f"Test: {testname} accepted by match: {m}",**kwargs )
            return True
    return False

def do_tests( **kwargs: Any ) -> None:
    #
    # existence tests
    #
    if tests := kwargs.get( "EXISTENCETEST" ):
        for test in tests:
            if test_match( test,kwargs["match"],kwargs["filter"],**kwargs ):
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
            if test_match( test,kwargs["match"],kwargs["filter"],**kwargs ):
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
            if test_match( test,kwargs["match"],kwargs["filter"],**kwargs ):
                success,failure = do_make_test( test,**kwargs )
                for s in success:
                    echo_string( f"    {s}",**kwargs, )
                for f in failure:
                    echo_string( f"    ERROR: {f}",**kwargs, )

##
## Lines from the grep file are added to success unconditionally
## This means it's up to the test to interpret these lines
## as containing the right thing or not
##
def add_grep_lines(
    grepfile: str,
    success: list[str],
    **kwargs: Any,
) -> list[str]:
    try:
        with open( grepfile,"r" ) as grep_out:
            for line in grep_out.readlines():
                line = line.strip("\n")
                success.append( f"grep output: {line}" )
    except:
        echo_warning( f"Can not find grep file: {grepfile}",**kwargs )
        pass
    return success

