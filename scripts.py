################################################################
####
#### scripts.py : partial unix scripts
####
################################################################

import re

from MrPackMod.basics  import module_version_from_env
from MrPackMod.error   import isnull,nonnull,error_abort,nonzero_keyword,abort_on_zero_keyword
from MrPackMod.names   import compilers_names,family_names,\
    mode_has_mpi,mode_has_seq
from MrPackMod.tracing import trace_string,echo_string,echo_warning,trace_var

from typing import Any

def export_compilers_script( dummy : list[str],**kwargs: Any ) -> tuple[str,str]:
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
    loadscript : str = f"""
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
function modulelist ()
{ module -t list 2>&1 | sort | tr '\n' ' ' && echo
}
        """
    loadscript += f"""
function modulecommand () {{
    echo
    echo .... $1 : module $2 {redirect}
    if [ -z "$3" ] ; then 
      module -t $2 2>/dev/null
    else
      module -t $2
    fi
    modulereport $? "$1" "$2"
}}
    """
    loadscript += f"""
echo .... Module setup {redirect}

modulecommand "module purge" "purge"

modulecommand "load basics" "reset"

if [ ! -z "${{TACC_FAMILY_MPI}}" ] ; then
  modulecommand "unload mpi" "unload ${{TACC_FAMILY_MPI}}"
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
    if mode_has_mpi( **kwargs ):
        loadscript += f"""
modulecommand "Load mpi" "load {mpi}/{mpiversion}"
        """
    if nonnull( modules_to_load ):
        loadscript += f"""
echo .... Load packages \"{modules_to_load}\" {redirect}
        """
        for mod in modules_to_load.split(" "):
            if nonnull( ver := module_version_from_env( mod,**kwargs ) ):
                modver = f"{mod}/{ver}"
            else:
                modver = mod
            loadscript += f"""
modulecommand "load module: {modver}" "load {modver}"
            """
    else:
        echo_warning( "not loading any modules",**kwargs )
    loadscript += f"""
echo Module listing:
modulelist
    """
    return loadscript

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
