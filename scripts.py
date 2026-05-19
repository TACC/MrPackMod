################################################################
####
#### scripts.py : partial unix scripts
####
################################################################

import re

from MrPackMod.basics  import loaded_module_version
from MrPackMod.error   import isnull,nonnull,error_abort,nonzero_keyword,abort_on_zero_keyword
from MrPackMod.names   import compilers_names,family_names
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
    loadscript : str = ""
    if not ( redirect := nonzero_keyword( "redirect",**kwargs ) ):
        redirect = ""
    modulereport = f"""
function modulereport () {{
if [ $1 -gt 0 ] ; then
    echo FAILURE module command failed: $2 && exit
else
    echo Loaded: && modulelist
fi {redirect}
}}
    """
    if nonzero_keyword( "moduletrace",**kwargs ):
        loadscript += """
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
    else:
        loadscript += """
function modulelist ()
{ module -t list 2>&1 | sort | tr '\n' ' ' && echo
}
        """
    loadscript += f"""
echo .... Module reset {redirect}
module -t purge 2>/dev/null
echo .... Loading basic modules {redirect}
module -t reset 2>/dev/null
if [ ! -z "${{TACC_FAMILY_MPI}}" ] ; then
  module -ft unload ${{TACC_FAMILY_MPI}}
fi
modulereport $? "module purge/reset"

echo .... Set modulepath {redirect}
export MODULEPATH={modulepath}
echo MODULEPATH=$MODULEPATH | tr ':' '\n' {redirect}
echo .... Can we load compiler {compiler}/{compilerversion} {redirect}
module -t avail {compiler}/{compilerversion} 2>&3
{modulereport}

echo .... Load compiler {compiler}/{compilerversion} {redirect}
module -t load {compiler}/{compilerversion} 2>/dev/null
modulereport $? "load {compiler}/{compilerversion}"
    """
    if kwargs.get("MODE")=="mpi":
        loadscript += f"""
echo .... Load mpi {redirect}
module -t load {mpi}/{mpiversion} 2>/dev/null
modulereport $? "load {mpi}/{mpiversion}"
        """
    if nonnull( modules_to_load ):
        loadscript += f"""
echo .... Load packages \"{modules_to_load}\" {redirect}
        """
        for mod in modules_to_load.split(" "):
            if ver := loaded_module_version( mod,**kwargs ):
                modver = f"{mod}/{ver}"
            else:
                modver = mod
            loadscript += f"""
echo .... load {modver} {redirect}
module -t load {modver} 2>/dev/null
modulereport $? "load {modver}"
            """
    else:
        echo_warning( "not loading any modules",**kwargs )
    loadscript += f"""
echo Module listing:
modulelist
    """
    return loadscript

