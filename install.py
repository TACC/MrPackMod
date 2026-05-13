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

from MrPackMod.basics  import remove_macros
from MrPackMod.error   import error_abort, abort_on_zero_env, nonnull,\
    nonzero_keyword, zero_keyword, abort_on_zero_keyword
from MrPackMod.names import logfile_name,srcdir_name,builddir_name,prefixdir_name,\
    compilers_names,modulefile_path_and_name
from MrPackMod.process import process_execute, process_initiate, process_terminate,\
    process_execute_immediate,remove_macros
from MrPackMod.process import open_logfile,close_logfile,get_value_from_loaded
from MrPackMod.tracing import echo_string, trace_string
from MrPackMod.testing import start_test_stage,end_test_stage

def export_compilers_script( dummy : list[str],**kwargs: Any ) -> tuple[str,str]:
    echo_string( "Exporting compilers",**kwargs )
    compilers = compilers_names( **kwargs )
    script = ""; cont = ""
    for key,val in compilers.items():
        echo_string( f" .. Setting compiler: {key}={val}",**kwargs )
        which = process_execute_immediate( f"""
which {val}
if [ $? -gt 0 ] ; then
  echo FAILURE determining location of {val}
fi
        """,**kwargs, )
        if not re.match( "FAILURE",which ):
            echo_string( f"    where {val}={which}",**kwargs )
            if ( mpi := kwargs.get("MODE") ) == "mpi":
                info = process_execute( f"{which} -show",**kwargs )
                echo_string( f"    which is:\n    {info}",**kwargs )
            script += f"{cont}export {key}={val}"
            cont = " && "
    return script,"Compiler settings"

def compilers_flags( **kwargs: Any ) -> dict[str, str]:
    flags = { 'CFLAGS':"", 'CXXFLAGS':"", 'FFLAGS':"", }
    if cflags := nonzero_keyword( "cflags",**kwargs ):
        flags["CFLAGS"] = cflags
    if cxxflags := nonzero_keyword( "cxxflags",**kwargs ):
        flags["CCXXFLAGS"] = cxxflags
    if fflags := nonzero_keyword( "fflags",**kwargs ):
        flags["FFLAGS"] = fflags
    return flags

def export_flags( **kwargs: Any ) -> str:
    flags = compilers_flags( **kwargs )
    cmdline = ""; cont = ""
    for lang in [ "CFLAGS", "CXXFLAGS", "FFLAGS", ]:
        if nonnull( flag := flags[lang] ):
            cmdline += f"{cont}export {lang}=\"{flag}\""
            cont = " && "
    return cmdline

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

################################################################
####
#### CMake
####
################################################################

def cmake_basic_command( **kwargs : Any ) -> str:
    cmake : str = kwargs.get( "CMAKENAME","cmake" )
    if nonzero_keyword( "CMAKEUSENINJA",**kwargs ):
        cmake = f"{cmake} -G Ninja"
    return f"TERM=dumb {cmake} -Wno-dev \
-D CMAKE_COMPILE_WARNING_AS_ERROR=OFF \
-D CMAKE_POLICY_VERSION_MINIMUM=3.13 \
-D CMAKE_VERBOSE_MAKEFILE=ON \
-D CMAKE_COLOR_MAKEFILE=OFF \
-D CMAKE_TERM_SUPPORTS_ANSI=OFF"

def cmake_options( **kwargs: Any ) -> str:
    cmakeflags = "-D CMAKE_VERBOSE_MAKEFILE=ON -D CMAKE_EXPORT_COMPILE_COMMANDS=ON"
    if standard := kwargs.get("CPPSTANDARD"):
        cmakeflags += f" -D CMAKE_CXX_FLAGS=-std=c++{standard}"
    if flags := nonzero_keyword( "CMAKEFLAGS",**kwargs ):
        cmakeflags += f" {flags}"
    return cmakeflags.lstrip(" ")

def cmake_build_settings( **kwargs ) -> str:
    if kwargs.get("CMAKEBUILDDEBUG"):
        defaultbuild = "Debug"
    else: defaultbuild = "RelWithDebInfo"
    cmakebuildtype = kwargs.get("CMAKEBUILDTYPE",defaultbuild)
    if static := kwargs.get("buildstaticlibs"):
        buildsharedlibs = "OFF"
    else: buildsharedlibs = "ON"
    return f"-D BUILD_SHARED_LIBS={buildsharedlibs} -D CMAKE_BUILD_TYPE={cmakebuildtype}"

def cmake_paths_settings( cmakedirs : list[str],**kwargs ) -> str:
    srcdir,builddir,prefixdir = cmakedirs
    if nonnull( source := kwargs.get("CMAKESUBDIR") ):
        effsrcdir : str = f"{srcdir}/{source}"
    else: effsrcdir = srcdir
    settingsfile : str = f"{effsrcdir}/CMakeLists.txt"
    if not os.path.exists( f"{settingsfile}" ):
        error_abort( f"Can not find cmake settings file: {settingsfile}",**kwargs )
    cmakepathsetting : str = f"-S {effsrcdir} -B {builddir}"
    if nonnull(prefixdir):
        cmakepathsetting += f" -D CMAKE_INSTALL_PREFIX={prefixdir}"
    return cmakepathsetting

##
## CMake commandline with all options
## `pcmakedirs' is [program,src,build,prefix]
## where `program' is only nonnull for regression testing
##
def cmake_configure_script( pcmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program = pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    script : str = ""
    # setup
    if exports := nonzero_keyword( "exports",**kwargs ):
        export_cmdline : str = " && ".join(exports)
        echo_string( f"Using exports: {export_cmdline}",**kwargs )
        script += f"\n{export_cmdline}"
    compilers_export,_ = export_compilers_script( [],**kwargs )
    trace_string( f"Using compilers: {compilers_export}",**kwargs )
    script += f"\n{compilers_export}"
    # cmake
    cmake = cmake_basic_command( **kwargs )
    cmakeflags = cmake_options( **kwargs )
    buildsettings = cmake_build_settings( **kwargs )
    # set src, build, prefix
    pathsettings = cmake_paths_settings( cmakedirs,**kwargs )
    # for the regression case only: define project macro
    if nonnull(program) : pathsettings += f" -D PROJECTNAME={program}"
    script += f"""
{cmake} \
{buildsettings} \
{cmakeflags} \
{pathsettings}
if [ $? -eq 0 ] ; then
    echo SUCCESS: configure succeeded
else
    echo FAILURE: cmake failed
fi
    """
    return script,"CMake configuring"

def cmake_configure( **kwargs: Any ) -> str:
    output : OutputDict = \
        start_test_stage( "configure",kwargs,title="cmake configure",installing=True )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : str = get_value_from_loaded(
        cmake_configure_script,["",srcdir,builddir,prefixdir],**kwargs,**output, )
    success,failure = end_test_stage( [],[],kwargs,output )
    return retval

def cmake_build_script( pcmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program = pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir,builddir,prefixdir = cmakedirs
    # flags and options
    jcount          : str = kwargs.get("jcount","6")
    make            : str = f"make --no-print-directory V=1 VERBOSE=1 -j {jcount}"
    makebuildtarget : str = kwargs.get("makebuildtarget","")
    # execute make & make install
    echo_string( f"Making in builddir: {builddir}",**kwargs )
    if ninja := kwargs.get( "CMAKEUSENINJA" ):
        makeline = f"ninja install"
    else:
        makeline = f"{make} --no-print-directory V=1 VERBOSE=1 -j {jcount} {makebuildtarget}"
    script : str = f"""
cd {builddir}
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
    return script,"CMake make and install"

def cmake_build( **kwargs: Any ) -> str:
    if nonzero_keyword("noinstall",**kwargs):
        return "No installation needed"
    output : OutputDict = \
        start_test_stage( "build",kwargs,title="cmake build",installing=True )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=False )
    retval : str = get_value_from_loaded(
        cmake_build_script,["",srcdir,builddir,prefixdir],**kwargs,**output )
    success,failure = end_test_stage( [],[],kwargs,output )
    return retval

################################################################
####
#### Autotools
####
################################################################

def autotools_configure_script( pmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program,srcdir,builddir,prefixdir = pmakedirs
    # setup
    compilers_export,_ = export_compilers_script( [],**kwargs )
    trace_string( f"Using compilers: {compilers_export}",**kwargs )
    flags_export : str = export_flags( **kwargs )
    trace_string( f"Using flags: {flags_export}",**kwargs )
    script : str = f"""
cd {srcdir}
{compilers_export}
{flags_export}
    """
    if before := nonzero_keyword( "BEFORECONFIGURECMDS",**kwargs ):
        script += f"\n{before}\n"

    ##
    ## go to the right location for configure
    ##
    if nonzero_keyword( "CONFIGINBUILDDIR",**kwargs ):
        trace_string( " .. going to configure in build dir",**kwargs )
        configloc : str = builddir
        config_cmdline : str = f"{srcdir}/configure"
    elif subdir := nonzero_keyword( "CONFIGURESUBDIR",**kwargs ):
        trace_string( f" .. going to configure in subdir: {subdir}.",**kwargs )
        configloc = subdir
        config_cmdline = f"./configure"
    else:
        configloc = "."
        config_cmdline = f"./configure"
    config_loc_script : str = f"""
if [ -f \"{configloc}/configure\" ] ; then
  has_configure=1 ; else has_configure= ; fi
if [ -f \"{configloc}/autogen.sh\" ] ; then
  has_autogen=1 ; else has_autogen= ; fi
if [ -f \"{configloc}/configure.ac\" ] ; then
  has_ac=1 ; else has_ac= ; fi
cd {configloc}
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
  elif [ ! -z \"has_autogen\" ] ; then 
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
        flags : str = f" {flags}"
    else: flags = ""
    configure_script : str = f"""
./configure {prefixoption}={prefixdir} --libdir={prefixdir}/lib {flags}
    """
    return config_loc_script+reconf_script+configure_script,"Autotools configuring"

    
def autotools_configure( **kwargs : Any ) -> str:
    output : OutputDict = \
        start_test_stage( "configure",kwargs,title="autotools configure",installing=True )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : str = get_value_from_loaded(
        autotools_configure_script,["",srcdir,builddir,prefixdir],**kwargs,**output, )
    success,failure = end_test_stage( [],[],kwargs,output )
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
def autotools_build( **kwargs: Any ) -> None:
    logfilename,_,_ = open_logfile( "install",kwargs ) # note dict!
    #
    # setup directories
    #
    srcdir    = srcdir_name( **kwargs )
    builddir  = builddir_name( **kwargs )
    prefixdir = prefixdir_name( **kwargs )
    if nonzero_keyword("NOINSTALL"):
        return
    if subdir := nonzero_keyword("MAKESUBDIR",**kwargs):
        os.chdir(subdir)
    else:
        os.chdir(srcdir)
    echo_string( f"Building and installing in {os.getcwd()}" )
    #
    # Make
    #
    jval = kwargs.get("jcount",6)
    makecommand = f"make --no-print-directory -j {jval}"
    echo_string( f"Making default target with: {makecommand}",**kwargs )
    process_execute( makecommand,**kwargs )
    if extra := nonzero_keyword( "EXTRABUILDTARGETS",**kwargs ):
        echo_string( f" .. making extra targets: {extra}",**kwargs )
        process_execute( f"{makecommand} {extra}",**kwargs )
    #
    # install
    #
    extra = kwargs.get( "EXTRAINSTALLTARGET","" )
    cmdline = f"make --no-print-directory install {extra}"
    process_execute( cmdline,**kwargs )
    if cptoinstall := nonzero_keyword( "CPTOINSTALLDIR",**kwargs ):
        echo_string( f"Extra installs: {cptoinstall}",**kwargs )
        process_execute( f"cp -r {cptoinstall} {prefixdir}",**kwargs )
    close_logfile( logfilename,kwargs )

################################################################
####
#### Make
####
################################################################

def make_configure_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    script : str = ""
    if premake := nonzero_keyword( "PREMAKE",**kwargs ):
        premake = remove_macros( premake,kwargs )
        trace_string( f"Using premake: {premake}",**kwargs )
        script += f"\n{premake}\n"
    return script,"Make setup"

def make_configure( **kwargs : Any ) -> str:
    output : OutputDict = \
        start_test_stage( "configure",kwargs,title="make configure",installing=True )
    srcdir,builddir,prefixdir = configure_prep( **kwargs,scratch=True )
    retval : str = get_value_from_loaded(
        make_configure_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],kwargs,output )
    return retval

def make_build_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    srcdir  : str = srcdir_name( **kwargs )
    jcount  : str = kwargs.get("jcount",6)
    targets : str = kwargs.get( "MAKETARGETS","" )
    script = f"""
cd {srcdir}
make -j {jcount} {targets}
    """
    return script,"Make build"

def make_build( **kwargs : Any ) -> str:
    output : OutputDict = \
        start_test_stage( "build",kwargs,title="make build",installing=True )
    retval : str = get_value_from_loaded(
        make_build_script,[],**kwargs,**output )
    success,failure = end_test_stage( [],[],kwargs,output )
    return retval

################################################################
####
#### Post-install stuff
####
################################################################


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
    output = start_test_stage( "module",kwargs,linedisplay=trace_string,installing=True )

    #
    # module contents
    #
    help_string   = modulefile.module_help_string ( **kwargs,**output )
    pkg_info      = modulefile.package_info       ( **kwargs,**output )
    path_settings = modulefile.path_settings      ( **kwargs,**output )
    system_paths  = modulefile.system_paths       ( **kwargs,**output )
    if nonnull( depends := modulefile.dependency_clauses( **kwargs,**output ) ):
        depends = f"\n{depends}"

    #
    # write
    #
    modulefilepath,luaversion = modulefile_path_and_name( **kwargs )
    if not os.path.isdir(modulefilepath):
        echo_string( f"First create module dir: {modulefilepath}",**kwargs )
        # create directories recursively
        os.makedirs( modulefilepath,exist_ok=True )
        # too limited os.mkdir( modulefilepath )
    echo_string( f"Writing modulefile: {modulefilepath}/{luaversion}" )
    with open( f"{modulefilepath}/{luaversion}","w" ) as lua_out:
        modulecontents = f"""\
{help_string}

{pkg_info}

{path_settings}

{system_paths}{depends}
"""
        trace_string( f"Module contents:\n{modulecontents}",**kwargs )
        lua_out.write( modulecontents )
    success,failure = end_test_stage( [],[],kwargs,output )
    return success,failure

def public_module( **kwargs: Any ) -> None:
    modulefilepath,_ = modulefile_path_and_name( **kwargs )
    trace_string( f"Chmod rx modulefilepath={modulefilepath}",**kwargs )
    recursive_rx(modulefilepath)

