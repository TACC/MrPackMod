import os
import re
import subprocess
from typing import Any,Optional,TypedDict

from MrPackMod.basics     import echo_string,trace_string,echo_warning,\
    nonnull,nonzero_keyword,isnull
from MrPackMod.modulefile import module_loaded_script
from MrPackMod.names      import srcdir_name,scriptsdir_name,family_names,package_names,\
    package_prerequisites
from MrPackMod.process    import process_execute, process_initiate, process_terminate,\
    get_value_from_loaded,get_value_from_virgin
#    load_compiler_and_mpi_and_prereqs,load_compiler_and_mpi_and_package,\
from MrPackMod.process    import open_logfile,close_logfile
from MrPackMod.scripts    import module_proper_script

class OutputDict(TypedDict):
    logfile : str
    logdir : str
    terminal : Optional[str]
    #process : Any
    installing  : bool
    linedisplay : Any
    scriptsdir : str

def do_config_tests( installing : bool,**kwargs : Any ) -> str:
    allgood : bool = True
    modulestring : str = package_prerequisites( **kwargs )
    moduleslist  : list[str] = modulestring.split()
    output : OutputDict  = \
        start_test_stage( "moduleconfig",kwargs,
                          installing=installing,terminal="suppress" )
    retval : str = get_value_from_virgin(
        module_proper_script,moduleslist,**kwargs,**output )
    success,failure = end_test_stage( [],[],kwargs,output )
    for s in success:
        echo_string(s,**kwargs)
    for f in failure:
        echo_string(f,**kwargs)
    if len(failure)>0:
        # VLE some of the failure results are not relevant.
        return f"FAILURE: not all modules proper: <<{failure[0]}>>"
    else: return "SUCCESS: all modules proper"

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
    # note: kwargs does not contain "scriptsdir",
    # test_options is allowed to not contain it either,
    # then logfile will go to default dir
    scriptsdir : str = scriptsdir_name( **kwargs, )
    logname,loghandle,scriptsdir = \
        open_logfile( stage.replace(' ','_'),**kwargs, ) 
    kwargs["logfiles"][logname] = loghandle

    # Create a process for the commands of this test stage
    ## shell  : subprocess.Popen[str] = process_initiate()
    output : OutputDict = {
        "logfile":logname, # full path, so we don't need logdir separately
        "terminal":test_options.get("terminal",""), # actual terminal, or `suppress'
        "linedisplay":linedisplay, # either echo_string or trace_string, used in process_terminate
        "installing":installing,   # default True, make sure to unset in regression
        "scriptsdir":scriptsdir,
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
    process_execute\
        ( f"echo Using modulepath:",**kwargs )
    process_execute\
        ( f"echo $MODULEPATH  | tr ':' '\n'",**kwargs )
    if installing := kwargs.get( "installing",False ):
        if nonnull( modulestotest := package_prerequisites(**kwargs) ):
            echo_string( f"Test for prereq modules {modulestotest}",**kwargs )
        else: modulestotest = ""
    else:
        modulestotest,_ = package_names( **kwargs )
        echo_string( f"Test for test module {modulestotest}",**kwargs )
    if nonnull( modulestotest ):
        test_loaded_modules( modulestotest,**kwargs )
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
