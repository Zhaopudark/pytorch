import os
import fnmatch
import warnings

from io import IOBase
from typing import Iterable, List, Tuple, Union

try:
    import dill

    # XXX: By default, dill writes the Pickler dispatch table to inject its
    # own logic there. This globally affects the behavior of the standard library
    # pickler for any user who transitively depends on this module!
    # Undo this extension to avoid altering the behavior of the pickler globally.
    dill.extend(use_dill=False)
    DILL_AVAILABLE = True
except ImportError:
    DILL_AVAILABLE = False


def check_lambda_fn(fn):
    # Partial object has no attribute '__name__', but can be pickled
    if hasattr(fn, "__name__") and fn.__name__ == "<lambda>" and not DILL_AVAILABLE:
        warnings.warn(
            "Lambda function is not supported for pickle, please use "
            "regular python function or functools.partial instead."
        )


def match_masks(name : str, masks : Union[str, List[str]]) -> bool:
    # empty mask matches any input name
    if not masks:
        return True

    if isinstance(masks, str):
        return fnmatch.fnmatch(name, masks)

    for mask in masks:
        if fnmatch.fnmatch(name, mask):
            return True
    return False


def get_file_pathnames_from_root(
        root: str,
        masks: Union[str, List[str]],
        recursive: bool = False,
        abspath: bool = False,
        non_deterministic: bool = False) -> Iterable[str]:

    # print out an error message and raise the error out
    def onerror(err : OSError):
        warnings.warn(err.filename + " : " + err.strerror)
        raise err

    if os.path.isfile(root):
        path = root
        if abspath:
            path = os.path.abspath(path)
        fname = os.path.basename(path)
        if match_masks(fname, masks):
            yield path
    else:
        for path, dirs, files in os.walk(root, onerror=onerror):
            if abspath:
                path = os.path.abspath(path)
            if not non_deterministic:
                files.sort()
            for f in files:
                if match_masks(f, masks):
                    yield os.path.join(path, f)
            if not recursive:
                break
            if not non_deterministic:
                dirs.sort()


def get_file_binaries_from_pathnames(pathnames: Iterable, mode: str):
    if not isinstance(pathnames, Iterable):
        pathnames = [pathnames, ]

    if mode in ('b', 't'):
        mode = 'r' + mode

    for pathname in pathnames:
        if not isinstance(pathname, str):
            raise TypeError("Expected string type for pathname, but got {}"
                            .format(type(pathname)))
        yield pathname, StreamWrapper(open(pathname, mode))


def validate_pathname_binary_tuple(data: Tuple[str, IOBase]):
    if not isinstance(data, tuple):
        raise TypeError(f"pathname binary data should be tuple type, but it is type {type(data)}")
    if len(data) != 2:
        raise TypeError(f"pathname binary stream tuple length should be 2, but got {len(data)}")
    if not isinstance(data[0], str):
        raise TypeError(f"pathname within the tuple should have string type pathname, but it is type {type(data[0])}")
    if not isinstance(data[1], IOBase) and not isinstance(data[1], StreamWrapper):
        raise TypeError(
            f"binary stream within the tuple should have IOBase or"
            f"its subclasses as type, but it is type {type(data[1])}"
        )


def deprecation_warning(name, new_name: str = ""):
    new_name_statement = ""
    if new_name:
        new_name_statement = f" Please use {new_name} instead."
    warnings.warn(f"{name} and its functional API are deprecated and will be removed from the package `torch`." +
                  new_name_statement, DeprecationWarning)


class StreamWrapper:
    '''
    StreamWrapper is introduced to wrap file handler generated by
    DataPipe operation like `FileOpener`. StreamWrapper would guarantee
    the wrapped file handler is closed when it's out of scope.
    '''
    def __init__(self, file_obj):
        self.file_obj = file_obj

    def __getattr__(self, name):
        file_obj = self.__dict__['file_obj']
        return getattr(file_obj, name)

    def __dir__(self):
        attrs = list(self.__dict__.keys()) + list(StreamWrapper.__dict__.keys())
        attrs += dir(self.file_obj)
        return list(set(list(attrs)))

    def __del__(self):
        try:
            self.file_obj.close()
        except AttributeError:
            pass

    def __iter__(self):
        for line in self.file_obj:
            yield line

    def __next__(self):
        return next(self.file_obj)

    def __repr__(self):
        return f"StreamWrapper<{self.file_obj!r}>"

    def __getstate__(self):
        return self.file_obj

    def __setstate__(self, obj):
        self.file_obj = obj
