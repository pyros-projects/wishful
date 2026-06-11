import pytest

from wishful.safety.validator import SecurityError, validate_code


# Constructs that must be rejected with safety on. Each closes a path the
# 2026-06-11 review demonstrated (or a logical sibling of one).
BLOCKED = [
    "__import__('os').system('x')",
    "importlib.import_module('os')",
    "import importlib",
    "import builtins",
    "import ctypes",
    "import os",
    "from subprocess import run",
    "getattr(__builtins__, 'eval')('1')",
    "__builtins__['eval']('1')",
    "compile('x', '<s>', 'exec')",
    "open('f', mode)",            # non-literal mode
    "open('f', 'w')",            # positional write
    "open('f', mode='a')",       # keyword write
    "eval('1')",
    "exec('x')",
    "os.system('ls')",           # unbound os
    "sys.exit(1)",               # unbound sys
    "globals()['eval']('1')",
    "vars()['__import__']",
    "locals()['__builtins__']['eval']",   # locals() subscript gadget
    "b = locals()['__import__']",          # locals() subscript
    "f = __import__",            # bare __import__ reference
    "b = __builtins__",          # bare __builtins__ reference
    "f = open",                  # aliased open (gadget)
    "g = getattr\nr = g(o, 'system')",   # aliased getattr (gadget)
    "def h(x=open):\n    return x('f', 'w')",  # open as default arg
    "k = eval",                  # aliased eval
    # Introspection sandbox-escape gadget chains:
    "x = [].__class__.__bases__[0].__subclasses__()",
    "g = (lambda: 0).__globals__",
    "c = (lambda: 0).__code__",
    "b = ().__class__.__bases__",
    "e = type('A',(),{}).__bases__[0].__subclasses__()[0].__init__.__globals__['__builtins__']['eval']",
    "g = {'__builtins__': 1}\ne = g['__builtins__']['eval']",
    "x = obj.__getattribute__('eval')",
    "m = something.__mro__",
    # getattr with computed/variable attribute names (escape via indirection):
    "a = '__class__'\ny = getattr((), a)",
    "s = 'sy' + 'stem'\ng = getattr(o, s)",
    "f = getattr(globals().get('__builtins__'), 'open')",
    "x = getattr(o, '__bases__')",
    "setattr(o, '__globals__', 1)",
    "a='__class__'\nb='__bases__'\nc='__subclasses__'\nx=()\ny=getattr(x,a)\nz=getattr(y,b)[0]\nw=getattr(z,c)()",
    # Escape dunders via subscript (mirror of the attribute form):
    "m = type.__dict__['__subclasses__'](object)",
    # Code/file execution modules and write methods:
    "import runpy\nrunpy.run_path('x')",
    "import pickle",
    "import shutil",
    "import marshal",
    "import pathlib\npathlib.Path('x').write_text('y')",
    "obj.write_bytes(b'data')",
]

# Legitimate code that must keep passing — including a shadowed `os` local,
# which the unbound-base tracking must not flag.
ALLOWED = [
    "open('f', 'r')",
    "open('f')",
    "getattr(obj, 'name')",
    "x = 'linux'\nos = x\nif os.lower() == 'linux':\n    pass",
    "def f(x):\n    return x * 2",
    "import json\nimport re\nfrom datetime import datetime\nimport math",
    "import re\np = re.compile(r'\\d+')",
    "data = {'a': 1}\nv = data['a']",
    "result = sorted([3, 1, 2])",
    "name = obj.__class__.__name__",   # common introspection stays allowed
    "import pathlib\nt = pathlib.Path('x').read_text()",   # reading is fine
    "import json\nd = json.loads('{}')",                   # json.loads is fine
    "d = {}\nv = d.get('k')",                              # dict.get is fine
    # Every binding form that introduces a local `os`/`sys`/`subprocess` must
    # suppress the unbound-base check (no false positives):
    "os, sys = 'x', 'y'\nif os.lower() == sys.upper():\n    pass",   # tuple unpack
    "for sys in ['a', 'b']:\n    sys.strip()",                       # for target
    "with open('f') as sys:\n    data = sys.read()",                # with-as
    "g = lambda os, *a, **k: os.lower()",                            # lambda args
    "try:\n    pass\nexcept Exception as sys:\n    msg = sys.args",   # except-as
    "items = [os.strip() for os in ['a', 'b']]",                    # comprehension
    "if (os := 'linux'):\n    os.upper()",                          # walrus
    "head, *sys = [1, 2, 3]\nsys.append(4)",                        # starred unpack
    "n = 0\nn += 1\nresult = n",                                     # aug-assign
    "value: int = 3\nresult = value",                               # ann-assign
]

# Known residual bypasses: AST scanning fundamentally cannot follow reflective or
# computed access through library indirection. Documented as xfail so a future
# hardening that catches them surfaces as xpass. getattr/subscript with computed
# *literal-class* names are now blocked; what remains needs a non-getattr
# reflection primitive or value-level indirection the validator cannot model.
RESIDUAL_BYPASSES = [
    "import operator\nf = operator.attrgetter('__class__')",   # reflection via operator module
    "m = {}.get('__builtins__')",                              # builtins via an arbitrary mapping's .get()
]


@pytest.mark.parametrize("source", BLOCKED)
def test_blocked_constructs_raise(source):
    with pytest.raises(SecurityError):
        validate_code(source, allow_unsafe=False)


@pytest.mark.parametrize("source", ALLOWED)
def test_allowed_constructs_pass(source):
    validate_code(source, allow_unsafe=False)  # must not raise


@pytest.mark.parametrize("source", RESIDUAL_BYPASSES)
@pytest.mark.xfail(reason="AST scanning cannot catch aliased/computed access", strict=False)
def test_residual_bypasses_are_documented_gaps(source):
    with pytest.raises(SecurityError):
        validate_code(source, allow_unsafe=False)


def test_allow_unsafe_skips_all_checks():
    validate_code("import os\nos.system('rm -rf /')\n", allow_unsafe=True)


def test_validate_raises_syntaxerror_not_importerror():
    """Malformed source must raise SyntaxError so the loader can retry it.

    The old behaviour wrapped syntax errors as ImportError, which made the
    loader's regenerate-once path unreachable whenever safety was on.
    """
    with pytest.raises(SyntaxError):
        validate_code("def broken(:\n    pass\n", allow_unsafe=False)
    assert not issubclass(SyntaxError, ImportError)
