################################################################
####
#### scripts.py : partial unix scripts
####
################################################################

import re

from MrPackMod.basics  import module_version_from_env,\
    trace_string,echo_string,echo_warning,trace_var,\
    abort_on_zero_keyword
from MrPackMod.error   import isnull,nonnull,nonzero_keyword
from MrPackMod.names   import compilers_names,family_names,srcdir_name,\
    mode_has_mpi,mode_has_seq,mode_is_core

from typing import Any

def compilers_flags( **kwargs: Any ) -> dict[str, str]:
    flags = { 'CFLAGS':"", 'CXXFLAGS':"", 'FFLAGS':"", }
    if cflags := nonzero_keyword( "cflags",**kwargs ):
        flags["CFLAGS"] = cflags
    if cxxflags := nonzero_keyword( "cxxflags",**kwargs ):
        flags["CCXXFLAGS"] = cxxflags
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
    if mode_is_core( **kwargs ): return "","No compilers in core mode"
    trace_string( "Exporting compilers",**kwargs )
    compilers = compilers_names( **kwargs )
    script = ""; cont = ""
    for key,val in compilers.items():
        trace_string( f" .. Setting compiler: {key}={val}",**kwargs )
        script += f"""
export {key}={val}
echo Export {key}={val}
whichcomp=$( which {val} )
if [ $? -gt 0 ] ; then
  echo FAILURE: could not determine {val} && exit 1
fi
echo where {val}=${{whichcomp}}
            """
    return script,"Compiler settings"

# this routine is called through the above two wrappers
# from `start_test_stage'
def load_compiler_and_mpi_script( modules_to_load : str,**kwargs: Any ) -> str:
    title : str = f"Load compiler and mpi and modules: {modules_to_load}"
    errmsg : str = f"Failed to load compiler and mpi and modules: {modules_to_load}"
    _,compiler,compilerversion,_,mpi,mpiversion = family_names( **kwargs )
    modulepath = nonzero_keyword( "modulepath",**kwargs )
    if not ( redirect := nonzero_keyword( "redirect",**kwargs ) ):
        redirect = ""
    loadscript : str = ""
    #
    # Start by defining some functions
    #
    loadscript += f"""
# Non-redirected return code reporting
function modulereport () {{
if [ $1 -gt 0 ] ; then
    echo FAILURE module command failed: $2
    echo Output: && module -t $3
    exit
else
    echo SUCCESS module command succeeded: $2
    echo Now loaded: && modulelist
fi {redirect}
}}
    """
    loadscript += """
# Single line module listing
function modulelist ()
{ module -t list 2>&1 | sort | tr '\n' ' ' && echo
}
        """
    loadscript += f"""
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
    #
    # Now the actual script
    #
    loadscript += f"""
echo
echo Module setup starts here {redirect}

modulecommand "module purge" "purge"

export LMOD_SYSTEM_DEFAULT_MODULES=TACC

modulecommand "reset" "reset"
    """
    if not mode_is_core( **kwargs ):
        loadscript += f"""
if [ ! -z "${{TACC_FAMILY_MPI}}" ] ; then
  modulecommand "unload mpi" "-f unload ${{TACC_FAMILY_MPI}}"
fi

modulecommand "unload compiler" "unload ${{TACC_FAMILY_COMPILER}}"

echo .... After reset: {redirect}
modulelist {redirect}

echo .... Set modulepath {redirect}
export MODULEPATH={modulepath}
echo MODULEPATH=${{MODULEPATH}} {redirect}
modulecommand "Can we load compiler?" "avail {compiler}/{compilerversion}" display

modulecommand "Load compiler" "load {compiler}/{compilerversion}"
    """
    if nonzero_keyword( "BLASLAPACK",**kwargs ):
        if comp := abort_on_zero_keyword( "COMPILER",**kwargs ):
            blas : str = ""
            if comp=="gcc": blas : str = "mkl"
            if comp=="nvidia" : bas = "nvpl"
            if nonnull(blas):
                loadscript += f"""
echo "Load blas/lapack library: {blas}"
modulecommand "load blas" "load {blas}"
                """
    if mode_has_mpi( **kwargs ):
        loadscript += f"""
modulecommand "Load mpi" "load {mpi}/{mpiversion}"
        """
    if nonnull( modules_to_load ):
        loadscript += f"""
echo .... Load packages \"{modules_to_load}\" {redirect}
        """
        for modver in modules_to_load.split(" "):
            module,slash,version = module_and_version_to_load(modver,**kwargs )
            loadscript += f"""
modulecommand "load module: {module}{slash}{version}" "load {module}{slash}{version}"
            """
    else:
        echo_warning( "not loading any modules",**kwargs )
    loadscript += f"""
echo Module listing:
modulelist
echo -e \"End of module proper testing\n"
    """
    return loadscript

def module_and_version_to_load( modver : str,**kwargs ) -> tuple[str,str,str]:
    if modslshver := re.match( r'^([^/]+)(/)([^/]+)$',modver ):
        # if there was a slash, keep original mod+ver
        return modslshver.groups()
    else:
        # no slash, let's see if we can find a version
        module : str = modver
        # no version required, let's see if the environment has one
        version = module_version_from_env( modver,**kwargs )
        if nonnull( version ):
            return module,"/",version
            modver = f"{module}/{version}"
        else:
            # no slash and no environment version, so load default
            return module,"",""

modulelonglist : str = """
function modulelist ()
{
    local compiler=$( module -t list "${TACC_FAMILY_COMPILER}" 2>&1 );
    local mpi=$( module -t list ${TACC_FAMILY_MPI} 2>&1 );
    local modules=$( module -t list 2>&1 | grep -v $compiler | grep -v $mpi | sort );
    for m in $compiler $mpi cont $modules;
    do
        if [ $m = "cont" ]; then
            echo "----------------";
        else
            loc=$(module -t show $m 2>&1 | sed -e 's?'${WORK}'?${WORK}?' );
            echo "$m : $loc";
        fi;
    done
}
        """

def module_proper_script( moduleslist : list[str],**kwargs : Any ) -> tuple[str,str]:
    script : str = f"echo \"Testing module proper for: {moduleslist}\"\n"
    if  nonzero_keyword("installing",**kwargs ):
        srcdir = srcdir_name( **kwargs )
        script += f"""
if [ ! -d "{srcdir}" ] ; then
    echo "FAILURE: Source directory {srcdir} does not exist"
    exit 1
fi
        """
    for modver in moduleslist:
        # strip any version number
        module,_ = f"{modver}/".split("/",maxsplit=1)
        script += f"""
modulecommand "load {modver}" "load {modver}"
nam=TACC_{module.upper()}_DIR
eval dir=\\${{$nam}}
if [ ! -d "${{dir}}" ] ; then
    echo "FAILURE: package dir $nam=$dir does not exist"
else
    echo "SUCCESS: package {modver} is at $dir"
fi
for e in BIN LIB INC ; do
    nam=TACC_{module.upper()}_${{e}}
    if [ ! -z "${{dir}}" -a ! -d "${{dir}}" ] ; then 
        echo "FAILURE: variable $nam set but dir $dir does not exist"
    fi
done
        """
    script += f"\necho End of module proper testing\n"
    return script,f"test modules"
