# -*- coding: utf-8 -*-
#   Copyright (C) 2009 Rocky Bernstein
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
#    02110-1301 USA.

from import_relative import import_relative
# Our local modules
# FIXME: Until import_relative is fixed up...
Mbase_subcmd = import_relative('base_subcmd', '..', 'pydbgr')
Mcmdfns      = import_relative('cmdfns', '..', 'pydbgr')

class SetAutoList(Mbase_subcmd.DebuggerSetBoolSubcommand):
    """Run a 'list' command every time we enter the debugger.
    """

    in_list    = True
    min_abbrev = 5 # Need at least "set autol"
    short_help = "Execute 'list' command on every stop"

    list_cmd = None

    def run(self, args):
        Mcmdfns.run_set_bool(self, args)
        if self.settings['autolist']:
            if self.list_cmd == None:
                self.list_cmd = self.proc.name2cmd['list'].run
                pass
            self.proc.add_preloop_hook(self.run_list, 0)
        else:
            self.proc.remove_preloop_hook(self.run_list)
            pass
        return

    def run_list(self, args):
        self.list_cmd(['list'])
        return
    pass

if __name__ == '__main__':
    mock = import_relative('mock', '..')
    Mset = import_relative('set', '..')
    d, cp = mock.dbg_setup()
    s = Mset.SetCommand(cp)
    sub = SetAutoList(s)
    pass
