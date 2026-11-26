################################################################
####
#### install_make.py : make configure & build
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

def make_build_script( dirnamesl : tuple[str,DirNamesDict],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames = dirnamesl
    # srcdir,builddir,prefixdir = cmakedirs
    srcdir = dirnames["srcdir"]
    # flags and options
    jcount          : str = kwargs.get("jcount","6")
    make            : str = f"make --no-print-directory V=1 VERBOSE=1 -j {jcount}"
    makebuildtarget : str = kwargs.get("makebuildtarget","")

    script : str = f"""
make -f {srcdir}/Makefile SRCDIR={srcdir} PROJECTNAME={program} {program}
    """
    return script,"Make compilation"

def make_configure_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    script : str = ""
    if premake := nonzero_keyword( "PREMAKE",**kwargs ):
        premake = remove_macros( premake,**kwargs )
        trace_string( f"Using premake: {premake}",**kwargs )
        if redirectloc := nonzero_keyword( "setupredirect",**kwargs ):
            redirect : str = "1>&3" # This is copied from process.py. Generalize?
        else: redirect = ""
        startdir = kwargs.get("startdir")
        script += f"""\n
cd {startdir}
report_success_failure \
    "enter {startdir} for premake actions" \
    "startdir={startdir} for premake does not exist"
echo "Doing premake=<<{premake}>> in $(pwd)"
( {premake} ) {redirect}
report_success_failure "premake succeeded" "premake failed"
        """
    return script,"Make setup"

def make_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "configure", **kwargs )
    #**{ **kwargs,"title":"make configure", } )
    retval : Optional[str] = get_value_from_loaded(
        make_configure_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def make_build_install_script( pmakedirs : tuple[str,DirNamesDict],
                       **kwargs : dict[str,Any] ) -> tuple[str,str]:
    _,dirnames = pmakedirs
    srcdir = dirnames["srcdir"]
    prefixdir = dirnames["prefixdir"]
    #builddir = dirnames["builddir"]; 

    jcount  : str = kwargs.get("jcount",6)
    targets : str = kwargs.get( "MAKETARGETS","" )
    trace_string( f"making targets: {targets}",**kwargs )
    script = f"""
cd {srcdir}
report_success_failure "entering {srcdir=}" "does not exist {srcdir=}" 
make -j {jcount} {targets}
report_success_failure "make succeeded" "make failed"
    """

    if postmake := nonzero_keyword( "POSTMAKE",**kwargs ):
        # this does DESTDIR and such
        # maybe should have a better name?
        trace_string( f"post make: {postmake}",**kwargs )
        script += f"\n{postmake}\n"

    if postinstall := nonzero_keyword( "POSTINSTALL",**kwargs ):
        trace_string( f"post install: {postinstall}",**kwargs )
        script += f"\ncd {prefixdir} && {postinstall}\n"

    return script,"Make build install"

def make_build( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage( "build",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        make_build_install_script,[ "",get_dir_names(**kwargs) ],
        **kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
