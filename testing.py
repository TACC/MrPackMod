import os
import re
import subprocess
from typing import Any,Optional,TypedDict

from MrPackMod.error   import nonnull,nonzero_keyword,error_abort
from MrPackMod.modulefile import test_modules,\
    load_compiler_and_mpi_and_prereqs,load_compiler_and_mpi_and_package
from MrPackMod.names   import srcdir_name,family_names,package_prerequisites
from MrPackMod.process import process_execute, process_initiate, process_terminate
from MrPackMod.process import open_logfile,close_logfile
from MrPackMod.tracing import echo_string,trace_string,echo_warning

def do_config_tests( installing : bool,**kwargs : Any ) -> tuple[ list[str],list[str] ]:
    # open a log file and load modules; pkg or prereqs depending on installing
    output  = start_test_stage( "moduleconfig",kwargs,
                                installing=installing,terminal="suppress" )
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
    linedisplay : Any

##
## Start test stage:
## open logfile, start process, load modules
##
def start_test_stage(
        stage: str,
        kwargs: dict[str, Any],
        title       : Optional[str] = None,
        package     : Optional[str] = "",
        linedisplay : Optional[Any]  = echo_string,
        # installing  : Optional[bool] = False,
        # terminal    : Optional[str] = "",
        # skipmodules : Optional[bool] = False,
        **test_options    : dict[str,Any],
        ) -> OutputDict:
    if kwargs.get("process"):
        error_abort( f"Trying to create nested process <<{name},{stage}>>",**kwargs )

    # Create log file for this test stage, and add it to the stack of logfiles, write header
    logdir : str = kwargs.get("logdir",".")
    logname,loghandle = \
        open_logfile( stage,logdir=logdir,**kwargs ) 
    kwargs["logfiles"][logname] = loghandle

    # Create a process for the commands of this test stage
    shell  : subprocess.Popen[str] = process_initiate()
    output : OutputDict = {
        "logfile":logname, # full path, so we don't need logdir separately
        "process":shell,
        "terminal":test_options.get("terminal",""), # actual terminal, or `suppress'
        "linedisplay":linedisplay, # either echo_string or trace_string, used in process_terminate
    }
    if title :
        process_execute\
        ( f"echo ================ && echo Test title: {title} && echo ================",
          **kwargs,**output )
    if nonnull(title):
        trace_string( f"Created process {shell.pid} for: {title}",**kwargs )
    else:
        trace_string( f"Created process {shell.pid}",**kwargs )
    linedisplay( f"see logfile: {logname}",**kwargs,**output )
    if not test_options.get("skipmodules"):
        # we skip modules in `config.read_config'
        if nonnull( chdir := test_options.get("chdir") ):
            process_execute( f"cd {chdir}",**kwargs,**output )
        if test_options.get("installing"):
            load_compiler_and_mpi_and_prereqs( **kwargs,**output, )
        else:
            load_compiler_and_mpi_and_package( **kwargs,**output, )
    return output

def end_test_stage(
        success : list[str], failure : list[str],
        kwargs : dict[str, Any], output : OutputDict,
        ) -> tuple[list[str], list[str]]:
    process = output["process"]
    # terminate process and parse output; result is ignored here
    result_line : str = process_terminate( process,**kwargs,**output ) 
    # close log file and pop from the list of active logs
    logfile = output["logfile"]
    close_logfile( logfile,kwargs )
    success,failure = success_failure_in_logfile\
        ( logfile,success=success,failure=failure,**kwargs )
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
