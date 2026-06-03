#!/usr/bin/env/python3

#
# standard python modules
#
import datetime
import os
import re
import sys
from typing import Any, Optional, Union, cast

#
# my own modules
#
from MrPackMod.basics  import nonnull,isnull,\
    zero_keyword,nonzero_keyword,abort_on_zero_keyword,error_abort,\
    echo_string,trace_string
from MrPackMod.error import abort_on_null,abort_on_nonzero_env,abort_on_zero_env    

####
#### General names
####

#
# compute package name and version,
# both lowercase
# in the future we will handle the case of git pulls
# Result: pair package,version
# version can be null-string if we are using the default
#
def package_names( **kwargs: Any ) -> tuple[str, str]:
    package : str = nonzero_keyword( "PACKAGE",**kwargs)
    # when do we allow null versions
    version = nonzero_keyword( "PACKAGEVERSION",**kwargs )
    return package,version

def package_names_nonnull( **kwargs: Any ) -> tuple[str, str]:
    p,v = package_names( **kwargs )
    abort_on_null( v,"package version is null/unspecified",**kwargs )
    return p,v

def package_prerequisites( **kwargs : Any ) -> str:
    return kwargs.get( "MODULES","" )

#
# name of a logfile
# the "logstage" typically contains the package name
# 
def logfile_name(
        logstage : str, **kwargs : Any, ) -> tuple[str, str,str]:
    scriptsdir : str = scriptsdir_name( **kwargs )
    
    _,moduleversion = module_names( **kwargs )
    system,compiler,cversion,cshortv,mpi,mversion = family_names( **kwargs )
    logfileshortname : str = f"{logstage}-{moduleversion}"
    if nonnull(compiler):
        logfileshortname += f"_{compiler}-{cversion}"
    if mode := nonzero_keyword( "MODE",**kwargs ):
        logfileshortname += f"_{mpi}-{mversion}"
    logfileshortname += ".log"
    logfilename = f"{scriptsdir}/{logfileshortname}"
    return logfilename,logfileshortname,scriptsdir

def scriptsdir_name( **kwargs : Any ) -> str:
    if scriptsdir := nonzero_keyword( "scriptsdir",**kwargs ):
        return scriptsdir
    else:
        scriptroot : str = scriptsdir_root( **kwargs )
        scriptdir  : str = scriptsdir_local( **kwargs )
        return f"{scriptroot}/{scriptdir}"

def scriptsdir_root( **kwargs : Any ) -> str:
        if bdir := nonzero_keyword( "builddirroot",**kwargs ):
            scriptroot : str =  bdir
        elif startdir := nonzero_keyword( "startdir",**kwargs ):
            scriptroot : str = startdir
        else: # this should 
            raise Exception( f"should have startdir or builddirroot for scripts" )
        if not os.access( scriptroot,os.W_OK ):
            raise Exception( f"scrptroot {scriptroot} not writable" )
        return scriptroot

def scriptsdir_local( **kwargs : Any ) -> str:
    local : str = "mpmscripts"
    if ext := nonzero_keyword( "SCRIPTSDIREXTRA",**kwargs ):
        local += f"-{ext}"
    return local
#
# Create a directory for either building or install
#
def create_homedir( **kwargs: Any ) -> str:
    root     = kwargs.get( "packageroot",None )
    package  = kwargs.get( "package","nullpackage" )
    homedir  = kwargs.get( "homedir",None )
    package,_ = package_names( **kwargs )
    if root:
        trace_string( f"homedir value based on root: {root}",**kwargs )
        homedir = f"{root}/{package}"
    else:
        if not nonnull( homedir ): raise Exception( "need either root or homedir" )
        trace_string( f"homedir value based on homedir: {homedir}",**kwargs )
    homedir_final: str = cast(str, homedir)
    trace_string( f"using homedir: {homedir_final}",**kwargs )
    if not os.path.isdir(homedir_final):
        echo_string( f"creating homedir: {homedir_final}",**kwargs )
        try:
            os.mkdir(homedir_final)
        except PermissionError:
            error_abort( f"No permission to create homedir: {homedir_final}",**kwargs )
    return homedir_final

##
## Description: compute compiler & mpi name & version
## Result: quintuple system,cname,cversion,mname,mversion
##
def family_names( **kwargs: Any ) -> Union[
    tuple[str, str, str, str, str, str],
    tuple[None, None, None, None, None, None],
    ]:
    system   = nonzero_keyword("SYSTEM",**kwargs)
    compiler = kwargs.get("COMPILER")
    cversion = kwargs.get("COMPILERVERSION")
    cshortv  = cversion
    # re.sub( r'^([^\.]*)\.([^\.]*)(\.*)?$',r'\1\2',cversion ) # DOESN'T WORK
    mpi      = kwargs.get("MPI")
    mversion = kwargs.get("MPIVERSION")
    return system,compiler,cversion,cshortv,mpi,mversion

def mode_has_mpi( **kwargs ) -> bool:
    has : str = abort_on_zero_keyword( "MODE",**kwargs )
    return has in [ "mpi","hybrid", ]

def mode_has_seq( **kwargs ) -> bool:
    has : str = abort_on_zero_keyword( "MODE",**kwargs )
    return has in [ "seq", "omp", ]

def mode_is_core( **kwargs ) -> bool:
    has : str = abort_on_zero_keyword( "MODE",**kwargs )
    return has == "core"

def compilers_names( **kwargs: Any ) -> dict[str, str]:
    compilers = { 'CC':"unknown_cc", 'CXX':"unknown_cxx", 'FC':"unknown_fc", }
    if mode_has_mpi( **kwargs ):
        compilers["CC"] = "mpicc"; compilers["CXX"] = "mpicxx"; compilers["FC"] = "mpif90"
    elif mode_has_seq( **kwargs ):
        compilers["CC"]  = abort_on_zero_env( "TACC_CC",**kwargs )
        compilers["CXX"] = abort_on_zero_env( "TACC_CXX",**kwargs )
        compilers["FC"]  = abort_on_zero_env( "TACC_FC",**kwargs )
    elif ( mode := abort_on_zero_keyword( "MODE",**kwargs ) )  == "core":
        compilers["CC"] = "gcc"; compilers["CXX"] = "g++"; compilers["FC"] = "gfortran"
    else: raise Exception( f"Unknown mode: {mode}" )
    return compilers

##
## Description: compute single system/compiler/mpi identifier
##
def environment_code( **kwargs: Any ) -> Optional[str]:
    mode = abort_on_zero_keyword( "MODE",**kwargs )
    systemcode,compilercode,compilerversion,compilershortversion,mpicode,mpiversion = \
        family_names( **kwargs )
    if isnull(compilercode):
        # we are running in jail with only system compilers
        return systemcode
    else:
        envcode = f"{systemcode}-{compilercode}{compilerversion}"
        if mode_has_mpi(**kwargs):
            envcode = f"{envcode}-{mpicode}{mpiversion}"
        return envcode

def systemnames() -> tuple[Optional[str], Optional[str]]:
    _s, _cc, _cv, _csv, mpicode, mpiversion = family_names()
    return mpicode, mpiversion

def install_extension( **kwargs: Any ) -> str:
    package,packageversion = package_names_nonnull( **kwargs )
    envcode = abort_on_null( environment_code( **kwargs ),"environment code for install ext" )
    installext = f"{packageversion}-{envcode}"
    if nonnull( iext := kwargs.get( "INSTALLEXT","" ) ):
        installext = f"{installext}-{iext}"
    if nonnull( variant := kwargs.get("INSTALLVARIANT","") ):
        installext = f"{installext}-{variant}"
    return installext

def srcdir_local_name( **kwargs: Any ) -> str:
    packagebasename,packageversion = package_names_nonnull( **kwargs )
    return f"{packagebasename}-{packageversion}"

def gitdir_local_name( **kwargs: Any ) -> str:
    packagebasename,_ = package_names( **kwargs )
    packageversion : str = "git"
    if stamp := nonzero_keyword( "GITDATE",**kwargs):
        if stamp=="today":
            packageversion += str( datetime.date.today() ).replace('-','')
        else:
            packageversion += stamp
    return f"{packagebasename}-{packageversion}"

##
## Name of source directory,
## not needed in cases such as regression
##
def srcdir_name( **kwargs: Any ) -> str:
    if nocreate := kwargs.get( "no_home" ):
        return "NO_HOME_DIR"
    else:
        homedir = create_homedir( **kwargs )
        srcdir_local = srcdir_local_name( **kwargs )
        if srcdir := nonzero_keyword( "srcpath",**kwargs ):
            return srcdir
        else: return  f"{homedir}/{srcdir_local}"

def builddir_name( **kwargs: Any ) -> str:
    if bdir := nonzero_keyword( "builddirroot",**kwargs ):
        builddir = bdir
    elif bdir := nonzero_keyword( "packageroot",**kwargs ):
        builddir = bdir
    else:
        homedir = create_homedir( **kwargs )
        builddir = homedir
    package,_ = package_names( **kwargs )
    installext = install_extension( **kwargs )
    builddir += f"/{package}/build-{installext}"
    return builddir

def prefixdir_name( **kwargs: Any ) -> str:
    package,_ = package_names( **kwargs )
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

def package_dir_names( **kwargs: Any ) -> tuple[str, str, str, str]:
    prefixdir = prefixdir_name( **kwargs )
    # lib
    if zero_keyword( "NOLIB",**kwargs ):
        libdir = f"{prefixdir}/lib64"
        if not os.path.isdir( libdir ):
            libdir = f"{prefixdir}/lib"
            if not os.path.isdir( libdir ):
                raise Exception( f"Could not find lib or lib64 dir in prefix={prefixdir}; maybe set NOLIB?" )
    else: libdir = ""
    # inc
    if zero_keyword( "NOINC",**kwargs ):
        if custom := nonzero_keyword( "INCLUDELOC",**kwargs ):
            incdir = f"{prefixdir}/{custom}"
        else:
            incdir = f"{prefixdir}/include"
        if not os.path.isdir( incdir ):
            raise Exception( f"Could not find include dir in prefix={prefixdir}, maybe set NOINC?" )
    else: incdir = ""
    # bin
    if nonzero_keyword( "HASBIN",**kwargs ):
        bindir = f"{prefixdir}/bin"
        if not os.path.isdir( bindir ):
            raise Exception( f"Could not find bin dir in prefix={prefixdir} but HASBIN was specified" )
    else: bindir = ""
    return prefixdir,libdir,incdir,bindir

def modulefile_path_and_name( **kwargs: Any ) -> tuple[str, str,Any]:
    abort_on_nonzero_env( "MODULEDIRSET" )
    package,packageversion = package_names_nonnull( **kwargs )
    modulename,moduleversion = module_names( **kwargs )
    #
    # construct module path
    #
    if existing := nonzero_keyword( "modulediradd",**kwargs ):
        # in jail we can get an explicit, already-existing path (see netcdf/netcdff)
        modulepath = existing
        return f"{modulepath}",f"{moduleversion}.lua",True
    elif nonnull( dirset := kwargs.get("moduledir") ):
        # in jail we get an explicit path
        modulepath = dirset
        return f"{modulepath}",f"{moduleversion}.lua",False
    else:
        # otherwise we build the path from system & compiler info
        modulepath = abort_on_zero_keyword( "moduleroot",**kwargs )
        if ( mode := kwargs.get("MODE","MODE_NOT_FOUND") ) == "core":
            modulepath += f"/Core"
        else:
            # ignore system & compiler short version
            _,compilercode,compilerversion,_,mpicode,mpiversion = family_names( **kwargs )
            if mode in [ "mpi","hybrid", ]:
                modulepath += f"/MPI/{compilercode}/{compilerversion}/{mpicode}/{mpiversion}"
            elif mode in [ "seq","omp", ]:
                modulepath += f"/Compiler/{compilercode}/{compilerversion}"
            else: error_abort( f"Unknown mode: {mode}" )
        return f"{modulepath}/{modulename}",f"{moduleversion}.lua",False

def module_names( **kwargs: Any ) -> tuple[str, str]:
    package,packageversion = package_names( **kwargs )
    modulename = kwargs.get( "MODULENAME",package )
    if alt := nonzero_keyword( "MODULENAMEALT" ):
        modulename = alt
    # package version can be null, so module version can be null
    moduleversion = packageversion
    if mx := nonzero_keyword( "MODULEVERSIONEXTRA",**kwargs ):
        moduleversion += f"-{mx}"
    return modulename,moduleversion

def pathjoin( prefix: str, dir: str ) -> str:
    ext = re.sub(prefix,"",dir).lstrip('/')
    return f"pathJoin( prefixdir, \"{ext}\" )"
