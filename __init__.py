# -*- coding: utf-8 -*-
#########################################################################
# Copyright (C) 2014 by Simone Gaiarin <simgunz@gmail.com>              #
#                                                                       #
# This program is free software; you can redistribute it and/or modify  #
# it under the terms of the GNU General Public License as published by  #
# the Free Software Foundation; either version 3 of the License, or     #
# (at your option) any later version.                                   #
#                                                                       #
# This program is distributed in the hope that it will be useful,       #
# but WITHOUT ANY WARRANTY; without even the implied warranty of        #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         #
# GNU General Public License for more details.                          #
#                                                                       #
# You should have received a copy of the GNU General Public License     #
# along with this program; if not, see <http://www.gnu.org/licenses/>.  #
#########################################################################

from anki import hooks
from anki.utils import ids2str

from aqt import browser
from aqt.qt import *
from aqt.utils import shortcut, showInfo

def fastRepositionOnSortChanged(self, idx, ord):
    isDueSort = self.model.activeCols[idx] == 'cardDue'
    self.form.mvtotopAction.setEnabled(isDueSort)
    self.form.mvuponeAction.setEnabled(isDueSort)
    self.form.mvdownoneAction.setEnabled(isDueSort)
    
def setupFastRepositionActions(browser):
    """Add actions to the browser menu to move the cards up and down
    """
    # Set the actions active only if the cards are sorted by due date. This is necessary because the reposition
    # is done considering the current ordering in the browser
    mvtotopAction = QAction(_("Move to top"), browser)
    mvtotopAction.setShortcut(shortcut(_("Alt+0")))
    mvtotopAction.triggered.connect(browser.moveCardToTop)
    
    mvuponeAction = QAction(_("Move one up"), browser)
    mvuponeAction.setShortcut(shortcut(_("Alt+Up")))
    mvuponeAction.triggered.connect(browser.moveCardUp)
    
    mvdownoneAction = QAction(_("Move one down"), browser)
    mvdownoneAction.setShortcut(shortcut(_("Alt+Down")))
    mvdownoneAction.triggered.connect(browser.moveCardDown)
    
    browser.form.mvtotopAction = mvtotopAction
    browser.form.mvuponeAction = mvuponeAction
    browser.form.mvdownoneAction = mvdownoneAction
    
    browser.form.menu_Cards.addSeparator()
    browser.form.menu_Cards.addAction(mvtotopAction)
    browser.form.menu_Cards.addAction(mvuponeAction)
    browser.form.menu_Cards.addAction(mvdownoneAction)
    
    isDueSort = browser.col.conf['sortType'] == 'cardDue'
    browser.form.mvtotopAction.setEnabled(isDueSort)
    browser.form.mvuponeAction.setEnabled(isDueSort)
    browser.form.mvdownoneAction.setEnabled(isDueSort)

def moveCard(self, pos):
    revs = self.col.conf['sortBackwards']
    srows = self.form.tableView.selectionModel().selectedRows()

    #Get only new cards and exit if none are selected
    cids = self.selectedCards()
    cids2 = self.col.db.list(
            "select id from cards where type = 0 and id in " + ids2str(cids))
    if not cids2:
        return showInfo(_("Only new cards can be repositioned."))

    #Get the list of indexes of the selcted rows
    srowsidxes = []
    for crow in srows:
        srowsidxes.append(crow.row())

    #Check if the first (last) selected row is the first (last) on the table
    #and return in that case because it cannot moved up (down)
    if pos == -1:
        srowidx = min(srowsidxes)
        if srowidx == 0:
            return
    elif pos == 1:
        srowidx = max(srowsidxes)
        if srowidx == len(self.model.cards)-1:
            return

    #Get the index of the card on which the new due is calculated
    startidx = srowidx+pos

    #Check that the card on which the new due is calculated is a new card, otherwise the selected
    #card is at the boundary with the review cards and should not be moved
    cf = [self.model.cards[startidx]]
    cf2 = self.col.db.list(
            "select id from cards where type = 0 and id in " + ids2str(cf))
    if not cf2:
        return

    #When we move down (up) and the cards are in ascending (descending) order, the new due date must be greater by one
    #respect the due date of the next (previous) card, otherwise the due date of the selected card will be equal of that of
    #the next (previous) card but its position will be still before the next (previous) card
    inc = (revs==0 and pos>0) or (revs==1 and pos<0)

    start=self.col.getCard(self.model.cards[startidx]).due+inc

    #Perform repositioning. Copied from browser.Browser repositon method. Should be updated is changed upstream
    self.model.beginReset()
    self.mw.checkpoint(_("Reposition"))
    self.col.sched.sortCards(cids, start=start, step=1, shuffle=0, shift=1) # Preserve this line like this
    self.search()
    self.mw.requireReset()
    self.model.endReset()
    #Update the due position of the next card added.
    #This guarantees that the new cards are added a the end.
    self.col.conf['nextPos'] = self.col.db.scalar(
            "select max(due)+1 from cards where type = 0") or 0

def moveCardUp(self):
    self.moveCard(-1)

def moveCardDown(self):
    self.moveCard(1)

def moveCardToTop(self):
    #Get only new cards and exit if none are selected
    cids = self.selectedCards()
    cids2 = self.col.db.list(
            "select id from cards where type = 0 and id in " + ids2str(cids))
    if not cids2:
        return showInfo(_("Only new cards can be repositioned."))

    #Perform repositioning. Copied from browser.Browser repositon method. Should be updated is changed upstream
    self.model.beginReset()
    self.mw.checkpoint(_("Reposition"))
    self.col.sched.sortCards(cids, start=0, step=1, shuffle=0, shift=1) # Preserve this line like this
    self.search()
    self.mw.requireReset()
    self.model.endReset()
    #Update the due position of the next card added.
    #This guarantees that the new cards are added a the end.
    self.col.conf['nextPos'] = self.col.db.scalar(
            "select max(due)+1 from cards where type = 0") or 0

browser.Browser.moveCard = moveCard
browser.Browser.moveCardUp = moveCardUp
browser.Browser.moveCardDown = moveCardDown
browser.Browser.moveCardToTop = moveCardToTop

browser.Browser.onSortChanged = hooks.wrap(
    browser.Browser.onSortChanged, fastRepositionOnSortChanged)

hooks.addHook("browser.setupMenus", setupFastRepositionActions)
