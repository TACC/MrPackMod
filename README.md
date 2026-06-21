# MrPackMod: Package installer with LMod integration

Usage:

``` 
mpm.py [ -c Configuration ] [ -t ] actions
```

where actions: `test download unpack configure build module public`, 
or `install` for `configure build module`.
This can download, configure, install a package, 
and generate LMod modules.

## Environment

To do anything with MrPackMod, some environment variables need to be set:

- `PACKAGEROOT`: this is where sources are downloaded
- `INSTALLROOT`: location where packages are installed
- `MODULEROOT`: location where module files are installed

## Configuration file

By default, `mpm` looks for a file `Configuration`, but the `-c` option
allows you to specify another name.
The configuration file contains lines:

```
# comment
key = value
let keymacro = value
```

Typical keys are

```
PACKAGE = somepackage
PACKAGEVERSION = 1.0.0
ABOUT = This package is for something
MODE = mpi
BUILDSYSTEM = cmake
CMAKEFLAGS = \
 -D FOO=ON \
 -D BAR=OFF
DOWNLOADURL = https://github.com/SomePackage/v${PACKAGEVERSION}.tar.gz
```

Each keyword can later be used as a macro,
as is illustrated here for `PACKAGEVERSION`.

There is a modest conditional facility:

```
SYSTEM!=legacy SETTING=OFF
SYSTEM==legacy SETTING=OFF
```

with equality and inequality the only available tests.
Both sides of the comparison can be literal or configuration keys.

A technical point: the `MODE` variable is used in generating log files, so it needs to come fairly high up in the configuration.

## Global settings

The MrPackMod system relies on a couple of global variables. 

- `SYSTEM` : this is used for path generation in case you have multiple systems on a shared file system
- `COMPILER `, `COMPILER_VERSION`, `MPI`, `MPI_VERSION` : these are mostly used for module path generation.
 
Certain environment variables can be overriden in the configuration file (see above):

- `PACKAGEROOT` : packages are downloaded and unpacked in `${PACKAGEROOT}/${PACKAGENAME}`; override this with the `DOWNLOADPATH` setting.
  The packageroot is also used as the default location of any builddirectory; override this with `BUILDDIRROOT`. (!!!not yet implemented!!!)
- `INSTALLROOT` : the package is installed in `${INSTALLROOT}/installation-${PACKAGE}-${EXTENSION}` where the extension is compound of system, compiler, mpi.
  Override this whole path with `INSTALLPATH`.
- `MODULEROOT` : this is used to build up the `${MODULEROOT}/{Core,Compiler,MPI}/et/cetera` path as in the LMod documentation.
  Override the whole of this path with `MODULEDIR`.

These can be set through a file called `.mrpackmodrc`, which is searched in 1) the current directory 2) one level back, 
to accomodate the case where you have one large "software" directory with each package a subdirectory, and
3) your home directory. Syntax:

```
# Comment about my settings
SYSTEM = MyLaptop
```

On TACC systems these settings can be set through environment variables (!!!this needs to be generalized!!!):

- `TACC_SYSTEM` : for the `SYSTEM` setting
- `TACC_FAMILY_COMPILER `, `TACC_FAMILY_COMPILER_VERSION`, `TACC_FAMILY_MPI`, `TACC_FAMILY_MPI_VERSION` : for the `COMPILER` and `MPI` settings.

Certain environment variables can be overriden:

- `PACKAGEROOT` : packages are downloaded and unpacked in `${PACKAGEROOT}/${PACKAGENAME}`; override this with the `DOWNLOADPATH` setting.
  The packageroot is also used as the default location of any builddirectory; override this with `BUILDDIRROOT`. (!!!not yet implemented!!!)
- `INSTALLROOT` : the package is installed in `${INSTALLROOT}/installation-${PACKAGE}-${EXTENSION}` where the extension is compound of system, compiler, mpi.
  Override this whole path with `INSTALLPATH`.
- `MODULEROOT` : this is used to build up the `${MODULEROOT}/{Core,Compiler,MPI}/et/cetera` path as in the LMod documentation.
  Override the whole of this path with `MODULEDIR`.
  
## Downloading

The `DOWNLOADURL` setting is used in the `download` action. It supports `tgz`, `tar.gz`, `xz`, and `zip` extensions. 
(!!!add bz2!!!)
This URL typically contains the compulsory `PACKAGEVERSION` setting.

A subsequent `unpack` action unpacks the downloaded file and renames the result to a standard naming scheme of
`${PACKAGE}-${PACKAGEVERSION}`.
(!!!not yet: the `retar` action then packs up the unpacked and renamed bundle to `${PACKAGE}-${PACKAGEVERSION}.tgz`. This is useful in an `rpmbuild` context.!!!)

(!!!not yet: there is a `GITREPO` setting and corresponding `clone` action!!!)

## Configure

The `BUILDSYSTEM` setting can be `cmake` or `autotools` 
or `make` for packages that are stuck in the 1980s.
(The setting `petsc` exists, only for the PETSc package.)

Corresponding to the build system,
the `CMAKEFLAGS` and `CONFIGUREFLAGS` settings are used.
These should be used for package-specific options;
a number of standard options are already provided.

- CMake uses a number of default flags such as:
  - `-D CMAKE_BUILD_TYPE=RelWithDebInfo`. Override this with `CMAKEBUILDTYPE`.
  - `-D BUILD_SHARED_LIBS=ON`. Override this with a nonzero value for `BUILDSTATICLIBS`.
- Autotools looks for `configure`, `configure.ac`, `autogen.sh` and treats them accordingly. Further settings:
  - `CONFIGURESUBDIR` indicates that the configure script is in a subdirectory;
  - By default an option `--prefix=/install/dir` is used.
    If your package uses `-prefix` or so (pdtoolkit), specify `PREFIXOPTION = -prefix` and such.

CMake will do the configuration in a builddirectory that is created alongside the source directory.
Override this with the `BUILDDIRROOT` setting.
Autotools will do the configuration in the source directory; 
packages that support a separate builddirectory can use the `CONFIGINBUILDDIR` setting.

## Building

After configuration, `make && make install` is done in the builddirectory, for which see the previous point.
The `make` is parallel, using the `JCOUNT` setting.
A target can be specified with `MAKEBUILDTARGET` (enzo).
The setting `EXTRABUILDTARGETS` is used in a second `make` call (sqlite).

## Module

Prerequisite modules are given as

```
MODULES = zlib hdf5
```

where optionally version numbers can be attached: `hdf5/<2` or `hdf5/1.>12`.
The `configure` and `build` actions tests for these modules to be loaded
and their `DIR/INC/LIB` variables to have correct values.
Example: if `TACC_MYPACKAGE_INC` is set, it is tested
whether the value is an existing directory.

### Module file

An LMod module file `${MODULENAME}/${PACKAGEVERSION}.lua` is generated on an automatically generated path, depending on the `MODE` setting:

- `core` : `${MODULEROOT}/Core`.
- `seq` or `omp` : `${MODULEROOT}/Compiler/${TACC_FAMILY_COMPILER}/${TACC_FAMILY_COMPILER_VERSION}`
- `mpi` or `hybrid` : `${MODULEROOT}/MPI/${TACC_FAMILY_COMPILER}/${TACC_FAMILY_COMPILER_VERSION}/${TACC_MPI_FAMILY}/${TACC_MPI_FAMILY_VERSION}`

Here `MODULENAME` is `PACKAGE`, unless the setting `MODULENAME` is explicitly used;
see for instance `MODULENAME = phdf5` for the parallel version of `PACKAGE = hdf5`.

Alternatively, use `MODULEDIR` for a fully explicit path.
Note: the module directory is created afresh;  `MODULEDIRADD` to prevent it first being erased,
for instance if you want to install multiple packages in the same module directory
(see `netcdf` and `netcdff`).

### Lib,Inc,Bin and such

By default, the module will have variables for an include and lib directory.

- If there is no include dir, set `NOINC = 1`;
- If there is no lib dir, set `NOLIB = 1`;
- If there is a bin dir, set `HASBIN = 1`.

If the include directory is non-standard, specify `INCLUDELOC = share/include` or so.

Depending on inscrutable cmake mechanisms, the library dir can be `lib` or `lib64`. Mpm searches for either and sets the variable accordingly.

The `INCLUDE`, `PATH`, `LD_LIBRARY_PATH` variables are updated accordingly.

The settings `PYTHONPATHABS`, `PYTHONPATHREL` update the `PYTHONPATH` 
variable with an absolute path, and a path relative to the installation respectively.

### Discoverability

If the package generates `.cmake` files, specify `PREFIXPATHSET = 1`.
If the package generates `.pc` files, specify 

- `PKGCONFIG = path` for a path relative to the installation, or
- `PKGCONFIGLIB = path` for a path relative to the lib directory.

### More

More settings:

- `ABOUT` is a compulsory one-line description of the package;
- `URL`, `SOFTWAREURL` are URLs for homepage and software page;
- `DEPENDSON = package` : inserts a `depends_on( "package" )` line;
- `DEPENDSONCURRENT = package` generates a `depends_on` clause that additionally includes the version number of the currently loaded package.
