################################################################
####
#### install_pip.py : pip configure & build
####
################################################################

import os
import re
from typing import Any, Optional

from MrPackMod.basics  import remove_macros,trace_string,\
    error_abort,nonnull,nonzero_keyword
from MrPackMod.names   import get_dir_names,srcdir_name,DirNamesDict
from MrPackMod.process import get_value_from_loaded
from MrPackMod.scripts import nonzero_exports
from MrPackMod.testing import start_test_stage,end_test_stage,\
    test_proper_prerequisites,OutputDict

def pip_configure_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    script : str = "echo SUCCESS: pip configure is noop"
    return script,"Pip configuring"

def pip_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage( "configure",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        pip_configure_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def pip_build_script( srcpfx : list[str],**kwargs : Any ) -> tuple[str,str]:
    print( f"dirs arg : {srcpfx}" )
    srcdir    = srcpfx["srcdir"]
    prefixdir = srcpfx["prefixdir"]
    if ( pip := kwargs.get("PIP") ) is None \
        and ( pip := os.getenv("PIP") ) is None:
        pip = "pip3"
    print( f"srcdir={srcdir}, prefix={prefixdir}, pip={pip}" )
    jcount  : str = kwargs.get("jcount",6)
    trace_string( f"pipping in {prefixdir}",**kwargs )
    script : str = f"""
cd {srcdir}
echo "Pipping into: {prefixdir}"
{pip} install --target={prefixdir} .
if [ $? -gt 0 ] ; then
    echo "FAILURE: pipping failed" && exit 1
fi
echo "SUCCESS: installed in {prefixdir}"
echo -e "contents:\n$( ls {prefixdir} )"
"""
    return script,"Pip build install"

def pip_build( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage( "build",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        pip_build_script,get_dir_names(**kwargs),
        **{ **kwargs,**output } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
