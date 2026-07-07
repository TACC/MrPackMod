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
from typing import Any,Optional,TypedDict

from MrPackMod.basics  import clean_title,remove_macros,\
    echo_string,trace_string,echo_warning,trace_var,error_abort,\
    isnull,nonnull, nonzero_keyword,\
    line_strip_conditionals,ModuleLoadStrategy
from MrPackMod.names   import package_names,scriptsdir_name,builddir_name,\
    DirNamesDict
from MrPackMod.process import process_execute, process_initiate, \
    create_dir,ensure_dir,get_value_from_loaded
from MrPackMod.scripts import export_compilers_script,\
    cmake_configure_script,cmake_build_script,make_build_script,\
    file_to_exist_script,ldd_script,run_script
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
    parser.add_argument( '-t',"--test_value",default="0" )

    parser.add_argument( '-k','--keywords',default="" )
    parser.add_argument( '-p',"--run_prefix" )
    # existence
    parser.add_argument( '-l',"--ldd", action='store_true', default=False )
    parser.add_argument( '-x',"--executable",action='store_true', default=False )
    parser.add_argument( "-d","--dir" )

    # grep in file
    parser.add_argument( "-g","--grep" )

    # universal
    parser.add_argument( '-i','--title',default="some cmake test" )
    parser.add_argument( 'program', nargs=1, help=f"program.c" )

    argument_list = shlex.split( f"{test_options}" )
    arguments  = parser.parse_args( argument_list )
    # convert argparse namespace to dictionary
    arguments_dict : dict = vars(arguments)
    arguments_dict["do_run"]  = arguments.run or arguments.run_in_dir
    arguments_dict["dirtype"] = arguments.dir
    arguments_dict["program"] = arguments.program[0]

    trace_string( f" .. parameters: {arguments_dict}",**kwargs )
    return arguments_dict

##
## Return directory, actual file name & name with LMOD variable unexpanded
##
def file_to_exist_names( package : str,dirtype : str,program : str,**kwargs ) -> tuple[str,str,str]:
    if isnull(dirtype) or dirtype=="dir":
        dirvar : str = dir_variable(package,"dir")
        filedir_to_report : str = f"${{{dirvar}}}"
    elif dirtype in [ "inc","lib","bin", ]:
        dirvar = dir_variable(package,dirtype)
        filedir_to_report = f"${{{dirvar}}}"
    else:
        filedir_to_report = f"${{TACC_{package.upper()}_DIR}}/{dirtype}"
    filedir        : str = remove_macros( filedir_to_report,**kwargs )
    file_to_test   : str = f"{filedir}/{program}"
    file_to_report : str = f"{filedir_to_report}/{program}"
    return filedir,file_to_test,file_to_report

def dir_variable( package: str, dirtype: str = "dir" ) -> str:
    return f"TACC_{package.upper()}_{dirtype.upper()}"

##
## Add lines to a process for testing the existence of a file
## In case we grep something in that file, return the name of the grep file
##
def execute_grep(
        package: str, dirtype: str, program: str, grep: str, **kwargs: Any, ) -> str:
    _,file_to_test,file_to_report = file_to_exist_names( package,dirtype,program,**kwargs )
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

def do_ldd_test(
        title : str,
        package : str, dirtype : str, program : str,
        success : list[str],failure : list[str],**kwargs : Any,
        ) -> tuple[list[str],list[str]]:

    filedir,file_to_test,file_to_report = \
        file_to_exist_names(
            package,dirtype,program,**kwargs )
    program_clean : str = re.sub( '/','',program )
    output : OutputDict = \
        start_test_stage( f"{title}, ldd test", **{ **kwargs, "package":program_clean }, )
    # prog_and_dirs : list[Optional[str]] = [file_to_test,file_to_report,".",filedir]
    dirnames : DirNamesDict = {
        "scriptsdir":output["logdir"],
        "srcdir":kwargs.get("startdir",".")+"/"+dirtype,
        "builddir":create_dir( "build",**kwargs ),
        "prefixdir":"" # for testing it's enough to have the result in `build',
    }
    res : Optional[str] = get_value_from_loaded(
        ldd_script,[program,dirnames],**{ **kwargs,**output } )
    success,failure = end_test_stage( success,failure,output,**kwargs )
    return success,failure

class RundataDict(TypedDict):
    programname : str
    runprefix  : Optional[str]
    rundir     : Optional[str]
    builddir   : Optional[str]
    runargs    : Optional[str]

def do_existence_test(
        test_definition: str, **kwargs: Any,
        ) -> tuple[list[str], list[str]]:

    run_config : dict = test_config( test_definition,**kwargs )
    testtitle : str = run_config["testtitle"]

    run_config["chdir"]   = create_dir( "build",**kwargs )

    success  : list[str] = []
    failure  : list[str] = []

    #
    # existence
    #
    args = run_config["package"],run_config["dirtype"],run_config["program"],\
        run_config["grep"],run_config["executable"]
    package,dirtype,program,grep,executable = args
    filedir,file_to_test,file_to_report = \
        file_to_exist_names(package,dirtype,program,**kwargs)
    fileargs = [ program,filedir,file_to_test,file_to_report ]
    output : OutputDict = \
        start_test_stage( f"{testtitle}, existence test",**{ **kwargs,**run_config } )
    retval : Optional[str] = get_value_from_loaded(
        file_to_exist_script,fileargs,
        **{ **kwargs,**output} )
    success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # run and ldd
    #

    # filedir,file_to_test,file_to_report = \
    #     file_to_exist_names(
    #         package,dirtype,program,**{ **kwargs,"installing":False } )

    do_run,ldd = run_config["do_run"],run_config["ldd"]
    if run_config.get("ldd"):
        dirnames : DirNamesDict = {
            "scriptsdir":kwargs.get( "scriptsdir",kwargs.get("startdir",".")+"/mpmscripts" ),
            "srcdir":filedir,
            "builddir":filedir, ## ldd script uses builddir as location 
            "prefixdir":"" # for testing it's enough to have the result in `build',
        }
        output = \
            start_test_stage( f"{testtitle}, ldd test", **{ **kwargs, **run_config } )
        retval = get_value_from_loaded(
            ldd_script,
            [ program,dirnames ],
            **{ **kwargs,**output } )
        success,failure = end_test_stage( success,failure,output,**kwargs )

        # success,failure = do_ldd_test(
        #     testtitle, run_config["package"],run_config["dirtype"],run_config["program"],
        #     success,failure, **{ **kwargs,"installing":False } )

    #
    # run!
    #
    if do_run:
        dirnames : DirNamesDict = {
            "scriptsdir" : "",
            "scrdir"     : None,
            "builddir"   : run_config.get("run_in_dir"),
            "prefixdir"  : run_config.get("run_prefix"),
        }
        success,failure = do_run_test(
            testtitle,
            program,dirnames,run_config.get("run_args"),
            success,failure,**kwargs, )
    return success,failure

def do_run_test( title : str,
                 programname : str,dirnames : DirNamesDict,runargs : str,
                 success : list[str],failure : list[str],**kwargs : Any
                ) -> tuple[list[str],list[str]]:
    output = start_test_stage( f"{title}, run", **{ **kwargs,"package":programname } )
    res : Optional[str] = get_value_from_loaded(
        run_script,[ programname,dirnames,runargs ],**{ **kwargs,**output } )
    success,failure = end_test_stage( success,failure,output,**kwargs )
    if ( res is not None ) and ( returnval := re.search( r"SUCCESS.*\[([^\[\]]+)\]",res ) ):
        outputval = returnval.groups()[0]
        #print( f"success output: {outputval}" )
        if testvalue := kwargs.get("testvalue"):
            print( f"Comparing output={outputval} against {testvalue}" )
    return success,failure

def do_cmake_test(
        test_definition: str, **kwargs: Any,
        ) -> tuple[list[str], list[str]]:

    run_config : dict = test_config( test_definition,**kwargs )
    testtitle : str = run_config["testtitle"]

    do_run    = run_config.get("do_run")
    testvalue = run_config.get("test_value")

    program : str = run_config["program"]
    if ( name_ext := re.search( r'^(.+)\.(.+)$',program ) ) is not None:
        programname,programext = name_ext.groups()
        run_config["programname"] = programname
        run_config["programext"]  = programext
    else: error_abort( f"Can not parse <<{program}>> as name.ext",**kwargs )

    # programsrcdir    : str = os.getcwd()+"/"+programext
    # programbuilddir  : str = create_dir( "build",**kwargs )
    # cmakeprefixdir : str = "" # for testing it's enough to have the result in `build'
    # prog_and_dirs : list[str] = [programname,programsrcdir,programbuilddir,cmakeprefixdir]
    dirnames : DirNamesDict = {
        "scriptsdir":"mpmscripts",
        "srcdir":os.getcwd()+"/"+programext,
        "builddir":create_dir( "build",**kwargs ),
        "prefixdir":"" # for testing it's enough to have the result in `build',
    }
    success : list[str] = []; failure : list[str] = []

    #
    # Cmake & compile
    #
    output : OutputDict = \
        start_test_stage( "cmake build and make",**{ **kwargs,"package":programname, } )
    res : Optional[str] = get_value_from_loaded(
        cmake_configure_script,[ programname,dirnames ],
        **{ **kwargs, **output, 'pkgconfig':"yes", 'cmakeconfig':"yes" } )
    failed : bool = ( res is not None ) and ( re.match( 'FAILURE',res ) is not None )
    if not failed:
        res = get_value_from_loaded(
            cmake_build_script,[ programname,dirnames, ],
            **{ **kwargs,**output } )
        failed = ( res is not None ) and ( re.match( 'FAILURE',res ) is not None )
    success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # Check library dependencies satisfied & run
    #
    output = start_test_stage( "ldd",**{ **kwargs,"package":programname } )
    # VLE maybe we need to adjust prog_and_dirs[1] : needs to be file_to_report
    # prog_and_dirs[1] = programext
    res = get_value_from_loaded(
        ldd_script,[ programname,dirnames ],
        **{ **kwargs,**output } )
    success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # Run
    #
    if do_run:
        dirnames : DirNamesDict = {
            "scriptsdir" : "",
            "scrdir"     : None,
            "builddir"   : run_config.get("run_in_dir"),
            "prefixdir"  : run_config.get("run_prefix"),
        }
        success,failure = do_run_test(
            testtitle,
            program,dirnames,run_config.get("run_args"),
            success,failure,**{ **kwargs,**output } )
    return success,failure

def do_make_test(
        test_definition: str,**kwargs: Any, ) -> tuple[list[str], list[str]]:

    run_config : dict = test_config( test_definition,**kwargs )
    testtitle : str = run_config["testtitle"]

    program : str = run_config["program"]
    if ( name_ext := re.search( r'^(.+)\.(.+)$',program ) ) is not None:
        programname,programext = name_ext.groups()
        run_config["programname"] = programname
        run_config["programext"]  = programext
    else: error_abort( f"Can not parse <<{program}>> as name.ext",**kwargs )

    programsrcdir    : str = os.getcwd()+"/"+programext
    programbuilddir  : str = create_dir( "build",**kwargs )
    prefixdir        : str = "" # for testing it's enough to have the result in `build'
    prog_and_dirs : list[str] = [programname,programsrcdir,programbuilddir,prefixdir]

    success : list[str] = []; failure : list[str] = []

    #
    # Make compilation
    #
    output : OutputDict = \
        start_test_stage( "make compile",**{ **kwargs,"package":programname, } )
    res : Optional[str] = get_value_from_loaded(
        make_build_script,prog_and_dirs,**{ **kwargs,**output } )
    success,failure = end_test_stage( success,failure,output,**kwargs )
    return success,failure

    #
    # execution
    #
    output = start_test_stage( "exec",**{ **kwargs,"package":name,"installing":False, } )
    # are library dependencies satisfied
    process_execute( f"ldd {name}",**kwargs,**output )
    # run!
    if do_run:
        process_execute( f"./{name}",**kwargs,**output )
    success,failure = end_test_stage( success,failure,output,**kwargs )

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

def test_config( test_definition : str,**kwargs : Any ) -> dict:
    #parsed_options
    run_config : dict = parse_command( test_definition,**kwargs )
    trace_string( f"Test options: {run_config}",**kwargs )

    if ( package := package_names( **kwargs )[0] ) is not None:
        run_config["package"] = package
    else: error_abort( "Expected package name",**kwargs )

    if ( program  := run_config.get("program") ) is not None:
        program_clean : str = re.sub( '/','',program )
    else: error_abort( "Expecting program parameter",**kwargs )

    testtitle     = run_config.pop("title") # need to remove because we pass a new title below
    run_config["testtitle"] = testtitle
    cleantitle = clean_title( testtitle )
    run_config["scriptsdir"] = f"{os.getcwd()}/mpmscripts_exist_{cleantitle}"

    echo_string( f"\nTEST: {testtitle}",**kwargs )
    return run_config

##
## Test driver
##

def do_tests( **kwargs: Any ) -> None:

    #
    # existence tests
    #
    if tests := kwargs.get( "EXISTENCETEST" ):
        for test in tests:
            if test_match( test,kwargs["match"],kwargs["filter"],**kwargs ):
                success,failure = do_existence_test(
                    test,**kwargs,moduleloadstrategy=ModuleLoadStrategy.package )
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
                success,failure = do_cmake_test(
                    test,**kwargs,moduleloadstrategy=ModuleLoadStrategy.package )
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
                success,failure = do_make_test( 
                    test,**kwargs,moduleloadstrategy=ModuleLoadStrategy.package )
                for s in success:
                    echo_string( f"    {s}",**kwargs, )
                for f in failure:
                    echo_string( f"    ERROR: {f}",**kwargs, )
            else: report_skipped_test( test,**kwargs )

def report_skipped_test( test_definition : str,**kwargs : Any ) -> None:
    run_config : dict = parse_command( test_definition,**kwargs )
    title : str   = run_config.pop("title")
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

