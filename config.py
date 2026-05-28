##
## standard python modules
##
import re
import os
from typing import Any, Tuple

#
# my modules
#
from MrPackMod.modulefile import loaded_modules
from MrPackMod.error      import nonnull,nonzero_env,abort_on_zero_keyword,error_abort
from MrPackMod.names      import srcdir_name,builddir_name,prefixdir_name
from MrPackMod.process    import line_strip_conditionals,remove_macros
from MrPackMod.tracing    import echo_string,trace_string,echo_warning
from MrPackMod.testing    import start_test_stage,end_test_stage,\
    OutputDict

additive_keys : list[str] = [ "DEPENDSON", "DEPENDSONCURRENT",
                              "MODULE", 
                              "CMAKEFLAGS","CONFIGUREFLAGS","PETSCFLAGS",
                             ]
list_keys     : list[str] = [ "CMAKETEST", "MAKETEST", "EXISTENCETEST",
                              "CLEANTARGET",
                             ]

def add_new_dict_item(
        newkey: str, assign: str, newval: str, config_dict: dict[str, Any],**output : Any ) -> None:
    """ Add a new value under the given key.
    Any macros in the value are expanded.
    Note: only one expansion pass, but macros can not contains macros anyway.
    If a key is added more than once, the initial value is silently overwritten,
    except for keys that are additive such as DEPENDSON, or if `assign' is `+='
    """
    newval = newval.strip('\n').strip(' ')
    newval = remove_macros( newval,config_dict )
    if ( newkey in additive_keys or assign in ["+=","*="] ) :
        if newkey in config_dict.keys() :
            if assign=="*=":
                config_dict[newkey] = f"{config_dict[newkey]}{newval}"
            else:
                config_dict[newkey] = f"{config_dict[newkey]} {newval}"
        else:
            # we tolerate "+=" if not previous value set
            config_dict[newkey] = newval
    elif newkey in list_keys:
        if newkey not in config_dict.keys() :
            config_dict[newkey] = []
        config_dict[newkey].append( newval )
        trace_string( f"Added test: {newkey}={config_dict[newkey]}",**config_dict,**output )
    else:
        config_dict[newkey] = newval
    trace_string( f"Setting {newkey}{assign}{newval} from config",**config_dict,**output )

def add_settings_from_config(
        configfile: str, config_dict: dict[str, Any], **output : Any ) -> None:
    tracing: bool = config_dict.get("tracing", False)
    with open(configfile,"r") as configuration_file:
        trace_string( f"Read configuration: {configfile}",**config_dict,**output )
        saving: bool = False
        for line in configuration_file.readlines():
            line = line.strip()
            if re.match( r'exit',line ) or re.match( r'return',line ): break
            if re.match( r'let ',line ):
                error_abort( f"obsolete syntax: <<{line}>>",**config_dict,**output )
            # ignore comments and blank lines
            if re.match( r'^\s*#',     line ): continue
            if re.match( r'^[ \t]*$',line ): continue
            # detect and strip conditionals, return acceptability & line to process
            line,accept = line_strip_conditionals( line,**config_dict,**output )
            if not accept: continue
            if False:
                continue
            elif include := re.search( r'^\s*include\s+(.+)$',line ):
                includefile = include.groups()[0]
                trace_string( f"Include file: {includefile}",**config_dict,**output )
                add_settings_from_config( includefile,config_dict )
            elif export := re.search( r'export\s+(.+)$',line ):
                line = remove_macros( line,config_dict )
                trace_string( f"Adding export: <<{line}>>",**config_dict,**output )
                config_dict["exports"].append(line)
            elif keyval := re.search( r'^\s*([A-Za-z0-9_]*)\s*([\+\*]?=)\s*(.*)$',line ):
                # definition line
                key,assign,val = keyval.groups()
                if assign in [ "+=","*=" ]:
                    trace_string( f" .. addition {key} {assign} {val}",
                                  **config_dict,**output )
                else:
                    trace_string( f" .. assignment {key} {assign} {val}",
                                  **config_dict,**output )
            elif saving:
                # continuation:
                # we inherit key from the previous iteration
                # we also inherit val & extend it with the current line
                trace_string( f" .. building up key={key} with: {line}",**output )
                val += line
            else:
                raise Exception( f"Can not parse: <<{line}>>\nin: {configfile}" )
            if re.search( r'\\$',val ):
                # if the, possibly compounded, line is still to be continued:
                val = val.strip( r'\\' )
                saving = True
                continue
            else:
                saving = False # time to add a value to the dict
                if envval := nonzero_env( key,**config_dict ):
                    # override with environment if specified
                    add_new_dict_item( key,assign,envval,config_dict,**output )
                else:
                    # use value deduced from file
                    add_new_dict_item( key,assign,val,config_dict,**output )

def setting_from_env_or_rc( name: str, env: str, default: str, rc_files: list[str], **kwargs: Any ) -> str:
    val : str = ""
    for file in rc_files:
        with open( file,"r" ) as rc:
            for line in rc.readlines():
                line = line.strip()
                if re.match( r"\s*#",line ): continue
                if re.match( name,line ):
                    m = re.search(
                        fr"^\s*{name}\s*=\s*([A-Za-z0-9_]+)\s*$",
                        line,
                    )
                    assert m is not None
                    val = m.groups()[0]
                    trace_string(
                        f"Setting {name}={val} found in file <<{file}>>.",
                        **kwargs )
                    return val
    osval = os.getenv( env,default )
    trace_string( f"Setting {name}={osval} found in environment.",**kwargs )
    return osval

def system_settings(
    config_dict: dict[str, Any],
    rc_files: list[str],
    **kwargs: Any,
) -> None:
    for k,v in {
            'SYSTEM':setting_from_env_or_rc(
                "SYSTEM","TACC_SYSTEM","UNKNOWN_SYSTEM",
                rc_files,**kwargs ),
            # compiler family
            'COMPILER':setting_from_env_or_rc(
            "COMPILER", "TACC_FAMILY_COMPILER","",
                rc_files,**kwargs  ),
            'COMPILERVERSION':setting_from_env_or_rc(
                "COMPILERVERSION", "TACC_FAMILY_COMPILER_VERSION","",
                rc_files,**kwargs  ),
            # mpi family
            'MPI':setting_from_env_or_rc(
                "MPI", "TACC_FAMILY_MPI","",
                rc_files,**kwargs  ),
            'MPIVERSION':setting_from_env_or_rc(
                "MPIVERSION", "TACC_FAMILY_MPI_VERSION","",
                rc_files,**kwargs  ),
            # compiler names
            'CC':setting_from_env_or_rc(
                "CC","TACC_CC","NO_CC_DEFINED",rc_files,**kwargs ),
            'FC':setting_from_env_or_rc(
                "FC","TACC_FC","NO_FC_DEFINED",rc_files,**kwargs ),
            'CXX':setting_from_env_or_rc(
                "CXX","TACC_CXX","NO_CXX_DEFINED",rc_files,**kwargs ),
            }.items():
        config_dict[k] = v
    if config_dict["SYSTEM"] == "vista":
        config_dict['blaslapack_inc'] = setting_from_env_or_rc(
            "BLASLAPACK_INC","TACC_NVPL_INC","NO_NVPL_INC_SETTING",
            rc_files,**kwargs )
        config_dict['blaslapack_lib'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","TACC_NVPL_LIB","NO_NVPL_LIB_SETTING",
            rc_files,**kwargs )
        config_dict['blaslapack_libs'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","nvpl_blas_lp64_seq;nvpl_blas_core",
            "NO_NVPL_LIBS_SETTING",
            rc_files,**kwargs )
    else:
        config_dict['blaslapack_inc'] = setting_from_env_or_rc(
            "BLASLAPACK_INC","TACC_MKL_INC","NO_MKL_INC_SETTING",
            rc_files,**kwargs )
        config_dict['blaslapack_lib'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","TACC_MKL_LIB","NO_MKL_LIB_SETTING",
            rc_files,**kwargs )
        config_dict['blaslapack_libs'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","mkl_intel_lp64;mkl_sequential;mkl_core;pthread",
            "NO_MKL_LIBS_SETTING",
            rc_files,**kwargs )

def install_settings(
        config_dict : dict[str, Any], rc_files : list[str], **kwargs: Any, ) -> None:
    tracing = kwargs.get("tracing")
    for k,v in {
            'homedir':setting_from_env_or_rc(
                "HOMEDIR", "HOMEDIR", "NO_HOMEDIR_GIVEN",
                rc_files,**kwargs  ),
            'modulepath':setting_from_env_or_rc(
                "MODULEPATH", "MODULEPATH", "NO_MODULEPATH_GIVEN",
                rc_files,**kwargs ),
            'srcpath':setting_from_env_or_rc(
                "SRCPATH", "SRCPATH", "",
                rc_files,**kwargs  ),
            'packageroot':setting_from_env_or_rc(
                "PACKAGEROOT", "PACKAGEROOT","NO_PACKAGEROOT_GIVEN",
                rc_files,**kwargs  ),
            'installroot':setting_from_env_or_rc(
                "INSTALLROOT", "INSTALLROOT","NO_INSTALLROOT_GIVEN",
                rc_files,**kwargs  ),
            'installpath':setting_from_env_or_rc(
                "INSTALLPATH", "INSTALLPATH","",
                rc_files,**kwargs  ),
            'downloadpath':setting_from_env_or_rc(
                "DOWNLOADPATH", "DOWNLOADPATH","",
                rc_files,**kwargs  ),
            'builddirroot':setting_from_env_or_rc(
                "BUILDDIRROOT", "BUILDDIRROOT","",
                rc_files,**kwargs  ),
            'moduleroot':setting_from_env_or_rc(
                "MODULEROOT", "MODULEROOT","NO_MODULEROOT_GIVEN",
                rc_files,**kwargs  ),
            'moduledir':setting_from_env_or_rc(
                "MODULEDIR", "MODULEDIR","",
                rc_files,**kwargs  ),
            'modulediradd':setting_from_env_or_rc(
                "MODULEDIRADD", "MODULEDIRADD","",
                rc_files,**kwargs  ),
            # optional stuff
            'INSTALLEXT':setting_from_env_or_rc(
                "INSTALLEXT", "INSTALLEXT", "",
                rc_files,**kwargs  ),
            'MODULENAMEALT':setting_from_env_or_rc(
                "MODULENAMEALT", "MODULENAMEALT", "",
                rc_files,**kwargs  ),
            'MODULEVERSIONEXTRA':setting_from_env_or_rc(
                "MODULEVERSIONEXTRA", "MODULEVERSIONEXTRA", "",
                rc_files,**kwargs  ),
    }.items():
        config_dict[k] = v

def environment_settings( config_dict: dict[str, Any], nowarn: bool = False ) -> None:
    mods : list[str] = \
        [ m for m,_ in
          loaded_modules( **config_dict, ) 
          + [ ["mkl",""], ["nvpl",""] ] ]
    trace_string( f"Setting variables from modules:\n{mods}",**config_dict )
    for module in mods:
        trace_string( f" .. settings from module: {module}",**config_dict )
        for ext in [ "dir", "inc", "lib", "bin", ]:
            macro = f"TACC_{module.upper()}_{ext.upper()}"
            if val := nonzero_env( macro,**config_dict ):
                if not os.path.isdir(val) and not nowarn:
                    echo_warning(
                        f"module {module}: path {val} does not exist for ext={ext}",
                        prefix=" .. ",**config_dict )
                config_dict[macro] = val

def config_from_rc_files( config_dict: dict[str, Any],**output ) -> None:
    system   = abort_on_zero_keyword( "SYSTEM",**config_dict )
    compiler = config_dict.get( "COMPILER" )
    # assume that we are in the makefiles/package dir
    rc_dir = f"{os.getcwd()}/.."
    if os.path.isdir(rc_dir):
        trace_string( f"Looking for rc files in{rc_dir}",**config_dict,**output )
    else:
        error_abort( f"Non-existing dir for rc files: {rc_dir}",**config_dict,**output )
    rc0 = f"{rc_dir}/.mrpackmodrc"
    if os.path.exists( f"{rc0}" ):
        add_settings_from_config( f"{rc0}",config_dict,**output )
    rc2 = f"{rc_dir}/.mrpackmod_{system}rc"
    if os.path.exists( f"{rc2}" ):
        add_settings_from_config( f"{rc2}",config_dict,**output )
    if nonnull(compiler):
        rc1 = f"{rc_dir}/.mrpackmod_{compiler}rc"
        if os.path.exists( f"{rc1}" ):
            add_settings_from_config( f"{rc1}",config_dict,**output )
    if nonnull(compiler):
        rc3 = f"{rc_dir}/.mrpackmod_{system}_{compiler}rc"
        if os.path.exists( f"{rc3}" ):
            add_settings_from_config( f"{rc3}",config_dict,**output )
    # trace_string(
    #     f"{rc0}: {has0}\n{rc1}: {has1}\n{rc2}; {has2}\n{rc3}: {has3}",
    #     **config_dict,**output )

def expr_value( expr: str, **kwargs: Any ) -> str:
    # expression is a key or literal
    if osval := os.getenv(expr):
        return osval
    elif keyval := kwargs.get(expr):
        return keyval
    else:
        return expr

#
# Keywords like SRCDIR that can be used in the user configuration
# see basics.derived_settings
#
def set_derived_settings( config_dict : dict[str,Any],**output ) -> None:
    # danger: when testing there is no srcdir
    config_dict["SRCDIR"]     = srcdir_name(    **config_dict,**output )
    config_dict["BUILDDIR"]   = builddir_name(  **config_dict,**output )
    config_dict["PREFIXDIR"]  = prefixdir_name( **config_dict,**output )

#
# Read configuration, starting with some basics
#
def read_config( configuration_dict : dict[str,Any], configfile: str, **kwargs: Any ) -> None:

    # create test process, open logfile;
    # note that we are not interested in modules here
    output : OutputDict = start_test_stage\
        ( "configure",configuration_dict,
          skipmodules=True,linedisplay=trace_string,
          scriptsdir=f"{os.getcwd()}/mpmscripts_config",
         )

    rc_name = ".mrpackmodrc"
    rc_files = [ rc for rc in [ rc_name, f"../{rc_name}",
                                f"{os.path.expanduser('~')}/{rc_name}" 
                               ] if os.path.exists(rc) ]
    system_settings      ( configuration_dict,rc_files, )
    trace_string( f"system settings:\n{configuration_dict}",**configuration_dict,**output )
    # install paths
    install_settings     ( configuration_dict,rc_files,**output )
    # variables from installed modules
    nowarn  : bool = kwargs.get("nowarn",False)
    environment_settings ( configuration_dict,nowarn=nowarn )
    config_from_rc_files ( configuration_dict,**output )
    if not os.path.exists(configfile):
        raise Exception( f"No config file <<{configfile}>> in dir {os.getcwd()}" )
    add_settings_from_config( configfile,configuration_dict,**output )
    set_derived_settings( configuration_dict,**kwargs,**output )
    trace_string( f"Configuration dict:\n{configuration_dict}",
                  **configuration_dict,**output )
    # close log file and test success/failure
    success,failure = end_test_stage( [],[],configuration_dict,output )
    return configuration_dict
