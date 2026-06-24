#!/usr/bin/env/python3

#
# standard python modules
#
import os
import re
from typing import Any,Optional

#
# my own modules
#
from MrPackMod.basics  import echo_string,trace_string,\
    abort_on_zero_keyword,nonzero_keyword
import MrPackMod.names as names
from MrPackMod.process import get_value_from_loaded,process_execute
from MrPackMod.testing import start_test_stage,end_test_stage,\
    OutputDict

def download_path( **kwargs: Any ) -> str:
    if downloadpath := nonzero_keyword("downloadpath",**kwargs):
        trace_string( f"Change dir to downloadpath: {downloadpath}",**kwargs )
        return downloadpath
    else:
        homedir :str = names.create_homedir( **kwargs )
        trace_string( f"Use home dir as downloadpath: {homedir}",**kwargs )
        return homedir

def cd_download_path( **kwargs: Any ) -> None:
    downloadpath = download_path( **kwargs )
    os.chdir( downloadpath )
    
def download_from_url( **kwargs: Any ) -> None:
    if ( url := nonzero_keyword( "DOWNLOADURL",**kwargs ) ) is None:
        raise Exception( f"No download url given" )
    downloadlog  = kwargs.pop( "logfile",open( f"{os.getcwd()}/download.log","w" ) )
    cd_download_path( **kwargs,logfile=downloadlog )
    echo_string( f"In download dir: {os.getcwd()} downloading {url}",logfile=downloadlog )
    tgz = re.sub( r'.*/','',url )
    process_execute( f"rm -f {tgz}",**kwargs,logfile=downloadlog )
    cmdline=f"wget {url}"
    process_execute( cmdline,logfile=downloadlog )

def unpack_from_url( **kwargs: Any ) -> None:
    url = kwargs.get( "DOWNLOADURL" ) or ""
    srcdir       = kwargs.get("srcdir")
    downloadlog  = kwargs.pop( "logfile",open( f"{os.getcwd()}/download.log","a" ) )
    ## downloadpath = ???
    cd_download_path( **kwargs,logfile=downloadlog )
    echo_string( f"Unpacking in {os.getcwd()}",logfile=downloadlog )
    file = re.sub( r'.*/','',url )
    if re.match( r'^[ \t]*$',file ):
        raise Exception( f"Unpack {url} gives empty file name" )
    if not os.path.isfile( f"./{file}" ):
        raise Exception( f"No such file {file} in directory {os.getcwd()}" )
    if root_ext := re.search( r'(.+)\.([^\.]+)$',file):
        _,ext = root_ext.groups()
    else:
        ext = "" # gnuplot downloads to `download' with no extension
    echo_string( f"Unpacking file: <<{file}>> ext: <<{ext}>>",logfile=downloadlog )
    if ext in [ "gz","tgz", "", ]: 
        unpackdir : str = process_execute( f"tar ftz {file} | head -n 1" )
        unpackdir = unpackdir.rstrip("/")
        echo_string( f"Packed file contains directory: {unpackdir}",**kwargs )
        if dotslash := re.match( r'^\./(.*)$',unpackdir):
            echo_string( " .. removing dot-slash",**kwargs )
            unpackdir = dotslash.groups()[0]
        # the `.*' is only needed for gmsh which has `.clang-tidy' on the 1st line
        # unpackdir = re.sub( r'/.*$','',unpackdir )
        process_execute( f"rm -rf {unpackdir}" )
        process_execute( f"tar fxz {file}" )
    elif ext in [ "xz", "txz", ] :
        process_execute( f"xz --decompress {file}" )
        file = re.sub( r'\.xz','',file )
        if not re.match( r'^.*\.tar$',file ):
            raise Exception( f"Was expecting .tar suffix in {file}" )
        unpackdir = process_execute( f"tar ft {file} | head -n 1" )
        ## ( f"zcat {file} | head -n 1 | sed -e 's?/.*??' " )
        unpackdir = re.sub( r'/$','',unpackdir )
        echo_string( f"Packed file contains directory: {unpackdir}")
        process_execute( f"rm -rf {unpackdir}" )
        process_execute( f"tar fx {unpackdir}.tar" )
    else: raise Exception(f"Cannot unpack {file}")
    if srcdir:
        if unpackdir.lstrip("./") != srcdir:
            echo_string( f"Moving unpacked dir <<{unpackdir}>> to srcdir <<{srcdir}>>" )
            process_execute( f"rm -rf {srcdir}" )
            process_execute( f"mv {unpackdir} {srcdir}" )
        else:
            echo_string( f"Unpacked dir is at final name: {srcdir}" )
    if bootstrap := nonzero_keyword( "BOOTSTRAP",**kwargs ):
        echo_string( f"Bootstrap action: {bootstrap}",**kwargs )
        os.system( f"cd {srcdir} && {bootstrap}" )
        
def retar_to_standard_name( **kwargs: Any ) -> None:
    downloadlog  = kwargs.pop( "logfile",open( f"{os.getcwd()}/download.log","a" ) )
    cd_download_path( **kwargs,logfile=downloadlog )
    package = kwargs.get( "PACKAGE" )
    version = kwargs.get( "PACKAGEVERSION" )
    unpackdir = f"{package}-{version}"
    process_execute( f"tar fcz {unpackdir}.tgz {unpackdir}",**kwargs )

def clone_from_url( **kwargs: Any ) -> None:
    url = abort_on_zero_keyword( "GITREPO",** kwargs )
    gitlog = kwargs.pop( "logfile",open( f"{os.getcwd()}/git.log","w" ) )
    cd_download_path( **kwargs,logfile=gitlog )
    gitdir_local = names.gitdir_local_name( **kwargs )
    if os.path.exists( f"{gitdir_local}" ):
        trace_string( f" .. removing previous clone f{gitdir_local}",**kwargs )
        process_execute( f"rm -rf {gitdir_local}",**kwargs )
    process_execute( f"git clone {url} {gitdir_local}",**kwargs )

def pull_from_url( **kwargs: Any ) -> None:
    gitlog = kwargs.pop( "logfile",open( f"{os.getcwd()}/git.log","a" ) )
    cd_download_path( **kwargs,logfile=gitlog )
    gitdir_local = names.gitdir_local_name( **kwargs )
    cmdline = f"cd {gitdir_local} && git pull"
    if branch := nonzero_keyword( "BRANCH",**kwargs ):
        cmdline += f" && git checkout {branch}"
    if commit := nonzero_keyword( "GITCOMMIT",**kwargs ):
        cmdline += f" && git checkout {commit}"
    process_execute( cmdline,**kwargs,logfile=gitlog )

def clone_pull_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    if ( url := nonzero_keyword( "GITREPO",** kwargs ) ) is None:
        raise Exception( "No git repo url given for clone" )
    downloadpath : str = download_path( **kwargs )
    if ( action := nonzero_keyword( "gitaction",**kwargs ) ) is None:
        raise Exception( "Need git action" )
    script : str = f"""
echo change dir for clone to {downloadpath}
cd {downloadpath}
    """
    gitdir_local : str = names.gitdir_local_name( **kwargs )
    if action=="clone":
        script += f"""
if [ -d \"{gitdir_local}\" ] ; then
    echo \" .... removing previous clone f{gitdir_local}\"
    rm -rf {gitdir_local}
fi
git clone {url} {gitdir_local}
        """
    script += f"\ncd {gitdir_local} && git pull\n"
    if branch := nonzero_keyword( "BRANCH",**kwargs ):
        script += f"""
echo \"Switching to branch {branch}\"
git checkout {branch}
        """
    if commit := nonzero_keyword( "GITCOMMIT",**kwargs ):
        script += f"""
echo \"Checkout specific commit {commit}\"
git checkout {commit}
        """
    return script,"clone pull repo"

def clone_or_pull( **kwargs: Any ) -> Optional[str]:
    output : OutputDict = \
        start_test_stage(
            "git",
            **{ **kwargs, "title":"git clone pull","installing":True }
            )
    retval : Optional[str] = get_value_from_loaded(
        clone_pull_script,[],**kwargs,**output, )
    success,failure = end_test_stage( [],[],output,**kwargs )
    return retval

