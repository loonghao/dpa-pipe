from collections import defaultdict

from PySide import QtCore, QtGui

from dpa.action import ActionError
from dpa.action.registry import ActionRegistry
from dpa.app.entity import EntityError, EntityRegistry
from dpa.app.session import SessionRegistry
from dpa.product import Product
from dpa.product.category import ProductCategory
from dpa.product.version import ProductVersion
from dpa.ui.app.entity import EntityTreeWidget
from dpa.ui.action.options import ActionOptionWidget
from dpa.ui.icon.factory import IconFactory


# -----------------------------------------------------------------------------
class EntityImportWizard(QtGui.QWizard):

    # -------------------------------------------------------------------------
    def __init__(self, session=None, parent=None):

        super(EntityImportWizard, self).__init__(parent=parent)

        self.setModal(True)

        if not session:
            session = SessionRegistry().current()

        self._session = session

        logo_pixmap = QtGui.QPixmap(
            IconFactory().disk_path("icon:///images/icons/import_32x32.png"))

        self.setWindowTitle("Product Import")
        self.setPixmap(QtGui.QWizard.LogoPixmap, logo_pixmap)

        self._query_categories()

        query_id = self.addPage(self.product_query_page)
        selection_id = self.addPage(self.product_selection_page)
        options_id = self.addPage(self.import_options_page)
        confirm_id = self.addPage(self.import_confirm_page)

        self.setOption(QtGui.QWizard.CancelButtonOnLeft, on=True)

        self.product_widget.itemSelectionChanged.connect(self._toggle_options)

        self.setButtonText(QtGui.QWizard.FinishButton, 'Export')

        self.currentIdChanged.connect(self._check_descriptions)

    # -------------------------------------------------------------------------
    def accept(self):

        # XXX currently assuming exports are fast. exports could be time 
        # consuming. should probably do these in a separate thread or at 
        # least give the user some more feedback about what is happening.

        self.setEnabled(False)

        errors = []

        publish = self._publish_check.isChecked()
        version_up = self._version_check.isChecked()

        for entity in self.entity_widget.selected_entities():
            
            option_widget = self._options[entity]['widget']
            desc_edit = self._descriptions[entity]['widget']

            try:
                product_reprs = entity.export(
                    product_desc=desc_edit.text(),
                    version_note=self._note_edit.text(),
                    **option_widget.value
                )
            except Exception as e:
                errors.append(e)
            else:
                # XXX should use product update action
                if publish:
                    for product_repr in product_reprs:
                        product_ver = product_repr.product_version
                        if not product_ver.published:
                            product_ver.publish()

        if version_up and not errors:
            version_action_cls = ActionRegistry().get_action('version', 'work')            
            if not version_action_cls:
                errors.append(
                    "Unable to version up. Could not location version action.")
            else:
                version_action = version_action_cls(
                    spec=self.session.ptask_area.spec,
                    description=self._note_edit.text(),
                )

                try:
                    version_action()
                except Exception as e:
                    errors.append("Unable to version up: "  + str(e))

        self.setEnabled(True)

        if errors:
            error_dialog = QtGui.QErrorMessage(self)
            error_dialog.setWindowTitle("Export Errors")
            error_dialog.showMessage(
                "There were errors during export:<br><br>" + \
                "<br>".join([str(e) for e in errors])
            )
        else:
            super(EntityExportWizard, self).accept()

    # -------------------------------------------------------------------------
    def showEvent(self, event):
        super(EntityImportWizard, self).showEvent(event)
        self._toggle_options()

    # -------------------------------------------------------------------------
    def initializePage(self, event):
        super(EntityImportWizard, self).initializePage(event)

        if self._product_selection_page == self.currentPage():
            print "entity selection page"
            self._query_products()

    # -------------------------------------------------------------------------
    def _query_categories(self): 
        self._entity_categories = []

        entity_classes = EntityRegistry().get_entity_classes(
            self.session.app_name)

        for entity in entity_classes:
            if not entity.importable:
                continue

            self._entity_categories.append(entity.category)
         
    # -------------------------------------------------------------------------
    def _query_products(self):
        # find all available published products based on input
        products = Product.list(category=self.query_values['category'],
            search=self.query_values['spec'],
            name=self.query_values['name'])

        self._importable_products = []

        for product in products:
            print product.spec
            print self.query_values['official']
            print self.query_values['published']
            print self.query_values['deprecated']

            if self.query_values['published']:
                if self.query_values['official']:
                    if not self.query_values['deprecated']:
                        product_versions = ProductVersion.list(
                            product=product.spec,
                            published=self.query_values['published'],
                            is_official=self.query_values['official'],
                            deprecated=self.query_values['deprecated'])

            print product_versions
            for pv in product_versions:
                print pv
                self._importable_products.append(pv)

        print self.importable_products
        self._product_widget = EntityTreeWidget(self.importable_products)
        self._product_widget.setFocusPolicy(QtCore.Qt.NoFocus)

    # -------------------------------------------------------------------------
    @property
    def importable_products(self):
        
        if not hasattr(self, '_importable_products'):
            return []

        return self._importable_products

    # -------------------------------------------------------------------------
    @property
    def session(self):
        return self._session

    # -------------------------------------------------------------------------
    @property
    def query_values(self):

        if not hasattr(self, '_query_values'):
            return defaultdict(dict)

        return self._query_values

    # -------------------------------------------------------------------------
    @property
    def product_widget(self):

        if not hasattr(self, '_product_widget'):
            return EntityTreeWidget(self.importable_products)

        return self._product_widget

    # -------------------------------------------------------------------------   
    def _set_query_values(self, key, value):
        self._query_values[key] = value

    # -------------------------------------------------------------------------
    @property
    def product_query_page(self):
        if hasattr(self, '_product_query_page'):
            return self._product_query_page

        self._query_values = defaultdict(dict)

        page = QtGui.QWizardPage()
        page.setTitle("Search")
        page.setSubTitle("Search for products you'd like to import.")

        nameQ = QtGui.QLineEdit()
        self._set_query_values('name', nameQ.text())
        specQ = QtGui.QLineEdit()
        self._set_query_values('spec', specQ.text())
        catQ = QtGui.QComboBox()
        for cat in self._entity_categories:
            catQ.addItem(self.tr(str(cat)))
        self._set_query_values('category', catQ.currentText())
        pubQ = QtGui.QCheckBox('Published Versions')
        self._set_query_values('published', pubQ.isChecked())
        offQ = QtGui.QCheckBox('Official Versions')
        self._set_query_values('official', offQ.isChecked())
        depQ = QtGui.QCheckBox('Exclude Deprecated')
        depQ.setChecked(True)
        self._set_query_values('deprecated', not depQ.isChecked())

        nameQ.textChanged.connect(
            lambda q: self._set_query_values('name', nameQ.text()))
        specQ.textChanged.connect(
            lambda q: self._set_query_values('spec', specQ.text()))
        catQ.activated.connect(
            lambda q: self._set_query_values('category', catQ.currentText()))
        pubQ.toggled.connect(
            lambda q: self._set_query_values('published', pubQ.isChecked()))
        offQ.toggled.connect(
            lambda q: self._set_query_values('official', offQ.isChecked()))
        depQ.toggled.connect(
            lambda q: self._set_query_values('deprecated', not depQ.isChecked()))

        queryForm = QtGui.QFormLayout()
        queryForm.addRow(self.tr("Category:  "), catQ)
        queryForm.addRow(self.tr("Name:      "), nameQ)
        queryForm.addRow(self.tr("Spec:      "), specQ)
        queryForm.setVerticalSpacing(5)

        optQuery = QtGui.QHBoxLayout()
        optQuery.addWidget(pubQ, 0, QtCore.Qt.AlignLeft)
        optQuery.addWidget(offQ, 1, QtCore.Qt.AlignCenter)
        optQuery.addWidget(depQ, 0, QtCore.Qt.AlignRight)
        optQuery.setSpacing(5)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(queryForm)
        layout.addSpacing(5)
        layout.addWidget(QtGui.QLabel("Other Options:    "))
        layout.addLayout(optQuery)

        page.setLayout(layout)

        self._product_query_page = page
        return self._product_query_page

    # -------------------------------------------------------------------------
    @property
    def product_selection_page(self):

        if hasattr(self, '_product_selection_page'):
            return self._product_selection_page

        page = QtGui.QWizardPage()
        page.setTitle("Selection")
        page.setSubTitle(
            "Select the products you'd like to import.")

        self._product_widget = EntityTreeWidget(self.importable_products)
        self._product_widget.setFocusPolicy(QtCore.Qt.NoFocus)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(QtGui.QLabel('Available for import :'))
        layout.addWidget(self.product_widget)

        page.setLayout(layout)

        self._product_selection_page = page
        return self._product_selection_page

    # -------------------------------------------------------------------------
    @property
    def entity_widget(self):

        if hasattr(self, '_entity_widget'):
            return self._entity_widget

        return None

    # -------------------------------------------------------------------------
    @property
    def import_options_page(self):

        if hasattr(self, '_import_options_page'):
            return self._import_options_page

        page = QtGui.QWizardPage()
        page.setTitle("Options")
        page.setSubTitle(
            "Set the options for the products being imported.")

        self._options = defaultdict(dict)

        options_layout = QtGui.QVBoxLayout()

        options_widget = QtGui.QWidget()
        options_widget.setLayout(options_layout)

        scroll_area = QtGui.QScrollArea()
        scroll_area.setFocusPolicy(QtCore.Qt.NoFocus)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(options_widget)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(scroll_area)

        page.setLayout(layout)

        self._import_options_page = page
        return self._import_options_page

    # -------------------------------------------------------------------------
    @property
    def import_confirm_page(self):

        if hasattr(self, '_import_confirm_page'):
            return self._import_confirm_page

        layout = QtGui.QVBoxLayout()

        note_lbl = QtGui.QLabel(
            "Describe the work you did on the entities being exported:   (required)")
        self._note_edit = QtGui.QLineEdit()
        self._note_edit.setFocus()

        self._note_edit.textChanged.connect(
            lambda t: self._check_descriptions())

        layout.addWidget(note_lbl)
        layout.addWidget(self._note_edit)
        layout.addSpacing(5)

        self._import_confirm_page = QtGui.QWizardPage()
        self._import_confirm_page.setTitle("Confirm")
        self._import_confirm_page.setSubTitle(
            "Describe and confirm the folowing imports :")
        self._import_confirm_page.setLayout(layout)

        return self._import_confirm_page

    # -------------------------------------------------------------------------
    def _check_descriptions(self):

        finish_btn = self.button(QtGui.QWizard.FinishButton)

        if not str(self._note_edit.text()):        
            finish_btn.setEnabled(False)
            return

        for entity_item in self.entity_widget.entity_items:

            entity = entity_item.entity
            desc_edit = self._descriptions[entity]['widget']

            if not desc_edit.isVisible():
                continue

            if not str(desc_edit.text()):
                finish_btn.setEnabled(False)
                return
        
        finish_btn.setEnabled(True)

    # -------------------------------------------------------------------------
    def _check_option_values(self):

        next_btn = self.button(QtGui.QWizard.NextButton) 

        for entity_item in self.entity_widget.entity_items:

            entity = entity_item.entity
            option_widget = self._options[entity]['widget']

            if not option_widget.isVisible():
                continue

            if not option_widget.value_ok:
                next_btn.setEnabled(False)
                return
        
        next_btn.setEnabled(True)

    # -------------------------------------------------------------------------
    def _toggle_options(self):

        some_selected = False

        for entity_item in self.entity_widget.entity_items:

            entity = entity_item.entity

            option_header = self._options[entity]['header']
            option_widget = self._options[entity]['widget']

            desc_lbl = self._descriptions[entity]['label']
            desc_edit = self._descriptions[entity]['widget']

            if entity_item.isSelected():
                option_header.show() 
                option_widget.show() 
                desc_lbl.show() 
                desc_edit.show() 
                some_selected = True
            else:
                option_header.hide() 
                option_widget.hide() 
                desc_lbl.hide() 
                desc_edit.hide() 

        next_btn = self.button(QtGui.QWizard.NextButton)

        if some_selected:
            next_btn.setEnabled(True) 
        else:
            next_btn.setEnabled(False)

        if self._product_query_page == self.currentPage():
            next_btn.setEnabled(True)
            
