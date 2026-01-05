##
## standard python modules
##
import re
import os

#
# my modules
#
import modules
from process import echo_string,nonnull,nonzero_env,abort_on_zero_keyword

def setting_from_env_or_rc( name,env,default,rc_files ):
    val = ""
    for file in rc_files:
        with open( file,"r" ) as rc:
            for line in rc.readlines():
                line = line.strip()
                if re.match( r"\s*#",line ): continue
                if re.match( name,line ):
                    val = re.search( fr"^\s*{name}\s*=\s*([A-Za-z0-9_]+)\s*$",line ).groups()[0]
                    #print( f"found setting for {name}: {val}" )
                    return val
    return os.getenv( env,default )

def config_from_rc_files( config_dict,macros ):
    system   = abort_on_zero_keyword( "system",**config_dict )
    compiler = abort_on_zero_keyword( "compiler",**config_dict )
    rc_dir = f"{os.getcwd()}/.."
    if not os.path.isdir(rc_dir):
        raise Exception( f"Non-existing dir for rc files: {rc_dir}" )
    rc0 = f".mrpackmod_{system}_{compiler}rc"
    rc1 = f".mrpackmod_{compiler}rc"
    rc2 = f".mrpackmod_{system}rc"
    if os.path.exists( f"{rc_dir}/{rc0}" ):
        add_settings_from_config( f"{rc_dir}/{rc0}",config_dict,macros )
    elif os.path.exists( f"{rc_dir}/{rc1}" ):
        add_settings_from_config( f"{rc_dir}/{rc1}",config_dict,macros )
    elif os.path.exists( f"{rc_dir}/{rc2}" ):
        add_settings_from_config( f"{rc_dir}/{rc2}",config_dict,macros )

def environment_macros( **kwargs ):
    macros = {}
    for module,_ in modules.loaded_modules( **kwargs,terminal=None ):
        #echo_string( f"investigate module: {module}",**kwargs )
        for ext in [ "dir", "inc", "lib", "bin", ]:
            macro = f"TACC_{module.upper()}_{ext.upper()}"
            if val := nonzero_env( macro,**kwargs ):
                #echo_string( f"Macro {macro}: {val}",**kwargs )
                macros[macro] = val
    return macros

def add_settings_from_config( configfile,configuration_dict,macros ):
    tracing = configuration_dict.get("tracing",False)
    with open(configfile,"r") as configuration_file:
        if tracing:
            echo_string( f"Read configuration: {configfile}" )
        saving = False
        for line in configuration_file.readlines():
            line = line.strip()
            if re.match( r'^#',     line ): continue
            if re.match( r'^[ \t]*$',line ): continue
            if letdef := re.search( r'^let\s*([A-Za-z0-9_]*)\s*=\s*(.*)$',line ):
                key,val = letdef.groups()
                # macro with literal key
                envval = os.getenv( key )
                if nonnull( envval ):
                    macros[key] = envval
                else: macros[key] = val
            elif keyval := re.search( r'^\s*([A-Za-z0-9_]*)\s*=\s*(.*)$',line ):
                key,val = keyval.groups()
                envval = os.getenv( key )
            elif saving:
                # we inherit key from the previous iteration
                # we also inherit val & extend it with the current line
                if tracing:
                    echo_string( f" .. building up key={key} with: {line}" )
                val += line
            else:
                raise Exception( f"Can not parse: <<{line}>>")
            key = key.lower(); val = val.strip('\n').strip(' ')
            if re.search( r'\\$',val ):
                # if the, possibly compounded, line is still to be continued:
                val = val.strip( r'\\' )
                saving = True
                continue
            else: saving = False # time to ship out
            for m in macros:
                searchstring = '${'+m+'}'
                val = val.replace( searchstring,macros[m] )
            if nonnull( envval ):
                configuration_dict[key] = envval
                if tracing:
                    echo_string( f"Setting: {key} = {envval} from environment" )
            else:
                configuration_dict[key] = val
                if tracing:
                    echo_string( f"Setting: {key} = {val} from config" )

def system_settings( configuration_dict,rc_files ):
    for k,v in {
            'system':setting_from_env_or_rc(
                "SYSTEM","TACC_SYSTEM","UNKNOWN_SYSTEM",rc_files),
            # compiler
            'compiler':setting_from_env_or_rc(
            "COMPILER", "TACC_FAMILY_COMPILER","UNKNOWN_COMPILER",rc_files ),
            'compilerversion':setting_from_env_or_rc(
                "COMPILERVERSION", "TACC_FAMILY_COMPILER_VERSION","UNKNOWN_COMPILER_VERSION",rc_files ),
            # mpi
            'mpi':setting_from_env_or_rc(
                "MPI", "TACC_FAMILY_MPI","UNKNOWN_MPI",rc_files ),
            'mpiversion':setting_from_env_or_rc(
                "MPIVERSION", "TACC_FAMILY_MPI_VERSION","UNKNOWN_MPI_VERSION",rc_files ),
            }.items():
        configuration_dict[k] = v
    if configuration_dict['system'] == "vista":
        configuration_dict['blaslapack_inc'] = setting_from_env_or_rc(
            "BLASLAPACK_INC","TACC_NVPL_INC","NO_NVPL_INC_SETTING",rc_files)
        configuration_dict['blaslapack_lib'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","TACC_NVPL_LIB","NO_NVPL_LIB_SETTING",rc_files)
        configuration_dict['blaslapack_libs'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","nvpl_blas_lp64_seq;nvpl_blas_core",
            "NO_NVPL_LIBS_SETTING",rc_files)
    else:
        configuration_dict['blaslapack_inc'] = setting_from_env_or_rc(
            "BLASLAPACK_INC","TACC_MKL_INC","NO_MKL_INC_SETTING",rc_files)
        configuration_dict['blaslapack_lib'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","TACC_MKL_LIB","NO_MKL_LIB_SETTING",rc_files)
        configuration_dict['blaslapack_libs'] = setting_from_env_or_rc(
            "BLASLAPACK_LIB","mkl_intel_lp64;mkl_sequential;mkl_core;pthread",
            "NO_MKL_LIBS_SETTING",rc_files)

def install_settings( configuration_dict,rc_files ):
    for k,v in {
            'homedir':setting_from_env_or_rc(
                "HOMEDIR", "HOMEDIR", "NO_HOMEDIR_GIVEN",rc_files ),
            'srcpath':setting_from_env_or_rc(
                "SRCPATH", "SRCPATH", "",rc_files ),
            'packageroot':setting_from_env_or_rc(
                "PACKAGEROOT", "PACKAGEROOT","NO_PACKAGEROOT_GIVEN",rc_files ),
            'installroot':setting_from_env_or_rc(
                "INSTALLROOT", "INSTALLROOT","NO_INSTALLROOT_GIVEN",rc_files ),
            'installpath':setting_from_env_or_rc(
                "INSTALLPATH", "INSTALLPATH","",rc_files ),
            'builddirroot':setting_from_env_or_rc(
                "BUILDDIRROOT", "BUILDDIRROOT","",rc_files ),
            'moduleroot':setting_from_env_or_rc(
                "MODULEROOT", "MODULEROOT","NO_MODULEROOT_GIVEN",rc_files ),
            'moduledir':setting_from_env_or_rc(
                "MODULEDIR", "MODULEDIR","",rc_files ),
            # optional stuff
            'installext':setting_from_env_or_rc(
                "INSTALLEXT", "INSTALLEXT", "",rc_files ),
            'moduleversionextra':setting_from_env_or_rc(
                "MODULEVERSIONEXTRA", "MODULEVERSIONEXTRA", "",rc_files ),
    }.items():
        configuration_dict[k] = v

def read_config(configfile,tracing=False):
    rc_name = ".mrpackmodrc"
    rc_files = [ rc for rc in [ rc_name, f"../{rc_name}",
                                f"{os.path.expanduser('~')}/{rc_name}" 
                               ] if os.path.exists(rc) ]
    #print( f"found rc files: {rc_files}" )
    configuration_dict = {
        'scriptdir':os.getcwd(),
        'buildsystem':"cmake",
        'modules':"",
    }
    system_settings ( configuration_dict,rc_files )
    install_settings( configuration_dict,rc_files )
    macros = environment_macros( **configuration_dict )
    config_from_rc_files( configuration_dict,macros )
    if not os.path.exists(configfile):
        raise Exception( f"No config file <<{configfile}>> in dir {os.getcwd()}" )
    add_settings_from_config( configfile,configuration_dict,macros )
    if tracing:
        print(configuration_dict)
    return configuration_dict
