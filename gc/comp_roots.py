#!/usr/bin/python

# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# The Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import sys
from collections import namedtuple
import comp_parse_gc_graph
import argparse



# this comment is out of date


# Find the objects that are rooting a particular object (or objects of
# a certain class) in the cycle collector graph
#
# This works by reversing the graph, then flooding to find roots.
#
# There are various options to alter what is treated as a root, but
# these are mostly experimental, so they may not produce particularly
# useful results.
#
# --node-name-as-root nsRange (for example) will treat all objects
# with the node name nsRange as roots.  This is useful if a previous
# analysis has determined that a leak always involves an object being
# held onto by a certain class, and you want to continue with manual
# analysis starting at that object.



# Command line arguments

parser = argparse.ArgumentParser(description='Find a rooting object in the cycle collector graph.')

parser.add_argument('file_name',
                    help='cycle collector graph file name')

parser.add_argument('target',
                    help='address of target object or prefix of class name of targets')

parser.add_argument('--ignore-rc-roots', dest='ignore_rc_roots', action='store_const',
                    const=True, default=False,
                    help='ignore ref counted roots')

parser.add_argument('--ignore-js-roots', dest='ignore_js_roots', action='store_const',
                    const=True, default=False,
                    help='ignore Javascript roots')

parser.add_argument('--node-name-as-root', dest='node_roots',
                    metavar='CLASS_NAME',
                    help='treat nodes with this class name as extra roots')


args = parser.parse_args()



# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels[x]))

# print an edge description
def print_edge (ga, x, y):
  def print_edge_label (l):
    if len(l) == 2:
      l = l[0]
    sys.stdout.write(l)

  sys.stdout.write(ga.compartments[y])
  sys.stdout.write(' ')

  sys.stdout.write('--')
  lbls = ga.edgeLabels.get(x, {}).get(y, [])
  if len(lbls) != 0:
    sys.stdout.write('[')
    print_edge_label(lbls[0])
    for l in lbls[1:]:
      sys.stdout.write(', ')
      print_edge_label(l)
    sys.stdout.write(']')

  sys.stdout.write('->')


def explain_root (ga, root):
  print "via", ga.rootLabels[root], ":"

# print out the path to an object that has been discovered
def print_path (revg, ga, roots, x, path):
  if path == []:
    explain_root(ga, x)
  else:
    explain_root(ga, path[0][0])

  for p in path:
    print_node(ga, p[0])
    sys.stdout.write('\n    ')
    print_edge(ga, p[0], p[1])
    sys.stdout.write(' ')
  print_node(ga, x)
  print
  print


# look for roots and print out the paths to the given object
def findRoots (revg, ga, roots, x):
  visited = set([])
  path = []
  anyFound = [False]

  def findRootsDFS (y):
    if y in visited:
      return False
    visited.add(y)
    if y in roots: # treats black and gray roots as roots
      path.reverse()
      print_path(revg, ga, roots, x, path)
      path.reverse()
      anyFound[0] = True
    else:
      if not y in revg:
        return False
      path.append(None)
      for z in revg[y]:
        path[-1] = (z, y)
        if findRootsDFS(z):
          return True
      path.pop()
    return False

  if not x in revg:
    sys.stdout.write ('No other nodes point to {0}.\n\n'.format(x))
    return

  findRootsDFS(x)

  if not anyFound[0]:
    print 'No roots found.'


def reverseGraph (g):
  g2 = {}
  print 'Reversing graph.',
  sys.stdout.flush()
  for src, dsts in g.iteritems():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  print 'Done.'
  print
  return g2

def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = comp_parse_gc_graph.parseGCEdgeFile(fname)
  #sys.stdout.write ('Converting to single graph. ') 
  #sys.stdout.flush()
  g = comp_parse_gc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga)


####################

(g, ga) = loadGraph (args.file_name)
roots = ga.roots
revg = reverseGraph(g)


my_compartment = args.target


if False:
  findRoots(revg, ga, roots, "0x11ac143d0")
  exit(0)


print
print "Looking for compartment", my_compartment

num_roots = 0

if True:
  print "Checking for direct root references to the compartment."

  for x in roots:
    if ga.compartments[x] == my_compartment:
      print_node(ga, x)
      sys.stdout.write(' via ' + ga.rootLabels[x] + "\n")

  print


print "Checking for references from other compartments to the compartment."

for src, dsts in g.iteritems():
  if ga.compartments[src] != my_compartment:
    for d in dsts:
      if ga.compartments[d] == my_compartment:
        print_node(ga, src)
        print " from compartment", ga.compartments[src]
        print "to: ",
        print_node(ga, d)
        print
        findRoots(revg, ga, roots, src)


# first, only consider pointers to a compartment from roots.

# (we should also consider compartments that hold onto other compartments)

# roots are the set of objects reachable from various roots.


# For a given compartment, which other compartments/roots hold onto it?
