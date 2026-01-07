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
from process import isnull,nonnull,echo_string,error_abort,trace_string
from process import abort_on_zero_keyword,zero_keyword,nonzero_keyword,nonzero_keyword_or_default
from process import abort_on_zero_env
from process import process_execute

def loaded_modules( **kwargs ):
    name_version_list = process_execute\
        ( "module -t list 2>&1 | tr '\n' ' '",**kwargs ).split()
    return [ f"{mv}/".split('/',1) for mv in name_version_list ]

non_packages = [ "mkl","nvpl","blaslapack", "mpi", ]
def test_modules( **kwargs ):
    tracing = kwargs.get( "tracing" )
    error = False
    if not (modules := nonzero_keyword( "MODULES",**kwargs ) ):
        trace_string( "No prerequisite modules",**kwargs )
        return
    if tracing:
        modulepath = re.sub( ":","\n",os.getenv( "MODULEPATH" ) )
        echo_string( f"\nUsing modulepath {modulepath}\n",**kwargs )
    for m in modules.split(" "):
        if not nonnull(m):continue
        mod,ver = f"{m}/".split('/',maxsplit=1)
        mod = mod.lower(); ver=ver.strip("/")
        if mod in non_packages:
            echo_string( f"Skip test for non-package: {mod}",**kwargs )
            continue
        echo_string( f"Test presence of module={mod} version={ver}" )
        if isnull( packdir := os.getenv( f"TACC_{mod.upper()}_DIR","" ) ):
            error = True
            echo_string( f"Please load module: {mod}",**kwargs )
            continue
        echo_string( f" .. module {mod} is at: {packdir}" )
        loc = process_execute( f"module -t show {mod}",**kwargs,terminal=None )
        echo_string( f" .. module {mod} loaded from: {loc}",**kwargs )
        if not os.path.isdir(packdir):
            error = True
            echo_string( f"Module {mod} loaded but directory not found: {packdir}",**kwargs )
        try:
            loadedversion = os.environ[ "TACC_"+mod.upper()+"_VERSION" ]
            if nonnull(ver):
                if not process.version_satisfies(loadedversion,ver,terminal=None):
                    echo_string( f"loaded version: {loadedversion} does not match version {ver}",
                                 **kwargs )
                    error = True
        except: continue
    if error:
        error_abort( "Errors during module testing",**kwargs )

def module_help_string( **kwargs ):
    package,packageversion   = names.package_names( **kwargs )
    modulename,moduleversion = names.module_names( **kwargs )

    about = abort_on_zero_keyword( "ABOUT",**kwargs )
    about += "\n"
    if notes    := nonzero_keyword( "MODULENOTES",**kwargs ):
        about += f"Notes: {notes}\n"
    if url      := nonzero_keyword( "URL",**kwargs ):
        about += f"Homepage: {url}\n"
    if software := nonzero_keyword( "SOFTWAREURL",**kwargs ):
        about += f"Software: {software}\n"

    vars = f"TACC_{package.upper()}_DIR"
    _,libdir,incdir,bindir = names.package_dir_names( **kwargs )
    if nonnull( libdir ):
            vars += f", TACC_{package.upper()}_LIB"
    if nonnull( incdir ):
            vars += f", TACC_{package.upper()}_INC"
    if nonnull( bindir ):
            vars += f", TACC_{package.upper()}_BIN"

    notes = ""
    cmake     = kwargs.get( "PREFIXPATHSET" )
    pkgconfig = kwargs.get( "PKGCONFIG" ) or kwargs.get( "PKGCONFIGLIB" )
    if cmake    : notes += "Discoverable by CMake through find_package.\n"
    if pkgconfig: notes += "Discoverable by CMake through pkg-config.\n"
    notes += f"\n(modulefile generated {datetime.date.today()})"

    return \
f"""\
local helpMsg = [[
Package: {package}/{packageversion}

{about}
The {package} modulefile defines the following variables:
    {vars}.
{notes}
]]
""".strip()

def package_info( **kwargs ):
    package,packageversion   = names.package_names( **kwargs )
    modulename,moduleversion = names.module_names( **kwargs )
    return \
f"""\
whatis( "Name:",   \"{package}\" )
whatis( "Version", \"{moduleversion}\" )
""".strip()

def path_settings( **kwargs ):
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

def system_paths( **kwargs ):
    prefixdir     = names.prefixdir_name( **kwargs )

    envs = ""
    for sub in [ "inc", "lib", "bin", ]:
        if dir := kwargs.get( f"{sub}dir" ):
            ext = re.sub( f"{prefixdir}/","",dir ).lstrip("/") # why the lstrip?
            path = f"pathJoin( prefixdir,\"{ext}\" )"
            if sub=="inc":
                envs += f"prepend_path( \"INCLUDE\", {path} )\n"
            elif sub=="lib":
                envs += f"prepend_path( \"LD_LIBRARY_PATH\", {path} )\n"
            elif sub=="bin":
                envs += f"prepend_path( \"PATH\", {path} )\n"
    for env,var in [ ["bindir","PATH"],
                 ["pkgconfig","PKG_CONFIG_PATH"], ["pkgconfiglib","PKG_CONFIG_PATH"],
                 ["prefixpathset","CMAKE_PREFIX_PATH"],
                 ["pythonpathabs","PYTHONPATH"], ["pythonpathrel","PYTHONPATH"],
                ]:
        if val := nonzero_keyword( env,**kwargs ):
            if env in [ "bindir", "pkgconfig", "pkgconfiglib", "pythonpathrel",
                       ]:
                #
                # add path relative to prefix
                #
                if env in [ "bindir", "pkgconfiglib", ]:
                    # relative to prefix & standard extension
                    val = re.sub( f"{prefixdir}/","",val ).lstrip("/") # why the lstrip?
                    # else relative to prefix & custom path
                path = f"pathJoin( prefixdir,\"{val}\" )"
                envs += f"prepend_path( \"{var}\", {path} )\n"
            elif env in [ "prefixpathset",
                         ]:
                #
                # add prefix path itself
                #
                envs += f"prepend_path( \"{var}\", prefixdir )\n"
            elif env in [ "pythonpathabs", ]:
                #
                # add absolute path
                #
                envs += f"prepend_path( \"{var}\", \"{val}\" )\n"

    return \
f"""\
{envs}
""".strip()

def dependencies( **kwargs ):
    tracing = kwargs.get( "tracing" )
    depends = ""
    if prereq := nonzero_keyword( "dependson",**kwargs ):
        if tracing:
            echo_string( f"depends on: {prereq}" )
        for dep in prereq.split(" "):
            depends += f"depends_on( \"{dep}\" )\n"
    if curreq  := nonzero_keyword( "dependsoncurrent",**kwargs ):
        version = abort_on_zero_env( f"TACC_{curreq.upper()}_VERSION" )
        if tracing:
            echo_string( f"depends on current: {curreq}/{version}" )
        depends += f"depends_on( \"{curreq}/{version}\" )\n"
    if family    := nonzero_keyword( "family",**kwargs ):
        if tracing:
            echo_string( f"belongs to family: {family}" )
        depends += f"family( \"{family}\" )\n"
    return depends
