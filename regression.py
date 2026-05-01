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

from MrPackMod.install import export_compilers,cmake_options,\
    cmake_configure_script,cmake_build_script
from MrPackMod.names   import package_names
from MrPackMod.process import process_execute, process_initiate, \
    create_dir,ensure_dir,get_value_from_loaded
from MrPackMod.error   import isnull,nonnull, nonzero_keyword,error_abort,\
    abort_on_zero_keyword
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
    # convert argparse namespace to dictionary
    arguments_dict : dict = vars(arguments)
    #print( arguments_dict )
    arguments_dict["do_run"]  = arguments.run or arguments.run_in_dir
    arguments_dict["dirtype"] = arguments.dir
    arguments_dict["program"] = arguments.program[0]

    print( f"Test: "+arguments_dict["title"] )
    trace_string( f" .. parameters: {arguments_dict}",**kwargs )
    return arguments_dict

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
def file_to_exist_script( args : list[str],**kwargs : Any, ) -> tuple[str,str]:
    package,dirtype,program,grep = args
    title : str = f"Test existence of {package} in {dirtype}"
    filedir,file_to_test,file_to_report = file_to_exist(package,dirtype,program,**kwargs)
    script : str = f"""
if [ ! -z \"{filedir}\" -a -d \"{filedir}\" ] ; then 
    echo ' .. directory {filedir} exists'
else 
    echo 'FAILURE: {filedir} does not exist'
fi

if [ -f \"{file_to_test}\" ] ; then
    echo 'SUCCESS: file exists: <<{file_to_report}>> '
else
    echo 'FAILURE: file does not exist <<{file_to_report}>>'
fi
        """
    if nonnull( grep ):
        program_clean = re.sub( '/','',program )
        grep_output_file : str = f"{os.getcwd()}/{program_clean}_grep.out"
        script += f"""
if [ -f \"{file_to_test}\" ] ; then
    grep \"{grep}\" {file_to_test} >{grep_output_file} 2>&1 ; 
fi
        """
    return script,title

def execute_file_to_exist(
        package : str, dirtype : str, program : str, grep : str,
        **kwargs : Any, ) -> str:
    return get_value_from_loaded(
        file_to_exist_script,[package,dirtype,program,grep],**kwargs )

##
## Add lines to a process for testing the existence of a file
## In case we grep something in that file, return the name of the grep file
##
def execute_grep(
        package: str, dirtype: str, program: str, grep: str, **kwargs: Any, ) -> str:
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

def cmake_script( args : list[str],**kwargs ) -> tuple[str,str]:
    program,ext,cmakebuilddir = args
    compiler_exports = export_compilers( **kwargs )
    cmakeflags = cmake_options( **kwargs )
    scriptdir : str = abort_on_zero_keyword( "scriptdir",**kwargs )
    script : str = f"""
{compiler_exports} && cmake -D PROJECTNAME={program} -B {cmakebuilddir} {cmakeflags} -S {scriptdir}/{ext}
cd {cmakebuilddir}
make V=1
if [ -f \"{program}\" ] ; then
    found=1 && echo SUCCESS: program created
else
    found=0 && echo FAILURE: program not created
fi
    """
    return script,f"CMake configure and make program {program}"

def execute_cmake_script(
        program: str, ext: str, cmakebuilddir : str,**kwargs: Any ) -> str:
    return get_value_from_loaded(cmake_script,[program,ext,cmakebuilddir],**kwargs )

def ldd_script( args : list[str],**kwargs ) -> tuple[str,str]:
    program,cmakebuilddir = args
    lddout = "ldd.out"
    script = f"""
cd {cmakebuilddir}
rm -f {lddout}

if [ -f \"{program}\" ] ; then
    ldd {program} 2>&1 | tee {lddout} ; 
else
    touch {lddout} ; 
fi

if [ -f \"{program}\" ] ; then
    notfound=$( grep \"not found\" {lddout} | wc -l )
    if [ $notfound -eq 0 ] ; then
        echo \"SUCCESS: all libraries resolved\" 
    else
        echo \"FAILURE: $notfound references not found\"
    fi
fi
    """
    return script,f"ldd test on {program}"

def execute_ldd_script( program: str, cmakebuilddir : str, **kwargs: Any ) -> str:
    return get_value_from_loaded( ldd_script,[program,cmakebuilddir],**kwargs )

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

def dir_variable( package: str, dirtype: str = "dir" ) -> str:
    return f"TACC_{package.upper()}_{dirtype.upper()}"

def do_existence_test(
        test_options: str,
        **kwargs: Any,
        ) -> tuple[list[str], list[str]]:
    package,_ = package_names( **kwargs )
    options_dict : dict = parse_command( test_options,**kwargs )
    trace_string( f"Existence test options: {options_dict}",**kwargs )
    program = options_dict["program"]
    title   = options_dict.pop("title")
    dirtype = options_dict.get("dirtype")

    filedir,_,_ = file_to_exist( package,dirtype,program, **kwargs )
    options_dict["run_dir"] = filedir
    options_dict["chdir"]   = create_dir( "build",**kwargs )
    #logdir   : str       = ensure_dir( os.getcwd()+"/"+kwargs.get("logdir","logfiles") )

    success  : list[str] = []
    failure  : list[str] = []

    #
    # existence
    #
    # program can contain a path
    program_clean = re.sub( '/','',program )
    output : OutputDict = \
        start_test_stage( "exists",kwargs, # note dict
                          title=f"{title}, existence test",**options_dict,
                          package=program_clean,linedisplay=trace_string ) 
    execute_file_to_exist( package,dirtype,program,options_dict["grep"],**kwargs,**output )
    # if nonnull( grep := options_dict["grep"] ):
    #     grepfile : str = execute_grep( package,dirtype,program,grep,**kwargs,**output )
    # else:
    #     grepfile = ""
    success,failure = end_test_stage( success,failure,kwargs,output )
    # if nonnull(grepfile):
    #     success = add_grep_lines( f"{grepfile}",success,**kwargs,**output )

    #
    # run and ldd
    #
    do_run,ldd = options_dict["do_run"],options_dict["ldd"]
    if do_run or ldd:
        filedir,file_to_test,file_to_report = \
            file_to_exist(package,dirtype,program,**kwargs,**output)
        output = \
            start_test_stage( "exec",kwargs, # dict!
                              title=f"{title}, run/ldd test",**options_dict,
                              package=program_clean,linedisplay=trace_string ) 
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

    #parsed_options
    run_config : dict = parse_command( test_options,**kwargs )
    ## ???? run_config : dict = get_run_configuration( parsed_options,**kwargs )
    try :
        program = run_config["program"]
        title   = run_config["title"]
    except KeyError:
        error_abort( "Did not find program/title/do_run",**kwargs )

    if name_ext := re.search( r'^(.+)\.(.+)$',program ):
        name,ext = name_ext.groups()
    else:
        error_abort( f"Can not parse <<{program}>> as name.ext",**kwargs )
    logdir : str = ensure_dir( "logfiles",**kwargs )
    cmakesrcdir    : str = os.getcwd()+"/"+ext
    cmakebuilddir  : str = create_dir( "build",**kwargs )
    cmakeprefixdir : str = "" # for testing it's enough to have the result in `build'

    success : list[str] = []
    failure : list[str] = []

    #
    # Cmake & compile
    #

    output : OutputDict = \
        start_test_stage(
            "cmake build",kwargs, # note dict
            title=f"{title}, cmake/make stage",package=name,terminal="suppress", )
    #execute_cmake_script( name,ext,cmakebuilddir,**kwargs, **output )
    res : str = get_value_from_loaded(
        cmake_configure_script,[name,cmakesrcdir,cmakebuilddir,cmakeprefixdir],
        **kwargs,**output )
    if not re.match( 'FAILURE',res ):
        res = get_value_from_loaded(
            cmake_build_script,[name,cmakesrcdir,cmakebuilddir,cmakeprefixdir],
            **kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    return success,failure

    #
    # Check library dependencies satisfied & run
    #

    output = start_test_stage(
        "exec",kwargs,
        title=f"{title}, ldd/run stage",package=name,terminal="suppress", )
    execute_ldd_script( name,cmakebuilddir,**kwargs,**output )
    if nonnull( run_config["do_run"] ):
        execute_run_script( name,run_config,**kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )

    return success,failure

def do_make_test(
    test_options: str,
    **kwargs: Any,
) -> tuple[list[str], list[str]]:
    failure : list[str] = []; success : list[str] = []
    run_config : dict = parse_command( test_options,**kwargs )
    try :
        program = run_config["program"]
        title   = run_config["title"]
        do_run  = run_config["do_run"]
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
        start_test_stage( "compile",kwargs,chdir=builddir,package=name, ) # note dict
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
    output = start_test_stage( "exec",kwargs,chdir=builddir,package=name, ) # note dict
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
    # first the reject tests
    filters  : list[str] = filtering.lower().split(",")
    keywords : str       = kwargs.get("keywords","")
    for f in filters:
        if nonnull(f) and \
           ( re.search(f,testname.lower()) or re.search(f,keywords) ):
            trace_string( f"Test: {testname} rejected by filter: {f}",**kwargs )
            return False
    if isnull(matching):
        trace_string( f"Test: {testname} accepted by default",**kwargs )
        return True
    # accept if there are no matches
    matches  : list[str] = matching.lower().split(",")
    # otherwise only accept if satisfies specific match
    for m in matches:
        if nonnull(m) and \
           ( re.search(m,testname.lower()) or re.search(m,keywords) ):
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
            else: report_skipped_test( test,**kwargs )
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
            else: report_skipped_test( test,**kwargs )
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
            else: report_skipped_test( test,**kwargs )

def report_skipped_test( test_options : str,**kwargs : Any ) -> None:
    options_dict : dict = parse_command( test_options,**kwargs )
    title : str   = options_dict.pop("title")
    echo_string( f"Skipping test: {title}",**kwargs )

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

