################################################################
#### basics.py : basic tests
################################################################

import os
import re
import sys
import traceback

from typing import Any, NoReturn, Optional, Tuple

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

####
#### Macro related
####

##
## stripping of macros
##

def remove_macros( string : str,valdict : dict[str,Any] ) -> str:
    for key,val in valdict.items():
        if not type(val) is str: continue
        searchstring : str = f"${{{key}}}"
        oldstring : str = string
        string = string.replace( searchstring,val )
        # if oldstring!=string:
        #     trace_string( f"replace: {key} => {val}",**valdict )
    return string

def clean_title( title : str,**kwargs : Any ) -> str:
    clean : str = re.sub("/",'-',re.sub(' ','_',title))
    clean = remove_macros( clean,kwargs )
    return clean

####
#### Slightly higher level
####

def loaded_module_version( mod,**kwargs : Any ) -> Optional[str]:
    if not os.getenv( f"TACC_{mod.upper()}_DIR" ):
        return None
    if ver := os.getenv( f"TACC_{mod.upper()}_VER" ):
        return ver
    elif version := os.getenv( f"TACC_{mod.upper()}_VERSION" ):
        return version
    else: return ""

derived_settings : list[str] = [ "SRCDIR","BUILDDIR","PREFIXDIR" ]
