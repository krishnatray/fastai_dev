#AUTOGENERATED! DO NOT EDIT! File to edit: dev/91_notebook_export.ipynb (unless otherwise specified).

__all__ = ['read_nb', 'check_re', 'is_export', 'find_default_export', 'export_names', 'extra_add', 'notebook2script',
           'get_name', 'qual_name', 'source_nb']

from ..imports import *
from .core import *
import nbformat,inspect

def read_nb(fname):
    "Read the notebook in `fname`."
    with open(Path(fname),'r') as f: return nbformat.reads(f.read(), as_version=4)

def check_re(cell, pat, code_only=True):
    "Check if `cell` contains a line with regex `pat`"
    if code_only and cell['cell_type'] != 'code': return
    if isinstance(pat, str): pat = re.compile(pat, re.IGNORECASE | re.MULTILINE)
    return pat.search(cell['source'])

_re_blank_export = re.compile(r'^\s*#\s*exports?\s*$', re.IGNORECASE | re.MULTILINE)

_re_mod_export = re.compile(r'^\s*#\s*exports?\s*(\S+)\s*$', re.IGNORECASE | re.MULTILINE)

def is_export(cell, default):
    "Check if `cell` is to be exported and returns the name of the module."
    if check_re(cell, _re_blank_export):
        if default is None:
            print(f"This cell doesn't have an export destination and was ignored:\n{cell['source'][1]}")
        return default
    tst = check_re(cell, _re_mod_export)
    return os.path.sep.join(tst.groups()[0].split('.')) if tst else None

_re_default_exp = re.compile( r'^\s*#\s*default_exp\s*(\S*)\s*$', re.IGNORECASE | re.MULTILINE)

def find_default_export(cells):
    "Find in `cells` the default export module."
    for cell in cells:
        tst = check_re(cell, _re_default_exp)
        if tst: return tst.groups()[0]

def _create_mod_file(fname, nb_path):
    "Create a module file for `fname`."
    fname.parent.mkdir(parents=True, exist_ok=True)
    with open(fname, 'w') as f:
        f.write(f"#AUTOGENERATED! DO NOT EDIT! File to edit: dev/{nb_path.name} (unless otherwise specified).")
        f.write('\n\n__all__ = []')

_re_patch_func = re.compile(r'@patch\s*def\s+([^\(\s]*)\s*\([^:]*:\s*([^,\)\s]*)\s*(?:,|\))')

_re_class_func_def = re.compile(r'^(?:def|class)\s+([^\(\s]*)\s*(?:\(|:)', re.MULTILINE)

_re_obj_def = re.compile(r'^([^=\s]*)\s*=', re.MULTILINE)

def _not_private(n):
    for t in n.split('.'):
        if t.startswith('_'): return False
    return True

def export_names(code, func_only=False):
    "Find the names of the objects, functions or classes defined in `code` that are exported."
    #Format monkey-patches with @patch
    code = _re_patch_func.sub(r'def \2.\1() = ', code)
    names = _re_class_func_def.findall(code)
    if not func_only: names += _re_obj_def.findall(code)
    return [n for n in names if _not_private(n)]

_re_all_def   = re.compile(r'^_all_\s*=\s*\[([^\]]*)\]', re.MULTILINE)
_re__all__def = re.compile(r'^__all__\s*=\s*\[([^\]]*)\]', re.MULTILINE)

def extra_add(code):
    "Catch adds to `__all__` required by a cell with `_all_=`"
    if _re_all_def.search(code):
        names = _re_all_def.search(code).groups()[0]
        names = re.sub('\s*,\s*', ',', names)
        names = names.replace('"', "'")
        code = _re_all_def.sub('', code)
        code = re.sub(r'([^\n]|^)\n*$', r'\1', code)
        return names.split(','),code
    return [],code

def _add2add(fname, names, line_width=120):
    if len(names) == 0: return
    with open(fname, 'r') as f: text = f.read()
    tw = TextWrapper(width=120, initial_indent='', subsequent_indent=' '*11, break_long_words=False)
    re_all = _re__all__def.search(text)
    start,end = re_all.start(),re_all.end()
    text_all = tw.wrap(f"{text[start:end-1]}{'' if text[end-2]=='[' else ', '}{', '.join(names)}]")
    with open(fname, 'w') as f: f.write(text[:start] + '\n'.join(text_all) + text[end:])

def _relative_import(name, fname):
    mods = name.split('.')
    splits = str(fname).split(os.path.sep)
    if mods[0] not in splits: return name
    splits = splits[splits.index(mods[0]):]
    while splits[0] == mods[0]: splits,mods = splits[1:],mods[1:]
    return '.' * (len(splits)) + '.'.join(mods)

_re_import = re.compile(r'^\s*from (local.\S*) import (.*)$')

def _deal_import(code_lines, fname):
    pat = re.compile(r'from (local.\S*) import (\S*)$')
    lines = []
    def _replace(m):
        mod,obj = m.groups()
        return f"from {_relative_import(mod, fname)} import {obj}"
    for line in code_lines:
        line = re.sub('_'+'file_', '__'+'file__', line) #Need to break __file__ or that line will be treated
        lines.append(_re_import.sub(_replace,line))
    return lines

def _get_index():
    if not (Path(__file__).parent/'index.txt').exists(): return {}
    return json.load(open(Path(__file__).parent/'index.txt', 'r'))

def _save_index(index): json.dump(index, open(Path(__file__).parent/'index.txt', 'w'), indent=2)
def _reset_index():
    if (Path(__file__).parent/'index.txt').exists():
        os.remove(Path(__file__).parent/'index.txt')

def _notebook2script(fname):
    "Finds cells starting with `#export` and puts them into a new module"
    if os.environ.get('IN_TEST',0): return  # don't export if running tests
    fname = Path(fname)
    nb = read_nb(fname)
    default = find_default_export(nb['cells'])
    if default is not None:
        default = os.path.sep.join(default.split('.'))
        _create_mod_file(Path.cwd()/'local'/f'{default}.py', fname)
    index = _get_index()
    exports = [is_export(c, default) for c in nb['cells']]
    cells = [(c,e) for (c,e) in zip(nb['cells'],exports) if e is not None]
    for (c,e) in cells:
        fname_out = Path.cwd()/'local'/f'{e}.py'
        orig = '' if e==default else f'#Comes from {fname.name}.\n'
        code = '\n\n' + orig + '\n'.join(_deal_import(c['source'].split('\n')[1:], fname_out))
        # remove trailing spaces
        names = export_names(code)
        extra,code = extra_add(code)
        _add2add(fname_out, [f"'{f}'" for f in names if '.' not in f] + extra)
        index.update({f: fname.name for f in names})
        code = re.sub(r' +$', '', code, flags=re.MULTILINE)
        with open(fname_out, 'a') as f: f.write(code)
    _save_index(index)
    print(f"Converted {fname}.")

def _get_sorted_files(all_fs: Union[bool,str], up_to=None):
    "Return the list of files corresponding to `g` in the current dir."
    if (all_fs==True): ret = glob.glob('*.ipynb') # Checks both that is bool type and that is True
    else: ret = glob.glob(all_fs) if isinstance(g,str) else []
    if len(ret)==0: print('WARNING: No files found')
    ret = [f for f in ret if not f.startswith('_')]
    if up_to is not None: ret = [f for f in ret if str(f)<=str(up_to)]
    return sorted(ret)

def notebook2script(fname=None, all_fs=None, up_to=None):
    "Convert `fname` or all the notebook satisfying `all_fs`."
    # initial checks
    if os.environ.get('IN_TEST',0): return  # don't export if running tests
    assert fname or all_fs
    if all_fs: _reset_index()
    if (all_fs is None) and (up_to is not None): all_fs=True # Enable allFiles if upTo is present
    fnames = _get_sorted_files(all_fs, up_to=up_to) if all_fs else [fname]
    [_notebook2script(f) for f in fnames]

def get_name(obj):
    "Get the name of `obj`"
    if hasattr(obj, '__name__'):       return obj.__name__
    elif getattr(obj, '_name', False): return obj._name
    elif hasattr(obj,'__origin__'):    return str(obj.__origin__).split('.')[-1] #for types
    else:                              return str(obj).split('.')[-1]

def qual_name(obj):
    "Get the qualified name of `obj`"
    if hasattr(obj,'__qualname__'): return obj.__qualname__
    if inspect.ismethod(obj):       return f"{get_name(obj.__self__)}.{get_name(fn)}"
    return get_name(obj)

def source_nb(func, is_name=None, return_all=False):
    "Return the name of the notebook where `func` was defined"
    is_name = is_name or isinstance(func, str)
    index = _get_index()
    name = func if is_name else qual_name(func)
    while len(name) > 0:
        if name in index: return (name,index[name]) if return_all else index[name]
        name = '.'.join(name.split('.')[:-1])