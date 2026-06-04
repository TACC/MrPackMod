import os
import re
import sys
import traceback

from typing import Any, Optional, NoReturn

from MrPackMod.basics  import nonzero_env,nonnull,isnull,\
    require_nonzero,unimplemented,\
    echo_string,trace_string,echo_warning,trace_var,error_abort

## test on string
def abort_on_null( val: Any, msg: str, **kwargs: Any ) -> Any:
    if nonnull( val ):
        return val
    else:
        error_abort( f"Can not have null: {msg}",**kwargs )

## test on environment variable
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

# test on FAILURE/SUCCESS
def abort_on_failure_result( result : str,**kwargs : Any ) -> Optional[NoReturn]:
    if match := re.match( r'FAILURE:?\s*(.*)$',result ):
        error_abort( match.groups()[0],**kwargs )
