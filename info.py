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
from MrPackMod.basics  import echo_string,error_abort,nonzero_keyword


def list_installations( **kwargs: Any ) -> None:
    if ( installroot := nonzero_keyword( "installroot",**kwargs ) ) is None:
        error_abort( "no installroot found",**kwargs )
    else: installroot = installroot.lower()
    if ( package := nonzero_keyword( "PACKAGE",**kwargs ) ) is None:
        error_abort( "no package keyword found",**kwargs )
    else: package = package.lower()
    dirs = [ d for d in os.listdir(installroot)
             if os.path.isdir( f"{installroot}/{d}" )
             and re.match( f"installation-{package}",d )
             ]
    echo_string( f"Found installations in installroot {installroot}\n{dirs}" )
    
# def list_logfiles( **kwargs: Any ) -> None:
#     _,configurelog = names.logfile_name( "configure",**kwargs )
#     _,installlog   = names.logfile_name( "install",**kwargs )
#     print( f"{configurelog} {installlog}" )

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
