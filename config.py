##
## standard python modules
##
import re
import os

#
# my modules
#
import modules
from install import open_logfile,close_logfile
from process import echo_string,trace_string,\
    nonnull,nonzero_env,abort_on_zero_keyword

def setting_from_env_or_rc( name,env,default,rc_files,**kwargs ):
    val = ""
    for file in rc_files:
        with open( file,"r" ) as rc:
            for line in rc.readlines():
                line = line.strip()
                if re.match( r"\s*#",line ): continue
                if re.match( name,line ):
                    val = re.search( fr"^\s*{name}\s*=\s*([A-Za-z0-9_]+)\s*$",line ).groups()[0]
                    trace_string(
                        f"file <<{file}>> found setting for {name}: {val}",
                        **kwargs )
                    return val
    osval = os.getenv( env,default )
    trace_string( f"environment variable {name}: {osval}",**kwargs )
    return osval

def config_from_rc_files( config_dict ):
    system   = abort_on_zero_keyword( "system",**config_dict )
    compiler = abort_on_zero_keyword( "compiler",**config_dict )
    rc_dir = f"{os.getcwd()}/.."
    if not os.path.isdir(rc_dir):
        raise Exception( f"Non-existing dir for rc files: {rc_dir}" )
    rc0 = f".mrpackmod_{system}_{compiler}rc"
    rc1 = f".mrpackmod_{compiler}rc"
    rc2 = f".mrpackmod_{system}rc"
    if os.path.exists( f"{rc_dir}/{rc0}" ):
        add_settings_from_config( f"{rc_dir}/{rc0}",config_dict )
    elif os.path.exists( f"{rc_dir}/{rc1}" ):
        add_settings_from_config( f"{rc_dir}/{rc1}",config_dict )
    elif os.path.exists( f"{rc_dir}/{rc2}" ):
        add_settings_from_config( f"{rc_dir}/{rc2}",config_dict )

def environment_settings( config_dict ):
    for module,_ in modules.loaded_modules( **config_dict,terminal=None ):
        #echo_string( f"investigate module: {module}",**kwargs )
        for ext in [ "dir", "inc", "lib", "bin", ]:
            macro = f"TACC_{module.upper()}_{ext.upper()}"
            if val := nonzero_env( macro,**config_dict ):
                #echo_string( f"Macro {macro}: {val}",**kwargs )
                config_dict[macro] = val

def add_settings_from_config( configfile,configuration_dict ):
    tracing = configuration_dict.get("tracing",False)
    with open(configfile,"r") as configuration_file:
        trace_string( f"Read configuration: {configfile}",**configuration_dict )
        saving = False
        for line in configuration_file.readlines():
            line = line.strip(); line = line.lstrip("let ") ## WARNING
            if re.match( r'^\s*#',     line ): continue
            if re.match( r'^[ \t]*$',line ): continue
            # either a definition line, or a continuation
            if keyval := re.search( r'^\s*([A-Za-z0-9_]*)\s*=\s*(.*)$',line ):
                key,val = keyval.groups()
            elif saving:
                # we inherit key from the previous iteration
                # we also inherit val & extend it with the current line
                trace_string( f" .. building up key={key} with: {line}" )
                val += line
            else:
                raise Exception( f"Can not parse: <<{line}>>\nin: {configfile}" )
            if re.search( r'\\$',val ):
                # if the, possibly compounded, line is still to be continued:
                val = val.strip( r'\\' )
                saving = True
                continue
            else:
                saving = False # time to ship out
                add_new_dict_item( key,val,configuration_dict )

def system_settings( configuration_dict,rc_files,**kwargs ):
    for k,v in {
            'system':setting_from_env_or_rc(
                "SYSTEM","TACC_SYSTEM","UNKNOWN_SYSTEM",
                rc_files,**kwargs ),
            # compiler
            'compiler':setting_from_env_or_rc(
            "COMPILER", "TACC_FAMILY_COMPILER","UNKNOWN_COMPILER",
                rc_files,**kwargs  ),
            'compilerversion':setting_from_env_or_rc(
                "COMPILERVERSION", "TACC_FAMILY_COMPILER_VERSION","UNKNOWN_COMPILER_VERSION",
                rc_files,**kwargs  ),
            # mpi
            'mpi':setting_from_env_or_rc(
                "MPI", "TACC_FAMILY_MPI","UNKNOWN_MPI",
                rc_files,**kwargs  ),
            'mpiversion':setting_from_env_or_rc(
                "MPIVERSION", "TACC_FAMILY_MPI_VERSION","UNKNOWN_MPI_VERSION",
                rc_files,**kwargs  ),
            }.items():
        configuration_dict[k] = v
    if configuration_dict['system'] == "vista":
        configuration_dict['blaslapack_inc'] = setting_from_env_or_rc(
            "BLASLAPACK_INC","TACC_NVPL_INC","NO_NVPL_INC_SETTING",
            rc_files,**kwargs )
        configuration_dict['blaslapack_lib'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","TACC_NVPL_LIB","NO_NVPL_LIB_SETTING",
            rc_files,**kwargs )
        configuration_dict['blaslapack_libs'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","nvpl_blas_lp64_seq;nvpl_blas_core",
            "NO_NVPL_LIBS_SETTING",
            rc_files,**kwargs )
    else:
        configuration_dict['blaslapack_inc'] = setting_from_env_or_rc(
            "BLASLAPACK_INC","TACC_MKL_INC","NO_MKL_INC_SETTING",
            rc_files,**kwargs )
        configuration_dict['blaslapack_lib'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","TACC_MKL_LIB","NO_MKL_LIB_SETTING",
            rc_files,**kwargs )
        configuration_dict['blaslapack_libs'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","mkl_intel_lp64;mkl_sequential;mkl_core;pthread",
            "NO_MKL_LIBS_SETTING",
            rc_files,**kwargs )

def install_settings( configuration_dict,rc_files,**kwargs ):
    tracing = kwargs.get("tracing")
    for k,v in {
            'homedir':setting_from_env_or_rc(
                "HOMEDIR", "HOMEDIR", "NO_HOMEDIR_GIVEN",
                rc_files,**kwargs  ),
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
            'builddirroot':setting_from_env_or_rc(
                "BUILDDIRROOT", "BUILDDIRROOT","",
                rc_files,**kwargs  ),
            'moduleroot':setting_from_env_or_rc(
                "MODULEROOT", "MODULEROOT","NO_MODULEROOT_GIVEN",
                rc_files,**kwargs  ),
            'moduledir':setting_from_env_or_rc(
                "MODULEDIR", "MODULEDIR","",
                rc_files,**kwargs  ),
            # optional stuff
            'installext':setting_from_env_or_rc(
                "INSTALLEXT", "INSTALLEXT", "",
                rc_files,**kwargs  ),
            'moduleversionextra':setting_from_env_or_rc(
                "MODULEVERSIONEXTRA", "MODULEVERSIONEXTRA", "",
                rc_files,**kwargs  ),
    }.items():
        configuration_dict[k] = v

def expr_value( expr,**kwargs ):
    # expression is a key or literal
    if osval := os.getenv(expr):
        return osval
    elif keyval := kwargs.get(expr):
        return keyval
    else:
        return expr

def add_new_dict_item( newkey,newval,config_dict ):
    newval = newval.strip('\n').strip(' ')
    for key,val in config_dict.items():
        if not type(val) is str: continue
        searchstring = '${'+key+'}'
        oldval = newval
        newval = newval.replace( searchstring,val )
        if oldval!=newval:
            trace_string( f"replace: {key} => {val}",**config_dict )
    config_dict[newkey] = newval
    trace_string( f"Setting: {newkey} = {newval} from config",**config_dict )

def read_config(configfile,tracing=False):
    rc_name = ".mrpackmodrc"
    rc_files = [ rc for rc in [ rc_name, f"../{rc_name}",
                                f"{os.path.expanduser('~')}/{rc_name}" 
                               ] if os.path.exists(rc) ]
    #print( f"found rc files: {rc_files}" )
    configuration_dict = {
        'buildsystem':"cmake",
        'modules':"", 'mode':"seq",
        'PACKAGE':"all", 'PACKAGEVERSION':"0.0",
        'tracing':tracing,
        'logfiles':{}, # name,handle pairs
        'scriptdir':os.getcwd(),
    }
    system_settings      ( configuration_dict,rc_files,tracing=tracing )
    logname,loghandle = open_logfile( "setup",configuration_dict )
    trace_string( f"system settings:\n{configuration_dict}",**configuration_dict )
    install_settings     ( configuration_dict,rc_files,tracing=tracing )
    environment_settings ( configuration_dict )
    config_from_rc_files ( configuration_dict )
    if not os.path.exists(configfile):
        raise Exception( f"No config file <<{configfile}>> in dir {os.getcwd()}" )
    add_settings_from_config( configfile,configuration_dict )
    trace_string( f"Configuration dict:\n{configuration_dict}",
                  **configuration_dict )
    close_logfile( logname,loghandle,configuration_dict )
    return configuration_dict
