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
from enum import Enum

from anki import hooks
from anki.utils import ids2str

from aqt import browser, gui_hooks, mw
from aqt.operations.scheduling import reposition_new_cards
from aqt.qt import QAction
from aqt.switch import Switch
from aqt.utils import qconnect, shortcut, showInfo, tr


class ShiftDirection(Enum):
     UP = 0
     DOWN = 1


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
        self._moveCard(ShiftDirection.UP)

    def moveCardDown(self):
        self._moveCard(ShiftDirection.DOWN)

    def moveCardToTop(self):
        card_ids = self.browser.selected_cards()
        if not self._ensureOnlyNewCards(card_ids):
            return showInfo(tr.browsing_only_new_cards_can_be_repositioned())

        verticalScrollBar = self.browser.form.tableView.verticalScrollBar()
        scrollBarPosition = verticalScrollBar.value()

        # old repositioning code was removed with https://github.com/ankitects/anki/commit/0331d8b588e2173af33aea3807538f17daf042bb
        op = reposition_new_cards(parent=self.browser, card_ids=card_ids, starting_from=0, step_size=1, randomize=False, shift_existing=True)
        op.run_in_background()
        self.browser.onSearchActivated()
        self._updateNewCardsDueDate()
        verticalScrollBar.setValue(scrollBarPosition)

    def _moveCard(self, shiftDirection):  # self is browser
        card_ids = self.browser.selected_cards()
        if not self._ensureOnlyNewCards(card_ids):
            return showInfo(tr.browsing_only_new_cards_can_be_repositioned())

        #Get the list of indexes of the selcted rows
        srowsidxes = []
        srows = self.browser.table._selected()
        for crow in srows:
            srowsidxes.append(crow.row())

        model = self.browser.table._model

        #Check if the first (last) selected row is the first (last) on the table
        #and return in that case because it cannot moved up (down)
        if shiftDirection == ShiftDirection.UP:
            if not self.browser.table.has_previous():
                return
            srowidx = min(srowsidxes)
        elif shiftDirection == ShiftDirection.DOWN:
            if not self.browser.table.has_next():
                return
            srowidx = max(srowsidxes)

        #Get the index of the card on which the new due is calculated
        if shiftDirection == ShiftDirection.UP:
            startidx = srowidx - 1
        else:
            startidx = srowidx + 1
        #Check that the card on which the new due is calculated is a new card, otherwise the selected
        #card is at the boundary with the review cards and should not be moved
        cf = model._items[startidx]
        cf2 = self.browser.col.db.list(
                "select id from cards where type = 0 and id in " + ids2str([cf]))
        if not cf2:
            return

        start = self.browser.col.getCard(cf).due

        #When we move down (up) and the cards are in ascending (descending) order, the new due date must be greater by one
        #respect the due date of the next (previous) card, otherwise the due date of the selected card will be equal of that of
        #the next (previous) card but its position will be still before the next (previous) card
        revs = self.browser.col.conf['sortBackwards']
        if shiftDirection == ShiftDirection.UP and revs or shiftDirection == ShiftDirection.DOWN and not revs:
            start = start + 1

        # old repositioning code was removed with https://github.com/ankitects/anki/commit/0331d8b588e2173af33aea3807538f17daf042bb
        op = reposition_new_cards(parent=self.browser, card_ids=card_ids, starting_from=start, step_size=1, randomize=False, shift_existing=True)
        op.run_in_background()
        self.browser.onSearchActivated()
        self._updateNewCardsDueDate()

    def _ensureOnlyNewCards(self, card_ids):
        new_card_ids = self.browser.col.db.list("select id from cards where type = 0 and id in " + ids2str(card_ids))
        return len(card_ids) == len(new_card_ids)

    def _updateNewCardsDueDate(self):
        """Update the due position of the next card added to place them at the end of the deck."""
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

        browse_mode_switch = self.browser.findChild(Switch)
        qconnect(browse_mode_switch.toggled, self._onBrowserModeToggled)

        isDueSort = self.browser.col.conf['sortType'] == 'cardDue'
        self.setActionsEnabled(isDueSort and not browse_mode_switch.isChecked())

    def _onBrowserModeToggled(self, checked):
        self.browser.fastCardReposition.setActionsEnabled(not checked)

def fastRepositionOnSortChanged(self, section, order):
    column = self._model.column_at_section(section)
    isDueSort = column.cards_mode_label == 'Due'
    self.browser.fastCardReposition.setActionsEnabled(isDueSort)


def initFastCardReposition(browser):
    browser.fastCardReposition = FastCardReposition(browser)


browser.table.Table._on_sort_column_changed = hooks.wrap(
    browser.table.Table._on_sort_column_changed, fastRepositionOnSortChanged
)

gui_hooks.browser_menus_did_init.append(initFastCardReposition)
