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

from MrPackMod.basics  import remove_macros,clean_title,derived_settings,\
    trace_string,echo_string,echo_warning,trace_var,\
    abort_on_zero_keyword,nonzero_keyword,zero_keyword,\
    isnull,nonnull,error_abort
from MrPackMod.names   import package_names,family_names,package_prerequisites,\
    mode_is_core
from MrPackMod.scripts import export_compilers_script,export_flags,\
    load_compiler_and_mpi_and_modules_script

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
    if os.path.isdir( dir ):
        trace_string( f"mkdir existing : {name} -> {dir}",**kwargs )
    else:
        #breakpoint()
        trace_string( f"mkdir new dir : {name} -> {dir}",**kwargs )
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
        logstage : str, terminal : str = "", **kwargs   : Any, ) -> tuple[str,str]:
    # if nonnull( package := kwargs.get("program") ):
    #     logname : str = f"{package}_{logstage}"
    # elif kwargs.get("PACKAGE") and kwargs.get("PACKAGEVERSION"):
    #     # this case is needed for the initial config test, prior to mpm actions
    #     packagename,_  = package_names( **kwargs )
    #     logname = f"{packagename}_{logstage}"
    # else:
    #     logname = logstage

    # get global name, ignore local name
    logname,_,scriptsdir = logfile_name( logstage,**kwargs )
    ensure_dir(scriptsdir)
    loghandle = open( logname,"w" )
    loghandle.write( f"""================
Logstage {logstage} started {datetime.date.today()}
================\n""" )
    return logname,loghandle,scriptsdir

# VLE this function is simple, needs to be inlined
# def close_logfile( output : OutputDict,**kwargs : dict[str,Any] ) -> None:
#     # logname: str, kwargs: dict[str, Any] ) -> None:
#     if ( loghandle := output.get("logfiles") ) is None:
#         error_abort( f"Can not find logfile to close: {logname}",**kwargs )
#     #kwargs["logfiles"].pop(logname)
#     loghandle.close()


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

    # All set: add the commandline to process input
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

def modules_to_load( **kwargs : Any ) -> tuple[str,str]:
    if nonzero_keyword("installing",**kwargs):
        modulestoload : str = package_prerequisites( **kwargs )
        loadcomment : str = f"# Loading environment for prerequisites: {modulestoload}"
    else:
        package,packageversion =  package_names( **kwargs )
        if nonnull(packageversion):
            modulestoload = f"{package}/{packageversion}"
            loadcomment = f"# Loading environment for package: {package}/{packageversion}"
        else:
            modulestoload = package
            loadcomment = f"#Loading environment for package: {package}"
    return modulestoload,loadcomment

##
## Execute a script in the context of compiler and modules
## return: value, or FAILURE string
##
def get_value_from_loaded( script_function : Callable[ list[str],tuple[str,str] ],
                           args : list[Optional[str]],**kwargs : Any ) -> str:
    # Generate the meat of the script
    mainscript,scripttitle = script_function(args,**kwargs)
    scripttitle = remove_macros( scripttitle,kwargs )

    # Script location
    scriptsdir : str = abort_on_zero_keyword( "scriptsdir",**kwargs )
    ensure_dir(scriptsdir,**kwargs)

    # title can contain path macros like TACC_PACKAGE_LIB
    cleantitle = clean_title( scripttitle,**kwargs )
    outputbase : str = f"{scriptsdir}/{cleantitle}"

    # cobble together script
    scriptfilename : str = f"{outputbase}.sh"
    outputfilename : str = f"{outputbase}.out"

    write_script_file( scriptfilename,scripttitle,cleantitle,mainscript,**kwargs )

    trace_string( f"Script for {scripttitle} in: {scriptfilename}",**kwargs )
    value = process_execute_immediate(
        execute_execute_script( scriptfilename,outputfilename,**kwargs ),
        **kwargs,title=scripttitle )
    #
    # Parse script output for success/failure
    #
    msg : str = f"""\
UNEXPECTED: {outputfilename} has no success/failure lines
    """
    with open(outputfilename,"r") as results:
        for line in results:
            line = line.strip()
            if fail := re.match( r'FAILURE[:\s]*(.*)',line ):
                msg = fail.groups()[0]
                print( f"""\
FAILURE: {scripttitle}; 
failed with: {msg}
see for details: {outputfilename}
                """ )
                return None
            elif fine := re.match( r'SUCCESS[:\s]*(.*)',line ):
                msg = fine.groups()[0]
    print( f"""\
SUCCEEDED: {scripttitle}
with: {msg}
see for details: {outputfilename}
                """ )
    return value
    
def get_value_from_virgin( script_function : Callable[ list[str],tuple[str,str] ],
                           args : list[str], **kwargs : Any ) -> str:
    return get_value_from_loaded(
        script_function,args,**kwargs,skipmodules=True )

##
## Aux
##

#
# Generate the script file
#
def write_script_file(
        scriptfilename : str,scripttitle : str,cleantitle : str,mainscript : str,
        **kwargs ) -> None:
    if nonzero_keyword( "setupredirect",**kwargs ):
        redirectstart : str = f"\nexec 3>f{cleantitle}_setup.out"
        redirectstop  : str = f"\nexec 3>&-"
        redirect      : str = f"1>&3"
    else:
        redirectstart = ""; redirectstop = ""; redirect = ""
    
    with open(scriptfilename,"w") as scriptfile:

        # header
        scriptfile.write( f"""\
#!/bin/bash

echo "Start script: {scripttitle}"
echo "This output was generated by: {scriptfilename}"
{redirectstart}
        """ )
        # prerequisites or package
        modulestoload,loadcomment = modules_to_load( **kwargs )
        # compiler modules, in core mode this only resets
        compilermpi,_ = load_compiler_and_mpi_and_modules_script\
            ( modulestoload, redirect=redirect, **kwargs )
        scriptfile.write( compilermpi+"\n" )

        # compiler names, this is empty in core mode
        compilersettings,_ = export_compilers_script( [],**kwargs )
        scriptfile.write( compilersettings+"\n" )
        flags_export : str = export_flags( **kwargs )
        scriptfile.write( flags_export+"\n" )

        # stuff
        for s in derived_settings:
            scriptfile.write( f"export {s}={kwargs[s]}\n" )

        # actual script
        scriptfile.write( f"""
# Now follows script: {scripttitle}:
{mainscript}
{redirectstop}
        """ )

#
# Script that executes a script
#
def execute_execute_script( scriptfilename : str,outputfilename : str,**kwargs : Any ) -> str:
    script : str = f"""
chmod +x {scriptfilename}
set -o pipefail
    """
    if nonzero_keyword( "immediate_output",**kwargs ):
        script += f"""
{scriptfilename} 2>&1 | tee {outputfilename}
if [ ${{PIPESTATUS[0]}} -gt 0 ] ; then
    echo FAILURE running script {scriptfilename}
fi
        """
    else:
        script += f"""
{scriptfilename} > {outputfilename} 2>&1
if [ $? -gt 0 ] ; then
    echo FAILURE running script {scriptfilename}
fi
        """
    return script

##
## Return directory, actual file name & name with LMOD variable unexpanded
##
def file_to_exist_names( package : str,dirtype : str,program : str,**kwargs ) -> tuple[str,str,str]:
    if dirtype in [ "dir","inc","lib","bin", ]:
        dirvar : str = dir_variable(package,dirtype)
        filedir_to_report :str = f"${{{dirvar}}}"
    else:
        filedir_to_report = f"${{TACC_{package.upper()}_DIR}}/{dirtype}"
    filedir        : str = remove_macros( filedir_to_report,kwargs )
    file_to_test   : str = f"{filedir}/{program}"
    file_to_report : str = f"{filedir_to_report}/{program}"
    return filedir,file_to_test,file_to_report

def dir_variable( package: str, dirtype: str = "dir" ) -> str:
    return f"TACC_{package.upper()}_{dirtype.upper()}"

