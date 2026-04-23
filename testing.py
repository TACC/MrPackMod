import os
import re
import subprocess
from typing import Any,Optional,TypedDict

from MrPackMod.error   import nonnull,nonzero_keyword,error_abort
from MrPackMod.modulefile import test_modules,\
    load_compiler_and_mpi_and_prereqs,load_compiler_and_mpi_and_package
from MrPackMod.names   import srcdir_name,family_names,package_names,package_prerequisites
from MrPackMod.process import process_execute, process_initiate, process_terminate
from MrPackMod.process import open_logfile,close_logfile
from MrPackMod.tracing import echo_string,trace_string,echo_warning

def do_config_tests( installing : bool,**kwargs : Any ) -> tuple[ list[str],list[str] ]:
    logdir     : str = kwargs.get("logdir",".")
    # open a log file and load modules; pkg or prereqs depending on installing
    output  = start_test_stage( "moduleconfig",logdir,kwargs,installing=installing )
    success : list[str] = []
    failure : list[str] = []

    # test presence of source dir
    if  nonzero_keyword("installing",**kwargs ):
        srcdir = srcdir_name( **kwargs,**output )
        process_execute( f"""
if [ ! -d "{srcdir}" ] ; then
    echo FAILURE: Source directory {srcdir} does not exist
fi 
        """,**kwargs,**output )
    # test depends on whether we are installing
    test_modules( **kwargs,**output,installing=installing )
    success,failure = end_test_stage( success,failure,kwargs,output )
    return success,failure

class OutputDict(TypedDict):
    logfile : str
    logdir : str
    terminal : Optional[str]
    process : Any

##
## Start test stage:
## open logfile, start process, load modules
##
def start_test_stage(
        stage: str, logdir: str, kwargs: dict[str, Any],
        chdir: Optional[str] = None, title: Optional[str] = None,
        package : Optional[str] = "",installing : Optional[bool] = False
        ) -> OutputDict:
    if kwargs.get("process"):
        error_abort( f"Trying to create nested process <<{name},{stage}>>",**kwargs )
    # Create log file for this test stage, and add it to the stack of logfiles, write header
    if nonnull(package):
        logname : str = f"{package}_{stage}"
    else:
        packagename,_  = package_names( **kwargs )
        logname = f"{packagename}_{stage}"
    logfile : str = \
        open_logfile( logname,kwargs,logdir=logdir,terminal="" ) # note dict
    # Create a process for the commands of this test stage
    shell  : subprocess.Popen[str] = process_initiate()
    output : OutputDict = {
        "logfile":logfile, "logdir":logdir, "terminal":"", "process":shell,
    }
    trace_string( f"Created process {shell.pid}",**kwargs )
    if title :
        process_execute( f"echo Test title: {title}",**kwargs,**output )
    echo_string( f"see logfile: {logfile}",**kwargs,**output )
    if chdir :
        process_execute( f"cd {chdir}",**kwargs,**output )
    if installing:
        load_compiler_and_mpi_and_prereqs( **kwargs,**output, )
    else:
        load_compiler_and_mpi_and_package( **kwargs,**output, )
    return output

def end_test_stage(
        success: list[str], failure: list[str], kwargs: dict[str, Any], output: OutputDict,
        ) -> tuple[list[str], list[str]]:
    process = output["process"]
    process_terminate( process,**kwargs,**output )
    close_logfile( output["logfile"],kwargs )
    success,failure = success_failure_in_logfile\
        ( output["logfile"],success=success,failure=failure,**kwargs )
    return success,failure

##
## Grep for SUCCESS or FAILURE in a log file;
## add those messages to two list-of-strings variables
##
def success_failure_in_logfile(
        logoutput: str,
        **kwargs: Any,
        ) -> tuple[list[str], list[str]]:
    success : list[str] = kwargs.get( "success",[] )
    failure : list[str] = kwargs.get( "failure",[] )
    with open( logoutput,"r" ) as loglines:
        for line in loglines:
            if succ := re.match( r'SUCCESS:? (.*)$',line ):
                msg : str = succ.groups()[0]
                trace_string( msg,**kwargs )
                success.append( msg )
            if fail := re.match( r'FAILURE:? (.*)$',line ):
                msg = fail.groups()[0]
                trace_string( msg,**kwargs )
                failure.append( msg )
    return success,failure

def report_success_failure( success : list[str],failure : list[str],**kwargs : Any ) -> None:
    for s in success:
        echo_string( f"Success: {s}",**kwargs )
    for f in failure:
        echo_string( f"Failure: {f}",**kwargs )
