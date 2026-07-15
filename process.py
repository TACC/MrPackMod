#!/usr/bin/env python3

##
## python modules
##
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
    ensure_dir,isnull,nonnull,error_abort,\
    ModuleLoadStrategy
from MrPackMod.names   import package_names,family_names,package_prerequisites,\
    mode_is_core
from MrPackMod.scripts import export_compilers_script,export_flags,\
    load_compiler_and_mpi_and_modules_script

##
## File handling
##

####
#### Logfiles
####

##
## Process routines
##
def process_initiate() -> subprocess.Popen[str]:
    return subprocess.Popen\
        (['/bin/bash', '-l'], 
         stdin=subprocess.PIPE, 
         stdout=subprocess.PIPE, 
         stderr=subprocess.PIPE, #STDOUT,
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
    if ( process_input := process.stdin ) is None:
        error_abort( "could not get stdin of process",**kwargs )
    trace_string( f"Execute cmdline=\"{cmdline}\" on new process {process.pid}",**kwargs )

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

#
# This is called indirectly through get_value which is used everywhere
# Hence we need the case where no strategy is defined (yet)
#
def modules_to_load( **kwargs : Any ) -> tuple[str,str]:
    if ( strategy := kwargs.get("moduleloadstrategy") ) is not None:
        package,packageversion =  package_names( **kwargs )
        if nonnull(packageversion):
            packagetoload = f"{package}/{packageversion}"
            loadcomment = f"# Loading environment for package: {package}/{packageversion}"
        else:
            packagetoload = package
            loadcomment = f"#Loading environment for package: {package}"
        prereqmodules : str = package_prerequisites( **kwargs )
        if strategy==ModuleLoadStrategy.prerequisites:
            return prereqmodules,f"# Loading environment for prerequisites: {prereqmodules}"
        elif strategy==ModuleLoadStrategy.package:
            return packagetoload,loadcomment
        elif strategy==ModuleLoadStrategy.all:
            return f"{prereqmodules} {packagetoload}","Loading pkg and prereqs"
    else: 
        return "",""
##
## Execute a script in the context of compiler and modules
## return: value, or FAILURE string
##
def get_value_from_loaded( script_function : Callable[ list[str],tuple[str,str] ],
                           args : list[Any],**kwargs : Any ) -> Optional[str]:
    # Generate the meat of the script
    mainscript,scripttitle = script_function(args,**kwargs)
    scripttitle = remove_macros( scripttitle,**kwargs )

    # Script location
    scriptsdir : str = abort_on_zero_keyword( "scriptsdir",**kwargs )
    ensure_dir(scriptsdir,**kwargs)

    # title can contain path macros like TACC_PACKAGE_LIB
    cleantitle = clean_title( scripttitle,**kwargs )
    outputbase : str = f"{scriptsdir}/{cleantitle}"

    # cobble together script
    scriptfilename : str = f"{outputbase}.sh"
    outputfilename : str = f"{outputbase}.out"

    # make a script that outputs to explicit file & terminal
    write_script_file( scriptfilename,outputfilename,
                       scripttitle,cleantitle,mainscript,**kwargs )
    # not sure what this return value is. ignore?
    processvalue : str = process_execute_immediate(
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
            # we want to catch the last line
            # but filter out time stamps
            if re.match( 'Finished',line): continue
            returnvalue : str = line
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
see for details: {outputfilename}\
""" ) # no newlines before/after
    return returnvalue
# with: {msg}
# returning: {returnvalue}
    
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
        scriptfilename : str,outputfilename : str,
        scripttitle : str,cleantitle : str,mainscript : str,
        **kwargs ) -> None:
    
    immediate : str = "| tee /dev/tty" \
        if nonzero_keyword( "immediate_output",**kwargs ) else ""
    trace_string( f"Write script for <<{scripttitle}>> into <<{scriptfilename}>>",
                  **kwargs )
    with open(scriptfilename,"w") as scriptfile:
        # header
        scriptfile.write( f"""\
#!/bin/bash

exec >"{outputfilename}" 2>&1
echo "Start script: {scripttitle}"
echo " .. at $( date )"
echo "This output was generated by: {scriptfilename}"
        """ )
        # prerequisites or package
        modulestoload,loadcomment = modules_to_load( **kwargs )
        if not ( without_context := kwargs.get("without_context",False) ):
            # compiler modules, in core mode this only resets
            compilermpi,_ = load_compiler_and_mpi_and_modules_script\
                ( modulestoload, **kwargs )
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
        # note that we need to filter out the time stamp to retain the return result
        scriptfile.write( f"""
# Now follows script: {scripttitle}:
{{ {mainscript} }} {immediate}

echo "Finished: $( date )"
        """ )

#
# Script that executes a script
#
def execute_execute_script( scriptfilename : str,outputfilename : str,**kwargs : Any ) -> str:
    script : str = f"""
chmod +x {scriptfilename}
{scriptfilename} # the script does output routing itself
    """
    if nonzero_keyword("traceresult",**kwargs):
        script += f"""
if [ $? -gt 0 ] ; then
    echo FAILURE running script {scriptfilename}
fi
    """
    return script
