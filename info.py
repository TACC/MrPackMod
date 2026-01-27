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
import process
from process import echo_string,abort_on_zero_keyword


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
