##
## standard python modules
##
import re
import os
import sys
from typing import Any,Optional,Tuple

#
# my modules
#
from MrPackMod.basics     import echo_string,trace_string,echo_warning,\
    abort_on_zero_keyword,error_abort,\
    line_strip_conditionals
from MrPackMod.modulefile import loaded_modules
from MrPackMod.error      import nonnull,nonzero_env
from MrPackMod.names      import srcdir_name,builddir_name,prefixdir_name
from MrPackMod.process    import remove_macros
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
    newval = remove_macros( newval,**config_dict )
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
        totalline : str = ""
        for line in configuration_file.readlines():
            line = line.strip("\n")

            # ignore comments and blank lines
            if re.match( r'^\s*#',     line ): continue
            if re.match( r'^[ \t]*$',line ): continue

            if saving:
                trace_string( f" .. building up line with: {line}",**output )
                totalline += " "+line
            else: totalline = line

            if re.search( r'\\$',totalline ):
                # if the, possibly compounded, line is still to be continued:
                totalline = totalline.strip( r'\\' )
                saving = True
                continue
            else:
                # VLE move the abort into the process function
                if ( status := process_total_line( totalline,configfile,config_dict,**output ) ) is not None:
                    if status in ["exit","return"] : break
                    saving = False ; totalline = ""
                else:
                    error_abort( f"Can not parse: <<{line}>>\nin: {configfile}",**config_dict )

def process_total_line( line : str,configfile : str,
                        config_dict : dict[str,Any],**output : Any ) -> Optional[str]:
    trace_string( f"Processing line  : {line}",**{ **config_dict,**output } )
    line,accept = line_strip_conditionals( line,**config_dict,**output )
    if not accept: return "reject"
    trace_string( f" .. unconditional: {line}",**{ **config_dict,**output } )

    # detect and strip conditionals, return acceptability & line to process
    # if `nowarn' is set, we can deal with undefined macros
    line = remove_macros( line,**config_dict )
    trace_string( f" .. expanded     : {line}",**{ **config_dict,**output } )
    if re.match( r'exit',line )  : return "exit"
    if re.match( r'return',line ): return "return"
    if callitaday := re.match( r'\s*abort\s+(.*)$',line ):
        if nonnull( msg := callitaday.groups()[0] ):
            print( f"\n{msg}\n" )
            sys.exit(1)
    if include := re.search( r'^\s*include\s+(.+)$',line ):
        includefile = include.groups()[0]
        trace_string( f"Include file: {includefile}",**config_dict,**output )
        add_settings_from_config( includefile,config_dict )
        return "normal"
    elif export := re.search( r'export\s+(.+)$',line ):
        trace_string( f"Adding export: <<{line}>>",**config_dict,**output )
        config_dict["exports"].append(line)
        return "normal"
    elif unset := re.search( r'unset\s+(.+)$',line ):
        trace_string( f"Adding unset: <<{line}>>",**config_dict,**output )
        config_dict["unsets"].append(line)
        return "normal"
    elif keyval := re.search( r'^\s*([A-Za-z0-9_]*)\s*([\+\*]?=)\s*(.*)$',line ):
        process_key_setting( keyval.groups(),config_dict,**output )
        return "normal"
    else: return None

##
## We have determined a variable assignment
##
def process_key_setting( keyval,config_dict,**output ) -> None:
    key,assign,val = keyval
    if assign in [ "+=","*=" ]:
        type : str = "addition"
    else: type = "assignment"
    trace_string( f" .. {type} {key} {assign} {val}",**{ **config_dict,**output } )

    # start generating compiler/mpi stuff names
    if key in derived_setting_triggers:
        set_derived_settings( config_dict,**output )

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

##
## Query system
## this should really only come from the environment
##
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

##
## High level settings such as
## - compiler
## - location of build/install/module files
##
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

##
## Inspect loaded modules for integrity
## and insert their variables into the configuration dict
##
def module_settings( config_dict: dict[str, Any],  ) -> None:
    mods : list[str] = \
        [ m for m,_ in
          loaded_modules( **config_dict, ) 
          + [ ["mkl",""], ["nvpl",""] ] ]
    trace_string( f"Setting variables from modules:\n{mods}",**config_dict )
    nowarn : bool = config_dict.get("nowarn") is not None
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
    system   = config_dict.get( "SYSTEM" )
    compiler = config_dict.get( "COMPILER" )
    # assume that we are in the makefiles/package dir
    rc_dir = f"{os.getcwd()}/.."
    if os.path.isdir(rc_dir):
        trace_string( f"Looking for rc files in{rc_dir}",**config_dict,**output )
    else:
        error_abort( f"Non-existing dir for rc files: {rc_dir}",**config_dict,**output )
    ##
    ## General settings,
    ## first system specific, then general
    ##
    rc0 = f"{rc_dir}/.mrpackmodrc"
    if os.path.exists( f"{rc0}" ):
        add_settings_from_config( f"{rc0}",config_dict,**output )
    else:
        rc2 = f"{rc_dir}/.mrpackmod_{system}rc"
        if os.path.exists( f"{rc2}" ):
            add_settings_from_config( f"{rc2}",config_dict,**output )
    ##
    ## Compiler settings,
    ## first system specific, then general
    ##
    if nonnull(compiler):
        rc3 = f"{rc_dir}/.mrpackmod_{system}_{compiler}rc"
        if os.path.exists( f"{rc3}" ):
            add_settings_from_config( f"{rc3}",config_dict,**output )
        else:
            rc1 = f"{rc_dir}/.mrpackmod_{compiler}rc"
            if os.path.exists( f"{rc1}" ):
                add_settings_from_config( f"{rc1}",config_dict,**output )

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
derived_setting_triggers = [
    "BUILDSYSTEM",
    "EXISTENCETEST","CMAKETEST","MAKETEST",
    ]
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
        ( "configure",
          **{ **configuration_dict,**kwargs,
              "skipmodules":True,"linedisplay":trace_string }
         )

    ##
    ## Context settings: system, compiler, blaslapack
    ##

    rc_types = [ "" ]
    rc_files = [ rc for rc in
                 [ f"{location}/mrpackmod{type}rc"
                   for type in rc_types
                   for location in [ ".","..",os.path.expanduser('~') ]
                   ]
                 if os.path.exists(rc) ]
    system_settings      ( configuration_dict,rc_files, )
    trace_string( f"system settings:\n{configuration_dict}",**configuration_dict,**output )

    system   = configuration_dict["SYSTEM"]
    compiler = configuration_dict["COMPILER"]
    rc_types = [ "",f"_{system}",f"_{compiler}" ]
    rc_files = [ rc for rc in
                 [ f"{location}/mrpackmod{type}rc"
                   for type in rc_types
                   for location in [ ".","..",os.path.expanduser('~') ]
                   ]
                 if os.path.exists(rc) ]
    install_settings     ( configuration_dict,rc_files,**output )

    # variables from installed modules
    module_settings ( configuration_dict, )
    config_from_rc_files ( configuration_dict,**output )

    ##
    ## Settings for this package specifically
    ##
    if not os.path.exists(configfile):
        raise Exception( f"No config file <<{configfile}>> in dir {os.getcwd()}" )
    # this may try to make the src dir, which should not if we are testing
    no_home : bool = kwargs.get("no_home",False)
    add_settings_from_config(
        configfile,configuration_dict,no_home=no_home,
        **output )
    trace_string( f"Configuration dict:\n{configuration_dict}",
                  **configuration_dict,**output )
    # close log file and test success/failure
    success,failure = end_test_stage( [],[],output,**configuration_dict )
