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

from MrPackMod.basics  import clean_title,\
    echo_string,trace_string,echo_warning,trace_var,error_abort,\
    isnull,nonnull, nonzero_keyword
from MrPackMod.install import cmake_options,cmake_configure_script,cmake_build_script
from MrPackMod.names   import package_names,scriptsdir_name,builddir_name
from MrPackMod.process import process_execute, process_initiate, \
    create_dir,ensure_dir,get_value_from_loaded,\
    line_strip_conditionals,file_to_exist_names
from MrPackMod.scripts import export_compilers_script
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

    ##print( f"Test: "+arguments_dict["title"] )
    trace_string( f" .. parameters: {arguments_dict}",**kwargs )
    return arguments_dict

##
## Add process lines for testing file existence
##
def file_to_exist_script( args : list[str],**kwargs : Any, ) -> tuple[str,str]:
    package,dirtype,program,grep,executable = args
    title : str = f"Test existence of {package} in {dirtype}"
    filedir,file_to_test,file_to_report = file_to_exist_names(package,dirtype,program,**kwargs)
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
    exit 1
fi
        """
    if executable:
        script += f"""
if [ -x \"{file_to_test}\" ] ; then
    echo "SUCCESS: file is executable"
else
    echo "FAILURE: file is not executable"
fi
        """
    if nonnull( grep ):
        program_clean = re.sub( '/','',program )
        grep_output_file : str = f"{os.getcwd()}/{program_clean}_grep.out"
        script += f"""
if [ -f \"{file_to_test}\" ] ; then
    grep \"{grep}\" {file_to_test} >{grep_output_file} 2>&1
    echo INFORMATION: grep result is $( head -n 1 {grep_output_file} )
fi
        """
    return script,title

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

def ldd_script( args : list[str],**kwargs ) -> tuple[str,str]:
    program,programdir,cmakebuilddir,cmakeprefixdir = args
    programdir = re.sub( r'\${(.+)}/',r'\1',programdir )
    scriptsdir : str = scriptsdir_name( **kwargs )
    lddout = f"{scriptsdir}/ldd_{programdir}_{program}.out"
    where : str = cmakeprefixdir if nonnull(cmakeprefixdir) else cmakebuilddir
    trace_string( f"Generate ldd script for file={program} in dir={where}",**kwargs )
    script = f"""
cd {where}
rm -f {lddout}

if [ -f \"{program}\" ] ; then
    ldd {program} 2>&1 | tee {lddout}
else
    touch {lddout}
fi

if [ -f \"{program}\" ] ; then
    notfound=$( grep \"not found\" {lddout} | wc -l )
    if [ $notfound -eq 0 ] ; then
        echo \"SUCCESS: all libraries resolved\" 
    else
        echo \"FAILURE: $notfound references not found\"
    fi
else
    echo FAILURE: could not find program={program} to run ldd on
fi
    """
    return script,f"ldd test on {programdir}/{program}"

##
## Run a program
##
def run_script( runstuff : list[str],**kwargs : Any ) -> tuple[str,str]:
    program,prefix,rundir,args = runstuff 
    title : str = f"run program {program}"
    if nonnull( prefix ):
        cmdline :str = f"{prefix}{program}"
    else:
        cmdline = f"./{program}"
    if nonnull( rundir ):
        cdir = rundir
    else:
        builddir = builddir_name(**kwargs)
        cdir = builddir
    if nonnull( args ):
        cmdline += f" {args}"
    script : str = f"""
cd {cdir}
result=$( {cmdline} {args} )
if [ $? -eq 0 ] ; then 
    echo "SUCCESS: running {program} with output [${{result}}]"
else
    echo "FAILURE: running {program}"
fi 
#echo ${{output}}
    """
    return script,title

class RundataDict(TypedDict):
    programname : str
    runprefix  : Optional[str]
    rundir     : Optional[str]
    builddir   : Optional[str]
    runargs    : Optional[str]

def do_existence_test(
        test_definition: str, **kwargs: Any,
        ) -> tuple[list[str], list[str]]:

    if ( package := package_names( **kwargs )[0] ) is None:
        error_abort( "Expected package name",**kwargs )
    run_config : dict = parse_command( test_definition,**kwargs )
    trace_string( f"Existence test options: {run_config}",**kwargs )
    if ( program := run_config.get("program") ) is None:
        error_abort( "Need program parameter",**kwargs )
    title   = run_config.pop("title") # need to remove because we pass a new title below
    dirtype = run_config.get("dirtype","")
    grep    = run_config.get("grep")
    executable = run_config.get("executable")

    # VLE these lines are also in file_to_exist_script
    # filedir,_,_ = file_to_exist_names( package,dirtype,program, **kwargs )
    # run_config["run_dir"] = filedir

    run_config["chdir"]   = create_dir( "build",**kwargs )

    success  : list[str] = []
    failure  : list[str] = []

    #
    # existence
    #
    # program can contain a path
    if program:
        program_clean : str = re.sub( '/','',program )
    else: program_clean = "program"
    cleantitle = clean_title( title )
    run_config["scriptsdir"] = f"{os.getcwd()}/mpmscripts_exist_{cleantitle}"
    output : OutputDict = \
        start_test_stage(
            "exists",
            **{ **kwargs,**run_config, # weird construct to placate mypy
                "title":f"{title}, existence test","package":program_clean, }
            )
    res : str = get_value_from_loaded(
        file_to_exist_script,[package,dirtype,program,grep,executable],
        **{ **kwargs,**output} )
    success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # run and ldd
    #
    filedir,file_to_test,file_to_report = \
        file_to_exist_names(
            package,dirtype,program,**{ **kwargs,"installing":False } )
    do_run,ldd = run_config["do_run"],run_config["ldd"]
    if ldd:
        output = \
            start_test_stage(
                "exec",
                **{**kwargs,**run_config,
                   "title":f"{title}, run/ldd test","package":program_clean, },
                )
        # are library dependencies satisfied?
        prog_and_dirs : list[Optional[str]] = [file_to_test,file_to_report,".",filedir]
        res = get_value_from_loaded(
            ldd_script,prog_and_dirs,**{ **kwargs,**output } )
        success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # run!
    #
    if do_run:
        rundata : RundataDict = {
            "programname":program, 
            "runprefix"  : run_config["run_prefix"],
            "rundir"     : filedir if run_config["run_in_dir"] else None,
            "runargs"    : run_config["run_args"],
            "builddir"   : None
        }
        success,failure = do_run_test(
            title,rundata,
            success,failure,**kwargs, )
    return success,failure

def do_run_test( title : str,rundata : RundataDict,
                 success : list[str],failure : list[str],**kwargs : Any
                ) -> tuple[list[str],list[str]]:
    programname : str = rundata["programname"]
    output = start_test_stage(
        "run",
        **{ **kwargs,"title":f"{title}, run","package":programname } )
    res = get_value_from_loaded(
        run_script,
        # VLE so what's the point of having this dct?
        [ rundata["programname"],rundata["runprefix"],rundata["rundir"],rundata["runargs"] ],
        **{ **kwargs,**output } )
    success,failure = end_test_stage( success,failure,output,**kwargs )
    if returnval := re.search( r"SUCCESS.*\[([^\[\]]+)\]",res ):
        outputval = returnval.groups()[0]
        #print( f"success output: {outputval}" )
        if testvalue := kwargs.get("testvalue"):
            print( f"Comparing output={outputval} against {testvalue}" )
    return success,failure

def do_cmake_test(
        test_definition: str, **kwargs: Any,
        ) -> tuple[list[str], list[str]]:

    #parsed_options
    run_config : dict = parse_command( test_definition,**kwargs )
    trace_string( f"Existence test options: {run_config}",**kwargs )
    if ( program  := run_config.get("program") ) is None:
        error_abort( "Expecting program parameter",**kwargs )
    title     = run_config.pop("title") # need to remove because we pass a new title below
    do_run    = run_config.get("do_run")
    testvalue = run_config.get("test_value")

    if ( name_ext := re.search( r'^(.+)\.(.+)$',program ) ) is not None:
        programname,programext = name_ext.groups()
    else:
        error_abort( f"Can not parse <<{program}>> as name.ext",**kwargs )

    programsrcdir    : str = os.getcwd()+"/"+programext
    programbuilddir  : str = create_dir( "build",**kwargs )
    cmakeprefixdir : str = "" # for testing it's enough to have the result in `build'
    prog_and_dirs : list[str] = [programname,programsrcdir,programbuilddir,cmakeprefixdir]

    success : list[str] = []
    failure : list[str] = []

    #
    # Cmake & compile
    #
    output : OutputDict = \
        start_test_stage(
            "cmake build and make",
            **{ **kwargs,
                "title":f"{title}, cmake/make stage","package":programname, }
            )
    res : str = get_value_from_loaded(
        cmake_configure_script,prog_and_dirs,
        **kwargs,**output,
        pkgconfig="yes",cmakeconfig="yes" )
    failed : bool = ( re.match( 'FAILURE',res ) is not None )
    if not failed:
        res = get_value_from_loaded(
            cmake_build_script,prog_and_dirs,**kwargs,**output )
        failed = ( re.match( 'FAILURE',res ) is not None )
    success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # Check library dependencies satisfied & run
    #
    output = start_test_stage(
        "ldd",
        **{ **kwargs,**test_options,
            "title":f"{title}, ldd/run stage","package":programname }
        )
    # VLE maybe we need to adjust prog_and_dirs[1] : needs to be file_to_report
    prog_and_dirs[1] = programext
    res = get_value_from_loaded(
        ldd_script,prog_and_dirs,**kwargs,**output )
    success,failure = end_test_stage( success,failure,output,**kwargs )

    #
    # Run
    #
    if nonnull( do_run ):
        rundata : RundataDict = {
            "programname":programname,
            "prefixdir"  : run_config["run_prefix"],
            "builddir"   : programbuilddir,
            "run_in_dir" : run_config["run_in_dir"],
            "run_args"   : run_config["run_args"],
        }
        success,failure = do_run_test(
            title,rundata,
            success,failure,**kwargs,**test_options )
    return success,failure

def do_make_test(
        test_definition: str,**kwargs: Any, ) -> tuple[list[str], list[str]]:
    failure : list[str] = []; success : list[str] = []
    run_config : dict = parse_command( test_definition,**kwargs )
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
        start_test_stage(
            "compile",
            **{ **kwargs,
                "package":name,"installing":False, }
            )
    # set up for make
    compiler_exports,_ = export_compilers_script( [],**kwargs,**output )
    cmakeflags = cmake_options( **kwargs )
    process_execute\
        ( f"{compiler_exports} && make -f ../{ext}/Makefile SRCDIR=../{ext} PROJECTNAME={name} {name}",
          **kwargs,**output )
    process_execute( f"make", **kwargs,**output )
    success,failure = end_test_stage( success,failure,output,**kwargs )
    if os.path.exists( f"{builddir}/{name}" ):
        success.append( f"executable <<{name}>> created" )
    else:
        failure.append( f"Failed to create executable <<{name}>>" )

    #
    # execution
    #
    output = start_test_stage(
        "exec",
        **{ **kwargs,
            "package":name,"installing":False, }
        )
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

def do_tests( **kwargs: Any ) -> None:

    #
    # existence tests
    #
    if tests := kwargs.get( "EXISTENCETEST" ):
        for test in tests:
            if test_match( test,kwargs["match"],kwargs["filter"],**kwargs ):
                success,failure = do_existence_test(
                    test,**kwargs,installing=False )
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
                    test,**kwargs,installing=False )
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
                    test,**kwargs,installing=False )
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

