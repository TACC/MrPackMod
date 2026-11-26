################################################################
####
#### install.py
#### install functions for post-install actions and module files;
#### build-system specific code lives in install_<system>.py
####
################################################################

import os
import stat
from typing import Any, Optional

from MrPackMod.basics  import echo_string,trace_string,error_abort,\
    nonnull,nonzero_keyword
from MrPackMod.names import modulefile_path,module_name_and_version,\
    DirNamesDict,prefixdir_name,get_dir_names
from MrPackMod.process import get_value_from_loaded
from MrPackMod.testing import start_test_stage,end_test_stage,OutputDict

from MrPackMod.install_cmake     import cmake_configure,cmake_build
from MrPackMod.install_autotools import autotools_configure,autotools_build
from MrPackMod.install_meson     import meson_configure,meson_build
from MrPackMod.install_scons     import scons_configure,scons_build
from MrPackMod.install_make      import make_configure,make_build
from MrPackMod.install_pip       import pip_configure,pip_build
from MrPackMod.install_petsc     import petsc_configure,petsc_build

################################################################
####
#### Post-install stuff
####
################################################################

def post_install_actions_script( plist : DirNamesDict,**kwargs : Any ) -> tuple[str,str]:
    # if we get here, we already know there are actions
    script : str = ""
    srcdir,prefixdir = plist["srcdir"],plist["prefixdir"]
    if ( cptoinstall := nonzero_keyword( "CPTOINSTALLDIR",**kwargs ) ) is not None:
        trace_string( f"Extra cp from srcdir={srcdir} to prefix={prefixdir}: {cptoinstall}",
                      **kwargs )
        script += f"""
if [ -d "{prefixdir}/{cptoinstall}" ] ; then
    echo FAILURE: cptoinstall={cptoinstall} already exists in prefix
    exit 1
fi
echo "Copying <<{cptoinstall}>> from srcdir={srcdir} to prefix={prefixdir}"
cd {srcdir}
cp -r {cptoinstall} {prefixdir}
if [ $? -gt 0 ] ; then
    echo "FAILURE: copy failed"
else
    echo "SUCCESS: copy succeeded"
fi
        """
    if ( linkliblib := nonzero_keyword( "LINKLIB64toLIB",**kwargs ) ) is not None:
        script += f"""
echo "Linking lib64 to lib, any previous lib is first erased"
cd {prefixdir}
rm -rf lib
ln -s lib64 lib
"""
    if ( cplibib := nonzero_keyword("CPLIBtoLIB64",**kwargs) ) is not None:
        script += f"""
echo "Copying lib to lib64"
cd {prefixdir}
cp -r lib/* lib64/
"""
    return script,"Post-install actions"

def post_install_actions( **kwargs ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage( "actions",**kwargs )
    retval : Optional[str] = get_value_from_loaded(
        post_install_actions_script,get_dir_names(**kwargs),**{ **kwargs,**output} )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval
    
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
