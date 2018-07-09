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
from aqt.utils import shortcut

def borderImg(link, icon, on, title, tooltip=None):
    """Draw a button for the browser toolbar

       Has been copied from browser.BrowserToolbar draw function and should be updated
       if that function is changed upstream
    """
    if on:
        fmt = '''<a class=hitem title="%s" href="%s">\
              <img valign=bottom style='height: 16px; ankiborder: 1px solid #aaa;' src="qrc:/icons/%s.png"> %s</a>'''
    else:
        fmt = '''<a class=hitem title="%s" href="%s">\
              <img style="padding: 1px;" valign=bottom src="qrc:/icons/%s.png"> %s</a>'''
    return fmt % (tooltip or title, link, icon, title)

def setupFastRepositionButtons(self):
    """Add buttons to the browser toolbar to move the cards up and down
    """
    # Show the buttons only if the cards are sorted by due date. This is necessary because the reposition
    # is done considering the current ordering in the browser
    if self.browser.col.conf['sortType'] == 'cardDue':
        mf = self.web.page().mainFrame()
        buttonsrow = mf.findFirstElement('a.hitem').parent()
        buttons = buttonsrow.toInnerXml();
        buttons += borderImg("mvupone", "arrow-up", True, _("Move up"), shortcut(_("Move up (ALT+Up)"))) + \
                   borderImg("mvdownone", "arrow-down", True, _("Move down"), shortcut(_("Move down (ALT+Down)"))) + \
                   borderImg("mvtotop", "view-sort-descending", True, "Move to top", shortcut(_("Move to top (ALT+0)")))
        buttonsrow.setInnerXml(buttons)

def fastRepositionLinkHandler(self, l):
    """Extends the method _linkHandler in browser.BrowserToolbar in order to manage the two new actions
    """
    if l == "mvupone":
        self.browser.moveCard(-1)
    elif l == "mvdownone":
        self.browser.moveCard(1)
    elif l == "mvtotop":
        self.browser.moveCardToTop()

    #Update the due position of the next card added.
    #This guarantees that the new cards are added a the end.
    self.browser.col.conf['nextPos'] = self.browser.col.db.scalar(
            "select max(due)+1 from cards where type = 0") or 0

def moveCard(self, pos):
    revs = self.col.conf['sortBackwards']
    srows = self.form.tableView.selectionModel().selectedRows()

    #Get only new cards and exit if none are selected
    cids = self.selectedCards()
    cids2 = self.col.db.list(
            "select id from cards where type = 0 and id in " + ids2str(cids))
    if not cids2:
        return

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
    self.col.sched.sortCards(
        cids, start=start, step=1,
        shuffle=0, shift=1)
    self.onSearch(reset=False)
    self.mw.requireReset()
    self.model.endReset()

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
        return

    #Perform repositioning. Copied from browser.Browser repositon method. Should be updated is changed upstream
    self.model.beginReset()
    self.mw.checkpoint(_("Reposition"))
    self.col.sched.sortCards(
        cids, start=0, step=1,
        shuffle=0, shift=1)
    self.onSearch(reset=False)
    self.mw.requireReset()
    self.model.endReset()

def onSetupMenus(self):
    #Setup shortcuts
    self.moveuponeShct = QShortcut(QKeySequence("Alt+Up"), self)
    self.connect(self.moveuponeShct, SIGNAL("activated()"), self.moveCardUp)
    self.movedownoneShct = QShortcut(QKeySequence("Alt+Down"), self)
    self.connect(self.movedownoneShct, SIGNAL("activated()"), self.moveCardDown)
    self.movetotopShct = QShortcut(QKeySequence("Alt+0"), self)
    self.connect(self.movetotopShct, SIGNAL("activated()"), self.moveCardToTop)


browser.Browser.moveCard = moveCard
browser.Browser.moveCardUp = moveCardUp
browser.Browser.moveCardDown = moveCardDown
browser.Browser.moveCardToTop = moveCardToTop

browser.BrowserToolbar.draw = hooks.wrap(
    browser.BrowserToolbar.draw, setupFastRepositionButtons)
browser.BrowserToolbar._linkHandler = hooks.wrap(
    browser.BrowserToolbar._linkHandler, fastRepositionLinkHandler)
hooks.addHook("browser.setupMenus", onSetupMenus)
