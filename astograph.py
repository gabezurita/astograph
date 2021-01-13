#!/usr/bin/python
# -=- encoding: utf-8 -=-
#
# Copyright (C) 2008 - Alexandre Bourget
#
# Author: Alexandre Bourget <alex@bourget.cc>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import sys
import pdb


# POINTS OF FAILURE: when a multi-line comment comments out some include and context statements
# NOTE: the Goto things must be separated correctly with ? (and possibly ':'), and the goto destinations
#       must be correctly split with commas (,)
# TODO: add switch => support...

# to execute this script, run the following:
# cat path/to/file | ./astograph.py | dot -Tpng:cairo > graph.png
# for debugging with `pdb.set_trace()`, simply run ./astograph.py

internal_contexts = ['parkedcalls']


contexts = []
links = []

# Match context opening things..
ctxmatch = re.compile(r'\[([^ ]+)\]')
# Match include calls..
incmatch = re.compile(r'^include ?=> ?([^ ]+)')
# Match Return() calls (consider this section as a macro)
retmatch = re.compile(r',Return\(\)')
# Peak at Gotos, make sure it's not in comments..
gotomatch = re.compile(
    r'(;?)[^;]+Goto(If(Time)?)?\((.+)\)\s*(;.*)?$', re.IGNORECASE | re.VERBOSE)
# match things like Macro(voxeoretry
macromatch = re.compile(r'Macro\([a-zA-Z0-9_]*')
# TODO do we need to worry about comments? the source file we're parsing has no macro comments on it...
# could be an early optimization
# macromatch = re.compile(r'(;?)[^;]+Macro\([a-zA-Z0-9_]*?\((.+)\)\s*(;.*)?$')
readfrom = sys.stdin


def add_goto_context(curctx, newctx):
    """Just takes the ones with three arguments, and take the first.
    Add only if valid and not already linked within 'links'."""

    global contexts
    global links

    spl = newctx.split(',')
    type1 = (curctx, spl[0])
    type2 = (curctx, spl[0], 'dotted')

    if type1 not in links and type2 not in links and newctx in contexts:
        links.append((curctx, spl[0], 'dotted'))


curctx = None
for l in readfrom.readlines():
    # TODO: work out the comments (especially the multi-line comments)
    ctx = ctxmatch.match(l)
    inc = incmatch.match(l)
    ret = retmatch.search(l)
    gto = gotomatch.search(l.strip())
    mac = macromatch.search(l)

    if ctx:
        if ctx.group(1) in ['general', 'globals']:
            curctx = None
            continue

        curctx = ctx.group(1)

        # Don't add it twice.
        if curctx not in contexts:
            contexts.append(curctx)

        continue

    if inc:
        if not curctx:
            raise Exception(
                "include should not happen before a context definition")
        incctx = inc.group(1)

        # Add the internal contexts if we talk about them (like parkedcalls)OA
        if incctx in internal_contexts and incctx not in contexts:
            contexts.append(incctx)

        links.append((curctx, incctx))

        continue

    if gto:
        # Skip commented out lines with Goto..
        if gto.group(1) == ';':
            continue

        # Let's parse TIME stuff..
        if gto.group(3):
            chkctx = gto.group(4).split('?')[-1]
            add_goto_context(curctx, chkctx)
        # Let's do GotoIf parsing..
        elif gto.group(2):
            chks = gto.group(4).split('?')[-1].split(':')
            add_goto_context(curctx, chks[0])

            # A second possible destination ?
            if len(chks) == 2:
                add_goto_context(curctx, chks[1])

        # Standard Goto parsing.. go ahead..
        else:
            chkctx = gto.group(4)
            add_goto_context(curctx, chkctx)

        # Add links with style=dotted
        # make sure there's no ';' in front of the Goto
        # Check from the end the presence of a ? (got GotoIf), then parse the two possibilities, add two
        # Check the (curctx, gotoctx, '') doesn't exist in links (or as (curctx, gotoctx, 'style=dotted'))
        # then add it there..

    if mac:
        # TODO
        # Skip commented out lines with Macro..
        # if mac.group(1) == ';':
        #     continue

        chkctx = mac.group(0)
        # e.g. chkctx = Macro(assert_refer_triaged'
        # the below should update chkctx to equal macro macro-assert_refer_triaged
        chkctx = chkctx.replace("(", "-").lower()

        if chkctx not in contexts:
            contexts.append(chkctx)

        add_goto_context(curctx, chkctx)


dot = []
dot.append('digraph asterisk {\n')

for x in contexts:
    dot.append('  "%s" [label="%s"];\n' % (x, x))

dot.append('\n')

for x in links:
    add = ''
    if len(x) == 3:
        # TODO, the below is giving me diffuclties.
        # for hierarchy to work, need some constraint=false, but not always
        # add = ' [style="%s", constraint=false]' % x[2]
        add = ' [style="%s"]' % x[2]
    dot.append('  "%s" -> "%s"%s;\n' % (x[0], x[1].strip(), add))

dot.append('}\n')

f = open('graph.dot', 'w')
f.write(''.join(dot))
f.close()

sys.stdout.write(''.join(dot))
sys.stdout.flush()

# Gen the .dot thing, spit it to "dot -Tpng:cairo > output.png"
