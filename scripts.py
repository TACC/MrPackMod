################################################################
####
#### scripts.py : partial unix scripts
####
################################################################

import os
import re

from MrPackMod.basics  import module_version_from_env,\
    trace_string,echo_string,echo_warning,trace_var,\
    error_abort,abort_on_zero_keyword,nonzero_keyword,zero_keyword
from MrPackMod.error   import isnull,nonnull
from MrPackMod.names   import compilers_names,family_names,srcdir_name,scriptsdir_name,\
    dir_variable,\
    mode_has_mpi,mode_has_seq,mode_is_core,\
    ensure_download_path,DirNamesDict

from typing import Any,Optional

def compilers_flags( **kwargs: Any ) -> dict[str, str]:
    flags = { 'CFLAGS':"", 'CXXFLAGS':"", 'FFLAGS':"", }
    if cflags := nonzero_keyword( "cflags",**kwargs ):
        flags["CFLAGS"] = cflags
    if cxxflags := nonzero_keyword( "cxxflags",**kwargs ):
        flags["CXXFLAGS"] = cxxflags
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

def export_compilers_script( dummy : list[str],**kwargs: Any ) -> tuple[str,str]:
    trace_string( "Exporting compilers",**kwargs )
    compilers = compilers_names( **kwargs )
    script : str = "\necho \"Now exporting compilers for cmake and such\""
    for key,val in compilers.items():
        trace_string( f" .. Setting compiler: {key}={val}",**kwargs )
        script += f"""
echo Export {key}={val}
export {key}={val}
whichcomp=$( which {val} )
if [ $? -gt 0 ] ; then
  echo FAILURE: could not determine {val} && exit 1
fi
echo where {val}=${{whichcomp}}
            """
    return script,"Export compiler settings"

def load_compiler_and_mpi_and_modules_script( modulestoload : list[str],**kwargs: Any ) -> tuple[str,str]:
    title : str = f"Load compiler and mpi and modules: {modulestoload}"
    errmsg : str = f"Failed to load compiler and mpi and modules: {modulestoload}"
    _,compiler,compilerversion,_,mpi,mpiversion = family_names( **kwargs )
    trace_string( f"Loading {compiler=}/{compilerversion} and {mpi=}/{mpiversion}",
                  **kwargs )
    if ( modulepath := nonzero_keyword( "modulepath",**kwargs ) ) is None:
        error_abort( "Need a module path",**kwargs )
    if not ( redirect := nonzero_keyword( "redirect",**kwargs ) ):
        redirect = ""
    loadscript : str = ""
    #
    # Start by defining some functions
    #
    loadscript += successfailurefunction()
    loadscript += modulereportfunction()
    loadscript += modulelistfunction()
    loadscript += modulelonglistfunction()
    loadscript += modulecommandfunction()
    loadscript += moduleproperfunction()

    #
    # Now the actual script
    #
    loadscript += modulepurgefunction()
    if not mode_is_core( **kwargs ):
        if compiler is not None:
            if ( blasroot := kwargs.get("BLASLAPACK_ROOT") ) is None:
                trace_string( f"Not finding BLASLAPACK_ROOT in {kwargs}",**kwargs )
                blasroot = ""
            else: trace_string( f"Found BLASLAPACK_ROOT as {blasroot}",**kwargs )
            loadscript += compilerloadfunction( modulepath,compiler,compilerversion,blasroot )
        else: error_abort( "No compiler defined",**kwargs )
    if nonzero_keyword( "BLASLAPACK",**kwargs ):
        if comp := abort_on_zero_keyword( "COMPILER",**kwargs ):
            blas : str = ""
            # if comp=="gcc"    : blas = "mkl"
            # if comp=="nvidia" : blas = "nvpl"
            if nonnull(blas):
                loadscript += f"""
echo "Load blas/lapack library: {blas}"
modulecommand "load blas" "load {blas}"
                """
    if mode_has_mpi( **kwargs ):
        if mpi is not None:
            loadscript += mpiloadfunction( mpi,mpiversion )
        else: error_abort( "No mpi defined",**kwargs )
    if nonnull( modulestoload ) and zero_keyword( "skipmodules",**kwargs ) \
       and zero_keyword("NOMODULE",**kwargs) :
        scr,tit = modules_load_script( modulestoload,**kwargs )
        loadscript += scr
    else:
        trace_string( "Not loading any modules",**kwargs )
    loadscript += f"""
echo Module listing:
modulelonglist
    """
    return loadscript,title

def module_and_version_to_load( modver : str,**kwargs ) -> tuple[str,str,str]:
    if modslshver := re.match( r'^([^/]+)(/)([^/]+)$',modver ):
        # if there was a slash, keep original mod+ver
        m,s,v = modslshver.groups()
        return m,s,v
    else:
        # no slash, let's see if we can find a version
        module : str = modver
        # no version required, let's see if the environment has one
        if ( version := module_version_from_env(modver,**kwargs) ) is not None:
            return module,"/",version
            # modver = f"{module}/{version}"
        else:
            # no slash and no environment version, so load default
            return module,"",""

#
# This gets called only from the `test' action
#
def modules_proper_script( moduleslist : list[str],**kwargs : Any ) -> tuple[str,str]:
    modulestring : str = ','.join(moduleslist)
    title : str = f"Module proper testing for {modulestring}"
    script : str = f""
    if  nonzero_keyword("installing",**kwargs ):
        srcdir = srcdir_name( **kwargs )
        script += f"""
if [ ! -d "{srcdir}" ] ; then
    echo "FAILURE: Source directory {srcdir} does not exist"
    exit 1
fi
echo "Now testing properness of {moduleslist}"
        """
    for modver in moduleslist:
        onemodulescript,_ = one_module_proper_script( [modver],**kwargs )
        script += f"""
modulecommand "load {modver}" "load {modver}"
{onemodulescript}
        """
    script += f"\necho End of module proper testing\n"
    return script,title

#
# Assuming a module has been loaded,
# these lines test that the module is proper
#
def one_module_proper_script( modverlist : list[str],**kwargs : Any ) -> tuple[str,str]:
    modver : str = modverlist[0]
    title : str = f"test proper of module {modver}"
    module,_    = f"{modver}/".split("/",maxsplit=1)
    script : str = ""
    #
    # First make sure module is loaded
    #
    modvar : str = dir_variable(module)
    script += f"""
if [ -z "${{{modvar}}}" ] ; then
    echo "FAILURE: variable {modvar} is not set"
    exit 1
fi
"""
    #
    # Test all directories exist
    #
    f"""
echo \">>>> Test proper of module {modver}\"
testmoduleproper {modver}
    """
    if nonzero_keyword( "pkgconfig",**kwargs ) or nonzero_keyword( "pkgconfiglib",**kwargs ):
        script += f"""
echo " .. Finding pc files:"
find ${{pkgdir}} -name \\*.pc
echo "where PKG_CONFIG_PATH="
echo ${{PKG_CONFIG_PATH}} | tr ':' '\\n'
        """
    if nonzero_keyword( "cmakeconfig",**kwargs ):
        script += f"echo \" .. Finding cmake files:\"\nfind ${{pkgdir}} -name \\*.cmake\n"
    script += f"""
echo \"<<<< end of test proper of module {modver}\"
    """
    return script,title

##
## Some long literals,
## to make function above more readable
##
def successfailurefunction() -> str:
    return f"""
function report_success_failure () {{
    if [ $? -eq 0 ] ; then
        echo "SUCCESS: $1"
    else
        echo "FAILURE: $2"
        exit 1
    fi
}}
"""

def modulereportfunction( redirect="" ) -> str:
    return f"""
# Non-redirected return code reporting
# $1 : error code
# $2 : title
# $3 : actual command
function modulereport () {{
if [ $1 -gt 0 ] ; then
    echo FAILURE module command failed: $2
    echo Output: && module -t $3
    echo "Aborting this script" && exit
else
    echo SUCCESS module command succeeded: $2
    local cmd="$3"
    # echo "cmd was <<$cmd>>"
    echo -e "\\nNow loaded:"
    if [[ $cmd =~ load* ]] ; then
        module -t show ${{cmd##load}}
    fi 
    modulelist
fi {redirect}
}}
    """

def modulelistfunction() -> str:
    return """
# Single line module listing
function modulelist ()
{ module -t list 2>&1 | sort | tr '\n' ' ' && echo
}
        """

def modulelonglistfunction() -> str:
    return """
function modulelonglist ()
{
    local compiler=$( module -t list ${TACC_FAMILY_COMPILER} 2>&1 );
    local mpi=$( module -t list ${TACC_FAMILY_MPI} 2>&1 );
    local modules=$( module -t list 2>&1 | grep -v $compiler 2>/dev/null | grep -v $mpi 2>/dev/null | sort 2>/dev/null );
    for m in $compiler $mpi cont $modules;
    do
        if [ $m = "cont" ]; then
            echo "----------------";
        else
            if [ ! -z "${WORK}" ] ; then
                loc=$(module -t show $m 2>&1 | sed -e 's?'${WORK}'?WORK?' );
            else
                loc=$(module -t show $m 2>&1 );
            fi
            echo "$m : $loc";
        fi;
    done
    echo "----------------";
    echo -e "LD_LIBRARY_PATH=\\n$( echo ${LD_LIBRARY_PATH} | tr ':' '\\n' )"
    echo -e "PYTHONPATH=\\n$( echo ${PYTHONPATH} | tr ':' '\\n' )"
}
"""

def modulecommandfunction( redirect="" ) -> str:
    return f"""
# Execute a module command and report result:
# $1 : title, $2 actual command, $3 nonzero to display, otherwise redirected
function modulecommand () {{
    echo
    echo .... $1 : module $2 {redirect}
    if [ -z "$3" ] ; then 
      module -t $2 2>/dev/null {redirect}
    else
      module -t $2 {redirect}
    fi
    modulereport $? "$1" "$2"
}}
"""

def moduleproperfunction() -> str:
    return """
# Test whether modver is properly loaded
function testmoduleproper () {
    local modver=$1
    local module=${modver%%/*}
    local MODULE=$( echo $module | tr a-z A-Z )
    local nam=TACC_${MODULE}_DIR
    eval pkgdir=\\${$nam}
    if [ ! -d "${pkgdir}" ] ; then
        echo "FAILURE: package dir $nam=$pkgdir does not exist"
    else
        echo "SUCCESS: package ${modver} is at $pkgdir"
    fi
    for e in DIR BIN LIB INC ; do
        nam=TACC_${MODULE}_${e}
        eval cmpdir=\\${$nam}
        if [ ! -z "${cmpdir}" -a ! -d "${cmpdir}" ] ; then 
            echo "FAILURE: variable $nam set but dir $cmpdir does not exist"
        else
            echo "${nam}=${cmpdir}"
        fi
    done
}
    """

def modulepurgefunction( redirect="" ) -> str:
    return f"""
echo
echo Module setup starts here {redirect}

modulecommand "module purge" "purge"

# export LMOD_SYSTEM_DEFAULT_MODULES=TACC

# modulecommand "reset" "reset"
    """

def compilerloadfunction( modulepath : str,compiler : str,compilerversion : Optional[str],
                          blasroot : Optional[str],
                          redirect="" ) -> str:
    if compilerversion is None:
        compver : str = compiler
    else:
        compver = f"{compiler}/{compilerversion}"
    return f"""
if [ ! -z "${{TACC_FAMILY_MPI}}" ] ; then
  modulecommand "unload mpi" "-f unload ${{TACC_FAMILY_MPI}}"
fi

modulecommand "unload compiler" "unload ${{TACC_FAMILY_COMPILER}}"

echo .... After reset: {redirect}
modulelist {redirect}

echo ".... Set modulepath" {redirect}
export MODULEPATH={modulepath}
echo "MODULEPATH=${{MODULEPATH}}" {redirect}
modulecommand "Can we load compiler?" "avail {compver}" display

modulecommand "Load compiler" "load {compver}"

echo "\n.... Can we find BLASLAPACK_ROOT?" {redirect}
if [ -z "{blasroot}" ] ; then
    echo "WARNING: no BLASLAPACK_ROOT variable defined"
else
    echo "BLASLAPACK_ROOT={blasroot}"
fi {redirect}
    """

# VLE Should be insist on an mpi version?
def mpiloadfunction( mpi : str,mpiversion : Optional[str] ) -> str:
    if mpiversion is not None:
        return f"""
modulecommand "Load mpi" "load {mpi}/{mpiversion}"
        """
    else:
        return f"""
modulecommand "Load mpi" "load {mpi}"
    """

def modules_load_script( modulestoload : list[str],**kwargs ) -> tuple[str,str]:
    redirect : str = kwargs.get( "redirect","" )
    loadscript : str = f"""
echo ".... Load packages <<{modulestoload}>>" {redirect}
    """
    for modver in modulestoload:
        if isnull(modver): continue
        module,slash,version = module_and_version_to_load(modver,**kwargs )
        modulepropertest,_ = one_module_proper_script( [modver],**kwargs )
        loadscript += f"""
modulecommand "load module: {module}{slash}{version}" "load {module}{slash}{version}"
{modulepropertest}
        """
    modulesstring : str = re.sub( '/','',"-".join(modulestoload) )
    return loadscript,f"module loading {modulesstring}"

##
## Now the big scripts!
##

################################################################
####
#### Download
####
################################################################

def download_url_script( pdirs : tuple[str,DirNamesDict],**kwargs : dict[str,Any],
                        ) -> tuple[str,str]:
    package,dirnames = pdirs
    downloadpath : str = ensure_download_path( **kwargs )
    downloadurl  : str = dirnames["srcdir"]
    script : str = f"""
downloadpath={downloadpath}
echo "Using download location: ${{downloadpath}}"
cd ${{downloadpath}}

downloadurl={downloadurl}
tgz=${{downloadurl##*/}}
echo "First remove existing compressed file ${{tgz}}"
rm -f ${{tgz}}
echo "Now download from url: ${{downloadurl}}"
wget ${{downloadurl}}
if [ $? -gt 0 ] ; then
  echo "FAILURE Executing wget ${{downloadurl}}"
  exit
fi
echo "SUCCESS: package {package} downloaded as ${{tgz}}"
    """
    return script,"Download from url"

#
# Auxs for the build scripts
#
def nonzero_exports( **kwargs : Any ) -> Optional[str]:
    if exports := nonzero_keyword( "exports",**kwargs ):
        export_cmdline : str = " && ".join(exports)
        trace_string( f"Using exports: {export_cmdline}",**kwargs )
        return export_cmdline
    else: return None

def nonzero_unsets( **kwargs : Any ) -> Optional[str]:
    if unsets := nonzero_keyword( "unsets",**kwargs ):
        unset_cmdline : str = " && ".join(unsets)
        trace_string( f"Using unsets: {unset_cmdline}",**kwargs )
        return unset_cmdline
    else: return None

################################################################
####
#### More scripts
####
################################################################

def ldd_script( dirnamesl : tuple[str,DirNamesDict],**kwargs ) -> tuple[str,str]:
    # old: program,programdir,cmakebuilddir,cmakeprefixdir = args
    # new:
    program,dirnames = dirnamesl
    program = re.sub( r'\..*','',program )

    # srcdir,builddir,prefixdir = cmakedirs
    if ( scriptsdir := kwargs.get("scriptsdir") ) is None:
        error_abort( f"need scriptsdir for ldd tmps",**kwargs )
    cmakebuilddir  = dirnames["builddir"]
    cmakeprefixdir = dirnames["prefixdir"]

    script : str = f"""
echo -e "\n>>> Start of ldd testing"
    """

    where : str = cmakeprefixdir if nonnull(cmakeprefixdir) else cmakebuilddir
    script += f"""
echo "ldd testing on file={program} in dir={where}"
if [ ! -d ] ; then
    echo "FAILURE: directory <<{where}>> does not exist" && exit 1
fi
cd {where}
if [ ! -d "{scriptsdir}" ] ; then
    echo "FAILURE: scripts dir {scriptsdir} does not exist" && exit 1
fi

program_full_path={where}/{program}"
if [ ! -f \"${{program_full_path}}\" ] ; then
    echo "FAILURE: could not find file=${{program_full_path}} to run ldd on"
else
    echo "Going to ldd on ${{program_full_path}}"
    lddout="{scriptsdir}/ldd_{program}.out"
    rm -f "${{lddout}}"
    ldd ${{program_full_path}} 2>&1 | tee "${{lddout}}"
    notfound=$( grep \"not found\" "${{lddout}}" | wc -l )
    if [ $notfound -eq 0 ] ; then
        echo "SUCCESS: all libraries resolved"
    else
        echo "FAILURE: $notfound references not found"
    fi
fi
    """
    return script,f"ldd test on {program}"

##
## Test file existence
##
def file_to_exist_script( args : list[str],**kwargs : Any, ) -> tuple[str,str]:
    package,dirtype,program,grep,executable = args
    dirvar : str = dir_variable(package,dirtype)
    title : str = f"Test existence of {dirtype}:{program}"
    script : str = f"""
echo "{title}"

echo "Using directory variable: {dirvar}"
eval filedir=\\${{{dirvar}}}
echo " .. expands to path: ${{filedir}}"
if [ ! -z "${{filedir}}" -a -d "${{filedir}}" ] ; then 
    echo " .. directory {dirvar}=${{filedir}} exists"
else 
    echo "FAILURE: {dirvar} does not exist"
    exit 1
fi

file_to_test=${{filedir}}/{program}
echo "File to test: ${{file_to_test}}"
if [ -f "${{file_to_test}}" ] ; then
    echo "SUCCESS: file exists: <<${{file_to_test}}>>"
else
    echo "FAILURE: file does not exist <<${{file_to_report}}>>"
    exit 1
fi
        """
    if nonnull(executable):
        script += f"""
if [ -x "${{file_to_test}}" ] ; then
    echo "SUCCESS: file is executable"
else
    echo "FAILURE: file is not executable"
fi
"""
    return script,title
    #
    if nonnull( grep ):
        program_clean = re.sub( '/','',program )
        grep_output_file : str = f"{os.getcwd()}/{program_clean}_grep.out"
        script += f"""
if [ -f \"{file_to_test}\" ] ; then
    grep \"{grep}\" {file_to_test} >{grep_output_file} 2>&1
    echo INFORMATION: grep result is $( head -n 1 {grep_output_file} )
fi
        """
    return script,title

##
## Run a program
##
def run_script( dirnamesl : tuple[str,DirNamesDict,str,str],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames,args,val = dirnamesl
    # strip any extension
    program = re.sub( r'\..*','',program )

    title   : str = f"run program {program}"

    script : str = ""
    # where do we run?
    rundir : str = dirnames.get("builddir","build")
    script += f"""
if [ ! -d "{rundir}" ] ; then
    echo "FAILURE: rundir does not exist: <<{rundir}>> in pwd=<<$(pwd)>>"
    exit 1
fi
cd {rundir}
echo "Running in rundir={rundir} full path=$( pwd )"
    """

    # what do we run?
    #  - prefix is empty for runing along path
    #  - prefix can be ./
    prefix  : str = dirnames.get("prefix","")
    #print( f"prefix=<<{prefix}>> out of dirnames={dirnames}" )
    cmdline : str = f"{prefix}{program}"
    if nonnull( args ):
        cmdline += f" {args}"
    if kwargs.get("MODE") in ["mpi","hybrid",]:
        cmdline = f"ibrun -n 1 {cmdline}"
    script += f"""
echo "cmdline={cmdline}"
echo ">>>> start execution"
runout=run_{program}.out
{cmdline} >${{runout}} 2>&1
runcode=$?
echo "<<<< end execution"
if [ ${{runcode}} -eq 0 ] ; then 
    echo "SUCCESS: running {program}"
else
    echo "FAILURE: running {program}"
fi 
echo ">>>> output"
cat ${{runout}}
echo "<<<< output"
    """
    return script,title

