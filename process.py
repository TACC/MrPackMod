#!/usr/bin/env python3

##
## python modules
##
import os
import re
import shutil
import subprocess
import sys
import traceback

##
## Tracing
##

def echo_string( string,**kwargs ):
    # echo to stdout if no terminal
    # echo to terminal is specified unless suppressed
    if terminal := nonzero_keyword( "terminal",**kwargs ):
        if terminal != "suppress": print( string,file=terminal )
    else:
        print( f"{string}" )
    # even if no interactive output, we still go to all logfiles
    for logname,loghandle in kwargs.get("logfiles",{}).items():
        #print( string,file=loghandle )
        loghandle.write( f"{string}\n" )

def trace_string( string,**kwargs ):
    if kwargs.get( "tracing" ):
        echo_string( string,**kwargs )

def trace_var( var,**kwargs ):
    varvalue = eval(var)
    trace_string( f"var={varvalue}",**kwargs )

def echo_warning( string,**kwargs ):
    prefix = kwargs.get("prefix","")
    echo_string( f"{prefix}WARNING {string}",**kwargs )

def error_abort( string,**kwargs ):
    echo_string( f"\nERROR {string}\n\ntraceback:" )
    traceback.print_stack()
    sys.exit(1)

##
## Keyword handling
##
def nonzero_env( envvar,**kwargs ):
    return os.getenv( envvar,"" )

def abort_on_null( val,msg,**kwargs ):
    if nonnull( val ):
        return val
    else:
        error_abort( f"Can not have null: {msg}",**kwargs )

def abort_on_zero_env( envvar,**kwargs ):
    try:
        val = os.environ[envvar]
        return val
    except:
        error_abort( f"Environment variable can not be null: {envvar}",**kwargs )

def abort_on_nonzero_env( envvar,**kwargs ):
    try:
        val = os.environ[envvar]
        if nonnull( val ) :
            error_abort( f"Can not handle nonzero environment variable {envvar}={val}" )
    except:
        pass

def abort_on_zero_keyword( keyword,**kwargs ):
    if not ( val := kwargs.get(keyword) ):
        error_abort( f"must have non-null keyword: {keyword}",**kwargs )
    else: return val

def nonnull( val ):
    return ( val is not None ) \
        and ( val is not False ) \
        and  ( ( isinstance(val,list) and len(val)>0) \
               or ( isinstance(val,str) and not re.match( r'^\s*$',val ) )
               or ( isinstance(val,bool) and val==True )
              )

def isnull( val ):
    return not nonnull( val )

def zero_keyword( var,**kwargs ):
    return not nonzero_keyword( var,**kwargs )

# return value or false
def nonzero_keyword( var,**kwargs ):
    #print( f"test {var}: {kwargs.get(var)}" )
    if nonnull( val := kwargs.get(var) ):
        return val
    return False

def nonzero_keyword_or_default( var,**kwargs ):
    if nonnull( val := kwargs.get(var) ):
        return val
    elif val := kwargs.get("default"):
        return val
    else:
        raise Exception( f"Keyword not given or defaulted: {var}" )

def requirenonzero( var ):
    try:
        val = locals()[var]
        if val == "":
            raise Exception( f"variable is zero: {var}" )
    except:
        pass

def unimplemented( var ):
    try:
        val = locals()[var]
    except:
        pass

##
## File handling
##

#
# Create directory, or make sure it exists
#
def ensure_dir( name : str,**kwargs ) -> str:
    if re.match( r'/',name):
        dir : str = name
    else:
        pwd = os.getcwd()
        dir = f"{pwd}/{name}"
    trace_string( f"mkdir -p : {dir}",**kwargs )
    os.makedirs( dir,exist_ok=True)
    return dir

def create_dir( name : str,**kwargs ) -> str:
    try:
        shutil.rmtree(name)
    except FileNotFoundError: pass
    return ensure_dir( name,**kwargs )

##
## Process routines
##
def process_initiate( **kwargs ):
    return subprocess.Popen\
        (['/bin/bash', '-l'], 
         stdin=subprocess.PIPE, 
         stdout=subprocess.PIPE, 
         stderr=subprocess.STDOUT,
         text=True,
         bufsize=1)

def process_terminate( finished_process,**kwargs ):
    process_input = finished_process.stdin
    process_input.flush()
    process_input.close()
    lastline = ""
    while True:
        line = finished_process.stdout.readline()
        if not line:
            break
        line = re.sub( r'^[ \t]*','', re.sub( r'[ \t\n]*$','', line ) )
        if line != "":
            echo_string( line,**kwargs )
            lastline = line
    finished_process.wait()
    return lastline

def process_execute( cmdline,**kwargs ):
    outside_process = kwargs.get("process",None)
    immediate       = kwargs.get("immediate",None)
    if outside_process is None:
        process = process_initiate()
    else: process = outside_process
    #print( kwargs.get("terminal","no terminal") )
    echo_string( f"Command line={cmdline}",**kwargs )
    process_input = process.stdin
    process_output = process.stdout
    process_input.write( cmdline+"\n" )
    if immediate:
        process_input.flush() # VLE not sure if this works
    if outside_process:
        return ""
    else:
        result = process_terminate( process,**kwargs )
        trace_string( f" .. process result: {result}",**kwargs )
        return result

def number_satisfies( loaded,wanted,**kwargs ):
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
        res = re.search( match,loaded ); op = "*..."
    elif loaded==wanted:
        res = True; op = "=="
    else:
        res = False; op = "??"
    trace_string( f" .. tested {loaded} {op} {wanted}: {res}",**kwargs )
    return res

def version_satisfies( loaded,tomatch,**kwargs ):
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

