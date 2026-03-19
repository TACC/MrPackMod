#!/usr/bin/env/python3

#
# standard python modules
#
import os
import re

#
# my own modules
#
from process import process_execute,echo_string,trace_string
from process import echo_string,nonzero_keyword,abort_on_zero_keyword
import names

def cd_download_path( **kwargs ):
    if downloadpath := nonzero_keyword("downloadpath",**kwargs):
        trace_string( f"Change dir to downloadpath: {downloadpath}",**kwargs )
        os.chdir( downloadpath )
    else:
        homedir = names.create_homedir( **kwargs )
        trace_string( f"Use home dir as downloadpath: {homedir}",**kwargs )
        os.chdir(homedir)

def download_from_url( **kwargs, ):
    url = abort_on_zero_keyword( "DOWNLOADURL",**kwargs )
    downloadlog  = kwargs.pop( "logfile",open( f"{os.getcwd()}/download.log","w" ) )
    cd_download_path( **kwargs,logfile=downloadlog )
    echo_string( f"In download dir: {os.getcwd()} downloading {url}",logfile=downloadlog )
    tgz = re.sub( r'.*/','',url )
    process_execute( f"rm -f {tgz}" )
    cmdline=f"wget {url}"
    process_execute( cmdline,logfile=downloadlog,terminal=None )

def unpack_from_url( **kwargs ):
    url          = kwargs.get( "DOWNLOADURL" )
    srcdir       = kwargs.get("srcdir")
    downloadlog  = kwargs.pop( "logfile",open( f"{os.getcwd()}/download.log","a" ) )
    ## downloadpath = ???
    cd_download_path( **kwargs,logfile=downloadlog )
    echo_string( f"Unpacking in {os.getcwd()}",logfile=downloadlog )
    file = re.sub( r'.*/','',url )
    if re.match( file,r'^[ \t]*$' ):
        raise Exception( f"Unpack {url} gives empty file name" )
    if not os.path.isfile( f"./{file}" ):
        raise Exception( f"No such file {file} in directory {os.getcwd()}" )
    ext = re.sub( r'.*\.','',file )
    echo_string( f"Unpacking file: {file} ext: {ext}",logfile=downloadlog )
    if ext in [ "gz","tgz", ]:
        unpackdir = process_execute( f"tar ftz {file} | head -n 1" )
        # the `.*' is only needed for gmsh which has `.clang-tidy' on the 1st line
        unpackdir = re.sub( r'/.*$','',unpackdir )
        echo_string( f"Packed file contains directory: {unpackdir}")
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
            echo_string( f"Moving unpacked dir to srcdir: {srcdir}" )
            process_execute( f"rm -rf {srcdir}" )
            process_execute( f"mv {unpackdir} {srcdir}" )
        else:
            echo_string( f"Unpacked dir is at final name: {srcdir}" )
    if bootstrap := nonzero_keyword( "BOOTSTRAP",**kwargs ):
        echo_string( f"Bootstrap action: {bootstrap}",**kwargs )
        os.system( f"cd {srcdir} && {bootstrap}" )
        
def retar_to_standard_name( **kwargs ):
    downloadlog  = kwargs.pop( "logfile",open( f"{os.getcwd()}/download.log","a" ) )
    cd_download_path( **kwargs,logfile=downloadlog )
    if kwargs.get( "PACKAGEVERSION" )=="git":
        package = kwargs.get( "PACKAGE" )
        unpackdir = f"{package}-git"
    else:
        url = kwargs.get( "GITREPO" )
        file = re.sub( r'.*/','',url )
        unpackdir = process_execute( f"tar ftz {file} | head -n 1" ).rstrip('/')
    process_execute( f"tar fcz {unpackdir}.tgz {unpackdir}",**kwargs )

def clone_from_url( **kwargs ):
    url = abort_on_zero_keyword( "GITREPO",** kwargs )
    gitlog = kwargs.pop( "logfile",open( f"{os.getcwd()}/git.log","w" ) )
    cd_download_path( **kwargs,logfile=gitlog )
    gitdir_local = names.gitdir_local_name( **kwargs )
    if os.path.exists( f"{gitdir_local}" ):
        trace_string( f" .. removing previous clone f{gitdir_local}",**kwargs )
        process_execute( f"rm -rf {gitdir_local}",**kwargs )
    process_execute( f"git clone {url} {gitdir_local}",**kwargs )

def pull_from_url( **kwargs ):
    gitlog = kwargs.pop( "logfile",open( f"{os.getcwd()}/git.log","a" ) )
    cd_download_path( **kwargs,logfile=gitlog )
    gitdir_local = names.gitdir_local_name( **kwargs )
    cmdline = f"cd {gitdir_local} && git pull"
    if branch := nonzero_keyword( "BRANCH",**kwargs ):
        cmdline += f" && git checkout {branch}"
    process_execute( cmdline,**kwargs,logfile=gitlog )
