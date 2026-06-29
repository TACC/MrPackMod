################################################################
#### install.py
#### install functions for cmake/autotools.make
################################################################

#
# standard python modules
#
import datetime
import os
import pdb
import re
import shutil
from typing import Any, Optional

from MrPackMod.basics  import remove_macros,\
    echo_string, trace_string,\
    abort_on_zero_keyword,error_abort,\
    nonnull,nonzero_keyword, zero_keyword,\
    ModuleLoadStrategy
from MrPackMod.error   import abort_on_zero_env
from MrPackMod.names import logfile_name,srcdir_name,builddir_name,prefixdir_name,\
    compilers_names,modulefile_path,module_name_and_version
from MrPackMod.process import process_execute, process_initiate, process_terminate,\
    process_execute_immediate
from MrPackMod.process import open_logfile,get_value_from_loaded
from MrPackMod.scripts import export_compilers_script,\
    cmake_configure_script,cmake_build_script
from MrPackMod.testing import start_test_stage,end_test_stage,\
    OutputDict

def configure_prep( **kwargs: Any ) -> tuple[str, str, str]:
    from  MrPackMod import  modulefile
    #
    # setup directories
    #
    srcdir    = srcdir_name( **kwargs )
    builddir  = builddir_name( **kwargs )
    prefixdir = prefixdir_name( **kwargs )
    if nonzero_keyword( "scratch",**kwargs ):
        try:
            shutil.rmtree(builddir)
        except FileNotFoundError: pass
        os.makedirs(builddir,exist_ok=True)
    return srcdir,builddir,prefixdir

##
## CMake commandline with all options
## `pcmakedirs' is [program,src,build,prefix]
## where `program' is only nonnull for regression testing
##
def cmake_configure( **kwargs: Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "configure",
            **{ **kwargs,"title":"cmake configure", }
            )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : Optional[str] = get_value_from_loaded(
        cmake_configure_script,["",srcdir,builddir,prefixdir],**kwargs,**output, )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def cmake_build( **kwargs: Any ) -> Optional[str]:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage(
            "build",
            **{ **kwargs,"title":"cmake build", } )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=False )
    retval : Optional[str] = get_value_from_loaded(
        cmake_build_script,["",srcdir,builddir,prefixdir],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

################################################################
####
#### Autotools
####
################################################################

def autotools_configure_script( pmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program,srcdir,builddir,prefixdir = pmakedirs
    if before := nonzero_keyword( "BEFORECONFIGURECMDS",**kwargs ):
        setup_script : str = f"\n{before}\n"
    else: setup_script = "\n"

    ##
    ## go to the right location for configure
    ##
    if nonzero_keyword( "CONFIGINBUILDDIR",**kwargs ):
        trace_string( " .. going to configure in build dir",**kwargs )
        configloc : str = builddir
        config_cmdline : str = f"{srcdir}/configure"
    elif subdir := nonzero_keyword( "CONFIGURESUBDIR",**kwargs ):
        trace_string( f" .. going to configure in subdir: {subdir}.",**kwargs )
        configloc = f"{srcdir}/{subdir}"
        config_cmdline = f"./configure"
    else:
        configloc = f"{srcdir}"
        config_cmdline = f"./configure"
    config_loc_script : str = f"""
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
    """

    ##
    ## do stuff before configure
    ##
    if nonzero_keyword( "AUTOUPDATE",**kwargs ):
        autoupdate : str = "./autoupdate"
    else: autoupdate = ""
    reconf_script : str = f"""
if [ -z \"$has_configure\" ] ; then 
  if [ ! -z \"$has_ac\" ] ; then
    aclocal && autoconf
  elif [ ! -z \"$has_autogen\" ] ; then 
    ./autogen.sh
  else
    echo FAILURE Need configure.ac or autogen.sh to generate configure script && exit 1
  fi
fi
{autoupdate}
    """
    ##
    ## do configure
    ##
    if option := nonzero_keyword( "PREFIXOPTION",**kwargs ):
        prefixoption = option # pdtoolkit
    else: prefixoption = "--prefix"
    if flags := nonzero_keyword( "CONFIGUREFLAGS",**kwargs ):
        flags = f" {flags}"
    else: flags = ""
    configure_script : str = f"""
./configure {prefixoption}={prefixdir} --libdir={prefixdir}/lib {flags}
    """
    return setup_script+config_loc_script+reconf_script+configure_script,"Autotools configuring"

    
def autotools_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "configure",
            **{ **kwargs,"title":"autotools configure", } )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : Optional[str] = get_value_from_loaded(
        autotools_configure_script,["",srcdir,builddir,prefixdir],**kwargs,**output, )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def original_autotools_configure():
    if not has_configure or nonzero_keyword( "FORCERECONF",**kwargs ):
        if has_ac: 
            if nonzero_keyword( "DEFUNPROGFC",**kwargs ):
                process_execute( "sed -i configure.ac -e \'/AC_INIT/aAC_DEFUN([_AC_PROG_FC_V],[])\'",
                                 process=shell,**kwargs )
            if reconf := nonzero_keyword( "AUTORECONF",**kwargs ): # when does this happen?
                cmdline = f"{reconf} -i"
            else:
                cmdline = f"aclocal && autoconf"
            if nonzero_keyword( "PKGPROGPKGCONFIG",**kwargs ):
                process_execute( "sed -i configure -e \'s/PKG_PROG_PKG_CONFIG/pkg-config/\'",
                                 process=shell,**kwargs )
        elif has_autogen:
            cmdline = "./autogen.sh"
        else:
            raise Exception( "Need configure.ac or autogen.sh to generate configure script" )
        process_execute( cmdline,**kwargs,process=shell )

def autotools_build_script( pmakedirs : list[str],**kwargs: Any ) -> tuple[str,str]:
    program = pmakedirs[0]; cmakedirs = pmakedirs[1:]
    srcdir,builddir,prefixdir = cmakedirs

    if not ( subdir := nonzero_keyword("MAKESUBDIR",**kwargs) ):
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
    script += f"\n{makecommand} install {extra}\n"

    return script,"Autotools make and install"

def autotools_build( **kwargs : Any ) ->Optional[str]:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage(
            "build",
            **{ **kwargs,"title":"autotools build", } )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=False )
    retval : Optional[str] = get_value_from_loaded(
        autotools_build_script,["",srcdir,builddir,prefixdir],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

################################################################
####
#### Make
####
################################################################

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
echo "Doing premake in $(pwd)"
( {premake} ) {redirect}
        """
    return script,"Make setup"

def make_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "configure",
            **{ **kwargs,"title":"make configure", } )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : Optional[str] = get_value_from_loaded(
        make_configure_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def make_build_script( srcpfx : list[str],**kwargs : Any ) -> tuple[str,str]:
    srcdir,prefixdir = srcpfx
    jcount  : str = kwargs.get("jcount",6)
    targets : str = kwargs.get( "MAKETARGETS","" )
    trace_string( f"making targets: {targets}",**kwargs )
    script = f"""
cd {srcdir}
make -j {jcount} {targets}
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
        start_test_stage(
            "build",
            **{ **kwargs,"title":"make build", } )
    srcdir,_,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : Optional[str] = get_value_from_loaded(
        make_build_script,[ srcdir,prefixdir],
        **kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

################################################################
####
#### PETSc has a custom installer
####
################################################################

def petsc_configure( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "configure",
            **{ **kwargs,"title":"petsc configure", } )
    srcdir,_,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : Optional[str] = get_value_from_loaded(
        petsc_configure_script,[srcdir,prefixdir],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

def petsc_build( **kwargs : Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "build",
            **{ **kwargs,"title":"make build", } )
    retval : Optional[str] = get_value_from_loaded(
        petsc_build_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

################################################################
####
#### Post-install stuff
####
################################################################

def post_install_actions_script( plist : list[str],**kwargs : Any ) -> tuple[str,str]:
    # if we get here, we already know there are actions
    cptoinstall : Optional[str] = abort_on_zero_keyword( "CPTOINSTALLDIR",**kwargs )
    srcdir,prefixdir = plist
    trace_string( f"Extra cp from srcdir={srcdir} to prefix={prefixdir}: {cptoinstall}",
                  **kwargs )
    script : str = f"""
if [ -d "{prefixdir}/{cptoinstall}" ] ; then
    echo FAILURE: cptoinstall={cptoinstall} already exists in prefix
    exit 1
fi
cd {srcdir}
cp -r {cptoinstall} {prefixdir}
    """
    return script,"Post-install copy actions"

def post_install_actions( **kwargs ) -> Optional[str]:
    if cptoinstall := nonzero_keyword( "CPTOINSTALLDIR",**kwargs ):
        srcdir,_,prefixdir = configure_prep( **kwargs,scratch=True )
        output : OutputDict = \
            start_test_stage(
                "actions",
                **{ **kwargs,"title":"post-install actions", } )
        retval : Optional[str] = get_value_from_loaded(
            post_install_actions_script,[srcdir,prefixdir],**kwargs,**output )
        success,failure = end_test_stage( [],[],output,**kwargs )
        return retval
    else: return "SUCCESS: no cp-to-install"
    
import os
import stat

def recursive_rx( path: str ) -> None:
    perm_dir = stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR \
        + stat.S_IRGRP + stat.S_IXGRP \
        + stat.S_IROTH + stat.S_IXOTH
    perm_file = perm_dir

    # Change permissions for the top-level folder
    os.chmod(path, perm_dir )

    for root, dirs, files in os.walk(path):
        # set perms on sub-directories  
        for momo in dirs:
            os.chmod(os.path.join(root, momo), perm_dir )
        # set perms on files
        for momo in files:
            os.chmod(os.path.join(root, momo), perm_file )

def public_installation( **kwargs: Any ) -> None:
    prefixdir = prefixdir_name( **kwargs )
    echo_string( f"Chmod rx prefixdir={prefixdir}",**kwargs )
    recursive_rx(prefixdir)

def write_module_file( **kwargs: Any ) -> tuple[ list[str],list[str] ]:
    from  MrPackMod import  modulefile
    # we don't actually use the process that's created here;
    # module versions are found in a separate process_execute 
    output = start_test_stage(
        "module",
        **{ **kwargs,"linedisplay":trace_string, } )

    #
    # module contents
    #
    help_string   = modulefile.module_help_string ( **kwargs,**output )
    pkg_info      = modulefile.package_info       ( **kwargs,**output )
    path_settings = modulefile.path_settings      ( **kwargs,**output )
    system_paths  = modulefile.system_paths       ( **kwargs,**output )
    if nonnull( vars := modulefile.extra_vars( **kwargs,**output ) ):
        modvars : str = f"\n{vars}"
    else: modvars = ""
    if nonnull( depends := modulefile.dependency_clauses( **kwargs,**output ) ):
        depends = f"\n{depends}"
    else: depends = ""

    #
    # write
    #
    modulefilepath,existing = modulefile_path( **kwargs )
    _,moduleversion = module_name_and_version( **kwargs )
    # maybe create moduledir
    if not ( hasdir := os.path.isdir(modulefilepath) ):
        if existing:
            error_abort( f"Module specified as add-able, but does not exist: {modulefilepath}",**kwargs )
        else:
            echo_string( f"First ensure module dir: {modulefilepath}",**kwargs )
            # create directories recursively
            os.makedirs( modulefilepath,exist_ok=True )
    # now write
    modulefilefullname : str = f"{modulefilepath}/{moduleversion}.lua"
    echo_string( f"Writing modulefile: {modulefilefullname}" )
    with open( modulefilefullname,"w" ) as lua_out:
        modulecontents = f"""\
{help_string}

{pkg_info}

{path_settings}

{system_paths}{modvars}{depends}
"""
        trace_string( f"Module contents:\n{modulecontents}",**kwargs )
        lua_out.write( modulecontents )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return success,failure

def public_module( **kwargs: Any ) -> None:
    modulefilepath,_ = modulefile_path( **kwargs )
    trace_string( f"Chmod rx modulefilepath={modulefilepath}",**kwargs )
    recursive_rx(modulefilepath)

