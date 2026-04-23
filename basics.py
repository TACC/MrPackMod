################################################################
#### basics.py : basic tests
################################################################

import os
import re
import sys
import traceback

from typing import Any, NoReturn

def nonnull( val: Any ) -> bool:
    return ( val is not None ) \
        and ( val is not False ) \
        and  ( ( isinstance(val,list) and len(val)>0) \
               or ( isinstance(val,str) and not re.match( r'^\s*$',val ) )
               or ( isinstance(val,bool) and val==True )
              )

def isnull( val: Any ) -> bool:
    return not nonnull( val )

def nonzero_env( envvar: str, **kwargs: Any ) -> str:
    return os.getenv( envvar,"" )

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

def require_nonzero( var: str ) -> None:
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

