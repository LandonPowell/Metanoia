# Intended for Python2

"""
    /etc/browserConfig/ must be created with the
    correct files placed within it for this to work
    properly.

    * /etc/browserConfig/style.css
"""

import sys
import config
import thread # To-do
import re
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
    QDialog,
    QLabel,
    QMenu,
    QGraphicsDropShadowEffect,
    QLineEdit,
    QPushButton,
)

from PyQt5.QtWebKit import *
from PyQt5.QtWebKitWidgets import QWebView, QWebInspector

from PyQt5.QtCore import *
from PyQt5.QtGui import *

class Prompt(QThread):
    promptSubmit = pyqtSignal(str, str)

    def __init__(self, parent):
        super(Prompt, self).__init__()
        self.type = "js"

    def run(self):
        promptText = raw_input(self.type + ":> ")
        if promptText[0] == "@":
            self.type = promptText[1:]
        else:
            self.promptSubmit.emit(self.type, promptText)
        self.run()

class Window(QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.initUI()

    def evalPrompt(self, type, command):
        if type == "js":
            self.browser.loadJS(command)
        elif type == "url":
            self.browser.load(QUrl(command))
        elif type == "search":
            self.browser.load(QUrl(
                self.omnibar.line.searchParser(
                    command
                )
            ))

    def initUI(self):
        self.tabID = 0

        self.browser = Browser(self)
        self.setCentralWidget(self.browser)

        self.omnibar = Omnibar(self.browser, self)

        self.browser.addTab({'url' : QUrl(
            sys.argv[1] if len(sys.argv) > 1
            else config.homePage
        )})
        self.browser.changeTab(1)

        self.resizeEvent = self.resize

        self.setWindowTitle(config.name)
        self.setGeometry(20, 20, 1200, 800)

        self.prompt = Prompt(self)
        self.prompt.promptSubmit.connect(self.evalPrompt)
        self.prompt.start()

        self.show()

    def urlChange(self, url):
        self.omnibar.line.setText( url.toString() )
        mainWindow.setWindowTitle(config.name + " @ " + url.toString())

        # Check for insecure protocols.
        if url.scheme() in ["http"]:
            warning = Warning(self)

    def resize(self, resizeEvent):
        self.omnibar.resize(resizeEvent.size().width() - 20,  20)
        self.omnibar.tabBox.resize(resizeEvent.size().width() - 19, 45)
        for x in self.browser.tabViews:
            self.browser.tabViews[x].resize(resizeEvent.size())

    def event(self, event):
        modifiers = QApplication.keyboardModifiers()
        ctrl = modifiers == Qt.ControlModifier

        if event == QEvent(12345): print(event)

        # Hide and show on control press and release.
        if event.type() == 6 and event.key() == 16777249:
            self.omnibar.moveIn()
        elif event.type() == 7 and event.key() == 16777249:
            if not self.omnibar.line.hasFocus():
                self.omnibar.moveOut()

        # Keyboard shortcuts using control.
        elif ctrl and event.type() == 6:
            if event.key() == Qt.Key_L: # Focus on URL bar.
                self.omnibar.line.setFocus()
                return True

            elif event.key() == Qt.Key_T: # Create new tab.
                self.browser.addTab({
                    'url' : QUrl(config.homePage),
                })
                return True

            elif event.key() == Qt.Key_W:
                self.browser.removeTab(self.browser.activeTab)
                print(self.browser.activeTab)
                self.browser.moveToHomeTab()
                return True

            elif event.key() == Qt.Key_Tab:
                for x in self.browser.tabViews:
                    if x > self.browser.activeTab:
                        self.browser.changeTab(x)
                        return True
                self.browser.moveToHomeTab()
                return True

        return QMainWindow.event(self, event)

class Browser(QWidget):
    def __init__(self, parent):
        super(Browser, self).__init__(parent)
        self.parent = parent
        self.tabViews = {}
        self.activeTab = 0

    def addTab(self, tab):
        self.parent.tabID += 1
        tab['id'] = self.parent.tabID

        tabView = BrowserTab(self, tab['id'])
        tabView.resize(self.size())
        tabView.load(tab['url'])

        self.tabViews[tab['id']] = tabView
        self.parent.omnibar.newTab(tab)

    def changeTab(self, id):
        self.activeTab = id
        if id not in self.tabViews:
            print(str(id) + " does not exist.")
            return False
        # O(n) currently. Possibly could be O(1)?
        for x in self.tabViews:
            self.tabViews[x].setVisible(False)
        self.tabViews[id].setVisible(True)
        self.parent.omnibar.line.setText(
            self.tabViews[id].url().toString()
        )

    def moveToHomeTab(self):
        for x in self.tabViews:
            return self.changeTab(x)

    def removeTab(self, id):
        self.tabViews[id].close()
        self.tabViews.pop(id, None)
        self.parent.omnibar.removeTab(id)

        if self.activeTab == id:
            for x in self.tabViews:
                return self.changeTab(x)

    def load(self, url):
        self.tabViews[self.activeTab].load(url)

    def loadJS(self, code):
        self.tabViews[self.activeTab].page(
        ).currentFrame().evaluateJavaScript(
            code
        )

class BrowserTab(QWebView):
    def __init__(self, parent, tabID):
        super(BrowserTab, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.parent = parent
        self.tabID = tabID
        self.settings().setUserStyleSheetUrl(QUrl(
            "file://etc/browserConfig/style.css"
        ))
        self.urlChanged.connect(self.urlChange)
        self.titleChanged.connect(self.titleChange)

        self.settings().setAttribute(
            self.settings().DeveloperExtrasEnabled, True
        )

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        hit = self.page().currentFrame().hitTestContent(event.pos())
        url = hit.linkUrl()

        if url.isValid():
            newTab = menu.addAction("New Tab")
            copyLink = menu.addAction("Copy Link Address")
        else:
            newTab = ""
            copyLink = ""

        debug = menu.addAction("Debug/Inspect")
        quitBrowser = menu.addAction("Quit")

        action = menu.exec_( self.mapToGlobal(event.pos()) )
        if action == quitBrowser:
            sys.exit(0)

        elif action == debug:
            # Tl:dr; This ugly code opens a debug window.
            self.dlg = QDialog()
            self.inspector = QWebInspector(self.parent)
            self.inspector.setPage(self.page())
            self.dlg.vbox = QVBoxLayout()
            self.dlg.vbox.addWidget(self.inspector)
            self.dlg.vbox.setContentsMargins(0,0,0,0)
            self.dlg.setLayout(self.dlg.vbox)
            self.dlg.setModal(False)
            self.dlg.show()

        elif action == newTab:
            self.parent.addTab({'url':url})
        elif action == copyLink:
            app.clipboard().setText(url.toString())

    def urlChange(self, url):
        self.parent.parent.omnibar.updateTab({
            'id' : self.tabID,
            'title': url.toString(),
            'url': url,
        })

    def titleChange(self, title):
        self.parent.parent.omnibar.updateTab({
            'id' : self.tabID,
            'title' : title,
            'url' : self.url()
        })

class Omnibar(QFrame):
    def __init__(self, browser, parent):
        super(Omnibar, self).__init__(parent)
        self.out = True
        self.browser = browser
        self.parent = parent
        self.tabs = []

        self.setGeometry(QRect(10, -50, 500, 40))
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            QWidget {
                background-color: #fff;
            }
            QLineEdit, QPushButton {
                color: #666;
                border: 0px solid #fff;
                margin: 0px;
            }
            QPushButton {
                text-align: center;
                border-right: 1px solid #ccc;
                background-color: #fff;
            }
            QLineEdit {
                padding-left: 5px;
            }
        """)
        self.setFixedHeight(35)
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(4)
        self.shadow.setOffset(0,1)
        self.shadow.setColor(QColor(0,0,0, 100))
        self.setGraphicsEffect(self.shadow)

        self.hbox = QHBoxLayout()
        self.hbox.setSpacing(0)
        self.hbox.setContentsMargins(10,0,0,10)
        self.tabBox = TabBox(self)
        self.tabBox.setLayout(self.hbox)

        self.line = Line(self)

    def moveOut(self):
        if self.out:
            return True
        self.out = True

        self.anim = QPropertyAnimation(self, "pos")
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.anim.setStartValue(QPointF( 10, 10 ))
        self.anim.setEndValue(QPointF( 10, -50 ))
        self.anim.start()

    def moveIn(self):
        if not self.out:
            return True
        self.out = False

        self.anim = QPropertyAnimation(self, "pos")
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.anim.setStartValue(QPointF( 10, -50 ))
        self.anim.setEndValue(QPointF( 10, 10 ))
        self.anim.start()

    def newTab(self, tab):
        tabButton = Tab(self, tab, self.browser)
        url = tab['url']
        tabButton.setText(url.toString())
        self.hbox.addWidget(tabButton)
        self.tabs.append({
            'id' : tab['id'],
            'title': url.toString(),
            'url': url,
            'item': tabButton
        })

    # removeTab and updateTab need to be fixed.
    # Currently O(tabs) instead of O(1)

    def removeTab(self, id):
        for x in self.tabs:
            if x['id'] == id:
                self.hbox.removeWidget( x['item'] )
                x['item'].close()
                self.tabs.remove(x)

    def updateTab(self, tab):
        if self.parent.browser.activeTab == tab['id']:
            self.line.setText(tab['url'].toString())

        for x in self.tabs:
            if x['id'] == tab['id']:
                return x['item'].setText(tab['title'] or tab['url'].toString())

    def event(self, event):
        ctrl = QApplication.keyboardModifiers() == Qt.ControlModifier

        return QWidget.event(self, event)

class Line(QLineEdit):
    def __init__(self, parent):
        super(Line, self).__init__(parent)
        self.parent = parent
        self.returnPressed.connect(self.onEnter)

    def onEnter(self):
        if self.text()[:11] == "javascript:":
            return self.parent.browser.loadJS(self.text()[11:])

        url = self.searchParser( self.text() )
        self.parent.browser.load(url)

    def event(self, event):
        ctrl = QApplication.keyboardModifiers() == Qt.ControlModifier

        if event.type() == QEvent.FocusOut and not ctrl:
            self.parent.moveOut()
            self.moveOut()
        elif event.type() == QEvent.FocusIn:
            self.moveIn()

        return QLineEdit.event(self, event)

    def moveOut(self):
        self.anim = QPropertyAnimation(self, "size")
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.anim.setStartValue( QSize(self.parent.width(), self.parent.height()) )
        self.anim.setEndValue( QSize(self.parent.width(), 0) )
        self.anim.start()

    def moveIn(self):
        self.anim = QPropertyAnimation(self, "size")
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.anim.setStartValue( QSize(self.parent.width(), 0) )
        self.anim.setEndValue( QSize(self.parent.width(), self.parent.height()) )
        self.anim.start()

    def searchParser(self, text):
        search = "https://duckduckgo.com/?q="
        if re.match('http(s)?://', text):
            return QUrl(text)
        elif re.match('([a-z\d-]+\\.)+[a-z\d-]+/', text):
            return QUrl("https://"+text)
        elif re.match('([a-z\d-]+\\.)+[a-z\d-]+/?', text):
            if " " in text:
                return QUrl(search + text)
            else:
                return QUrl("https://"+text)
        elif re.match('javascript: ', text):
            return QUrl(text)
        else:
            return QUrl(search + text)

class TabBox(QWidget):
    def __init__(self, parent):
        super(TabBox, self).__init__(parent)

class Tab(QPushButton):
    def __init__(self, parent, tab, browser):
        super(Tab, self).__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.parent = parent
        self.browser = browser
        self.tabID = tab['id']
        self.active = False
        self.clicked.connect(self.clickEvent)

    def clickEvent(self, _):
        self.browser.changeTab(self.tabID)

class Warning(QDialog):
    def __init__(self, parent):
        super(Warning, self).__init__(parent)
        self.createWarning()

    def createWarning(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #000;
                padding: 10px;
            }
            QLabel {
                color: #f00;
            }
        """)
        vbox = QVBoxLayout()

        text = QLabel()
        text.setText("Warning: You're vulnerable! Your browser traffic is <br>\
likely being intercepted. To resolve this issue, only <br>\
use <code>http<b>s</b>://</code> webpages, and avoid <code>http://</code>. <br>\
The difference is only one letter! ")
        vbox.addWidget(text)

        self.setLayout(vbox)
        self.setWindowTitle("SECURITY WARNING!")
        self.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = Window()
    sys.exit(app.exec_())
