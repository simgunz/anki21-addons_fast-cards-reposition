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

from aqt import browser, gui_hooks, mw
from aqt.operations.scheduling import reposition_new_cards
from aqt.qt import QAction
from aqt.utils import shortcut, showInfo

def gc(arg, fail=False):
    conf = mw.addonManager.getConfig(__name__)
    if conf:
        return conf.get(arg, fail)
    else:
        return fail

class FastCardReposition:
    def __init__(self, browser):
        self.browser = browser
        self.actions = []
        self._setupFastRepositionActions()

    def setActionsEnabled(self, enabled):
        for action in self.actions:
           action.setEnabled(enabled)

    def moveCardUp(self):
        self._moveCard(-1)

    def moveCardDown(self):
        self._moveCard(1)

    def moveCardToTop(self):
        #Get only new cards and exit if none are selected
        cids = self.browser.selectedCards()
        cids2 = self.browser.col.db.list(
                "select id from cards where type = 0 and id in " + ids2str(cids))
        if not cids2:
            return showInfo("Only new cards can be repositioned.")

        verticalScrollBar = self.browser.form.tableView.verticalScrollBar()
        scrollBarPosition = verticalScrollBar.value()

        # old repositioning code was removed with https://github.com/ankitects/anki/commit/0331d8b588e2173af33aea3807538f17daf042bb
        op = reposition_new_cards(parent=self.browser, card_ids=cids, starting_from=0, step_size=1, randomize=0, shift_existing=1)
        op.run_in_background()
        self.browser.onSearchActivated()
        #Update the due position of the next card added.
        #This guarantees that the new cards are added a the end.
        self.browser.col.conf['nextPos'] = self.browser.col.db.scalar(
                "select max(due)+1 from cards where type = 0") or 0

        verticalScrollBar.setValue(scrollBarPosition)

    def _moveCard(self, pos):  # self is browser
        revs = self.browser.col.conf['sortBackwards']
        srows = self.browser.table._selected()

        # sanity check
        if self.browser.table.is_notes_mode():
            return showInfo("Only works in cards mode.")

        #Get only new cards and exit if none are selected
        cids = self.browser.selectedCards()
        cids2 = self.browser.col.db.list(
                "select id from cards where type = 0 and id in " + ids2str(cids))
        if not cids2:
            return showInfo("Only new cards can be repositioned.")

        #Get the list of indexes of the selcted rows
        srowsidxes = []
        for crow in srows:
            srowsidxes.append(crow.row())

        model = self.browser.table._model

        #Check if the first (last) selected row is the first (last) on the table
        #and return in that case because it cannot moved up (down)
        if pos == -1:
            if not self.browser.table.has_previous():
                return
            srowidx = min(srowsidxes)
        elif pos == 1:
            if not self.browser.table.has_next():
                return
            srowidx = max(srowsidxes)

        #Get the index of the card on which the new due is calculated
        startidx = srowidx+pos
        #Check that the card on which the new due is calculated is a new card, otherwise the selected
        #card is at the boundary with the review cards and should not be moved
        cf = model._items[startidx]
        cf2 = self.browser.col.db.list(
                "select id from cards where type = 0 and id in " + ids2str([cf]))
        if not cf2:
            return

        #When we move down (up) and the cards are in ascending (descending) order, the new due date must be greater by one
        #respect the due date of the next (previous) card, otherwise the due date of the selected card will be equal of that of
        #the next (previous) card but its position will be still before the next (previous) card
        inc = (revs==0 and pos>0) or (revs==1 and pos<0)

        start=self.browser.col.getCard(cf).due+inc

        # old repositioning code was removed with https://github.com/ankitects/anki/commit/0331d8b588e2173af33aea3807538f17daf042bb
        op = reposition_new_cards(parent=self.browser, card_ids=cids, starting_from=start, step_size=1, randomize=0, shift_existing=1)
        op.run_in_background()
        self.browser.onSearchActivated()
        #Update the due position of the next card added.
        #This guarantees that the new cards are added a the end.
        self.browser.col.conf['nextPos'] = self.browser.col.db.scalar(
                "select max(due)+1 from cards where type = 0") or 0

    def _setupFastRepositionActions(self):
        """Add actions to the browser menu to move the cards up and down
        """
        # Set the actions active only if the cards are sorted by due date. This is necessary because the reposition
        # is done considering the current ordering in the browser
        mvtotopAction = QAction("Move to top", self.browser)
        mvtotopAction.setShortcut(shortcut(gc("shortcut: Move to top", "Alt+0")))
        mvtotopAction.triggered.connect(self.moveCardToTop)
        self.actions.append(mvtotopAction)

        mvuponeAction = QAction("Move one up", self.browser)
        mvuponeAction.setShortcut(shortcut(gc("shortcut: Move one up", "Alt+Up")))
        mvuponeAction.triggered.connect(self.moveCardUp)
        self.actions.append(mvuponeAction)

        mvdownoneAction = QAction("Move one down", self.browser)
        mvdownoneAction.setShortcut(shortcut(gc("shortcut: Move one down", "Alt+Down")))
        mvdownoneAction.triggered.connect(self.moveCardDown)
        self.actions.append(mvdownoneAction)

        self.browser.form.menu_Cards.addSeparator()
        self.browser.form.menu_Cards.addAction(mvtotopAction)
        self.browser.form.menu_Cards.addAction(mvuponeAction)
        self.browser.form.menu_Cards.addAction(mvdownoneAction)

        isDueSort = self.browser.col.conf['sortType'] == 'cardDue'
        self.setActionsEnabled(isDueSort)


def fastRepositionOnSortChanged(self, section, order):
    column = self._model.column_at_section(section)
    isDueSort = column.cards_mode_label == 'Due'
    self.browser.fastCardReposition.setActionsEnabled(isDueSort)


def initFastCardReposition(browser):
    browser.fastCardReposition = FastCardReposition(browser)


browser.table.Table._on_sort_column_changed = hooks.wrap(
    browser.table.Table._on_sort_column_changed, fastRepositionOnSortChanged)

gui_hooks.browser_menus_did_init.append(initFastCardReposition)
