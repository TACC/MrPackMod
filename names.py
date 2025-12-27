#!/usr/bin/env/python3

#
# standard python modules
#
import datetime
import os
import re
import sys

#
# my own modules
#
import names
import process
from process import echo_string,trace_string
from process import abort_on_null,abort_on_nonzero_env,abort_on_zero_env,\
    zero_keyword,nonzero_keyword,abort_on_zero_keyword
from process import error_abort,requirenonzero,nonnull

####
#### General names
####

#
# compute package name and version,
# both lowercase
# in the future we will handle the case of git pulls
# Result: pair package,version
#
def package_names( **kwargs ):
    package = kwargs.get("package").lower()
    version = kwargs.get("packageversion").lower()
    terminal = kwargs.get("terminal")
    if version == "git":
        # raise Exception( "gitdate not yet implemented" )
        today = re.sub( '-','',str(datetime.date.today()) )
        version = f"git{today}"
    echo_string( f"setting internal variables packagebasename={package} packageversion={version}",
                 terminal=terminal )
    return package,version

#
# name of a logfile
# 
def logfile_name( logstage,**kwargs ):
    scriptdir       = abort_on_zero_keyword( "scriptdir",**kwargs )
    packagename,_   = package_names( **kwargs )
    _,moduleversion = module_names( **kwargs )
    system,compiler,cversion,cshortv,mpi,mversion = family_names( **kwargs )
    logfilename = f"{scriptdir}/{logstage}_{packagename}-{moduleversion}_{compiler}-{cversion}"
    if mode := nonzero_keyword( "mode",**kwargs ):
        logfilename += f"_{mpi}-{mversion}"
    logfilename += ".log"
    return logfilename

#
# Create a directory for either building or install
#
def create_homedir( **kwargs ):
    root     = kwargs.get( "packageroot",None )
    package  = kwargs.get( "package","nullpackage" )
    homedir  = kwargs.get( "homedir",None )
    terminal = kwargs.get( "terminal",None )
    package,_ = package_names(package=package,packageversion="0.0",termminal=terminal)
    if root:
        echo_string( f"creating homedir value based on root: {root}",terminal=terminal )
        homedir = f"{root}/{package}"
    else:
        if not nonnull( homedir ): raise Exception( "need either root or homedir" )
        echo_string( f"creating homedir value based on homedir: {homedir}",terminal=terminal )
    echo_string( f"using homedir: {homedir}",terminal=terminal )
    if not os.path.isdir(homedir):
        echo_string( f"creating homedir: {homedir}",terminal=terminal )
        try:
            os.mkdir(homedir)
        except PermissionError:
            echo_string( f"ERROR: no permission to create homedir: {homedir}" )
            sys.exit(1)
    return homedir

##
## Description: compute compiler & mpi name & version
## Result: quintuple system,cname,cversion,mname,mversion
##
def family_names( **kwargs ):
    try:
        # in jail we can run without compiler loaded
        system   = nonzero_keyword("system",**kwargs)
        compiler = nonzero_keyword("compiler",**kwargs)
        cversion = nonzero_keyword("compilerversion",**kwargs)
        cshortv  = cversion
        # re.sub( r'^([^\.]*)\.([^\.]*)(\.*)?$',r'\1\2',cversion ) # DOESN'T WORK
        mpi      = nonzero_keyword("mpi",**kwargs)
        mversion = nonzero_keyword("mpiversion",**kwargs)
        return system,compiler,cversion,cshortv,mpi,mversion
    except:
        print( "Deduce running in jail" )
        return None,None,None,None,None,None

def compilers_names( **kwargs ):
    compilers = { 'CC':"unknown_cc", 'CXX':"unknown_cxx", 'FC':"unknown_fc", }
    if ( mode := kwargs.get("mode","mode_not_found") ) in [ "mpi","hybrid", ]:
        compilers["CC"] = "mpicc"; compilers["CXX"] = "mpicxx"; compilers["FC"] = "mpif90"
    elif mode in [ "seq", "omp", ]:
        compilers["CC"]  = abort_on_zero_env( "TACC_CC",**kwargs )
        compilers["CXX"] = abort_on_zero_env( "TACC_CXX",**kwargs )
        compilers["FC"]  = abort_on_zero_env( "TACC_FC",**kwargs )
    elif mode == "core":
        compilers["CC"] = "gcc"; compilers["CXX"] = "g++"; compilers["FC"] = "gfortran"
    else: raise Exception( "Unknown mode: {mode}" )
    return compilers

##
## Description: compute single system/compiler/mpi identifier
##
def environment_code( **kwargs ):
    mode = abort_on_zero_keyword( "mode",**kwargs )
    systemcode,compilercode,compilerversion,compilershortversion,mpicode,mpiversion = \
        family_names( **kwargs )
    if compilercode is None:
        # we are running in jail with only system compilers
        return systemcode
    else:
        envcode = f"{systemcode}-{compilercode}{compilerversion}"
        if mode in ["mpi","hybrid",]:
            envcode = f"{envcode}-{mpicode}{mpiversion}"
        return envcode

def systemnames():
    compilercode,compilerversion,compilershortversion,mpicode,mpiversion = family_names()
    return mpicode,mpiversion

def install_extension( **kwargs ):
    package,packageversion = package_names( **kwargs )
    envcode = abort_on_null( environment_code( **kwargs ),"environment code for install ext" )
    installext = f"{packageversion}-{envcode}"
    if nonnull( iext := kwargs.get( "installext","" ) ):
        installext = f"{installext}-{iext}"
    if nonnull( variant := kwargs.get("installvariant","") ):
        installext = f"{installext}-{variant}"
    return installext

def srcdir_local_name( **kwargs ):
    packagebasename,packageversion = package_names( **kwargs )
    return f"{packagebasename}-{packageversion}"

def srcdir_name( **kwargs ):
    homedir = create_homedir( **kwargs )
    srcdir_local = srcdir_local_name( **kwargs )
    if srcdir := nonzero_keyword( "srcpath",**kwargs ):
        return srcdir
    else: return  f"{homedir}/{srcdir_local}"

def builddir_name( **kwargs ):
    if bdir := nonzero_keyword( "builddirroot",**kwargs ):
        builddir = bdir
    elif bdir := nonzero_keyword( "packageroot",**kwargs ):
        builddir = bdir
    else:
        homedir = create_homedir( **kwargs )
        builddir = homedir
    package,packageversion = package_names( **kwargs )
    installext = install_extension( **kwargs )
    builddir += f"/{package}/build-{installext}"
    return builddir

def prefixdir_name( **kwargs ):
    package,packageversion = package_names( **kwargs )
    if nonnull( pdir:=kwargs.get("installpath","") ):
        echo_string( f"Using external prefixdir: {pdir}" )
        prefixdir = pdir
    elif nonnull( kwargs.get("noinstall","") ):
        raise Exception( f"use of NOINSTALL not implemented" )
    else:
        # path & "installation"
        if nonnull( idir:=kwargs.get("installroot","") ):
            trace_string( f"prefixdir from installroot: {idir}",**kwargs )
            prefixpath = f"{idir}"
        else: 
            hdir = create_homedir( **kwargs )
            trace_string( f"prefixdir from homedir: {hdir}",**kwargs )
            prefixpath = f"{hdir}"
        # attach package name
        prefixdir = "installation"
        if nonnull( mname:=kwargs.get("modulename","") ):
            prefixdir += f"-{mname}"
        else:
            prefixdir += f"-{package}"
        # install extension
        prefixdir += "-"+install_extension( **kwargs )
        prefixdir = f"{prefixpath}/{prefixdir}"
    if not nonnull( prefixdir ):
        raise Exception( "failed to set prefixdir" )
    if nonnull( var := kwargs.get("installvariant","") ):
        echo_string( f"using subdir for installvariant: {var}" )
        prefixdir = f"{prefixdir}/{var}"
    return prefixdir

def package_dir_names( **kwargs ):
    prefixdir = names.prefixdir_name( **kwargs )
    # lib
    if zero_keyword( "nolib",**kwargs ):
        libdir = f"{prefixdir}/lib64"
        if not os.path.isdir( libdir ):
            libdir = f"{prefixdir}/lib"
            if not os.path.isdir( libdir ):
                raise Exception( "Could not find lib or lib64 dir; maybe set NOLIB?" )
    else: libdir = ""
    # inc
    if zero_keyword( "noinc",**kwargs ):
        incdir = f"{prefixdir}/include"
        if not os.path.isdir( incdir ):
            raise Exception( "Could not find include dir, maybe set NOINC?" )
    else: incdir = ""
    # bin
    if nonzero_keyword( "hasbin",**kwargs ):
        bindir = f"{prefixdir}/bin"
        if not os.path.isdir( bindir ):
            raise Exception( "Could not find bin dir but HASBIN was specified" )
    else: bindir = ""
    return prefixdir,libdir,incdir,bindir

def modulefile_path_and_name( **kwargs ):
    abort_on_nonzero_env( "MODULEDIRSET" )
    package,packageversion = package_names( **kwargs )
    modulename,moduleversion = module_names( **kwargs )
    #
    # construct module path
    #
    if nonnull( dirset := kwargs.get("moduledir") ):
        # in jail we get an explicit path
        modulepath = dirset
        return f"{modulepath}",f"{moduleversion}.lua"
    else:
        # otherwise we build the path from system & compiler info
        modulepath = abort_on_zero_keyword( "moduleroot",**kwargs )
        if ( mode := kwargs.get("mode","mode_not_found") ) == "core":
            modulepath += f"/Core"
        else:
            # ignore system & compiler short version
            _,compilercode,compilerversion,_,mpicode,mpiversion = family_names( **kwargs )
            if mode in [ "mpi","hybrid", ]:
                modulepath += f"/MPI/{compilercode}/{compilerversion}/{mpicode}/{mpiversion}"
            elif mode in [ "seq","omp", ]:
                modulepath += f"/Compiler/{compilercode}/{compilerversion}"
            else: error_abort( f"Unknown mode: {mode}" )
        return f"{modulepath}/{modulename}",f"{moduleversion}.lua"

def module_names( **kwargs):
    package,packageversion = package_names( **kwargs )
    modulename = kwargs.get( "modulename",package )
    if alt := nonzero_keyword( "modulenamealt" ):
        modulename = alt
    moduleversion = packageversion
    if nonnull( mx := kwargs.get("moduleversionextra") ):
        moduleversion += f"-{mx}"
    return modulename,moduleversion
