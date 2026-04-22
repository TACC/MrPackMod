import os
import re
import subprocess
from typing import Any,Optional,TypedDict

from MrPackMod.error   import nonnull
from MrPackMod.names   import family_names,package_names,package_prerequisites
from MrPackMod.process import process_execute, process_initiate, process_terminate
from MrPackMod.process import open_logfile,close_logfile
from MrPackMod.tracing import echo_string,trace_string

def load_compiler_and_mpi_and_package( **kwargs : Any ) -> None:
    package,packageversion =  package_names( **kwargs )
    modules_to_load = package
    if nonnull(packageversion): modules_to_load = f"{modules_to_load}/{packageversion}"
    load_compiler_and_mpi_and( modules_to_load,**kwargs )

def load_compiler_and_mpi_and_prereqs( **kwargs : Any ) -> None:
    modules_to_load : str = package_prerequisites( **kwargs )
    load_compiler_and_mpi_and( modules_to_load,**kwargs )

def load_compiler_and_mpi_and( modules_to_load : str,**kwargs: Any ) -> None:
    # load the compiler since this is a fresh process
    _,compiler,compilerversion,_,mpi,mpiversion = family_names( **kwargs )
    # disable terminal output unless otherwise specified
    process_execute\
        ( f"module load {compiler}/{compilerversion}",**kwargs )
    if kwargs.get("MODE")=="mpi":
        process_execute\
            ( f"module load {mpi}/{mpiversion}",**kwargs )
    process_execute\
        ( f"module load {modules_to_load}",**kwargs )
    process_execute\
        ( f"module -t list 2>&1 | sort", **kwargs )

class OutputDict(TypedDict):
    logfile : str
    logdir : str
    terminal : Optional[str]
    process : Any

def start_test_stage(
        name: str, stage: str, logdir: str, kwargs: dict[str, Any],
        chdir: Optional[str] = None, title: Optional[str] = None,installing : Optional[bool] = False
        ) -> OutputDict:
    # Create log file for this test stage, and add it to the stack of logfiles
    logfile : str = \
        open_logfile( f"{name}_{stage}",kwargs,logdir=logdir,terminal="suppress" ) # note dict
    # Create a process for the commands of this test stage
    shell  : subprocess.Popen[str] = process_initiate( **kwargs )
    output : OutputDict = {
        "logfile":logfile, "logdir":logdir, "terminal":"suppress", "process":shell,
    }
    if title :
        process_execute( f"echo Test title: {title}",**kwargs,**output )
    if chdir :
        process_execute( f"cd {chdir}",**kwargs,**output )
    # this depends on `installing' to load pkg or prereqs
    if installing:
        load_compiler_and_mpi_and_prereqs( **kwargs,**output, )
    else:
        load_compiler_and_mpi_and_package( **kwargs,**output, )
    return output

def end_test_stage(
        success: list[str], failure: list[str], kwargs: dict[str, Any], output: OutputDict,
        ) -> tuple[list[str], list[str]]:
    process_terminate( output["process"],**kwargs,**output )
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
            if succ := re.match( r'SUCCESS: (.*)$',line ):
                msg : str = succ.groups()[0]
                trace_string( msg,**kwargs )
                success.append( msg )
            if fail := re.match( r'FAILURE: (.*)$',line ):
                msg = fail.groups()[0]
                trace_string( msg,**kwargs )
                failure.append( msg )
    return success,failure

