################################################################
####
#### install_autotools.py : autotools configure & build
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

def autotools_configure_script( pmakedirs : tuple[str,dict[str,Any]],**kwargs : dict[str,Any] ) \
    -> tuple[str,str]:
    program,dirnames = pmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    if before := nonzero_keyword( "BEFORECONFIGURECMDS",**kwargs ):
        setup_script : str = f"\n{before}\n"
    else: setup_script = "\n"

    ##
    ## go to the right location for configure
    ## do autogen stuff before configure
    ##
    configsetupscript : str = config_setup_script( srcdir,**kwargs )

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
./configure {prefixoption}={prefixdir} --libdir={prefixdir}/lib {flags}
echo "SUCCESS: autotools configure succeeded"
    """
    return setup_script+configsetupscript+configurescript,"Autotools configuring"

def config_setup_script( srcdir : str,**kwargs : dict[str,Any] ) -> str:    
    if ( builddir := nonzero_keyword( "CONFIGINBUILDDIR",**kwargs ) ) is not None:
        trace_string( f" .. going to configure in build dir {builddir}",**kwargs )
        configloc : str = builddir
        config_cmdline : str = f"{srcdir}/configure"
    elif ( subdir := nonzero_keyword( "CONFIGURESUBDIR",**kwargs ) ) is not None:
        trace_string( f" .. going to configure in subdir: {subdir}.",**kwargs )
        configloc = f"{srcdir}/{subdir}"
        config_cmdline = f"./configure"
    else:
        configloc = f"{srcdir}"
        config_cmdline = f"./configure"
    if nonzero_keyword( "AUTOUPDATE",**kwargs ):
        autoupdate : str = "./autoupdate"
    else: autoupdate = ""
    return f"""
cd {configloc}
echo Starting configure process in $(pwd)
if [ -f \"configure\" ] ; then
  has_configure=1
  echo has configure script
else has_configure= ; echo no configure script ; fi
if [ -f \"autogen.sh\" ] ; then
  has_autogen=1
  echo has autogen
else has_autogen= ; echo no autogen ; fi
if [ -f \"configure.ac\" ] ; then
  has_ac=1
  echo has configure.ac 
else has_ac= ; echo no configure.ac ; fi

if [ -z "${{has_configure}}" ] ; then 
  if [ ! -z "${{has_ac}}" ] ; then
    aclocal && autoconf
  elif [ ! -z "${{has_autogen}}" ] ; then 
    ./autogen.sh
  else
    echo FAILURE Need configure.ac or autogen.sh to generate configure script && exit 1
  fi
fi
{autoupdate}
    """

def autotools_build_script( pmakedirs : tuple[str,dict[str,Any]],**kwargs: dict[str,Any] ) \
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
    makecommand : str = f"make --no-print-directory -j {jval}"
    script : str = f"""
cd {subdir}
{makecommand}
    """
    if extra := nonzero_keyword( "EXTRABUILDTARGETS",**kwargs ):
        trace_string( f" .. making extra targets: {extra}",**kwargs )
        script += f"\n{makecommand} {extra}\n"

    #
    # install
    #
    extra = kwargs.get( "EXTRAINSTALLTARGET","" )
    script += f"""
{makecommand} install {extra}
echo "SUCCESS: autotools build succeeded"
    """

    return script,"Autotools make and install"

def autotools_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = start_test_stage( "configure",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        autotools_configure_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def autotools_build( **kwargs : Any ) ->Optional[str]:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage( "build",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        autotools_build_script,[ "",get_dir_names(**kwargs) ],
        **{ **kwargs,**output, } )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
