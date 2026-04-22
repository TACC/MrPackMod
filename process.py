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
from typing import Any, IO, NoReturn, Optional

from MrPackMod.tracing import trace_string,echo_string,echo_warning

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
        kwargs   : dict[str, Any],
        logdir   : Optional[str] = None,
        terminal : Any = None,
        ) -> str:
    # get global name, ignore local name
    logname,_ = logfile_name( logstage,dir=logdir,**kwargs )
    loghandle = open( logname,"w" )
    kwargs["logfiles"][logname] = loghandle
    trace_string( f"Open logfile {logname}",**kwargs,terminal=terminal )
    loghandle.write( f"""================
Logstage {logstage} started {datetime.date.today()}
================\n""" )
    return logname

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
def process_initiate( **kwargs: Any ) -> subprocess.Popen[str]:
    return subprocess.Popen\
        (['/bin/bash', '-l'], 
         stdin=subprocess.PIPE, 
         stdout=subprocess.PIPE, 
         stderr=subprocess.STDOUT,
         text=True,
         bufsize=1)

def process_terminate(
    finished_process: subprocess.Popen[str], **kwargs: Any
) -> str:
    process_input = finished_process.stdin
    process_output = finished_process.stdout
    assert process_input is not None and process_output is not None
    process_input.flush()
    process_input.close()
    lastline : str = ""
    while True:
        line : str = process_output.readline()
        if not line:
            break
        line = re.sub( r'^[ \t]*','', re.sub( r'[ \t\n]*$','', line ) )
        if line != "":
            echo_string( line,**kwargs )
            lastline = line
    finished_process.wait()
    return lastline

def process_execute( cmdline: str, **kwargs: Any ) -> str:
    outside_process = kwargs.get("process",None)
    immediate       = kwargs.get("immediate",None)
    if outside_process is None:
        process : subprocess.Popen[str] = process_initiate()
    else: process = outside_process
    #print( kwargs.get("terminal","no terminal") )
    echo_string( f"Command line={cmdline}",**kwargs )
    if re.search( r'\$\{',cmdline ):
        echo_warning( f"commandline contains unexpanded macros",**kwargs )
    if input := process.stdin:
        process_input  : IO[str] = input
    else: error_abort( f"Can not get process stdin",**kwargs )
    # if output := process.stdout:
    #     process_output : IO[str] = output
    # else: error_abort( f"Can not get process output",**kwargs )
    process_input.write( cmdline+"\n" )
    if immediate:
        process_input.flush() # VLE not sure if this works
    if outside_process:
        return ""
    else:
        result : str = process_terminate( process,**kwargs )
        trace_string( f" .. process result: {result}",**kwargs )
        return result

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

