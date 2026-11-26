################################################################
####
#### install_scons.py : scons configure & build
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

def scons_configure_script( pmakedirs : tuple[str,dict[str,Any]],**kwargs : dict[str,Any] ) \
    -> tuple[str,str]:
    package,dirnames = pmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    sconsflags : str = kwargs.get("SCONSFLAGS","")
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
echo "Test for Scons module"
PYTHONPATH=/scratch/00434/eijkhout/installation/scons/installation-scons-4.9.1-stampede3-gcc13.2.0 python3 -c "import SCons"
report_success_failure "python can load SCons" "python could not load SCons module"
python3 -c "from SCons.Script.Main import main"
report_success_failure "python can load scons script main" "python could not load scons module script main"

echo -e "\\nCheck validity of scons:\\n$(which scons)\\nuses:\\n$( head -1 $(which scons) )\\nand python is:\\n$(which python3)"

echo "Go to srcdir={srcdir}"
cd {srcdir}
echo -e "\\nTest for SConstruct file"
if [ ! -f SConstruct ] ; then
    echo "No SConstruct" && exit 1
else
    if [ -f {package}.conf ] ; then
        echo "removing {package}.conf"
        rm -f {package}.conf
    fi
    echo "scons=$(which scons)"
    PYTHONPATH=/scratch/00434/eijkhout/installation/scons/installation-scons-4.11.1-stampede3-gcc13.2.0/:${{PYTHONPATH}} \
    scons \
        build env_vars=all \
        CC=${{TACC_CC}} CXX=${{TACC_CXX}} FORTRAN=${{TACC_FC}} \
        prefix={prefixdir} \
        {sconsflags} \
        googletest='none'
    report_success_failure "scons build succeeded" "scons build failed"
fi
"""
    return setupscript+configurescript,"Scons configuring"

def scons_build_script( pmakedirs : tuple[str,dict[str,Any]],**kwargs: dict[str,Any] ) \
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
    makecommand : str = f"scons install"
    script : str = f"""
cd {subdir}
{makecommand}
    """
    if extra := nonzero_keyword( "EXTRABUILDTARGETS",**kwargs ):
        trace_string( f" .. making extra targets: {extra}",**kwargs )
        script += f"\n{makecommand} {extra}\n"

    return script,"Scons make and install"

def scons_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = start_test_stage( "configure",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        scons_configure_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def scons_build( **kwargs : Any ) ->Optional[str]:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage( "build",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        scons_build_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
