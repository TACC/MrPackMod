################################################################
####
#### install_petsc.py : PETSc configure & build
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

def petsc_configure_script( pdirs : tuple[str,DirNamesDict],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames = pdirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    # srcdir,prefixdir = plist
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    petscflags : str = kwargs.get("PETSCFLAGS","")
    script : str = f"""
if [ ! -d "{srcdir}" ] ; then
    echo "FAILURE: src dir {srcdir} does not exist" && exit 1
fi
cd {srcdir}
    """
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    script += f"""
if [ ! -f "configure" ] ; then
    echo "FAILURE: no petsc configure script found in ${{PWD}}" && exit 1
fi
which python3
cmdline="python3 ./configure \
    CC=${{CC}} CXX=${{CXX}} FC=${{FC}} \
    {petscflags} \
    --prefix={prefixdir}"
echo "Configure cmdline=$cmdline"
eval $cmdline
    """
    return script,"Make setup"

def petsc_build_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    srcdir  : str = srcdir_name( **kwargs )
    jcount  : str = kwargs.get("jcount",6)
    targets : str = kwargs.get( "MAKETARGETS","" )
    trace_string( f"making targets: {targets}",**kwargs )

    script : str = f"\ncd {srcdir}\n"
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    script += f"""
make -j {jcount} all
make -j {jcount} install
    """
    return script,"Make build"

def petsc_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage( "configure",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        petsc_configure_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output} )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def petsc_build( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage( "build",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        petsc_build_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
