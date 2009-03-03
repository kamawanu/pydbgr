# -*- coding: utf-8 -*-
#   Copyright (C) 2008, 2009 Rocky Bernstein <rocky@gnu.org>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
import inspect, linecache, os, sys, shlex, traceback, types
from repr import Repr

from import_relative import import_relative, get_srcdir
from tracer import EVENT2SHORT

Mbase_proc = import_relative('base_proc', '.', 'pydbgr')
Mbytecode  = import_relative('bytecode', '..lib', 'pydbgr')
Mexcept    = import_relative('except', '..', 'pydbgr')
Mdisplay   = import_relative('display', '..lib', 'pydbgr')
Mmisc      = import_relative('misc', '..', 'pydbgr')
Mfile      = import_relative('file', '..lib', 'pydbgr')
Mstack     = import_relative('stack', '..lib', 'pydbgr')
Mthread    = import_relative('thread', '..lib', 'pydbgr')

# arg_split culled from ipython's routine
def arg_split(s,posix=False):
    """Split a command line's arguments in a shell-like manner returned
    as a list of lists. Use ';;' with white space to indicate separate
    commands.

    This is a modified version of the standard library's shlex.split()
    function, but with a default of posix=False for splitting, so that quotes
    in inputs are respected. 
    """
    
    lex = shlex.shlex(s, posix=posix)
    lex.whitespace_split = True
    args = list(lex)
    args_list = [[]]
    for arg in args:
        if ';;' == arg: 
            args_list.append([])
        else:
            args_list[-1].append(arg)
            pass
        pass
    return args_list

def get_stack(f, t, botframe, proc_obj=None):
    """Return a stack of frames which the debugger will use for in
    showing backtraces and in frame switching. As such various frame
    that are really around may be excluded unless we are debugging the
    sebugger. Also we will add traceback frame on top if that
    exists."""
    exclude_frame = lambda f: False
    if proc_obj:
        dbg = proc_obj.debugger
        settings = proc_obj.debugger.settings
        if not settings['dbg_pydbgr']:
            exclude_frame = lambda f: \
                proc_obj.core.ignore_filter.is_included(f)
            pass
        pass
    stack = []
    if t and t.tb_frame is f:
        t = t.tb_next
    while f is not None:
        if exclude_frame(f): break  # See commented alternative below
        stack.append((f, f.f_lineno))
        # bdb has:
        # if f is botframe: break
        f = f.f_back
        pass
    stack.reverse()
    i = max(0, len(stack) - 1)
    while t is not None:
        stack.append((t.tb_frame, t.tb_lineno))
        t = t.tb_next
        pass
    return stack, i

def run_hooks(obj, hooks, *args):
    """Run each function in `hooks' with args"""
    for hook in hooks:
        hook(obj, *args)
        pass
    return True

def resolve_name(obj, command_name):
    if command_name not in obj.name2cmd:
        if command_name in obj.alias2name:
            command_name = obj.alias2name[command_name]
            pass
        else: 
            return None
        pass
    try:
        return command_name
    except:
        return None
    return

def print_source_line(msg_nocr, lineno, line, event_str=None):
    """Print out a source line of text , e.g. the second
    line in:
        (/tmp.py:2):  <module>
        L -- 2 import sys,os
        (Pydbgr)

    We define this method
    specifically so it can be customized for such applications
    like ipython."""

    # We don't use the filename normally. ipython and other applications
    # however might.
    return msg_nocr('%s %d %s' % (event_str, lineno, line))

def print_location(proc_obj):
    """Show where we are. GUI's and front-end interfaces often
    use this to update displays. So it is helpful to make sure
    we give at least some place that's located in a file.      
    """
    i_stack = proc_obj.curindex
    if i_stack is None or proc_obj.stack is None: 
        return False
    core_obj = proc_obj.core
    intf_obj = core_obj.debugger.intf[-1]

    # Evaluation routines like "exec" don't show useful location
    # info. In these cases, we will use the position before that in
    # the stack.  Hence the looping below which in practices loops
    # once and sometimes twice.
    while i_stack >= 0:
        frame_lineno = proc_obj.stack[i_stack]
        i_stack -= 1
        frame, lineno = frame_lineno

#         # Next check to see that local variable breadcrumb exists and
#         # has the magic dynamic value. 
#         # If so, it's us and we don't normally show this.a
#         if 'breadcrumb' in frame.f_locals:
#             if self.run == frame.f_locals['breadcrumb']:
#                 break

        filename = Mstack.frame2file(core_obj, frame)
        intf_obj.msg_nocr('(%s:%s):' % (filename, lineno))
        fn_name = frame.f_code.co_name
        if fn_name and fn_name != '?':
            intf_obj.msg(" %s" % frame.f_code.co_name)
        else:
            intf_obj.msg("")

        if '__loader__' in proc_obj.curframe.f_globals:
            l = proc_obj.curframe.f_globals['__loader__']
            intf_obj.msg(str(l))
            pass
        if 2 == linecache.getline.func_code.co_argcount:
            line = linecache.getline(filename, lineno)
        else:
            line = linecache.getline(filename, lineno, 
                                     proc_obj.curframe.f_globals)
            pass

        if line and len(line.strip()) != 0:
            if proc_obj.event:
                print_source_line(intf_obj.msg_nocr, lineno, line, 
                                  EVENT2SHORT[proc_obj.event])
            pass
        if '<string>' != filename:
            break
        pass
    return True

# Default settings for command processor method call
DEFAULT_PROC_OPTS = {
    # A list of debugger initialization files to read on first command
    # loop entry.  Often this something like [~/.pydbgrrc] which the
    # front-end sets. 
    'initfile_list' : []
}

class CommandProcessor(Mbase_proc.Processor):

    def __init__(self, core_obj, opts=None):
        get_option = lambda key: \
            Mmisc.option_set(opts, key, DEFAULT_PROC_OPTS)
        Mbase_proc.Processor.__init__(self, core_obj)
        
        self.cmd_instances  = self._populate_commands()
        self.cmd_queue      = [] # Queued debugger commands
        self.display_mgr    = Mdisplay.DisplayMgr()
        self.intf           = core_obj.debugger.intf
        self.last_cmd       = ''  # Initially a no-op
        self.precmd_hooks   = []
        self.preloop_hooks  = []
        self.postcmd_hooks  = []

        self._populate_cmd_lists()

        # Stop only if line/file is different from last time
        self.different_line = None

        # These values updated on entry. Set initial values.
        self.curframe       = None
        self.event          = None
        self.event_arg      = None
        self.frame          = None
        self.list_lineno    = 0

        # Create a custom safe Repr instance and increase its maxstring.
        # The default of 30 truncates error messages too easily.
        self._repr = Repr()
        self._repr.maxstring = 100
        self._repr.maxother  = 60
        self._repr.maxset    = 10
        self._repr.maxfrozen = 10
        self._repr.array     = 10
        self._saferepr       = self._repr.repr
        self.stack           = []
        self.thread_name     = Mthread.current_thread_name()

        initfile_list = get_option('initfile_list')
        for init_cmdfile in initfile_list:
            self.queue_startfile(init_cmdfile)
        return

    def add_preloop_hook(self, hook, position=-1, nodups = True):
        if hook in self.preloop_hooks: return False
        self.preloop_hooks.insert(position, hook)
        return True

    def adjust_frame(self, pos, absolute_pos):
        """Adjust stack frame by pos positions. If absolute_pos then
        pos is an absolute number. Otherwise it is a relative number.

        If self.gdb_dialect is True, the 0 position is the newest
        entry and doesn't match Python's indexing. Otherwise it does.

        A negative number indexes from the other end."""
        if not self.curframe:
            self.errmsg("No stack.")
            return

        # Below we remove any negativity. At the end, pos will be
        # the new value of self.curindex.
        if absolute_pos:
            if pos >= 0:
                pos = len(self.stack)-pos-1
            else:
                pos = -pos-1
        else:
            pos += self.curindex

        if pos < 0:
            self.errmsg("Adjusting would put us beyond the oldest frame.")
            return
        elif pos >= len(self.stack):
            self.errmsg("Adjusting would put us beyond the newest frame.")
            return

        self.curindex = pos
        self.curframe = self.stack[self.curindex][0]
        print_location(self)
        self.list_lineno = None
        return

    # To be overridden in derived debuggers
    def defaultFile(self):
        """Produce a reasonable default."""
        filename = self.curframe.f_code.co_filename
        # Consider using is_exec_stmt(). I just don't understand
        # the conditions under which the below test is true.
        if filename == '<string>' and self.debugger.mainpyfile:
            filename = self.debugger.mainpyfile
        return filename

    def event_processor(self, frame, event, event_arg):
        'command event processor: reading a commands do something with them.'
        self.frame     = frame
        self.event     = event
        self.event_arg = event_arg

        if self.settings('skip') is not None:
            filename = frame.f_code.co_filename
            lineno   = frame.f_lineno
            line     = linecache.getline(filename, lineno)
            if Mbytecode.is_def_stmt(line, frame):
                return True
            if Mbytecode.is_class_def(line, frame):
                return True
            pass
        self.process_commands()
        return True

    def forget(self):
        """ Remove memory of state variables set in the command processor """
        self.stack       = []
        self.curindex    = 0
        self.curframe    = None
        self.thread_name = None
        return

    def eval(self, arg):
        """Eval string arg in the current frame context."""
        try:
            return eval(arg, self.curframe.f_globals,
                        self.curframe.f_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
                pass
            else: exc_type_name = t.__name__
            self.errmsg(str("%s: %s" % (exc_type_name, arg)))
            raise
        return None # Not reached

    def exec_line(self, line):
        if self.curframe:
            local_vars = self.curframe.f_locals
            global_vars = self.curframe.f_globals
        else:
            local_vars = None
            # FIXME: should probably have place where the
            # user can store variables inside the debug session.
            # The setup for this should be elsewhere. Possibly
            # in interaction.
            global_vars = None
        try:
            code = compile(line + '\n', '"%s"' % line, 'single')
            exec code in global_vars, local_vars
        except:
            t, v = sys.exc_info()[:2]
            if type(t) == types.StringType:
                exc_type_name = t
            else: exc_type_name = t.__name__
            self.errmsg('%s: %s' % (str(exc_type_name), str(v)))
            pass
        return

    def parse_position(self, arg, old_mod=None):
        """parse_position(self, arg)->(fn, name, lineno)
    
        Parse arg as [filename:]lineno | function | module
        Make sure it works for C:\foo\bar.py:12
        """
        colon = arg.rfind(':') 
        if colon >= 0:
            # First handle part before the colon
            arg1 = arg[:colon].rstrip()
            lineno_str = arg[colon+1:].lstrip()
            (mf, filename, lineno) = self.parse_position_one_arg(arg1, old_mod,
                                                                 False)
            if filename is None: filename = self.core.canonic(arg1)
            # Next handle part after the colon
            val = self.get_an_int(lineno_str, "Bad line number: %s" % 
                                  lineno_str)
            if val is not None: lineno = val
        else:
            (mf, filename, lineno) = self.parse_position_one_arg(arg, old_mod)
            pass

        return mf, filename, lineno

    def parse_position_one_arg(self, arg, old_mod=None, obj_errmsg=True):
        """parse_position_one_arg(self,arg)->(module/function, file, lineno)
        
        See if arg is a line number, function name, or module name.
        Return what we've found. None can be returned as a value in
        the triple.
        """
        modfunc, filename = (None, None)
        if self.curframe:
            g = self.curframe.f_globals
            l = self.curframe.f_locals
        else:
            g = globals()
            l = locals()
            pass
        try:
            # First see if argument is an integer
            lineno   = int(eval(arg, g, l))
            if old_mod is None:
                filename = self.curframe.f_code.co_filename
                pass
        except:
            try:
                modfunc = eval(arg, g, l)
            except:
                modfunc = arg
                pass
            msg = ('Object %s is not known yet as a function, module, or is not found'
                   + ' along sys.path, and not a line number.') % str(repr(arg))
            try:
                # See if argument is a module or function
                if inspect.isfunction(modfunc):
                    pass
                elif inspect.ismodule(modfunc):
                    filename = Mfile.file_pyc2py(modfunc.__file__)
                    filename = self.core.canonic(filename)
                    return(modfunc, filename, None)
                elif hasattr(modfunc, 'im_func'):
                    modfunc = modfunc.im_func
                    pass
                else:
                    if obj_errmsg: self.errmsg(msg)
                    return(None, None, None)
                code     = modfunc.func_code
                lineno   = code.co_firstlineno
                filename = code.co_filename
            except:
                self.errmsg(msg)
                return (None, None, None)
            pass
        return (modfunc, self.core.canonic(filename), lineno)
    
    def get_an_int(self, arg, msg_on_error, min_value=None, max_value=None, 
                   cmdname=None):
        """Like cmdfns.get_an_int(), but if there's a stack frame use that
        in evaluation."""
        ret_value = self.get_int_noerr(arg)
        if ret_value is None:
            if msg_on_error:
                self.errmsg(msg_on_error)
            else:
                self.errmsg('Expecting an integer, got: %s.' % str(arg))
                pass
            return None
        if min_value and ret_value < min_value:
            self.errmsg('Expecting integer value to be at least %d, got: %d.' %
                        (min_value, ret_value))
            return None
        elif max_value and ret_value > max_value:
            self.errmsg('Expecting integer value to be at most %d, got: %d.' %
                        (max_value, ret_value))
            return None        
        return ret_value

    def get_int_noerr(self, arg):
        """Eval arg and it is an integer return the value. Otherwise
        return None"""
        if self.curframe:
            g = self.curframe.f_globals
            l = self.curframe.f_locals
        else:
            g = globals()
            l = locals()
            pass
        try:
            val = int(eval(arg, g, l)) 
        except (SyntaxError, NameError, ValueError):
            return None
        return val

    def getval(self, arg):
        try:
            return eval(arg, self.curframe.f_globals,
                        self.curframe.f_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else: exc_type_name = t.__name__
            self.errmsg(str("%s: %s" % (exc_type_name, arg)))
            raise
        return

    def ok_for_running(self, cmd_obj, name, nargs):
        '''We separate some of the common debugger command checks here:
        whether it makes sense to run the command in this execution state,
        if the command has the right number of arguments and so on.
        '''
        if hasattr(cmd_obj, 'execution_set'):
            if not (self.core.execution_status in cmd_obj.execution_set):
                self.errmsg(("Command '%s' is not available for " + 
                                  'execution status: %s.') % 
                                 (name, self.core.execution_status))
                return False
            pass
        if self.frame is None and cmd_obj.need_stack:
            self.intf[-1].errmsg("Command '%s' needs an execution stack." 
                                 % name)
            return False
        if nargs < cmd_obj.min_args:
            self.errmsg(("Command '%s' needs at least %d argument(s); " + 
                             "got %d.") % 
                             (name, cmd_obj.min_args, nargs))
            return False
        elif cmd_obj.max_args is not None and nargs > cmd_obj.max_args:
            self.errmsg(("Command '%s' can take at most %d argument(s);" + 
                              " got %d.") % 
                             (name, cmd_obj.max_args, nargs))
            return False
        return True

    def process_commands(self):
        """Handle debugger commands."""
        self.setup()
        print_location(self)
        run_hooks(self, self.preloop_hooks)
        self.continue_running = False
        while True:
            try:
                run_hooks(self, self.precmd_hooks)
                # bdb had a True return to leave loop.
                # A more straight-forward way is to set
                # instance variable self.continue_running.
                leave_loop = self.process_command()
                if leave_loop or self.continue_running: break
            except EOFError:
                # If we have stacked interfaces, pop to the next
                # one.  If this is the last one however, we'll
                # just stick with that.  FIXME: Possibly we should
                # check to see if we are interactive.  and not
                # leave if that's the case. Is this the right
                # thing?  investigate and fix.
                if len(self.debugger.intf) > 1:
                    del self.debugger.intf[-1]
                    self.last_cmd=''
                else:
                    if self.debugger.intf[-1].output:
                        self.debugger.intf[-1].output.writeline("Leaving")
                        pass
                    break
                pass
            pass
        return run_hooks(self, self.postcmd_hooks)

    def process_command(self):
        # process command
        if len(self.cmd_queue) > 0:
            last_cmd = self.cmd_queue[0].strip()
            del self.cmd_queue[0]
        else:
            last_cmd = self.intf[-1].read_command('(Pydbgr) ').strip()
            if '' == last_cmd and self.intf[-1].interactive: 
                last_cmd = self.last_cmd
                pass
            pass
        # Look for comments
        if '' == last_cmd:
            if self.intf[-1].interactive:
                self.errmsg("No previous command registered, " + 
                            "so this is a no-op.")
                pass
            return False
        if last_cmd[0] == '#':
            return False
        args_list = arg_split(last_cmd)
        for args in args_list:
            if len(args):
                cmd_name = resolve_name(self, args[0])
                if cmd_name:
                    self.last_cmd = last_cmd
                    cmd_obj = self.name2cmd[cmd_name]
                    if self.ok_for_running(cmd_obj, cmd_name, len(args)-1):
                        try: 
                            result = cmd_obj.run(args)
                            if result: return result
                        except (Mexcept.DebuggerQuit, 
                                Mexcept.DebuggerRestart):
                            # Let these exceptions propagate through
                            raise
                        except:
                            self.errmsg("INTERNAL ERROR: " + 
                                        traceback.format_exc())
                            pass
                        pass
                    pass
                elif not self.settings('autoeval'):
                    self.undefined_cmd(last_cmd)
                else:
                    self.exec_line(last_cmd)
                    pass
                pass
            pass
        return False
        
    def remove_preloop_hook(self, hook):
        try:
            position = self.preloop_hooks.index(hook)
        except ValueError:
            return False
        del self.preloop_hooks[position]
        return True

    def setup(self):
        """Initialization done before entering the debugger-command
        loop. In particular we set up the call stack used for local
        variable lookup and frame/up/down commands.

        We return True if we should NOT enter the debugger-command
        loop."""
        self.forget()
        if self.settings('dbg_pydbgr'):
            self.frame = inspect.currentframe()
            pass
        if self.event in ['exception', 'c_exception']:
            exc_type, exc_value, exc_traceback = self.event_arg
        else:
            exc_type, exc_value, exc_traceback = (None, None, None,)
            pass
        if self.frame or exc_traceback:
            self.stack, self.curindex = \
                get_stack(self.frame, exc_traceback, None, self)
            self.curframe = self.stack[self.curindex][0]
            self.thread_name = Mthread.current_thread_name()

        else:
            self.stack = self.curframe = \
                self.botframe = None
            pass
        self.list_lineno = \
            max(1, inspect.getlineno(self.curframe) \
                - (self.settings('listsize') / 2)) - 1
        # if self.execRcLines()==1: return True
        return False

    def queue_startfile(self, cmdfile):
        '''Arrange for file of debugger commands to get read in the
        process-command loop.'''
        expanded_cmdfile = os.path.expanduser(cmdfile)
        is_readable = Mfile.readable(expanded_cmdfile)
        if is_readable:
            self.cmd_queue.append('source ' + expanded_cmdfile)
        elif is_readable is None:
            self.errmsg("source file '%s' doesn't exist" % expanded_cmdfile)
        else:
            self.errmsg("source file '%s' is not readable" % 
                        expanded_cmdfile)
            pass
        return

    def undefined_cmd(self, cmd):
        """Error message when a command doesn't exist"""
        self.errmsg('Undefined command: "%s". Try "help".' % cmd)
        return

    def _populate_commands(self):
        """ Create an instance of each of the debugger
        commands. Commands are found by importing files in the
        directory 'command'. Some files are excluded via an array set
        in __init__.  For each of the remaining files, we import them
        and scan for class names inside those files and for each class
        name, we will create an instance of that class. The set of
        DebuggerCommand class instances form set of possible debugger
        commands."""
        cmd_instances = []
        command = import_relative('command')
        eval_cmd_template = 'command_mod.%s(self)'
        srcdir = get_srcdir()
        sys.path.insert(0, srcdir)
        for mod_name in command.__modules__:
            if mod_name in ('showsub', 'infosub', 'setsub'):
                pass
            import_name = "command." + mod_name
            command_mod = getattr(__import__(import_name), mod_name)
            classnames = [ tup[0] for tup in 
                           inspect.getmembers(command_mod, inspect.isclass)
                           if ('DebuggerCommand' != tup[0] and 
                               tup[0].endswith('Command')) ]
            for classname in classnames:
                eval_cmd = eval_cmd_template % classname
                try: 
                    instance = eval(eval_cmd)
                    cmd_instances.append(instance)
                except:
                    pass
                pass
            pass
        sys.path.remove(srcdir)
        return cmd_instances

    def _populate_cmd_lists(self):
        """ Populate self.lists and hashes:
        self.name2cmd, and self.alias2name, self.category """
        self.name2cmd = {}
        self.alias2name = {}
        self.category = {}
#         self.short_help = {}
        for cmd_instance in self.cmd_instances:
            name_aliases = cmd_instance.name_aliases
            cmd_name = name_aliases[0]
            self.name2cmd[cmd_name] = cmd_instance
            for alias_name in name_aliases[1:]:
                self.alias2name[alias_name] = cmd_name
                pass
            cat  = getattr(cmd_instance, 'category')
            if cat and self.category.get(cat):
                self.category[cat].append(cmd_name)
            else:
                self.category[cat] = [cmd_name]
                pass
#             sh = getattr(cmd_instance, 'short_help')
#             if sh:
#                 self.short_help[cmd_name] = getattr(c, 'short_help')
#                 pass
            pass
        for k in self.category.keys():
            self.category[k].sort()
            pass

        return

    pass

# Demo it
if __name__=='__main__':
    Mmock = import_relative('command.mock')
    d = Mmock.MockDebugger()
    cmdproc = CommandProcessor(d.core)
    print 'commands:'
    commands = cmdproc.name2cmd.keys()
    commands.sort()
    print commands
    print 'aliases:'
    aliases = cmdproc.alias2name.keys()
    aliases.sort()
    print aliases
    print resolve_name(cmdproc, 'quit')
    print resolve_name(cmdproc, 'q')
    print resolve_name(cmdproc, 'info')
    print resolve_name(cmdproc, 'i')
    print_source_line(sys.stdout.write, 100, 'source_line_test.py')
    cmdproc.frame = sys._getframe()
    cmdproc.setup()
    print
    print cmdproc.eval('1+2')
    print cmdproc.eval('len(aliases)')
    import pprint
    print pprint.pformat(cmdproc.category)
    print arg_split("Now is the time")
    print arg_split("Now is the time ;;")
    print arg_split("Now is 'the time'")
    print arg_split("Now is the time ;; for all good men")
    print arg_split("Now is the time ';;' for all good men")

    print cmdproc.parse_position_one_arg('4+1')
    print cmdproc.parse_position_one_arg('os.path')
    print cmdproc.parse_position_one_arg('os.path.join')
    print cmdproc.parse_position_one_arg('/bin/bash', obj_errmsg=False)
    print cmdproc.parse_position('/bin/bash')
    print cmdproc.parse_position('/bin/bash:4')

    fn = cmdproc.name2cmd['quit']
    print 'Removing non-existing quit hook: ', cmdproc.remove_preloop_hook(fn)
    cmdproc.add_preloop_hook(fn)
    print cmdproc.preloop_hooks
    print 'Removed existing quit hook: ', cmdproc.remove_preloop_hook(fn)
    pass
