import os
import re
import subprocess
from typing import Any,Optional,TypedDict

from MrPackMod.error      import nonnull,nonzero_keyword,error_abort,isnull
from MrPackMod.modulefile import module_loaded_script
from MrPackMod.names      import srcdir_name,family_names,package_prerequisites
from MrPackMod.process    import process_execute, process_initiate, process_terminate,\
    load_compiler_and_mpi_and_prereqs,load_compiler_and_mpi_and_package,\
    get_value_from_loaded
from MrPackMod.process    import open_logfile,close_logfile
from MrPackMod.tracing    import echo_string,trace_string,echo_warning

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
    test_modules( **kwargs,**output )
    success,failure = end_test_stage( success,failure,kwargs,output )
    return success,failure

class OutputDict(TypedDict):
    logfile : str
    logdir : str
    terminal : Optional[str]
    #process : Any
    installing  : bool
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
        installing  : Optional[bool] = True,
        linedisplay : Optional[Any]  = echo_string,
        **test_options    : dict[str,Any],
        ) -> OutputDict:

    # Create log file for this test stage, and add it to the stack of logfiles, write header
    logname,loghandle = \
        open_logfile( stage,**kwargs ) 
    kwargs["logfiles"][logname] = loghandle

    # Create a process for the commands of this test stage
    ## shell  : subprocess.Popen[str] = process_initiate()
    output : OutputDict = {
        "logfile":logname, # full path, so we don't need logdir separately
        "terminal":test_options.get("terminal",""), # actual terminal, or `suppress'
        "linedisplay":linedisplay, # either echo_string or trace_string, used in process_terminate
        "installing":installing,   # default True, make sure to unset in regression
    }
    if nonnull(title):
        trace_string( f"Starting stage for: {title}",**kwargs )
    else:
        trace_string( f"Starting stage",**kwargs )
    linedisplay( f"see logfile: {logname}",**kwargs,**output )
    return output

def end_test_stage(
        success : list[str], failure : list[str],
        kwargs : dict[str, Any], output : OutputDict,
        ) -> tuple[list[str], list[str]]:
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

####
#### Module tests  through process_execute or get_value_from_loaded
####

def test_modules( **kwargs: Any ) -> None:
    installing : bool = kwargs.get( "installing",False )
    process_execute\
        ( f"echo Using modulepath:",**kwargs )
    process_execute\
        ( f"echo $MODULEPATH  | tr ':' '\n'",**kwargs )
    if installing and  nonnull( modules := package_prerequisites(**kwargs) ):
        modules_to_test : str = modules
        echo_string( f"Test for prereq modules {modules_to_test}",**kwargs )
    else:
        modules_to_test,_ = package_names( **kwargs )
        echo_string( f"Test for test module {modules_to_test}",**kwargs )
    test_loaded_modules( modules_to_test,**kwargs )
    #test_nonmodules( **kwargs )

# are the required modules loaded?
non_packages: list[str] = [ "blaslapack", "mpi", ] # mkl","nvpl","
def test_loaded_modules( modules : str,**kwargs: Any ) -> None:
    for mod in modules.split(" "):
        if isnull(mod): continue
        if mod in non_packages:
            trace_string( f"Skip test for non-package: {mod}",**kwargs )
            continue
        test_module_loaded( mod,**kwargs )
        # if nonnull(ver):
        #     test_module_version( mod,ver,**kwargs )

# are no nonmodules loaded?
def test_nonmodules( **kwargs: Any ) -> bool:
    if not (nonmodules := nonzero_keyword( "NONMODULES",**kwargs ) ):
        trace_string( "No nonmodules",**kwargs )
        return True
    success = True
    for mod in nonmodules.split(" "):
        if loaded := test_module_loaded( mod,**kwargs ):
            echo_string( f"Please unload module: {mod}",**kwargs )
            success = False
        else: trace_string( " .. module correctly not loaded",**kwargs )
    return success

def test_module_loaded( modver : str, **kwargs: Any ) -> str:
    return get_value_from_loaded( module_loaded_script,[modver],**kwargs )

def test_module_version( mod: str, ver: str, **kwargs: Any ) -> bool:
    loadedversion :str = os.getenv( "TACC_"+mod.upper()+"_VERSION","" )
    if not loadedversion:
        loadedversion = os.getenv( "TACC_"+mod.upper()+"_VER","" )
    if not loadedversion:
        trace_string( " .. module does not declare VERSION parameter",**kwargs )
        return True
    else:
        if not ( version_match := version_satisfies( loadedversion,ver,**kwargs ) ):
            trace_string( f" .. loaded version: {loadedversion} does not match version {ver}",
                     **kwargs )
            return False
        else:
            trace_string( f" .. loaded version: {loadedversion} matches version {ver}",
                          **kwargs )
            return True
