#!/usr/bin/env/python3

#
# standard python modules
#
import datetime
import os
import re
import shutil

#
# my own modules
#
import modules
import names
import process
from process import process_execute, process_initiate, process_terminate
from process import echo_string, trace_string, error_abort, abort_on_zero_env
from process import nonnull, nonzero_keyword, zero_keyword, abort_on_zero_keyword

def export_compilers( **kwargs ):
    compilers = names.compilers_names( **kwargs )
    cmdline = ""; cont = ""
    for key,val in compilers.items():
        echo_string( f"Setting compiler: {key}={val}",**kwargs )
        which = process_execute( f"which {val}",**kwargs,terminal=None )
        echo_string( f" .. where {val}={which}",**kwargs )
        if ( mpi := kwargs.get("MODE") ) == "mpi":
            info = process_execute( f"{which} -show",**kwargs,terminal=None )
            echo_string( f" .. which is:\n    {info}",**kwargs )
        cmdline += f"{cont}export {key}={val}"
        cont = " && "
    return cmdline

def compilers_flags( **kwargs ):
    flags = { 'CFLAGS':"", 'CXXFLAGS':"", 'FFLAGS':"", }
    if cflags := nonzero_keyword( "cflags",**kwargs ):
        flags["CFLAGS"] = cflags
    if cxxflags := nonzero_keyword( "cxxflags",**kwargs ):
        flags["CCXXFLAGS"] = cxxflags
    if fflags := nonzero_keyword( "fflags",**kwargs ):
        flags["FFLAGS"] = fflags
    return flags

def export_flags( **kwargs ):
    flags = compilers_flags( **kwargs )
    cmdline = ""; cont = ""
    for lang in [ "CFLAGS", "CXXFLAGS", "FFLAGS", ]:
        if nonnull( flag := flags[lang] ):
            cmdline += f"{cont}export {lang}=\"{flag}\""
            cont = " && "
    return cmdline

def open_logfile( logstage,kwargs ):
    # get global name, ignore local name
    logfile,_ = names.logfile_name( logstage,**kwargs )
    loghandle = open( logfile,"w" )
    kwargs["logfiles"][logfile] = loghandle
    trace_string( f"Open logfile {logfile}",**kwargs )
    loghandle.write( f"""================
Logstage {logstage} started {datetime.date.today()}
================\n""" )
    return logfile,loghandle

def close_logfile( logname,loghandle,kwargs ):
    kwargs["logfiles"].pop(logname)
    loghandle.close()
    
def configure_prep( **kwargs ):
    modules.test_modules( **kwargs )
    #
    # setup directories
    #
    srcdir    = names.srcdir_name( **kwargs )
    builddir  = names.builddir_name( **kwargs )
    prefixdir = names.prefixdir_name( **kwargs )
    #print(srcdir,builddir,prefixdir)
    try:
        shutil.rmtree(builddir)
    except FileNotFoundError: pass
    os.makedirs(builddir,exist_ok=True)
    return srcdir,builddir,prefixdir

def cmake_configure( **kwargs ):
    tracing = kwargs.get( "tracing" )
    logfilename,logfilehandle = open_logfile( "configure",kwargs ) # note dict!
    srcdir,builddir,prefixdir = configure_prep( **kwargs )
    #
    # flags
    #
    cmakeflags = ""; cmakeflagsplatform = ""; exports = ""
    if standard := kwargs.get("CPPSTANDARD"):
        cmakeflags += f" -D CMAKE_CXX_FLAGS=-std=c++{standard}"
    if flags := nonzero_keyword( "CMAKEFLAGS",**kwargs ):
        cmakeflags += f" {flags}"
    cmake = kwargs.get( "CMAKENAME","cmake" )
    if nonzero_keyword( "CMAKEUSENINJA",**kwargs ):
        cmake = f"{cmake} -G Ninja"
    if kwargs.get("CMAKEBUILDDEBUG"):
        defaultbuild = "Debug"
    else: defaultbuild = "RelWithDebInfo"
    cmakebuildtype = kwargs.get("CMAKEBUILDTYPE",defaultbuild)
    if static := kwargs.get("buildstaticlibs"):
        buildsharedlibs = "OFF"
    else: buildsharedlibs = "ON"
    if nonnull( source := kwargs.get("CMAKESUBDIR") ):
        cmakesourcesetting = f"-S {srcdir}/{source} -B {builddir}"
        settingsfile = f"{srcdir}/{source}/CMakeLists.txt"
    else:
        cmakesourcesetting = f"{srcdir}"
        settingsfile = f"{cmakesourcesetting}/CMakeLists.txt"
    if not os.path.exists( f"{settingsfile}" ):
        error_abort( f"Can not find file: {settingsfile}",**kwargs )
    
    #
    # execute cmake
    #
    echo_string( f"Cmake configuring in {builddir}" )
    os.chdir( builddir )
    shell = process_initiate( **kwargs )
    compilers_export = export_compilers( **kwargs )
    if exports := nonzero_keyword( "exports",**kwargs ):
        export_cmdline = " && ".join(exports)
        process_execute( export_cmdline,**kwargs,process=shell )
    process_execute( compilers_export,**kwargs,process=shell )
    # --no-warn-unused-cli ?
    cmdline = f"TERM=dumb {cmake} -D CMAKE_INSTALL_PREFIX={prefixdir} \
-D CMAKE_COMPILE_WARNING_AS_ERROR=OFF \
-D CMAKE_POLICY_VERSION_MINIMUM=3.13 \
-D CMAKE_VERBOSE_MAKEFILE=ON \
-D CMAKE_COLOR_MAKEFILE=OFF \
-D CMAKE_TERM_SUPPORTS_ANSI=OFF \
-D BUILD_SHARED_LIBS={buildsharedlibs} \
-D CMAKE_BUILD_TYPE={cmakebuildtype} \
{cmakeflags} {cmakeflagsplatform} \
{cmakesourcesetting} \
"
    process_execute( cmdline,**kwargs,process=shell )
    process_terminate( shell,**kwargs )
    close_logfile( logfilename,logfilehandle,kwargs )

def cmake_build( **kwargs ):
    logfilename,logfilehandle = open_logfile( "install",kwargs ) # note dict!
    #
    # setup directories
    #
    srcdir    = names.srcdir_name( **kwargs )
    builddir  = names.builddir_name( **kwargs )
    prefixdir = names.prefixdir_name( **kwargs )
    #
    # flags and options
    #
    makebuildtarget = kwargs.get("makebuildtarget","")
    jcount          = kwargs.get("jcount","6")
    #
    # execute make & make install
    make = f"make --no-print-directory V=1 VERBOSE=1 -j {jcount}"
    if nonzero_keyword("noinstall"):
        return
    echo_string( f"Making in builddir: {builddir}",**kwargs )
    if not os.path.isdir(builddir):
        raise Exception( f"Invalid builddir: {builddir}",**kwargs )
    os.chdir( builddir )
    cmdline = f"{make} {makebuildtarget}"
    process_execute( cmdline,**kwargs )
    if extra_targets := nonzero_keyword( "extrabuildtargets" ):
        cmdline = f"{make} {extra_targets}"
        process_execute( cmdline )
    cmdline = f"{make} install"
    process_execute( cmdline,**kwargs )
    if extra_targets := nonzero_keyword( "extrainstalltargets" ):
        cmdline = f"{make} {extra_targets}"
        process_execute( cmdline )
    close_logfile( logfilename,logfilehandle,kwargs )

def autotools_configure( **kwargs ):
    logfilename,logfilehandle = open_logfile( "configure",kwargs ) # note dict!
    srcdir,builddir,prefixdir = configure_prep( **kwargs )
    #
    # execute configure
    #
    os.chdir(srcdir)
    shell = process_initiate( **kwargs )
    compilers_export = export_compilers( **kwargs )
    process_execute( compilers_export,**kwargs,process=shell )
    flags_export = export_flags( **kwargs )
    process_execute( flags_export,**kwargs,process=shell )
    if before := nonzero_keyword( "BEFORECONFIGURECMDS",**kwargs ):
        process_execute( before,**kwargs,process=shell )
    ##
    ## go to the right location
    ##
    if nonzero_keyword( "CONFIGINBUILDDIR",**kwargs ):
        trace_string( " .. going to configure in build dir",**kwargs )
        has_configure = os.path.exists( f"{builddir}/configure" )
        has_autogen = os.path.exists( f"{builddir}/autogen.sh" )
        has_ac = os.path.exists( f"{builddir}/configure.ac" )
        os.chdir(builddir) # needed for gcc
        cmdline = f"{srcdir}/configure"
    elif subdir := nonzero_keyword( "CONFIGURESUBDIR",**kwargs ):
        trace_string( f" .. going to configure in subdir: {subdir}.",**kwargs )
        has_configure = os.path.exists( f"{subdir}/configure" )
        has_autogen = os.path.exists( f"{subdir}/autogen.sh" )
        has_ac = os.path.exists( f"{subdir}/configure.ac" )
        process_execute( f"cd {subdir}",**kwargs,process=shell )
        # os.chdir(subdir) # needed for taccstats
        cmdline = f"./configure"
    else:
        has_configure = os.path.exists( f"configure" )
        has_autogen = os.path.exists( f"autogen.sh" )
        has_ac = os.path.exists( f"configure.ac" )
        cmdline = f"./configure"
    ##
    ## do stuff before configure
    ##
    if not has_configure or nonzero_keyword( "FORCERECONF",**kwargs ):
        if has_ac: 
            if nonzero_keyword( "DEFUNPROGFC",**kwargs ):
                process_execute( "sed -i configure.ac -e \'/AC_INIT/aAC_DEFUN([_AC_PROG_FC_V],[])\'",
                                 **kwargs,process=shell )
            if reconf := nonzero_keyword( "AUTORECONF",**kwargs ): # when does this happen?
                cmdline = f"{reconf} -i"
            else:
                cmdline = f"aclocal && autoconf"
        elif has_autogen:
            cmdline = "./autogen.sh"
        else:
            raise Exception( "Need configure.ac or autogen.sh to generate configure script" )
        process_execute( cmdline,**kwargs,process=shell )
    ##
    ## do configure
    if option := nonzero_keyword( "PREFIXOPTION",**kwargs ):
        prefixoption = option # pdtoolkit
    else: prefixoption = "--prefix"
    cmdline = f"./configure {prefixoption}={prefixdir} --libdir={prefixdir}/lib"
    if flags := nonzero_keyword( "CONFIGUREFLAGS",**kwargs ):
        cmdline += f" {flags}"
    process_execute( cmdline,**kwargs,process=shell )
    process_terminate( shell,**kwargs )
    close_logfile( logfilename,logfilehandle,kwargs )
    
def autotools_build( **kwargs ):
    logfilename,logfilehandle = open_logfile( "install",kwargs ) # note dict!
    #
    # setup directories
    #
    srcdir    = names.srcdir_name( **kwargs )
    builddir  = names.builddir_name( **kwargs )
    prefixdir = names.prefixdir_name( **kwargs )
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
    close_logfile( logfilename,logfilehandle,kwargs )

import os
import stat

def recursive_rx( path ):
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

def public_installation( **kwargs ):
    prefixdir = names.prefixdir_name( **kwargs )
    trace_string( f"Chmod rx prefixdir={prefixdir}",**kwargs )
    recursive_rx(prefixdir)

def write_module_file( **kwargs ):
    tracing = kwargs.get("tracing")
    logfilename,logfilehandle = open_logfile( "module",kwargs ) # note dict!

    #
    # module contents
    #
    help_string   = modules.module_help_string ( **kwargs )
    pkg_info      = modules.package_info       ( **kwargs )
    path_settings = modules.path_settings      ( **kwargs )
    system_paths  = modules.system_paths       ( **kwargs )
    if nonnull( depends := modules.dependencies( **kwargs ) ):
        depends = f"\n{depends}"

    #
    # write
    #
    modulefilepath,luaversion = names.modulefile_path_and_name( **kwargs )
    if not os.path.isdir(modulefilepath):
        echo_string( f"First create module dir: {modulefilepath}",**kwargs )
        # create directories recursively
        os.makedirs( modulefilepath,exist_ok=True )
        # too limited os.mkdir( modulefilepath )
    echo_string( f"Writing modulefile: {modulefilepath}/{luaversion}" )
    with open( f"{modulefilepath}/{luaversion}","w" ) as modulefile:
        modulecontents = f"""\
{help_string}

{pkg_info}

{path_settings}

{system_paths}{depends}
"""
        if tracing:
            echo_string( f"Module contents:\n{modulecontents}",**kwargs )
        modulefile.write( modulecontents )
    close_logfile( logfilename,logfilehandle,kwargs )

def public_module( **kwargs ):
    modulefilepath,_ = names.modulefile_path_and_name( **kwargs )
    trace_string( f"Chmod rx modulefilepath={modulefilepath}",**kwargs )
    recursive_rx(modulefilepath)

