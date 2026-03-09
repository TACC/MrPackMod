#!/usr/bin/env/python3

#
# standard python modules
#
import os
import re

#
# my own modules
#
import names
from process import echo_string,error_abort,abort_on_zero_keyword


def list_installations( **kwargs ):
    installroot = abort_on_zero_keyword( "installroot",**kwargs )
    package     = abort_on_zero_keyword( "PACKAGE",**kwargs ).lower()
    dirs = [ d for d in os.listdir(installroot)
             if os.path.isdir( f"{installroot}/{d}" )
             and re.match( f"installation-{package}",d )
             ]
    echo_string( f"Found installations in installroot {installroot}\n{dirs}" )
    
def list_logfiles( **kwargs ):
    _,configurelog = names.logfile_name( "configure",**kwargs )
    _,installlog   = names.logfile_name( "install",**kwargs )
    print( f"{configurelog} {installlog}" )

def configurelog_name( **kwargs ):
    if bs := kwargs.get("BUILDSYSTEM"):
        if bs=="cmake":
            error_abort( "Can not find log for cmake. Yet",**kwargs )
        elif bs=="autotools":
            src = names.srcdir_name(**kwargs)
            log = f"{src}/config.log"
            if os.path.exists( log ):
                return log
            else:
                error_abort( "Could not find autotools log under obvious name",**kwargs )
    else: error_abort( "No build system given",**kwargs )
