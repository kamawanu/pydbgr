# Copyright (C) 2008, 2009 Rocky Bernstein <rocky@gnu.org>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Debugger packaging information"""

# To the extent possible we make this file look more like a
# configuration file rather than code like setup.py. I find putting
# configuration stuff in the middle of a function call in setup.py,
# which for example requires commas in between parameters, is a little
# less elegant than having it here with reduced code, albeit there
# still is some room for improvement.

# Things that change more often go here.
copyright   = '''Copyright (C) 2008, 2009 Rocky Bernstein <rocky@gnu.org>.'''
classifiers =  ['Development Status :: 5 - Alpha',
                'Environment :: Console',
                'Intended Audience :: Developers',
                'License :: OSI Approved :: GNU General Public License (GPL)',
                'Operating System :: OS Independent',
                'Programming Language :: Python',
                'Topic :: Software Development :: Debuggers',
                'Topic :: Software Development :: Libraries :: Python Modules',
                ]

# The rest in alphabetic order
author             = "Rocky Bernstein"
author_email       = "rocky@gnu.org"
ftp_url            = None
install_requires   = ['columnize >= 0.3.2', 
                      'import_relative >= 0.1.0',
                      'pyficache >= 0.1.0',  # or 0.1.1?
                      'tracer >= 0.2.2']
license            = 'GPL'
mailing_list       = None
modname            = 'pydbgr'
namespace_packages = [
    'pydbgr', 
    'pydbgr.interface',
    'pydbgr.io',
    'pydbgr.lib',
    'pydbgr.processor',
    'pydbgr.processor.command',
    'pydbgr.processor.command.infosub',
    'pydbgr.processor.command.setsub',
    'pydbgr.processor.command.showsub'
]
packages           = namespace_packages
py_modules         = None
short_desc         = 'Modular Python Debugger'
version            = open('VERSION').readline().rstrip('\n')
web                = 'http://code.google.com/p/pydbgr/'

# tracebacks in zip files are funky and not debuggable
zip_safe = False 

import os
def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()
long_description   = ( read("README.txt") + '\n\n' +  read("CHANGES.txt") )

