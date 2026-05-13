#!/usr/bin/env python3

##
## python modules
##
import datetime
import os
import pdb
import re
import shutil
import subprocess
import sys
import traceback
from typing import Any, Callable, IO, NoReturn, Optional, Tuple

from MrPackMod.basics  import loaded_module_version,remove_macros,clean_title
from MrPackMod.error   import isnull,nonnull,error_abort,nonzero_keyword,abort_on_zero_keyword
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
        logstage : str, logdir   : Optional[str] = None,
        terminal : str = "", **kwargs   : Any, ) -> tuple[str,str]:
    logdir : str = kwargs.get("logdir",".")
    if nonnull( package := kwargs.get("program") ):
        logname : str = f"{package}_{logstage}"
    else:
        packagename,_  = package_names( **kwargs )
        logname = f"{packagename}_{logstage}"

    # get global name, ignore local name
    logname,_,logdir = logfile_name( logstage,**kwargs )
    ensure_dir(logdir)
    loghandle = open( logname,"w" )
    loghandle.write( f"""================
Logstage {logstage} started {datetime.date.today()}
================\n""" )
    return logname,loghandle,logdir

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
    # # Is this commandline proper?
    # if re.search( r'\$\{',cmdline ):
    #     echo_warning( f"Commandline \"{cmdline}\" contains unexpanded macros",**kwargs )
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
    if redirectloc := nonzero_keyword( "setupredirect",**kwargs ):
        redirect : str = f"1>&3"
        loadscript : str = f"exec 3>{redirectloc}"
    else:
        redirect = ""
        loadscript = ""
    modulereport = f"""
if [ $? -gt 0 ] ; then
    echo FAILURE module command failed && exit
else
    echo Loaded: && modulelist
fi {redirect}
    """
    if nonzero_keyword( "moduletrace",**kwargs ):
        loadscript += """
function modulelist ()
{
    local compiler=$( module -t list "${TACC_FAMILY_COMPILER}" 2>&1 );
    local mpi=$( module -t list ${TACC_FAMILY_MPI} 2>&1 );
    local modules=$( module -t list 2>&1 | grep -v $compiler | grep -v $mpi | sort );
    for m in $compiler $mpi cont $modules;
    do
        if [ $m = "cont" ]; then
            echo "----------------";
        else
            loc=$(module -t show $m 2>&1 | sed -e 's?'${WORK}'?${WORK}?' );
            echo "$m : $loc";
        fi;
    done
}
        """
    else:
        loadscript += """
function modulelist ()
{ module -t list 2>&1 | sort | tr '\n' ' ' && echo
}
        """
    loadscript += f"""
echo .... Module reset {redirect}
module -t purge 2>/dev/null
echo .... Loading basic modules {redirect}
module -t reset 2>/dev/null
module -ft unload impi mvapich openmpi
{modulereport}

echo .... Set modulepath {redirect}
export MODULEPATH={modulepath}
echo MODULEPATH=$MODULEPATH | tr ':' '\n' {redirect}
echo .... Can we load compiler {compiler}/{compilerversion} {redirect}
module -t avail {compiler}/{compilerversion} 2>&3
{modulereport}

echo .... Load compiler {compiler}/{compilerversion} {redirect}
module -t load {compiler}/{compilerversion} 2>/dev/null
{modulereport}
    """
    if kwargs.get("MODE")=="mpi":
        loadscript += f"""
echo .... Load mpi {redirect}
module -t load {mpi}/{mpiversion} 2>/dev/null
{modulereport}
        """
    if nonnull( modules_to_load ):
        loadscript += f"""
echo .... Load packages \"{modules_to_load}\" {redirect}
        """
        for mod in modules_to_load.split(" "):
            if ver := loaded_module_version( mod,**kwargs ):
                modver = f"{mod}/{ver}"
            else:
                modver = mod
            loadscript += f"""
module -t load {modver} 2>/dev/null
{modulereport}
            """
    else:
        echo_warning( "not loading any modules",**kwargs )
    loadscript += f"""
echo Final listing {redirect}
{modulereport}
    """
    return loadscript

def load_compiler_and_mpi_and( modules_to_load : str,**kwargs: Any ) -> str:
    load_string : str = load_compiler_and_mpi_script( modules_to_load,**kwargs )
    if not nonzero_keyword( "only_return",**kwargs ):
        process_execute( load_string,**kwargs )
    return load_string

##
## Execute a script in the context of compiler and modules
## return: value, or FAILURE string
##
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
    # where does all crap go?
    script,title = script_function(args,**kwargs)
    scriptsdir = abort_on_zero_keyword( "scriptsdir",**kwargs ) #kwargs.get("scriptdir",".")+"/mpmscripts"
    ## VLE title can contain path macros like TACC_PACKAGE_LIB
    cleantitle = clean_title( title,**kwargs )
    outputbase : str = f"{scriptsdir}/{cleantitle}"

    # cobble together script
    loadscript += "\n"+load_compiler_and_mpi_script(
        modules_to_load,setupredirect=f"{outputbase}.setup", # filter boring stuff
        **kwargs )
    ensure_dir(scriptsdir,**kwargs)
    scriptfilename : str = f"{outputbase}.sh"
    outputfilename : str = f"{outputbase}.out"
    with open(scriptfilename,"w") as scriptfile:
        scriptfile.write( "#!/bin/bash\n" )
        scriptfile.write( loadscript )
        scriptfile.write( f"\n# Now follows script: {title}" )
        scriptfile.write( script )
        scriptfile.write( "exec 3>&-\n" )
    trace_string( f"Script for {title} in: {scriptfilename}\n{script}",**kwargs )
    value = process_execute_immediate\
        ( f"""
chmod +x {scriptfilename}
set -o pipefail
{scriptfilename} 2>&1 | tee {outputfilename}
        """+"""
if [ ${PIPESTATUS[0]} -gt 0 ] ; then
        """+f"""
    echo FAILURE running script {scriptfilename}
fi
        """,
          **kwargs,title=title )
    if re.match( 'FAILURE',value ):
        return f"FAILURE: {title}; see: {outputfilename}"
    else:
        return value
    
##
## Aux
##

##
## return stripped line, and bool result of any prefixed test
##
def line_strip_conditionals( line: str, **config_dict: Any ) -> tuple[str, bool]:
    """ returns: line,accept """
    trace_string( f"Test line for conditions: {line}",**config_dict )
    if test := re.search( r'^([a-zA-Z0-9_]+)(==|\!=)([a-zA-Z0-9_]+)\s+(.*)$',line ):
        value1,comparison,value2,line = condition_split( test,**config_dict )
        trace_string( f"Line has conditions {line} : {value1}{comparison}{value2}",
                      **config_dict )
        if ( comparison=="==" and value1!=value2 ) or \
           ( comparison=="!=" and value1==value2 ):
            trace_string( f" .. reject because not {value1}{comparison}{value2}",
                          **config_dict )
            return line,False
        else: 
            trace_string( f" .. accept because {value1}{comparison}{value2}",
                          **config_dict )
            return line_strip_conditionals( line,**config_dict )
    else:
        trace_string( f" .. accept because no conditionals detected: {line}",
                      **config_dict )
        return line,True

def condition_split(
        cond: re.Match[str],
        **config_dict: Any,
        ) -> Tuple[Any, str, Any, str]:
    field1,op,field2,line = cond.groups()
    value1 = config_dict.get(field1,field1)
    value2 = config_dict.get(field2,field2)
    return value1,op,value2,line

##
## Return directory, actual file name & name with LMOD variable unexpanded
##
def file_to_exist_names( package : str,dirtype : str,program : str,**kwargs ) -> tuple[str,str,str]:
    if dirtype in [ "dir","inc","lib","bin", ]:
        dirvar : str = dir_variable(package,dirtype)
        filedir_to_report :str = f"${{{dirvar}}}"
    else:
        filedir_to_report = f"${{TACC_{package.upper()}_DIR/{dirtype}}}"
    filedir        : str = remove_macros( filedir_to_report,kwargs )
    file_to_test   : str = f"{filedir}/{program}"
    file_to_report : str = f"{filedir_to_report}/{program}"
    return filedir,file_to_test,file_to_report

def dir_variable( package: str, dirtype: str = "dir" ) -> str:
    return f"TACC_{package.upper()}_{dirtype.upper()}"

