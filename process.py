#!/usr/bin/env python3

##
## python modules
##
import datetime
import os
import re
import shutil
import subprocess
import sys
import traceback
from typing import Any, Callable, IO, NoReturn, Optional

from MrPackMod.error   import isnull,nonnull,error_abort,nonzero_keyword
from MrPackMod.names   import package_names,family_names,package_prerequisites
from MrPackMod.tracing import trace_string,echo_string,echo_warning,trace_var

##
## File handling
##

#
# Create directory, or make sure it exists
#
def ensure_dir( name: str, **kwargs: Any ) -> str:
    if re.match( r'/',name):
        dir : str = name
    else:
        pwd = os.getcwd()
        dir = f"{pwd}/{name}"
    trace_string( f"mkdir -p : {dir}",**kwargs )
    os.makedirs( dir,exist_ok=True)
    return dir

def create_dir( name: str, **kwargs: Any ) -> str:
    try:
        shutil.rmtree(name)
    except FileNotFoundError: pass
    return ensure_dir( name,**kwargs )

####
#### Logfiles
####

from MrPackMod.names import logfile_name

##
## Open a log file;
## add name/handle to kwargs["logfiles"]
##
def open_logfile(
        logstage : str,
        logdir   : Optional[str] = None,
        terminal : str = "",
        **kwargs   : Any,
        ) -> tuple[str,str]:
    logdir : str = kwargs.get("logdir",".")
    if nonnull( package := kwargs.get("program") ):
        logname : str = f"{package}_{logstage}"
    else:
        packagename,_  = package_names( **kwargs )
        logname = f"{packagename}_{logstage}"

    # get global name, ignore local name
    logname,_ = logfile_name( logstage,dir=logdir,**kwargs )
    loghandle = open( logname,"w" )
    loghandle.write( f"""================
Logstage {logstage} started {datetime.date.today()}
================\n""" )
    return logname,loghandle

def close_logfile( logname: str, kwargs: dict[str, Any] ) -> None:
    try :
        loghandle = kwargs["logfiles"][logname]
    except KeyError:
        error_abort( f"Can not find logfile to close: {logname}",**kwargs )
    kwargs["logfiles"].pop(logname)
    loghandle.close()


##
## Process routines
##
def process_initiate() -> subprocess.Popen[str]:
    return subprocess.Popen\
        (['/bin/bash', '-l'], 
         stdin=subprocess.PIPE, 
         stdout=subprocess.PIPE, 
         stderr=subprocess.STDOUT,
         text=True,
         bufsize=1)

def process_terminate(
        tofinish: subprocess.Popen[str], **kwargs: Any
        ) -> str:
    if tofinish.poll() is not None:
        error_abort( "Process {tofinish.pid} to terminate has already finished",**kwargs )
    process_input  = tofinish.stdin
    process_output = tofinish.stdout
    line_display   = kwargs.get("linedisplay",echo_string)
    trace_string( f" .. finishing process",**kwargs )
    assert process_input is not None and process_output is not None
    process_input.flush()
    process_input.close()
    trace_string( f">>>>>>>> Process {tofinish.pid} output:",**kwargs )
    lastline : str = ""
    while True:
        line : str = process_output.readline()
        if not line:
            break
        line = re.sub( r'^[ \t]*','', re.sub( r'[ \t\n]*$','', line ) )
        if line != "":
            line_display( line,**kwargs ) # maybe stdout, maybe stderr
            lastline = line
    tofinish.wait()
    trace_string( f"<<<<<<<< process output",**kwargs )
    trace_string( f" .. process {tofinish.pid} terminated with final result=\"{lastline}\"",
                  **kwargs )
    return lastline

def process_execute_immediate( cmdline : str, **kwargs : Any ) -> str:
    # create new process
    process : subprocess.Popen[str] = process_initiate()
    process_input  : IO[str] = process.stdin
    trace_string( f"Execute cmdline=\"{cmdline}\" on new process {process.pid}",**kwargs )
    # Is this commandline proper?
    if re.search( r'\$\{',cmdline ):
        echo_warning( f"Commandline \"{cmdline}\" contains unexpanded macros",**kwargs )
    # execute!
    process_input.write( cmdline+"\n" )
    process_input.flush() # VLE not sure if this works
    # parse result: either first failure, or final result
    result : str = process_terminate( process,**kwargs )
    return result

def process_execute( cmdline: str, **kwargs: Any ) -> str:
    outside_process = kwargs.get("process",None)
    immediate       = kwargs.get("immediate",None)
    load_context    = kwargs.get("load_context",False)

    # create a new process, if this call is not in context of another process
    if isnull( outside_process ) or nonnull( immediate ):
        process : subprocess.Popen[str] = process_initiate()
        trace_string( f"Execute cmdline=\"{cmdline}\" on new process {process.pid}",**kwargs )
    else:
        trace_string( f"Execute cmdline=\"{cmdline}\" on existing process {outside_process.pid}",
                      **kwargs )
        process = outside_process

    # Get stdin
    if process.poll() is not None:
        error_abort( f"Process {process.pid} has ended, can not execute cmdline",**kwargs )
    elif input := process.stdin:
        process_input  : IO[str] = input
    else:
        error_abort( f"Can not get process stdin",**kwargs )

    # # Is this commandline proper?
    # if re.search( r'\$\{',cmdline ):
    #     echo_warning( f"commandline \"{cmdline}\" contains unexpanded macros",**kwargs )

    # Does this execution has a title?
    if not outside_process and ( title := nonzero_keyword( "title",**kwargs ) ):
        process_input.write( f"echo {title}" )

    # All set: add the commandline to process intput
    if load_context:
        load_string = load_compiler_and_mpi_and_prereqs( **kwargs,only_return=True )
        process_input.write( load_string )
    process_input.write( cmdline+"\n" )
    if immediate:
        process_input.flush() # VLE not sure if this works

    # close process if opened earlier in this routine
    if isnull( outside_process ) or nonnull(immediate):
        result : str = process_terminate( process,**kwargs )
        #print( f"Process terminate returned:\n{result}" )
        return result
    else:
        return ""

def number_satisfies( loaded: str, wanted: str, **kwargs: Any ) -> Any:
    if wanted=="*":
        res = True; op = "~"
    elif re.match( r'<=',wanted ):
        wanted = wanted.lstrip('<=')
        res = int(loaded)<=int(wanted); op = "<="
    elif re.match( r'<',wanted ):
        wanted = wanted.lstrip('<')
        res = int(loaded)<int(wanted); op = "<"
    elif re.match( r'>=',wanted ):
        wanted = wanted.lstrip('>=')
        res = int(loaded)>=int(wanted); op = ">="
    elif re.match( r'>',wanted ):
        wanted = wanted.lstrip('>')
        res = int(loaded)>int(wanted); op = ">"
    elif ext := re.match( r'\*(.*)$',wanted ):
        match = ext.groups()[0].lstrip( "*" ).rstrip( "*" )
        res = bool( re.search( match,loaded ) ); op = "*..."
    elif loaded==wanted:
        res = True; op = "=="
    else:
        res = False; op = "??"
    trace_string( f" .. tested {loaded} {op} {wanted}: {res}",**kwargs )
    return res

def version_satisfies(
    loaded: Any, tomatch: Any, **kwargs: Any
) -> bool:
    if isnull(loaded) or isnull(tomatch): return True
    load_mjr,load_mnr,load_mcr = f"{loaded}.0.0".split(".",maxsplit=2)
    load_mnr = load_mnr.strip(".0")
    load_mcr = load_mcr.strip(".0")
    want_mjr,want_mnr,want_mcr = f"{tomatch}.99.99".split(".",maxsplit=2)
    want_mnr = want_mnr.strip(".99")
    want_mcr = want_mcr.strip(".99.99")
    trace_string( f" .. test loaded version {loaded}={load_mjr}.{load_mnr}.{load_mcr} against wanted {tomatch}={want_mjr}.{want_mnr}.{want_mcr}",
                  **kwargs )
    #
    # test successively major, minor, micro
    #
    for level,l,w in zip( ["major","minor","micro",],[load_mjr,load_mnr,load_mcr],[want_mjr,want_mnr,want_mcr] ):
        if isnull(w): break
        trace_string( f" .. {level} component {l} <> {w}",**kwargs )
        if number_satisfies(l,w,**kwargs) or w=="99":
            trace_string( f" .. module version matched load={l} want={w}",**kwargs )
        else:
            trace_string( f" .. module version mismatch load={l} want={w}",**kwargs )
            return False
    return True

def load_compiler_and_mpi_and_package( **kwargs : Any ) -> str:
    package,packageversion =  package_names( **kwargs )
    modules_to_load : str = package
    if nonnull(packageversion): modules_to_load = f"{modules_to_load}/{packageversion}"
    trace_string( f"---- Load base modules and package: <<{modules_to_load}>>",**kwargs )
    return load_compiler_and_mpi_and( modules_to_load,**kwargs )

def load_compiler_and_mpi_and_prereqs( **kwargs : Any ) -> str:
    modules_to_load : str = package_prerequisites( **kwargs )
    trace_string( f"---- Load base modules and prereqs: <<{modules_to_load}>>",**kwargs )
    return load_compiler_and_mpi_and( modules_to_load,**kwargs )

# this routine is called through the above two wrappers
# from `start_test_stage'
def load_compiler_and_mpi_script( modules_to_load : str,**kwargs: Any ) -> str:
    title : str = f"Load compiler and mpi and modules: {modules_to_load}"
    errmsg : str = f"Failed to load compiler and mpi and modules: {modules_to_load}"
    _,compiler,compilerversion,_,mpi,mpiversion = family_names( **kwargs )
    modulepath = nonzero_keyword( "modulepath",**kwargs )
    modulereport = r"""
if [ $? -gt 0 ] ; then
    echo .. module command failed 
else
    echo Loaded: && modulelist
fi
    """
    load_string : str = """
function modulelist ()
{
    local compiler=$( module -t list "${TACC_FAMILY_COMPILER}/" 2>&1 );
    local mpi=$( module -t list ${TACC_FAMILY_MPI} 2>&1 );
    local modules=$( module -t list 2>&1 | grep -v $compiler | grep -v $mpi | sort );
    for m in $compiler $mpi cont $modules;
    do
        if [ $m = "cont" ]; then
            echo "----------------";
        else
            loc=$(module -t show $m 2>&1 | sed -e 's?'${WORK}'?\$\{WORK\}?' );
            echo "$m : $loc";
        fi;
    done
}
    """
    load_string += f"""
echo .... Module reset
module -t purge 2>/dev/null

echo .... Set modulepath 
export MODULEPATH={modulepath}
echo $MODULEPATH
module -t load TACC 2>/dev/null
{modulereport}

echo .... Load compiler && module -t load {compiler}/{compilerversion} 2>/dev/null
{modulereport}
    """
    if kwargs.get("MODE")=="mpi":
        load_string += f"""
echo .... Load mpi && module -t load {mpi}/{mpiversion} 2>/dev/null
{modulereport}
        """
    if nonnull( modules_to_load ):
        load_string += f"""
echo .... Load packages \"{modules_to_load}\"
        """
        for mod in modules_to_load.split(" "):
            load_string += f"""
module -t load {mod} 2>/dev/null
if [ $? -gt 0 ] ; then
    echo FAILURE: module {mod} failed to load 
fi
            """
        load_string += f"{modulereport}"
    else:
        echo_warning( "not loading any modules",**kwargs )
    load_string += f"""
echo Final listing && {modulereport}
    """
    return load_string

def load_compiler_and_mpi_and( modules_to_load : str,**kwargs: Any ) -> str:
    load_string : str = load_compiler_and_mpi_script( modules_to_load,**kwargs )
    if not nonzero_keyword( "only_return",**kwargs ):
        process_execute( load_string,**kwargs )
    return load_string
        

##
## Specific module tests through process_execute
##
def module_loaded_script( modverlist : list[str],**kwargs : Any ) -> tuple[str,str]:
    modver : str = modverlist[0]
    title : str = f"Test presence of module: {modver}"
    if hasver := re.search( r'(.*)/(.*)',modver):
        mod,ver = hasver.groups()
    elif nonnull(modver):
        mod = modver; ver = ""
    else:
        echo_warning( f"Testing loaded with null modver",**kwargs )
        return
    modvar : str = f"TACC_{mod.upper()}_DIR"
    script : str = f"""
if [ -z \"${modvar}\" ] ; then 
  echo FAILURE: variable {modvar} not set, load module {mod}
else
  if [ ! -d \"${modvar}\" ] ; then
    echo FAILURE: directory {modvar} not found
  else
    echo SUCCESS: package={mod} version={ver} is at: {modvar}
  fi
fi
        """
    return script,title

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

def get_value_from_loaded( script_function : Callable[ list[str],tuple[str,str] ],
                           args : list[str],**kwargs : Any ) -> str:
    # setup
    loadscript = ""
    if nonzero_keyword("installing",**kwargs):
        modules_to_load : str = package_prerequisites( **kwargs )
        loadscript += "\n# Loading environment for prerequisites: {modules_to_laod}"
    else:
        package,packageversion =  package_names( **kwargs )
        if nonnull(packageversion):
            modules_to_load = f"{package}/{packageversion}"
            loadscript += f"\n# Loading environment for package: {package}/{packageversion}"
        else:
            modules_to_load = package
            loadscript += "\n#Loading environment for package: {package}"
    loadscript += "\n"+load_compiler_and_mpi_script( modules_to_load,**kwargs )
    # actual test
    script,title = script_function(args,**kwargs)
    scriptsdir = kwargs.get("scriptdir",".")+"/mpmscripts"
    # make script
    ensure_dir(scriptsdir,**kwargs)
    cleantitle = re.sub("/",'-',re.sub(' ','_',title))
    scriptfilename : str = f"{scriptsdir}/{cleantitle}.sh"
    outputfilename : str = f"{scriptsdir}/{cleantitle}.out"
    with open(scriptfilename,"w") as scriptfile:
        scriptfile.write( "#!/bin/bash\n" )
        scriptfile.write( loadscript )
        scriptfile.write( f"\n# Now follows script: {title}" )
        scriptfile.write( script )
    print( f"script in: {scriptfilename}" )
    value = process_execute_immediate\
        ( f"chmod +x {scriptfilename} && {scriptfilename} 2>&1 | tee {outputfilename}",
          **kwargs,title=title )
    if re.match( 'FAILURE',value ):
        error_abort( f"Failed: {title}",**kwargs )
    else:
        return value
    
