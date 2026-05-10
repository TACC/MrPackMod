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
from MrPackMod.error import abort_on_zero_keyword,zero_keyword,nonzero_keyword,\
    nonzero_keyword_or_default,abort_on_zero_env,error_abort,\
    isnull,nonnull
from  MrPackMod.names import package_names,package_names_nonnull,package_prerequisites,\
    module_names,\
    package_dir_names,prefixdir_name,pathjoin
from MrPackMod.tracing import echo_string,trace_string,echo_warning
from MrPackMod.process import version_satisfies,process_execute,\
    get_value_from_loaded

##
## list of loaded modules
## by running a new process
##
def loaded_modules( **kwargs: Any ) -> list[list[str]]:
    name_version_list : list[str] = process_execute\
        ( "module -t list 2>&1 | tr '\n' ' '",**kwargs ).split()
    return [ f"{mv}/".split('/',1) for mv in name_version_list ]

def mod_ver( m : str,**kwargs : Any ) -> tuple[str, str]:
    mod,ver = f"{m}/".split('/',maxsplit=1)
    if re.search( r'/',mod ):
        error_abort( f"module <<{m}={mod}/{ver}>> should have been split as mod/ver",**kwargs )
    mod = mod.lower(); ver = ver.strip("/")
    return mod,ver

def module_help_string( **kwargs: Any ) -> str:
    package,packageversion   = package_names_nonnull( **kwargs )
    modulename,moduleversion = module_names( **kwargs )

    about = kwargs.get( "ABOUT", f"The {package} package" )
    about += "\n"
    if notes    := nonzero_keyword( "MODULENOTES",**kwargs ):
        about += f"Notes: {notes}\n"
    if url      := nonzero_keyword( "URL",**kwargs ):
        about += f"Homepage: {url}\n"
    if software := nonzero_keyword( "SOFTWAREURL",**kwargs ):
        about += f"Software: {software}\n"

    vars = f"TACC_{modulename.upper()}_DIR"
    _,libdir,incdir,bindir = package_dir_names( **kwargs )
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
    package,packageversion   = package_names( **kwargs )
    modulename,moduleversion = module_names( **kwargs )
    return \
f"""\
whatis( "Name: {modulename}" )
whatis( "Version: {moduleversion}" )
""".strip()

def path_settings( **kwargs: Any ) -> str:
    package,packageversion   = package_names( **kwargs )
    modulename,moduleversion = module_names( **kwargs )
    modulenamealt = kwargs.get("modulenamealt","").lower()

    paths = ""
    info  = ""
    prefixdir,libdir,incdir,bindir = package_dir_names( **kwargs )
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
    #print( f"In system_paths:\n{kwargs}" )
    package    = kwargs.get("PACKAGE")
    modulename = kwargs.get( "MODULENAME",package )
    prefixdir  = prefixdir_name( **kwargs )

    envs = ""
    _,libdir,incdir,bindir = package_dir_names( **kwargs )
    ## print( f"dirs: {libdir} {incdir} {bindir}" )
    libext = "lib"
    if nonnull(incdir):
        path = pathjoin(prefixdir,incdir)
        envs += f"prepend_path( \"INCLUDE\", {path} )\n"
    if nonnull(libdir):
        path = pathjoin(prefixdir,libdir)
        envs += f"prepend_path( \"LD_LIBRARY_PATH\", {path} )\n"
        libext = re.sub( f"{prefixdir}/","",libdir ).lstrip("/")
    if nonnull(bindir):
        path = pathjoin(prefixdir,bindir)
        envs += f"prepend_path( \"PATH\", {path} )\n"
    envs += other_paths( **kwargs,libext=libext )

    system_path_settings = \
f"""\
{envs}
""".strip()
    trace_string( f"System paths:\n{system_path_settings}",**kwargs )
    return system_path_settings

def module_version_script( pkgl : list[str],**kwargs : Any ) -> tuple[str,str]:
    pkg : str = pkgl[0]
    return f"""
if [ ! -z \"$TACC_{pkg.upper()}_VERSION\" ] ; then
    echo $TACC_{pkg.upper()}_VERSION
elif [ ! -z \"$TACC_{pkg.upper()}_VER\" ] ; then
    echo $TACC_{pkg.upper()}_VER
else
    echo FAILURE No VER or VERSION macro for package {pkg}
fi
        """,\
            f"Find VERSION or VER macro for package {pkg}"

def ensure_module_version_loaded( pkg : str,**kwargs : Any ) -> str:
    return get_value_from_loaded( module_version_script,[pkg],**kwargs )

def get_module_version( pkg : str,**kwargs : Any ) -> str:
    return get_value_from_loaded( module_version_script,[pkg],**kwargs )

##
## Construct the modulefile string
## for module dependencies
##
def dependency_clauses( **kwargs: Any ) -> str:
    tracing = kwargs.get( "tracing" )
    clauses = ""
    if prereq := nonzero_keyword( "DEPENDSON",**kwargs ):
        trace_string( f"depends on: {prereq}" )
        for pre in [ p for p in prereq.split(" ") if nonnull(p) ]:
                clauses += f"depends_on( \"{pre}\" )\n"
    if curreq  := nonzero_keyword( "DEPENDSONCURRENT",**kwargs ):
        trace_string( f"depends on current versions of: {curreq}" )
        for cur in [ c for c in curreq.split(" ") if nonnull(c) ]:            
            version = get_module_version( cur,**kwargs )
            #version = ensure_module_version_loaded( cur,**kwargs )
            clauses += f"depends_on( \"{cur}/{version}\" )\n"
    if family    := nonzero_keyword( "FAMILY",**kwargs ):
        trace_string( f"belongs to family: {family}" )
        clauses += f"family( \"{family}\" )\n"
#     clauses = \
# f"""\
# {clauses}
# """.strip()
    trace_string( f"Dependency settings:\n{clauses}",**kwargs )
    return clauses

def module_loaded_script( modverlist : list[str],**kwargs : Any ) -> tuple[str,str]:
    modver : str = modverlist[0]
    title : str = f"Test presence of module: {modver}"
    if hasver := re.search( r'(.*)/(.*)',modver):
        mod,ver = hasver.groups()
    elif nonnull(modver):
        mod = modver; ver = ""
    else:
        echo_warning( f"Testing loaded with null modver",**kwargs )
        return
    modvar : str = f"TACC_{mod.upper()}_DIR"
    script : str = f"""
if [ -z \"${modvar}\" ] ; then 
  echo FAILURE: variable {modvar} not set, load module {mod}
else
  if [ ! -d \"${modvar}\" ] ; then
    echo FAILURE: directory {modvar} not found
  else
    echo SUCCESS: package={mod} version={ver} is at: {modvar}=${{{modvar}}}
  fi
fi
        """
    return script,title
