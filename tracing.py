from typing import Any, IO, NoReturn

from MrPackMod.basics  import nonzero_keyword

##
## Tracing
##

def echo_string( string: str, **kwargs: Any ) -> None:
    terminal_string( string,**kwargs )
    # even if no interactive output, we still go to all logfiles
    log_string( string,**kwargs )

def trace_string( string: str, **kwargs: Any ) -> None:
    if kwargs.get( "tracing" ):
        terminal_string( string,**kwargs )
    log_string( string,**kwargs )

def log_string( string : str,**kwargs : Any ) -> None:
    for _,loghandle in kwargs.get("logfiles",{}).items():
        loghandle.write( f"{string}\n" )

def terminal_string( string : str,**kwargs ) -> None:
    # echo to stdout if no terminal
    # echo to terminal is specified unless suppressed
    if terminal := nonzero_keyword( "terminal",**kwargs ):
        if terminal != "suppress": print( string,file=terminal )
    else:
        print( f"{string}" )

def trace_var( var: str, **kwargs: Any ) -> None:
    varvalue = eval(var)
    trace_string( f"var={varvalue}",**kwargs )

def echo_warning( string: str, **kwargs: Any ) -> None:
    prefix = kwargs.get("prefix","")
    echo_string( f"\n{prefix}WARNING {string}\n",**kwargs )
