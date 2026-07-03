################################################################
####
#### scripts.py : partial unix scripts
####
################################################################

import os
import re

from MrPackMod.basics  import module_version_from_env,\
    trace_string,echo_string,echo_warning,trace_var,\
    abort_on_zero_keyword,nonzero_keyword,zero_keyword
from MrPackMod.error   import isnull,nonnull
from MrPackMod.names   import compilers_names,family_names,srcdir_name,\
    mode_has_mpi,mode_has_seq,mode_is_core

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
    if mode_is_core( **kwargs ): return "","No compilers in core mode"
    trace_string( "Exporting compilers",**kwargs )
    compilers = compilers_names( **kwargs )
    script : str = "\necho \"Now exporting compilers for cmake and such\""
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
    return script,"Export compiler settings"

def load_compiler_and_mpi_and_modules_script( modules_to_load : str,**kwargs: Any ) -> str:
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
    loadscript += modulereportfunction(  )
    loadscript += modulelistfunction()
    loadscript += modulecommandfunction( )
    loadscript += moduleproperfunction()

    #
    # Now the actual script
    #
    loadscript += modulepurgefunction()
    if not mode_is_core( **kwargs ):
        loadscript += compilerloadfunction( modulepath,compiler,compilerversion )
    if nonzero_keyword( "BLASLAPACK",**kwargs ):
        if comp := abort_on_zero_keyword( "COMPILER",**kwargs ):
            blas : str = ""
            if comp=="gcc": blas : str = "mkl"
            if comp=="nvidia" : blas = "nvpl"
            if nonnull(blas):
                loadscript += f"""
echo "Load blas/lapack library: {blas}"
modulecommand "load blas" "load {blas}"
                """
    if mode_has_mpi( **kwargs ):
        loadscript += mpiloadfunction( mpi,mpiversion )
    if nonnull( modules_to_load ) and zero_keyword( "skipmodules",**kwargs ):
        loadscript += modulesloadscript( modules_to_load,**kwargs )
    else:
        echo_warning( "not loading any modules",**kwargs )
    loadscript += f"""
echo Module listing:
modulelist
    """
    return loadscript,title

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

#
# This gets called only from do_config_tests and the `test' action
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
    script : str = f"""
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
    exit
else
    echo SUCCESS module command succeeded: $2
    local cmd="$3"
    # echo "cmd was <<$cmd>>"
    echo "Now loaded:"
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
    for e in BIN LIB INC ; do
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

export LMOD_SYSTEM_DEFAULT_MODULES=TACC

modulecommand "reset" "reset"
    """

def compilerloadfunction( modulepath : str,compiler : str,compilerversion : str,
                          redirect="" ) -> str:
    return f"""
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

def mpiloadfunction( mpi : str,mpiversion : str ) -> str:
    return f"""
modulecommand "Load mpi" "load {mpi}/{mpiversion}"
    """

def modulesloadscript( modules_to_load : str,**kwargs ) -> str:
    redirect : str = kwargs.get( "redirect","" )
    loadscript : str = f"""
echo ".... Load packages <<{modules_to_load}>>" {redirect}
    """
    for modver in modules_to_load.split(" "):
        if isnull(modver): continue
        module,slash,version = module_and_version_to_load(modver,**kwargs )
        modulepropertest,_ = one_module_proper_script( [modver],**kwargs )
        loadscript += f"""
modulecommand "load module: {module}{slash}{version}" "load {module}{slash}{version}"
{modulepropertest}
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

##
## Now the big scripts!
##

################################################################
####
#### CMake
####
################################################################

def cmake_configure_script( pcmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program = pcmakedirs[0]; cmakedirs = pcmakedirs[1:]

    script : str = ""
    # setup
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    if unset_cmdline := nonzero_unsets( **kwargs ):
        script += f"\n{unset_cmdline}\n"

    # cmake
    cmake = cmake_basic_command( **kwargs )
    cmakeflags = cmake_options( **kwargs )
    buildsettings = cmake_build_settings( **kwargs )
    # set src, build, prefix
    pathsettings = cmake_paths_settings( cmakedirs,**kwargs )
    # for the regression case only: define project macro
    if nonnull(program) : pathsettings += f" -D PROJECTNAME={program}"
    script += f"""
cmdline="{cmake} {buildsettings} {cmakeflags} {pathsettings}"
echo Doing cmake in pwd=${{PWD}}
echo .... cmake cmdline=$cmdline | sed -e 's/-D/\\n    -D/g' -e 's/-S /\\n    -S /' -e 's/-B /\\n    -B /'
eval $cmdline
if [ $? -eq 0 ] ; then
    echo SUCCESS: configure succeeded
else
    echo FAILURE: cmake failed
fi
    """
    _,builddir,_ = cmakedirs
    script += f"""\necho "builddir contents:"\nls {builddir}\n"""
    # VLE I can't get newlines in this script. Hm.
    script = script.replace( r'^ +-D(.*)$',r'  -D \1\\\n' )
    return script,"CMake configuring"

def cmake_build_script( pcmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program = pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir,builddir,prefixdir = cmakedirs
    # flags and options
    jcount          : str = kwargs.get("jcount","6")
    make            : str = f"make --no-print-directory V=1 VERBOSE=1 -j {jcount}"
    makebuildtarget : str = kwargs.get("makebuildtarget","")
    # execute make & make install
    trace_string( f"Making in builddir: {builddir}",**kwargs )
    if ninja := kwargs.get( "CMAKEUSENINJA" ):
        makeline = f"ninja install"
    else:
        makeline = f"{make} --no-print-directory V=1 VERBOSE=1 -j {jcount} {makebuildtarget}"
    script : str = f"""
if [ ! -d "{builddir}" ] ; then
    echo "FAILURE: no such build dir: {builddir}"
    exit  1
else
    echo "entering builddir: {builddir}"
fi
cd {builddir}

if [ ! -f makefile -a ! -f Makefile ] ; then
    echo "FAILURE: build dir {builddir} has no makefile or Makefile"
    exit 1
fi
{makeline}
if [ $? -eq 0 ] ; then
    echo SUCCESS: compilation succeeded
else
    echo FAILURE: compilation failed
fi
    """
    if extra_targets := nonzero_keyword( "extrabuildtargets" ):
        script += f"""
{make} {extra_targets}
        """
    if nonnull(prefixdir) and not ninja:
        script += f"""
{make} install
if [ $? -eq 0 ] ; then
    echo SUCCESS: installation succeeded
else
    echo FAILURE: installation failed
fi
        """
    return script,"CMake make and install"

def cmake_basic_command( **kwargs : Any ) -> str:
    cmake : str = kwargs.get( "CMAKENAME","cmake" )
    if nonzero_keyword( "CMAKEUSENINJA",**kwargs ):
        cmake = f"{cmake} -G Ninja"
    return f"TERM=dumb {cmake} -Wno-dev \
-D CMAKE_COMPILE_WARNING_AS_ERROR=OFF \
-D CMAKE_POLICY_VERSION_MINIMUM=3.13 \
-D CMAKE_VERBOSE_MAKEFILE=ON \
-D CMAKE_COLOR_MAKEFILE=OFF \
-D CMAKE_TERM_SUPPORTS_ANSI=OFF"

def cmake_options( **kwargs: Any ) -> str:
    cmakeflags = "  -D CMAKE_VERBOSE_MAKEFILE=ON  -D CMAKE_EXPORT_COMPILE_COMMANDS=ON"
    if standard := kwargs.get("CPPSTANDARD"):
        cmakeflags += f"  -D CMAKE_CXX_FLAGS=-std=c++{standard}"
    if flags := nonzero_keyword( "CMAKEFLAGS",**kwargs ):
        cmakeflags += f" -D MPM_CUSTOM_FLAGS=START {flags} "
    return cmakeflags.lstrip(" ")

def cmake_build_settings( **kwargs ) -> str:
    if kwargs.get("CMAKEBUILDDEBUG"):
        defaultbuild = "Debug"
    else: defaultbuild = "RelWithDebInfo"
    cmakebuildtype = kwargs.get("CMAKEBUILDTYPE",defaultbuild)
    if static := kwargs.get("buildstaticlibs"):
        buildsharedlibs = "OFF"
    else: buildsharedlibs = "ON"
    return f""" -D BUILD_SHARED_LIBS={buildsharedlibs}  -D CMAKE_BUILD_TYPE={cmakebuildtype} """

def cmake_paths_settings( cmakedirs : list[str],**kwargs ) -> str:
    srcdir,builddir,prefixdir = cmakedirs
    if nonnull( source := kwargs.get("CMAKESUBDIR") ):
        effectivesrcdir : str = f"{srcdir}/{source}"
    else: effectivesrcdir = srcdir
    if not os.path.isdir(effectivesrcdir):
        error_abort( f"Can not find source dir {effectivesrcdir}; did you forget to download?",**kwargs )
    settingsfile : str = f"{effectivesrcdir}/CMakeLists.txt"
    if not os.path.exists( f"{settingsfile}" ):
        error_abort( f"Can not find cmake settings file: {settingsfile}",**kwargs )
    cmakepathsetting : str = f"-S {effectivesrcdir} -B {builddir}"
    if nonnull(prefixdir):
        cmakepathsetting += f" -D CMAKE_INSTALL_PREFIX={prefixdir}"
    return cmakepathsetting

################################################################
####
#### Autotools
####
################################################################

def autotools_configure_script( pmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program,srcdir,builddir,prefixdir = pmakedirs
    if before := nonzero_keyword( "BEFORECONFIGURECMDS",**kwargs ):
        setup_script : str = f"\n{before}\n"
    else: setup_script = "\n"

    ##
    ## go to the right location for configure
    ##
    if nonzero_keyword( "CONFIGINBUILDDIR",**kwargs ):
        trace_string( f" .. going to configure in build dir {builddir}",**kwargs )
        configloc : str = builddir
        config_cmdline : str = f"{srcdir}/configure"
    elif subdir := nonzero_keyword( "CONFIGURESUBDIR",**kwargs ):
        trace_string( f" .. going to configure in subdir: {subdir}.",**kwargs )
        configloc = f"{srcdir}/{subdir}"
        config_cmdline = f"./configure"
    else:
        configloc = f"{srcdir}"
        config_cmdline = f"./configure"
    config_loc_script : str = f"""
cd {configloc}
echo Starting configure process in $(pwd)
if [ -f \"configure\" ] ; then
  has_configure=1
  echo has configure script
else has_configure= ; echo no configure script ; fi
if [ -f \"autogen.sh\" ] ; then
  has_autogen=1
  echo has autogen
else has_autogen= ; echo no autogen ; fi
if [ -f \"configure.ac\" ] ; then
  has_ac=1
  echo has configure.ac 
else has_ac= ; echo no configure.ac ; fi
    """

    ##
    ## do stuff before configure
    ##
    if nonzero_keyword( "AUTOUPDATE",**kwargs ):
        autoupdate : str = "./autoupdate"
    else: autoupdate = ""
    reconf_script : str = f"""
if [ -z \"$has_configure\" ] ; then 
  if [ ! -z \"$has_ac\" ] ; then
    aclocal && autoconf
  elif [ ! -z \"$has_autogen\" ] ; then 
    ./autogen.sh
  else
    echo FAILURE Need configure.ac or autogen.sh to generate configure script && exit 1
  fi
fi
{autoupdate}
    """
    ##
    ## do configure
    ##
    if option := nonzero_keyword( "PREFIXOPTION",**kwargs ):
        prefixoption = option # pdtoolkit
    else: prefixoption = "--prefix"
    if flags := nonzero_keyword( "CONFIGUREFLAGS",**kwargs ):
        flags = f" {flags}"
    else: flags = ""
    configure_script : str = f"""
./configure {prefixoption}={prefixdir} --libdir={prefixdir}/lib {flags}
    """
    return setup_script+config_loc_script+reconf_script+configure_script,"Autotools configuring"

def autotools_build_script( pmakedirs : list[str],**kwargs: Any ) -> tuple[str,str]:
    program = pmakedirs[0]; cmakedirs = pmakedirs[1:]
    srcdir,builddir,prefixdir = cmakedirs

    if not ( subdir := nonzero_keyword("MAKESUBDIR",**kwargs) ):
        subdir = srcdir

    #
    # Make
    #
    jval : str = kwargs.get("jcount",6)
    makecommand : str = f"make --no-print-directory -j {jval}"
    script : str = f"""
cd {subdir}
{makecommand}
    """
    if extra := nonzero_keyword( "EXTRABUILDTARGETS",**kwargs ):
        trace_string( f" .. making extra targets: {extra}",**kwargs )
        script += f"\n{makecommand} {extra}\n"

    #
    # install
    #
    extra = kwargs.get( "EXTRAINSTALLTARGET","" )
    script += f"\n{makecommand} install {extra}\n"

    return script,"Autotools make and install"

################################################################
####
#### PETSc
####
################################################################

def petsc_configure_script( plist : list[str],**kwargs : Any ) -> tuple[str,str]:
    srcdir,prefixdir = plist
    petscflags : str = kwargs.get("PETSCFLAGS","")
    script : str = f"\ncd {srcdir}\n"
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    script += f"""
python3 ./configure \
    CC=${{CC}} CXX=${{CXX}} FC=${{FC}} \
    {petscflags} \
    --prefix={prefixdir} 
    """
    return script,"Make setup"

def petsc_build_script( dummy : list[str],**kwargs : Any ) -> tuple[str,str]:
    srcdir  : str = srcdir_name( **kwargs )
    jcount  : str = kwargs.get("jcount",6)
    targets : str = kwargs.get( "MAKETARGETS","" )
    trace_string( f"making targets: {targets}",**kwargs )

    script : str = f"\ncd {srcdir}\n"
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    script += f"""
make -j {jcount} all
make -j {jcount} install
    """
    return script,"Make build"

################################################################
####
#### Make
####
################################################################

def make_build_script( pcmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program = pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir,builddir,prefixdir = cmakedirs
    # flags and options
    jcount          : str = kwargs.get("jcount","6")
    make            : str = f"make --no-print-directory V=1 VERBOSE=1 -j {jcount}"
    makebuildtarget : str = kwargs.get("makebuildtarget","")

    script : str = f"""
make -f {srcdir}/Makefile SRCDIR={srcdir} PROJECTNAME={program} {program}
    """
    return script,"Make compilation"

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

