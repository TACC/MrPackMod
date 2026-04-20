#!/usr/bin/env/python3

#
# standard python modules
#
import os
import re
from typing import Any

#
# my own modules
#
import MrPackMod.names as names
from MrPackMod.process import echo_string,error_abort,abort_on_zero_keyword


def list_installations( **kwargs: Any ) -> None:
    installroot = abort_on_zero_keyword( "installroot",**kwargs )
    package     = abort_on_zero_keyword( "PACKAGE",**kwargs ).lower()
    dirs = [ d for d in os.listdir(installroot)
             if os.path.isdir( f"{installroot}/{d}" )
             and re.match( f"installation-{package}",d )
             ]
    echo_string( f"Found installations in installroot {installroot}\n{dirs}" )
    
def list_logfiles( **kwargs: Any ) -> None:
    _,configurelog = names.logfile_name( "configure",**kwargs )
    _,installlog   = names.logfile_name( "install",**kwargs )
    print( f"{configurelog} {installlog}" )

def configurelog_name( **kwargs: Any ) -> str:
    if bs := kwargs.get("BUILDSYSTEM"):
        if bs=="cmake":
            error_abort( "Can not find log for cmake. Yet",**kwargs )
        elif bs=="autotools":
            src = names.srcdir_name(**kwargs)
            log = f"{src}/config.log"
            if os.path.exists( log ):
                return log
            error_abort( "Could not find autotools log under obvious name",**kwargs )
        error_abort(
            f"No configure log support for build system: {bs}", **kwargs )
    error_abort( "No build system given",**kwargs )
