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

def load_compiler_and_mpi_and_modules_script( modules_to_load : str,**kwargs: Any ) -> tuple[str,str]:
    title : str = f"Load compiler and mpi and modules: {modules_to_load}"
    errmsg : str = f"Failed to load compiler and mpi and modules: {modules_to_load}"
    _,compiler,compilerversion,_,mpi,mpiversion = family_names( **kwargs )
    if ( modulepath := nonzero_keyword( "modulepath",**kwargs ) ) is None:
        error_abort( "Need a module path",**kwargs )
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
        if compiler is not None:
            loadscript += compilerloadfunction( modulepath,compiler,compilerversion )
        else: error_abort( "No compiler defined",**kwargs )
    if nonzero_keyword( "BLASLAPACK",**kwargs ):
        if comp := abort_on_zero_keyword( "COMPILER",**kwargs ):
            blas : str = ""
            if comp=="gcc"    : blas = "mkl"
            if comp=="nvidia" : blas = "nvpl"
            if nonnull(blas):
                loadscript += f"""
echo "Load blas/lapack library: {blas}"
modulecommand "load blas" "load {blas}"
                """
    if mode_has_mpi( **kwargs ):
        if mpi is not None:
            loadscript += mpiloadfunction( mpi,mpiversion )
        else: error_abort( "No mpi defined",**kwargs )
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

def compilerloadfunction( modulepath : str,compiler : str,compilerversion : Optional[str],
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

echo .... Set modulepath {redirect}
export MODULEPATH={modulepath}
echo MODULEPATH=${{MODULEPATH}} {redirect}
modulecommand "Can we load compiler?" "avail {compver}" display

modulecommand "Load compiler" "load {compver}"
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
echo "SUCCESS: package {package} downloaded as ${{tgz}}"
    """
    return script,"Download from url"

################################################################
####
#### CMake
####
################################################################

def cmake_configure_script( pcmakedirs : tuple[str,DirNamesDict],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames = pcmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    program = re.sub( r'\..*','',program )

    script : str = ""
    # setup
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    if unset_cmdline := nonzero_unsets( **kwargs ):
        script += f"\n{unset_cmdline}\n"

    # remove old crud
    script += configure_preclean( dirnames,**kwargs )

    # cmake
    cmake = cmake_basic_command( **kwargs )
    cmakeflags = cmake_options( **kwargs )
    buildsettings = cmake_build_settings( **kwargs )
    # set src, build, prefix
    pathsettings = cmake_paths_settings( dirnames,**kwargs )
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
    script += configure_postreport( dirnames,**kwargs )
    # VLE I can't get newlines in this script. Hm.
    script = script.replace( r'^ +-D(.*)$',r'  -D \1\\\n' )
    return script,"CMake configuring"

def configure_preclean( dirnames : DirNamesDict,**kwargs : Any ) -> str:
    builddir = dirnames ["builddir"]
    prefixdir = dirnames["prefixdir"]
    script : str =  f"""
echo "Remove any builddir: {builddir}"
rm -rf {builddir}
    """
    # netcdf installs c & f into the same prefix
    if kwargs.get("NOSCRATCHINSTALL") is not None:
        script += f"""
echo "Remove any prefixdir: {prefixdir}"
rm -rf {prefixdir}
        """
    return script

def configure_postreport( dirnames : DirNamesDict,**kwargs : Any ) -> str:
    builddir = dirnames ["builddir"]
    return f"""
echo "Builddir {builddir} contents:"
ls {builddir}
    """

def cmake_build_script( pcmakedirs : tuple[str,DirNamesDict],**kwargs : Any ) -> tuple[str,str]:
    _,dirnames = pcmakedirs
    srcdir = dirnames["srcdir"]; builddir = dirnames["builddir"]; prefixdir = dirnames["prefixdir"]

    script : str = f"""
echo -e "\n>>> Start of cmake build"
    """
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
    script += cmake_build_pre( dirnames,**kwargs )
    script += f"""
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
    script += f"""
echo " .. end of cmake build"
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

def cmake_paths_settings( dirnames : DirNamesDict,**kwargs ) -> str:
    srcdir = dirnames["srcdir"]; builddir = dirnames["builddir"]; prefixdir = dirnames["prefixdir"]
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

def cmake_build_pre( dirnames : DirNamesDict,**kwargs : Any ) -> str:
    builddir = dirnames["builddir"]
    return f"""
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
    """

################################################################
####
#### Autotools
####
################################################################

def autotools_configure_script( pmakedirs : list[str],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames = pmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    if before := nonzero_keyword( "BEFORECONFIGURECMDS",**kwargs ):
        setup_script : str = f"\n{before}\n"
    else: setup_script = "\n"

    ##
    ## go to the right location for configure
    ## do autogen stuff before configure
    ##
    configsetupscript : str = config_setup_script( srcdir,**kwargs )

    ##
    ## do configure
    ##
    if ( option := nonzero_keyword( "PREFIXOPTION",**kwargs ) ) is not None:
        prefixoption = option # pdtoolkit
    else: prefixoption = "--prefix"
    if ( flags := nonzero_keyword( "CONFIGUREFLAGS",**kwargs ) ) is not None:
        flags = f" {flags}"
    else: flags = ""
    configurescript : str = f"""
./configure {prefixoption}={prefixdir} --libdir={prefixdir}/lib {flags}
echo "SUCCESS: autotools configure succeeded"
    """
    return setup_script+configsetupscript+configurescript,"Autotools configuring"

def config_setup_script( srcdir : str,**kwargs : dict[str,Any] ) -> str:    
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
    if nonzero_keyword( "AUTOUPDATE",**kwargs ):
        autoupdate : str = "./autoupdate"
    else: autoupdate = ""
    return f"""
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

if [ -z "${{has_configure}}" ] ; then 
  if [ ! -z "${{has_ac}}" ] ; then
    aclocal && autoconf
  elif [ ! -z "${{has_autogen}}" ] ; then 
    ./autogen.sh
  else
    echo FAILURE Need configure.ac or autogen.sh to generate configure script && exit 1
  fi
fi
{autoupdate}
    """

def autotools_build_script( pmakedirs : list[str],**kwargs: Any ) -> tuple[str,str]:
    program,dirnames = pmakedirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    if ( subdir := nonzero_keyword("MAKESUBDIR",**kwargs) ) is None:
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
    script += f"""
{makecommand} install {extra}
echo "SUCCESS: autotools build succeeded"
    """

    return script,"Autotools make and install"

################################################################
####
#### PETSc
####
################################################################

def petsc_configure_script( pdirs : tuple[str,DirNamesDict],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames = pdirs # pcmakedirs[0]; cmakedirs = pcmakedirs[1:]
    # srcdir,prefixdir = plist
    srcdir    : str = dirnames["srcdir"]
    prefixdir : str = dirnames["prefixdir"]

    petscflags : str = kwargs.get("PETSCFLAGS","")
    script : str = f"""
if [ ! -d "{srcdir}" ] ; then
    echo "FAILURE: src dir {srcdir} does not exist" && exit 1
fi
cd {srcdir}
    """
    if export_cmdline := nonzero_exports( **kwargs ):
        script += f"\n{export_cmdline}\n"
    script += f"""
if [ ! -f "configure" ] ; then
    echo "FAILURE: no petsc configure script found in ${{PWD}}" && exit 1
fi
which python3
cmdline="python3 ./configure \
    CC=${{CC}} CXX=${{CXX}} FC=${{FC}} \
    {petscflags} \
    --prefix={prefixdir}"
echo "Configure cmdline=$cmdline"
eval $cmdline
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

def make_build_script( dirnamesl : tuple[str,DirNamesDict],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames = dirnamesl
    # srcdir,builddir,prefixdir = cmakedirs
    srcdir = dirnames["srcdir"]
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
lddout="{scriptsdir}/ldd_{program}.out"
rm -f "${{lddout}}"

if [ -f \"{program}\" ] ; then
    ldd {program} 2>&1 | tee "${{lddout}}"
else
    touch "${{lddout}}"
fi

if [ -f \"{program}\" ] ; then
    notfound=$( grep \"not found\" "${{lddout}}" | wc -l )
    if [ $notfound -eq 0 ] ; then
        echo "SUCCESS: all libraries resolved"
    else
        echo "FAILURE: $notfound references not found"
    fi
else
    echo "FAILURE: could not find program={program} to run ldd on"
fi
    """
    return script,f"ldd test on {program}"

##
## Test file existence
##
def file_to_exist_script( args : list[str],**kwargs : Any, ) -> tuple[str,str]:
    # _,filedir,file_to_test,file_to_report = args
    package,dirtype,program,grep,executable = args
    dirvar : str = dir_variable(package,dirtype)
    title : str = f"Test existence of {dirtype}:{program}"
    # filedir,file_to_test,file_to_report =
    # file_to_exist_names(package,dirtype,program,**kwargs)
    script : str = f"""
echo "{title}"

echo "Using directory variable: {dirvar}
eval filedir=\${{dirvar}}
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
    echo "SUCCESS: file exists: <<${{file_to_report}}>>"
else
    echo "FAILURE: file does not exist <<${{file_to_report}}>>"
    exit 1
fi
        """
    return script,title
    if executable:
        script += f"""
if [ -x \"{file_to_test}\" ] ; then
    echo "SUCCESS: file is executable"
else
    echo "FAILURE: file is not executable"
fi
        """
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
def run_script( dirnamesl : tuple[str,DirNamesDict,str],**kwargs : Any ) -> tuple[str,str]:
    program,dirnames,args = dirnamesl
    # strip any extension
    program = re.sub( r'\..*','',program )

    title   : str = f"run program {program}"

    script : str = ""
    # where do we run?
    rundir   = dirnames["builddir"]
    if isnull( rundir ):
        rundir = "build"
        script += f"""
cd {rundir}
echo "Running in rundir={rundir}=$( pwd )"
        """
    else:
        script += f"""
echo "Running in rundir={rundir}=$( pwd )"
        """

    # what do we run?
    #  - prefix is empty for runing along path
    #  - prefix can be ./
    prefix  : str = dirnames["prefixdir"]
    cmdline : str = f"{prefix}{program}"
    if nonnull( args ):
        cmdline += f" {args}"
    script += f"""
echo "cmdline={cmdline}"
echo ">>>> start execution"
result=$( {cmdline} )
echo "<<<< end execution"
if [ $? -eq 0 ] ; then 
    echo "SUCCESS: running {program} with output [${{result}}]"
else
    echo "FAILURE: running {program}"
fi 
#echo ${{output}}
    """
    return script,title

