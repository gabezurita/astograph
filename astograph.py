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

import re
import sys
import pdb

# POINTS OF FAILURE: when a multi-line comment comments out some include and context statements
# NOTE: the Goto things must be separated correctly with ? (and possibly ':'), and the goto destinations
#       must be correctly split with commas (,)
# TODO: add switch => support...

# to execute this script, run the following:
# echo path/to/file | ./astograph.py | dot -Tpng:cairo > graph.png
# for debugging with `pdb.set_trace()`, simply run ./astograph.py

internal_contexts = ['parkedcalls']

contexts = []
links = []

# Match context opening things..
context_match = re.compile(r'\[([^ ]+)\]')
# Match include calls..
include_match = re.compile(r'^include ?=> ?([^ ]+)')
# Match Return() calls (consider this section as a macro)
return_match = re.compile(r',Return\(\)')
# Peak at Gotos, make sure it's not in comments..
goto_match = re.compile(
    r'(;?)[^;]+Goto(If(Time)?)?\((.+)\)\s*(;.*)?$', re.IGNORECASE | re.VERBOSE)
# Match Macro calls
macro_match = re.compile(r'Macro\([a-zA-Z0-9_]*')
# Match AGI calls
agi_match = re.compile(r'AGI\([a-zA-Z0-9_]*')

readfrom = sys.stdin.readline().rstrip()


def add_link(current_context, new_context):
    """Just takes the ones with three arguments, and take the first.
    Add only if valid and not already linked within 'links'."""

    global contexts
    global links

    new_context_split = new_context.split(',')

    if not already_linked(current_context, new_context_split) and new_context in contexts:
        links.append((current_context, new_context_split[0], 'dotted'))


def already_linked(current_context, new_context):
    global links

    type1 = (current_context, new_context[0])
    type2 = (current_context, new_context[0], 'dotted')

    return type1 in links or type2 in links


def format_context(context):
    return context.replace("(", "-").lower()


def add_context(current_context, contexts):
    if current_context in ['general', 'globals']:
        return

    if current_context not in contexts:
        contexts.append(current_context)


current_context = None

with open(readfrom, 'r') as file:
    for line in file:
        ctx = context_match.match(line)

        if ctx:
            current_context = ctx.group(1)

            add_context(current_context, contexts)

            continue

    current_context = None

    file.seek(0)

    for line in file:
        # TODO: work out the comments (especially the multi-line comments)
        ctx = context_match.match(line)
        inc = include_match.match(line)
        ret = return_match.search(line)
        gto = goto_match.search(line.strip())
        mac = macro_match.search(line)
        agi = agi_match.search(line)

        if ret:
            # Ok, we were in a Macro, make sure the context is not added.
            return_context = current_context

            if return_context in contexts:
                contexts.remove(return_context)

            # TODO: to be turbo safe, we should check the `links` to make
            # sure nothing was included from this macro context, but usually,
            # if you've created them with AEL2, you should never have an `include`
            # in the macro (or the sub)

            continue

        if ctx:

            current_context = ctx.group(1)

            add_context(current_context, contexts)

            continue

        if inc:
            if not current_context:
                raise Exception(
                    "include should not happen before a context definition")
            incctx = inc.group(1)

            # Add the internal contexts if we talk about them (like parkedcalls)OA
            if incctx in internal_contexts:
                add_context(current_context, contexts)

            links.append((current_context, incctx))

            continue

        if gto:
            # Skip commented out lines with Goto..
            if gto.group(1) == ';':
                continue

            # Let's parse TIME stuff..
            if gto.group(3):
                chkctx = gto.group(4).split('?')[-1]
                add_link(current_context, chkctx)
            # Let's do GotoIf parsing..
            elif gto.group(2):
                chks = gto.group(4).split('?')[-1].split(':')
                add_link(current_context, chks[0])

                # A second possible destination ?
                if len(chks) == 2:
                    add_link(current_context, chks[1])
            else:
                chkctx = gto.group(4).split(',')[0]

                add_link(current_context, chkctx)

            # Add links with style=dotted
            # make sure there's no ';' in front of the Goto
            # Check from the end the presence of a ? (got GotoIf), then parse the two possibilities, add two
            # Check the (current_context, gotoctx, '') doesn't exist in links (or as (current_context, gotoctx, 'style=dotted'))
            # then add it there..

        if mac:
            # TODO
            # Skip commented out lines with Macro..
            # if mac.group(1) == ';':
            #     continue

            chkctx = mac.group(0)
            # e.g. chkctx = Macro(assert_refer_triaged
            # the below should update chkctx to equal macro macro-assert_refer_triaged
            chkctx = format_context(chkctx)

            add_context(chkctx, contexts)

            add_link(current_context, chkctx)

        if agi:
            chkctx = agi.group(0)
            # e.g. chkctx = AGI(get_voxeo_server.php
            # the below should update chkctx to equal agi-macro-get_voxeo_server
            chkctx = format_context(chkctx)

            add_context(chkctx, contexts)

            add_link(current_context, chkctx)

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
