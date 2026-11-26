################################################################
####
#### install_meson.py : meson configure & build
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

def meson_configure_script( pmakedirs : tuple[str,dict[str,Any]],**kwargs : dict[str,Any] ) \
    -> tuple[str,str]:
    package,dirnames = pmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir    : str = dirnames["srcdir"]
    builddir  : str = dirnames["builddir"]
    prefixdir : str = dirnames["prefixdir"]

    mesonflags : str = kwargs.get("MESONFLAGS","")
    setupscript : str = ""

    ##
    ## do configure
    ##
    if ( option := nonzero_keyword( "PREFIXOPTION",**kwargs ) ) is not None:
        prefixoption = option # pdtoolkit
    else: prefixoption = "--prefix"
    if ( flags := nonzero_keyword( "CONFIGUREFLAGS",**kwargs ) ) is not None:
        flags = f" {flags}"
    else: flags = ""
    configurescript : str = f"""
echo "Test for meson executable"
which meson 2>/dev/null
report_success_failure "meson executable found" "meson executable not found"

echo "Go to srcdir={srcdir}"
cd {srcdir}
echo -e "\\nTest for meson.build file"
if [ ! -f meson.build ] ; then
    echo "No meson.build file" && exit 1
else
    mesonconfigure="CC=${{TACC_CC}} CXX=${{TACC_CXX}} FORTRAN=${{TACC_FC}} \
    meson setup {builddir} \
        {prefixoption}={prefixdir} \
        {mesonflags} \
    "
    echo -e "Meson cmdline:\n${{mesonconfigure}}"
    eval ${{mesonconfigure}}
    report_success_failure "meson build succeeded" "meson build failed"
fi
"""
    return setupscript+configurescript,"Meson configuring"

def meson_build_script( pmakedirs : tuple[str,dict[str,Any]],**kwargs: dict[str,Any] ) \
    -> tuple[str,str]:
    program,dirnames = pmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    if ( subdir := nonzero_keyword("MAKESUBDIR",**kwargs) ) is None:
        subdir = srcdir

    #
    # Make
    #
    jval : str = kwargs.get("jcount",6)
    makecommand : str = f"meson install"
    script : str = f"""
cd {subdir}
{makecommand}
    """
    if extra := nonzero_keyword( "EXTRABUILDTARGETS",**kwargs ):
        trace_string( f" .. making extra targets: {extra}",**kwargs )
        script += f"\n{makecommand} {extra}\n"

    return script,"Meson make and install"

def meson_configure( **kwargs: Any ) -> Optional[str]:
    if re.match( "FAILURE", ( properness := test_proper_prerequisites( **kwargs ) ) ):
        error_abort( f"Can not configure due to:\n{properness}",**kwargs )
    output : OutputDict = \
        start_test_stage( "meson configure",**kwargs, )
    retval : Optional[str] = get_value_from_loaded(
        meson_configure_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def meson_build( **kwargs: Any ) -> Optional[str]:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage( "meson build",**kwargs, )
    retval : Optional[str] = get_value_from_loaded(
        meson_build_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
