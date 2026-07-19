import datetime
import os
import re
import subprocess
from typing import Any,Optional,TextIO,TypedDict

from MrPackMod.basics     import echo_string,trace_string,echo_warning,\
    nonnull,nonzero_keyword,isnull,\
    clean_title,ensure_dir
from MrPackMod.modulefile import module_loaded_script
from MrPackMod.names      import srcdir_name,scriptsdir_name,family_names,package_names,\
    logfile_name,package_prerequisites
from MrPackMod.process    import get_value_from_loaded,get_value_from_virgin
# process_execute, process_initiate, process_terminate
# from MrPackMod.process    import open_logfile # close_logfile
from MrPackMod.scripts    import modules_proper_script

def test_proper_prerequisites( **kwargs : Any ) -> str: # do_config_tests
    allgood : bool = True
    #modulestring : str = package_prerequisites( **kwargs )
    moduleslist  : list[str] = package_prerequisites( **kwargs ) #modulestring.split()
    if len(moduleslist)==0:
        return "SUCCESS: no modules to be tested"
    success : list[str] = []; failure : list[str] = []
    for module in moduleslist:
        output : OutputDict  = \
            start_test_stage(
                f"moduleconfig {module}",
                **{ **kwargs, "terminal":"suppress" }
                )
        retval : str = get_value_from_virgin(
            modules_proper_script,[module],**{ **kwargs,**output } )
        msuccess,mfailure = end_test_stage( [],[],output,**kwargs )
        success += msuccess; failure += mfailure
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
class OutputDict(TypedDict):
    logfile : str
    loghandle : TextIO
    logdir : str
    terminal : Optional[str]
    linedisplay : Any

def start_test_stage(
        stage: str,
        **kwargs: dict[str, Any],
        ) -> OutputDict:

    title      : str  = str( kwargs.get("title","notitle") )
    cleantitle : str  = clean_title(stage,**kwargs)
    package    : str  = str( kwargs.get("package","nopackage") )
    linedisplay = kwargs.pop("linedisplay",echo_string)

    # Create log file for this test stage, and add it to the stack of logfiles, write header
    # note: kwargs does not contain "scriptsdir",
    # then logfile will go to default dir

    # VLE this log file is more or less empty. Get rid?
    # except that we use `scriptsdir' left and right
    logname,loghandle = \
        open_logfile( cleantitle,**kwargs, ) 

    # Create a process for the commands of this test stage
    output : OutputDict = {
        "logfile"     : logname, # full path, so we don't need logdir separately
        "logdir"      : kwargs.get("startdir","."),
        "loghandle"   : loghandle,
        "terminal"    : kwargs.get("terminal",""), # actual terminal, or `suppress'
        "linedisplay" : linedisplay,
    }
    if nonnull(title):
        trace_string( f"Starting stage for: {title}",**kwargs )
    else:
        trace_string( f"Starting stage",**kwargs )
    # linedisplay( f"see logfile: {logname}",**{ **kwargs,**output } )
    return output

def end_test_stage(
        success : list[str], failure : list[str],
        output : OutputDict,
        **kwargs : dict[str, Any], 
        ) -> tuple[list[str], list[str]]:
    # close the log file to finish all writes
    if ( loghandle := output.get("loghandle") ) is None:
        error_abort( "Need logfile handle",**kwargs )
    loghandle.close()
    #close_logfile( output,**kwargs )
    # then analyze the now completed log file
    if ( logfile := output.get("logfile") ) is None:
        error_abort( "Need logfile name",**kwargs )
    success,failure = success_failure_in_logfile\
        ( logfile,success=success,failure=failure,**kwargs )
    return success,failure

##
## Open a log file;
## add name/handle to kwargs["logfiles"]
##
def open_logfile(
        logstage : str, **kwargs   : Any, ) -> tuple[str,Any]:
    # get global name, ignore local name
    logname,_,logfilesdir = logfile_name( logstage,**kwargs )
    ensure_dir(logfilesdir)
    loghandle = open( logname,"w" )
    loghandle.write( f"""================
Logstage {logstage} started {datetime.date.today()}
================\n""" )
    return logname,loghandle

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

# are the required modules loaded?
non_packages: list[str] = [ "blaslapack", "mpi", ] # mkl","nvpl","
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
