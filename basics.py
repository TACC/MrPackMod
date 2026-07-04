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

def nonzero_env( envvar: str, **kwargs: Any ) -> Optional[str]:
    if nonnull( val := os.getenv( envvar ) ):
        return val
    else: return None

#
# Return keyword value or false
# Test first environment because it can override configuration vars
#
def nonzero_keyword( var : str,**kwargs : Any ) -> Optional[str]:
    envres = nonzero_env( var,**kwargs )
    keyres = nonzero_keyword_from_args( var,**kwargs )
    #print( f"testing key={var} env:{envres} key:{keyres}" )
    # if nonnull(envres) and nonnull(keyres):
    #     echo_warning( f"Got both key and env values for {var}, using env",**kwargs )
    if nonnull(envres): return envres
    if nonnull(keyres): return keyres
    return None

def zero_keyword( var: str, **kwargs: Any ) -> bool:
    return nonzero_keyword( var,**kwargs ) is None

def abort_on_zero_keyword( keyword: str, **kwargs: Any ) -> Optional[str]:
    if nonnull( val := nonzero_keyword( keyword,**kwargs ) ):
        return val
    else:
        error_abort( f"must have non-null keyword: {keyword}",**kwargs )

#
# local helpers
#
def nonzero_keyword_from_args( var: str, **kwargs: Any ) -> Any:
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

def remove_macros( string : str,**kwargs : Any ) -> str:
    macro_search = re.compile( r'\${([a-zA-Z0-9_-]+)}' )
    while found_one := re.search( macro_search,string ):
        macroname : str = found_one.groups()[0]
        if ( macrovalue := kwargs.get(macroname) ) is not None:
            string = re.sub( macro_search,str(macrovalue),string,1 )
        elif ( macrovalue := os.getenv(macroname) ) is not None:
            trace_string( f"got {macroname} from env as {macrovalue}",**kwargs )
            string = re.sub( macro_search,str(macrovalue),string )
        else:
            if nonzero_keyword( "nowarn",**kwargs ):
                # replace macro by its name.
                # VLE maybe we should completely avoid this routine
                # but then, this helps in `prerequisitesinstall'
                string = re.sub( macro_search,macroname,string,1 )
            else:
                error_abort( f"No replacement found for <<{macroname}>>",
                             **kwargs )
    return string

def clean_title( title : str,**kwargs : Any ) -> str:
    clean : str = re.sub("/",'-',re.sub(' ','_',title))
    clean = remove_macros( clean,**kwargs )
    return clean

####
#### Error handling
####
def error_abort( string: str, **kwargs: Any ) -> NoReturn:
    echo_string( f"\nERROR {string}\n\ntraceback:",**kwargs )
    traceback.print_stack()
    sys.exit(1)


####
#### Error tracing
####

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


####
#### Slightly higher level
####

def module_version_from_env( mod,**kwargs : Any ) -> Optional[str]:
    PKG : str = mod.upper()
    if not os.getenv( f"TACC_{PKG}_DIR" ):
        #print( f"packge not loaded: {PKG}" )
        return None
    if ver := os.getenv( f"TACC_{PKG}_VER" ):
        #print( f"packge {PKG} has VER={ver}" )
        return ver
    elif version := os.getenv( f"TACC_{PKG}_VERSION" ):
        #print( f"packge {PKG} has VERSION={version}" )
        return version
    else:
        #print( f"packge {PKG} could not determine version" )
        return ""

derived_settings : list[str] = [ "SRCDIR","BUILDDIR","PREFIXDIR" ]

##
## Parsing tools
##

#
# return stripped line, and bool result of any prefixed test
#
def line_strip_conditionals( line: str, **config_dict: Any ) -> tuple[str, bool]:
    """ returns: line,accept """
    trace_string( f"Test line for conditions: {line}",**config_dict )
    if test := re.search( r'^([a-zA-Z0-9_]+)(==|\!=)([a-zA-Z0-9_]+|"")\s+(.*)$',line ):
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
        cond : re.Match[str],**config_dict : Any,
        ) -> Tuple[Any, str, Any, str]:
    field1,op,field2,line = cond.groups()
    value1 = config_dict.get(field1,field1)
    value2 = config_dict.get(field2,field2)
    # bit of a hack: we want to allow module tests like
    # KEY!=""
    if value2=="\"\"": value2 = ""
    return value1,op,value2,line

from enum import Enum,auto
class ModuleLoadStrategy(Enum):
    prerequisites = auto()
    package = auto()
    all = auto()
