################################################################
####
#### install_cmake.py : cmake configure & build
####
################################################################

import os
import re
from typing import Any, Optional

from MrPackMod.basics  import remove_macros,trace_string,\
    error_abort,nonnull,nonzero_keyword
from MrPackMod.names   import get_dir_names,srcdir_name,DirNamesDict
from MrPackMod.process import get_value_from_loaded
from MrPackMod.scripts import nonzero_exports,nonzero_unsets
from MrPackMod.testing import start_test_stage,end_test_stage,\
    test_proper_prerequisites,OutputDict

def cmake_configure_script( pcmakedirs : tuple[str,dict[str,Any]],
                            **kwargs : Any ) -> tuple[str,str]:
    program,dirnames = pcmakedirs
    program = re.sub( r'\..*','',program )
    cmakeopts = dirnames.get("cmakeopts")

    script : str = ""
    # setup
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    if unset_cmdline := nonzero_unsets( **kwargs ):
        script += f"\n{unset_cmdline}\n"

    # remove old crud
    script += configure_preclean( dirnames,**kwargs )

    # cmake
    cmake         = cmake_basic_command( **kwargs )
    cmakeflags    = cmake_options( cmakeopts,**kwargs )
    buildsettings = cmake_build_settings( **kwargs )

    # set src, build, prefix
    pathsettings  = cmake_paths_settings( dirnames,**kwargs )
    builddir      = dirnames["builddir"]

    # for the regression case only: define project macro
    if nonnull(program) : pathsettings += f" -D PROJECTNAME={program}"
    script += f"""
echo "CMAKE_PREFIX_PATH=$( echo ${{CMAKE_PREFIX_PATH}} | tr ':' '\\n' )"
echo "PKG_CONFIG_PATH=$(   echo ${{PKG_CONFIG_PATH}}   | tr ':' '\\n' )"
cmdline="{cmake} {buildsettings} {cmakeflags} {pathsettings}"
echo "Doing cmake in pwd=${{PWD}}"
echo " .. with cmake=$( which cmake )"
echo " .. cmake cmdline=$cmdline" \
    | sed -e 's/-D/\\n    -D/g' -e 's/-S /\\n    -S /' -e 's/-B /\\n    -B /'
eval $cmdline
report_success_failure "configure succeeded" "cmake failed"
"""
    if ( grep := dirnames.get("grep") ) is not None:
        script += f"""
cd {builddir}

"""

    ## maybe only in the log file? script += configure_postreport( dirnames,**kwargs )
    script = script.replace( r'^ +-D(.*)$',r'  -D \1\\\n' )
    return script,"CMake configuring"

def configure_preclean( dirnames : DirNamesDict,**kwargs : Any ) -> str:
    builddir = dirnames ["builddir"]
    prefixdir = dirnames["prefixdir"]
    script : str =  f"""
echo "Remove any builddir: {builddir}"
rm -rf {builddir}
    """
    # netcdf installs c & f into the same prefix
    if kwargs.get("NOSCRATCHINSTALL") is None:
        script += f"""
echo "Remove any prefixdir: {prefixdir}"
rm -rf {prefixdir}
        """
    return script

def configure_postreport( dirnames : DirNamesDict,**kwargs : Any ) -> str:
    builddir = dirnames ["builddir"]
    return f"""
echo "Builddir {builddir} contents:"
ls {builddir}
    """

def cmake_build_script( pcmakedirs : tuple[str,DirNamesDict],
                        **kwargs : dict[str,Any] ) -> tuple[str,str]:
    _,dirnames = pcmakedirs
    srcdir = dirnames["srcdir"]; builddir = dirnames["builddir"]; prefixdir = dirnames["prefixdir"]

    script : str = f"""
echo -e "\\n>>> Start of cmake build"
    """
    # flags and options
    jcount          : str = kwargs.get("jcount","6")
    make            : str = f"make --no-print-directory V=1 VERBOSE=1 -j {jcount}"
    makebuildtarget : str = kwargs.get("makebuildtarget","")
    # execute make & make install
    trace_string( f"Making in builddir: {builddir}",**kwargs )
    if ninja := kwargs.get( "CMAKEUSENINJA" ):
        makeline = f"ninja install"
    else:
        makeline = f"{make} --no-print-directory V=1 VERBOSE=1 -j {jcount} {makebuildtarget}"
    script += cmake_build_pre( dirnames,**kwargs )
    script += f"""
{makeline}
if [ $? -eq 0 ] ; then
    echo SUCCESS: compilation succeeded
else
    echo FAILURE: compilation failed
fi
    """
    if extra_targets := nonzero_keyword( "extrabuildtargets" ):
        script += f"""
{make} {extra_targets}
        """
    if nonnull(prefixdir) and not ninja:
        script += f"""
{make} install
if [ $? -eq 0 ] ; then
    echo SUCCESS: installation succeeded
else
    echo FAILURE: installation failed
fi
        """
    script += f"""
echo " .. end of cmake build"
    """
    return script,"CMake make and install"

def cmake_basic_command( **kwargs : Any ) -> str:
    cmake : str = kwargs.get( "CMAKENAME","cmake" )
    if nonzero_keyword( "CMAKEUSENINJA",**kwargs ):
        cmake = f"{cmake} -G Ninja"
    return f"TERM=dumb {cmake} --fresh -Wno-dev \
-D CMAKE_COMPILE_WARNING_AS_ERROR=OFF \
-D CMAKE_POLICY_VERSION_MINIMUM=3.13 \
-D CMAKE_VERBOSE_MAKEFILE=ON \
-D CMAKE_COLOR_MAKEFILE=OFF \
-D CMAKE_TERM_SUPPORTS_ANSI=OFF"

def cmake_options( opts : Optional[str],**kwargs: Any ) -> str:
    cmakeflags : str = "  -D CMAKE_VERBOSE_MAKEFILE=ON  -D CMAKE_EXPORT_COMPILE_COMMANDS=ON"
    if ( standard := kwargs.get("CPPSTANDARD") ) is not None:
        cmakeflags += f"  -D CMAKE_CXX_FLAGS=-std=c++{standard}"
    if ( conflags := nonzero_keyword("CMAKEFLAGS",**kwargs) ) is not None \
       or ( envflags := os.getenv("CMAKE_C_FLAGS") ) is not None \
       or nonnull( opts ):
        flags : str = f" -D MPM_CUSTOM_FLAGS=START "
        # VLE we need to cover the case that both are nonzero:
        # we need to edit the envflags into the conflags
        if conflags is not None:
            flags += conflags
        elif envflags is not None:
            flags += f" -D CMAKE_C_FLAGS={envflags}"
        if nonnull( opts ):
            flags += f" {opts}"
        cmakeflags += f"{flags} -D MPM_CUSTOM_FLAGS=END "
    return cmakeflags.lstrip(" ")

def cmake_build_settings( **kwargs ) -> str:
    if kwargs.get("CMAKEBUILDDEBUG"):
        defaultbuild = "Debug"
    else: defaultbuild = "RelWithDebInfo"
    cmakebuildtype = kwargs.get("CMAKEBUILDTYPE",defaultbuild)
    if static := kwargs.get("buildstaticlibs"):
        buildsharedlibs = "OFF"
    else: buildsharedlibs = "ON"
    return f""" -D BUILD_SHARED_LIBS={buildsharedlibs}  -D CMAKE_BUILD_TYPE={cmakebuildtype} """

def cmake_paths_settings( dirnames : DirNamesDict,**kwargs ) -> str:
    srcdir    = dirnames["srcdir"]
    builddir  = dirnames["builddir"]
    prefixdir = dirnames["prefixdir"]
    if nonnull( source := kwargs.get("CMAKESUBDIR") ):
        effectivesrcdir : str = f"{srcdir}/{source}"
    else: effectivesrcdir = srcdir
    if not os.path.isdir(effectivesrcdir):
        error_abort\
            ( f"Can not find source dir {effectivesrcdir}; did you forget to download?",
              **kwargs )
    settingsfile : str = f"{effectivesrcdir}/CMakeLists.txt"
    if not os.path.exists( f"{settingsfile}" ):
        error_abort( f"Can not find cmake settings file: {settingsfile}",**kwargs )
    cmakepathsetting : str = f"-S {effectivesrcdir} -B {builddir}"
    if nonnull(prefixdir):
        cmakepathsetting += f" -D CMAKE_INSTALL_PREFIX={prefixdir}"
    return cmakepathsetting

def cmake_build_pre( dirnames : DirNamesDict,**kwargs : Any ) -> str:
    builddir = dirnames["builddir"]
    prescript : str = f"""
if [ ! -d "{builddir}" ] ; then
    echo "FAILURE: no such build dir: {builddir}"
    exit  1
else
    echo "entering builddir: {builddir}"
fi
cd {builddir}
"""
    if kwargs.get( "CMAKEUSENINJA" ) is None:
        prescript += f"""
if [ ! -f makefile -a ! -f Makefile ] ; then
    echo "FAILURE: build dir {builddir} has no makefile or Makefile"
    exit 1
fi
"""
    return prescript

def cmake_configure( **kwargs: Any ) -> Optional[str]:
    if re.match( "FAILURE", ( properness := test_proper_prerequisites( **kwargs ) ) ):
        error_abort( f"Can not configure due to:\n{properness}",**kwargs )
    output : OutputDict = \
        start_test_stage( "cmake configure",**kwargs, )
    retval : Optional[str] = get_value_from_loaded(
        cmake_configure_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def cmake_build( **kwargs: Any ) -> Optional[str]:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage( "cmake build",**kwargs, )
    retval : Optional[str] = get_value_from_loaded(
        cmake_build_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
