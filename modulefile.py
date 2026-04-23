#!/usr/bin/env/python3

#
# standard python modules
#
import datetime
import os
import re
import sys
from typing import Any

#
# my own modules
#
from  MrPackMod import names 
from MrPackMod.tracing import echo_string,trace_string
from MrPackMod.error import abort_on_zero_keyword,zero_keyword,nonzero_keyword,\
    nonzero_keyword_or_default,abort_on_zero_env,error_abort,\
    isnull,nonnull
from MrPackMod.process import version_satisfies,process_execute

def loaded_modules( **kwargs: Any ) -> list[list[str]]:
    name_version_list : list[str] = process_execute\
        ( "module -t list 2>&1 | tr '\n' ' '",**kwargs ).split()
    return [ f"{mv}/".split('/',1) for mv in name_version_list ]

non_packages: list[str] = [ "blaslapack", "mpi", ] # mkl","nvpl","
def mod_ver(m: str) -> tuple[str, str]:
    mod,ver = f"{m}/".split('/',maxsplit=1)
    mod = mod.lower(); ver = ver.strip("/")
    return mod,ver

def test_module_loaded( mod: str, ver: str, **kwargs: Any ) -> None:
    process_execute\
        ( f"echo Test presence of module={mod} version={ver}",**kwargs )
    modvar : str = f"TACC_{mod.upper()}_DIR"
    process_execute\
        ( f"""
if [ -z \"${modvar}\" ] ; then 
  echo FAILURE: variable {modvar} not set, load module {mod}
else
  if [ ! -d \"${modvar}\" ] ; then
    echo FAILURE: directory {modvar} not found
  else
    echo SUCCESS: package {mod} is at {modvar}
  fi
fi
        """,**kwargs )

def test_module_version( mod: str, ver: str, **kwargs: Any ) -> bool:
    if isnull( loadedversion := os.getenv( "TACC_"+mod.upper()+"_VERSION","" ) ):
        trace_string( " .. module does not declare VERSION parameter",**kwargs )
        return True
    else:
        if not ( version_match := version_satisfies( loadedversion,ver,**kwargs ) ):
            trace_string( f" .. loaded version: {loadedversion} does not match version {ver}",
                     **kwargs )
            return False
        else:
            trace_string( f" .. loaded version: {loadedversion} matches version {ver}",
                          **kwargs )
            return True

# are the required modules loaded?
def test_loaded_modules( modules : str,**kwargs: Any ) -> bool:
    for m in modules.split(" "):
        if not nonnull(m): continue
        mod,ver = mod_ver(m)
        if mod in non_packages:
            trace_string( f"Skip test for non-package: {mod}",**kwargs )
            continue
        test_module_loaded( mod,ver,**kwargs )
        if nonnull(ver):
            test_module_version( mod,ver,**kwargs )

# are no nonmodules loaded?
def test_nonmodules( **kwargs: Any ) -> bool:
    if not (nonmodules := nonzero_keyword( "NONMODULES",**kwargs ) ):
        trace_string( "No nonmodules",**kwargs )
        return True
    success = True
    for m in nonmodules.split(" "):
        if not nonnull(m):continue
        mod,ver = mod_ver(m)
        if loaded := test_module_loaded( mod,ver,**kwargs ):
            echo_string( f"Please unload module: {mod}",**kwargs )
            success = False
        else: trace_string( " .. module correctly not loaded",**kwargs )
    return success

def test_modules( **kwargs: Any ) -> None:
    installing : bool = kwargs.get( "installing",False )
    process_execute\
        ( f"echo Using modulepath:",**kwargs )
    process_execute\
        ( f"echo $MODULEPATH  | tr ':' '\n'",**kwargs )
    if installing and  nonnull( modules := names.package_prerequisites(**kwargs) ):
        modules_to_test : str = modules
    else:
        modules_to_test,_ = names.package_names( **kwargs )
    test_loaded_modules( modules,**kwargs )
    #test_nonmodules( **kwargs )

def module_help_string( **kwargs: Any ) -> str:
    package,packageversion   = names.package_names_nonnull( **kwargs )
    modulename,moduleversion = names.module_names( **kwargs )

    about = kwargs.get( "ABOUT", f"The {package} package" )
    about += "\n"
    if notes    := nonzero_keyword( "MODULENOTES",**kwargs ):
        about += f"Notes: {notes}\n"
    if url      := nonzero_keyword( "URL",**kwargs ):
        about += f"Homepage: {url}\n"
    if software := nonzero_keyword( "SOFTWAREURL",**kwargs ):
        about += f"Software: {software}\n"

    vars = f"TACC_{modulename.upper()}_DIR"
    _,libdir,incdir,bindir = names.package_dir_names( **kwargs )
    if nonnull( libdir ):
            vars += f", TACC_{modulename.upper()}_LIB"
    if nonnull( incdir ):
            vars += f", TACC_{modulename.upper()}_INC"
    if nonnull( bindir ):
            vars += f", TACC_{modulename.upper()}_BIN"

    notes = ""
    pkgconfig = kwargs.get( "PKGCONFIG" ) or kwargs.get( "PKGCONFIGLIB" )
    if nonzero_keyword( "PREFIXPATHSET",**kwargs ):
        notes += "Discoverable by CMake through find_package.\n"
    if nonzero_keyword( "PKGCONFIG",**kwargs ) or \
       nonzero_keyword( "PKGCONFIGLIB",**kwargs ):
        notes += "Discoverable by CMake through pkg-config.\n"
    notes += f"\n(modulefile generated {datetime.date.today()})"

    return \
f"""\
local helpMsg = [[
Package: {modulename}/{moduleversion}

{about}
The {package} modulefile defines the following variables:
    {vars}.
{notes}
]]
""".strip()

def package_info( **kwargs: Any ) -> str:
    package,packageversion   = names.package_names( **kwargs )
    modulename,moduleversion = names.module_names( **kwargs )
    return \
f"""\
whatis( "Name: {modulename}" )
whatis( "Version: {moduleversion}" )
""".strip()

def path_settings( **kwargs: Any ) -> str:
    package,packageversion   = names.package_names( **kwargs )
    modulename,moduleversion = names.module_names( **kwargs )
    modulenamealt = kwargs.get("modulenamealt","").lower()

    paths = ""
    info  = ""
    prefixdir,libdir,incdir,bindir = names.package_dir_names( **kwargs )
    for name in [ modulename, modulenamealt, ]:
        if name=="": continue
        for sub,val in [ ["VERSION",f"\"{moduleversion}\""], ["DIR","prefixdir"], ]:
            for tgt in [ "TACC", "LMOD", ] :
                info += f"setenv( \"{tgt}_{name.upper()}_{sub.upper()}\", {val} )\n"
        for subname,subdir in [ ["inc",incdir], ["lib",libdir], ["bin",bindir], ]:
            if nonnull(subdir):
                ext = re.sub( f"{prefixdir}/","",subdir ).lstrip("/") # why the lstrip?
                for tgt in [ "TACC", "LMOD", ] :
                    paths += f"setenv( \"{tgt}_{name.upper()}_{subname.upper()}\", \
pathJoin( prefixdir,\"{ext}\" ) )\n"

    return \
f"""\
local prefixdir = \"{prefixdir}\"
{info}{paths}
""".strip()

def other_paths( **kwargs: Any ) -> str:
    paths = ""
    libext = nonzero_keyword( "libext",**kwargs )
    for cfg,var in [ ["BINDIR","PATH"],
                     ["PKGCONFIG","PKG_CONFIG_PATH"],
                     ["PKGCONFIGLIB","PKG_CONFIG_PATH"],
                     ["PREFIXPATHSET","CMAKE_PREFIX_PATH"],
                     ["PYTHONPATHABS","PYTHONPATH"],
                     ["PYTHONPATHADD","PYTHONPATH"],
                ]:
        if val := nonzero_keyword( cfg,**kwargs ):
            if cfg in [ "BINDIR", "PKGCONFIG", "PKGCONFIGLIB", "PYTHONPATHADD",
                       ]:
                #
                # add path relative to prefix
                #
                if cfg == "BINDIR":
                    suffix = "bin"
                elif cfg == "PKGCONFIGLIB":
                    suffix = f"{libext}/pkgconfig"
                else:
                    # relative to prefix & specified value
                    suffix = val
                newpath = f"pathJoin( prefixdir,\"{suffix}\" )"
                paths += f"prepend_path( \"{var}\", {newpath} )\n"
            elif cfg in [ "PREFIXPATHSET", ]:
                #
                # value==1 so ignire: add prefix path itself
                #
                paths += f"prepend_path( \"{var}\", prefixdir )\n"
            elif cfg in [ "PYTHONPATHABS", ]:
                #
                # add absolute path
                #
                paths += f"prepend_path( \"{var}\", \"{val}\" )\n"
    if extra_path := nonzero_keyword( "EXTRAPATHREL",**kwargs ):
        k,v = extra_path.split("=")
        paths += f"setenv( \"{k}\", pathJoin( prefixdir,\"{v}\" ) )"
    return paths

def system_paths( **kwargs: Any ) -> str:
    print( f"In system_paths:\n{kwargs}" )
    package    = kwargs.get("PACKAGE")
    modulename = kwargs.get( "MODULENAME",package )
    prefixdir  = names.prefixdir_name( **kwargs )

    envs = ""
    _,libdir,incdir,bindir = names.package_dir_names( **kwargs )
    ## print( f"dirs: {libdir} {incdir} {bindir}" )
    libext = "lib"
    if nonnull(incdir):
        path = names.pathjoin(prefixdir,incdir)
        envs += f"prepend_path( \"INCLUDE\", {path} )\n"
    if nonnull(libdir):
        path = names.pathjoin(prefixdir,libdir)
        envs += f"prepend_path( \"LD_LIBRARY_PATH\", {path} )\n"
        libext = re.sub( f"{prefixdir}/","",libdir ).lstrip("/")
    if nonnull(bindir):
        path = names.pathjoin(prefixdir,bindir)
        envs += f"prepend_path( \"PATH\", {path} )\n"
    envs += other_paths( **kwargs,libext=libext )
        

    system_path_settings = \
f"""\
{envs}
""".strip()
    trace_string( f"System paths:\n{system_path_settings}",**kwargs )
    return system_path_settings

def dependencies( **kwargs: Any ) -> str:
    tracing = kwargs.get( "tracing" )
    depends = ""
    if prereq := nonzero_keyword( "DEPENDSON",**kwargs ):
        if tracing:
            echo_string( f"depends on: {prereq}" )
        for pre in prereq.split(" "):
            depends += f"depends_on( \"{pre}\" )\n"
    if curreq  := nonzero_keyword( "DEPENDSONCURRENT",**kwargs ):
        if tracing:
            echo_string( f"depends on current versions of: {curreq}" )
        for cur in curreq.split(" "):
            version = abort_on_zero_env( f"TACC_{cur.upper()}_VERSION" )
            depends += f"depends_on( \"{cur}/{version}\" )\n"
    if family    := nonzero_keyword( "FAMILY",**kwargs ):
        if tracing:
            echo_string( f"belongs to family: {family}" )
        depends += f"family( \"{family}\" )\n"
    dependency_settings = \
f"""\
{depends}
""".strip()
    trace_string( f"Dependency settings:\n{dependency_settings}",**kwargs )
    return dependency_settings
