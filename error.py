import os
import re
import sys
import traceback

from typing import Any, NoReturn

from MrPackMod.tracing import echo_string,trace_string,echo_warning,trace_var

##
## Keyword handling
##
def nonzero_env( envvar: str, **kwargs: Any ) -> str:
    return os.getenv( envvar,"" )

def abort_on_null( val: Any, msg: str, **kwargs: Any ) -> Any:
    if nonnull( val ):
        return val
    else:
        error_abort( f"Can not have null: {msg}",**kwargs )

def abort_on_zero_env( envvar: str, **kwargs: Any ) -> str:
    try:
        val = os.environ[envvar]
        return val
    except Exception:
        error_abort( f"Environment variable can not be null: {envvar}",**kwargs )

def abort_on_nonzero_env( envvar: str, **kwargs: Any ) -> None:
    try:
        val = os.environ[envvar]
        if nonnull( val ) :
            error_abort( f"Can not handle nonzero environment variable {envvar}={val}" )
    except:
        pass

def abort_on_zero_keyword( keyword: str, **kwargs: Any ) -> Any:
    if not ( val := kwargs.get(keyword) ):
        error_abort( f"must have non-null keyword: {keyword}",**kwargs )
    else: return val

def nonnull( val: Any ) -> bool:
    return ( val is not None ) \
        and ( val is not False ) \
        and  ( ( isinstance(val,list) and len(val)>0) \
               or ( isinstance(val,str) and not re.match( r'^\s*$',val ) )
               or ( isinstance(val,bool) and val==True )
              )

def isnull( val: Any ) -> bool:
    return not nonnull( val )

def zero_keyword( var: str, **kwargs: Any ) -> bool:
    return not nonzero_keyword( var,**kwargs )

# return value or false
def nonzero_keyword( var: str, **kwargs: Any ) -> Any:
    #print( f"test {var}: {kwargs.get(var)}" )
    if nonnull( val := kwargs.get(var) ):
        return val
    return False

def nonzero_keyword_or_default( var: str, **kwargs: Any ) -> Any:
    if nonnull( val := kwargs.get(var) ):
        return val
    elif val := kwargs.get("default"):
        return val
    else:
        raise Exception( f"Keyword not given or defaulted: {var}" )

def requirenonzero( var: str ) -> None:
    try:
        val = locals()[var]
        if val == "":
            raise Exception( f"variable is zero: {var}" )
    except:
        pass

def unimplemented( var: str ) -> None:
    try:
        val = locals()[var]
    except:
        pass

def error_abort( string: str, **kwargs: Any ) -> NoReturn:
    echo_string( f"\nERROR {string}\n\ntraceback:" )
    traceback.print_stack()
    sys.exit(1)
