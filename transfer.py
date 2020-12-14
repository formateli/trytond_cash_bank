# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If, Bool, Or
from trytond.modules.log_action import LogActionMixin, write_log
from trytond.i18n import gettext
from trytond.exceptions import UserError
from decimal import Decimal

_STATES = {
    'readonly': Eval('state') != 'draft',
}

_DEPENDS = ['state']

STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('posted', 'Posted'),
    ('cancel', 'Canceled'),
]


class Transfer(Workflow, ModelSQL, ModelView):
    "Transfer between Cash/Bank"
    __name__ = "cash_bank.transfer"
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    date = fields.Date('Date', required=True,
        states=_STATES, depends=_DEPENDS)
    reference = fields.Char('Reference', size=None)
    description = fields.Char('Description', size=None)
    cash_bank_from = fields.Many2One('cash_bank.cash_bank',
        'From', required=True,
        domain=[
            ('company', '=', Eval('company')),
        ], states={
            'readonly': Or(Eval('state') != 'draft', Eval('documents')),
        }, depends=_DEPENDS + ['company', 'documents'])
    type_from = fields.Many2One('cash_bank.receipt_type',
        'Type', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank_from')),
                [('cash_bank', '=', Eval('cash_bank_from'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'out')
        ], states={
            'readonly': Or(Eval('state') != 'draft', Eval('documents')),
        }, depends=_DEPENDS + ['cash_bank_from', 'documents'])
    cash_bank_to = fields.Many2One('cash_bank.cash_bank',
        'To', required=True,
        domain=[
            ('company', '=', Eval('company')),
            If(
                Bool(Eval('cash_bank_from')),
                [('id', '!=', Eval('cash_bank_from'))],
                [('id', '=', -1)]
            ),
        ], states={
            'readonly': Or(Eval('state') != 'draft', Eval('documents')),
        }, depends=_DEPENDS + ['company', 'cash_bank_from', 'documents'])
    type_to = fields.Many2One('cash_bank.receipt_type',
        'Type', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank_to')),
                [('cash_bank', '=', Eval('cash_bank_to'))],
                [('cash_bank', '=', -1)]
            ),
            ('type', '=', 'in')
        ], states={
            'readonly': Or(Eval('state') != 'draft', Eval('documents')),
        }, depends=_DEPENDS + ['cash_bank_to', 'documents'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': True,
            },
        depends=['state', 'documents'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    cash = fields.Numeric('Cash',
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES, depends=_DEPENDS + ['currency_digits'])
    documents = fields.Many2Many('cash_bank.document-cash_bank.transfer',
        'transfer', 'document', 'Documents',
        domain=[
            If(Bool(Eval('type_from')),
                [
                    If(Eval('state') != 'posted',
                        [
                            ('convertion', '=', None),
                            If(Eval('state') == 'draft',
                                [
                                    ('last_receipt.cash_bank.id',
                                        '=', Eval('cash_bank_from')
                                    ),
                                ],
                                [
                                    ('last_receipt.cash_bank.id',
                                        '=', Eval('cash_bank_to')
                                    )
                                ]
                            )
                        ],
                        [('id', '!=', -1)]
                    )
                ],
                [('id', '=', -1)]
            ),
        ], states=_STATES,
        depends=_DEPENDS + ['type_from', 'cash_bank_from', 'cash_bank_to'])
    total_documents = fields.Function(fields.Numeric('Total Documents',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_total_documents')
    total = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_total')
    receipt_from = fields.Many2One('cash_bank.receipt', 'Receipt From',
        readonly=True)
    receipt_to = fields.Many2One('cash_bank.receipt', 'Receipt To',
        readonly=True)
    state = fields.Selection(STATES, 'State', readonly=True, required=True)
    logs = fields.One2Many('cash_bank.transfer.log_action', 'resource',
        'Logs', readonly=True)

    @classmethod
    def __register__(cls, module_name):
        super(Transfer, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)
        if table.column_exist('party'):
            table.drop_column('party')

    @classmethod
    def __setup__(cls):
        super(Transfer, cls).__setup__()
        cls._order[0] = ('id', 'DESC')

        cls._transitions |= set(
            (
                ('draft', 'confirmed'),
                ('confirmed', 'posted'),
                ('confirmed', 'cancel'),
                ('cancel', 'draft'),
            )
            )

        cls._buttons.update({
            'cancel': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            'confirm': {
                'invisible': ~Eval('state').in_(['draft']),
                },
            'post': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            'draft': {
                'invisible': ~Eval('state').in_(['cancel']),
                'icon': If(
                    Eval('state') == 'cancel',
                    'tryton-clear', 'tryton-go-previous'),
                },
            })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_cash():
        return Decimal('0.0')

    @staticmethod
    def default_total_documents():
        return Decimal('0.0')

    @staticmethod
    def default_total():
        return Decimal('0.0')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('cash_bank_from', 'type_from',
        'cash_bank_to', 'type_to')
    def on_change_company(self):
        self.cash_bank_from = None
        self.type_from = None
        self.cash_bank_to = None
        self.type_to = None

    @fields.depends('type_from', 'type_to', 'cash_bank_to')
    def on_change_cash_bank_from(self):
        self.type_from = None
        self.cash_bank_to = None
        self.type_to = None

    @fields.depends('type_to')
    def on_change_cash_bank_to(self):
        self.type_to = None

    @fields.depends('type_from', 'cash_bank_from')
    def on_change_type_from(self):
        if self.type_from:
            self.cash_bank_from = self.type_from.cash_bank

    @fields.depends('type_to', 'cash_bank_to')
    def on_change_type_to(self):
        if self.type_to:
            self.cash_bank_to = self.type_to.cash_bank

    @fields.depends('cash', 'total_documents')
    def on_change_cash(self):
        if not self.cash:
            self.cash = Decimal('0.0')
        self._set_total()

    @fields.depends('documents', 'cash', 'total_documents')
    def on_change_documents(self):
        self.total_documents = self.get_total_documents()
        self._set_total()

    def get_total_documents(self, name=None):
        total = Decimal('0.0')
        if self.documents:
            for doc in self.documents:
                if doc.amount:
                    total += doc.amount
        return total

    def get_total(self, name=None):
        total = self.cash + self.total_documents
        return total

    def _set_total(self):
        self.total = Decimal('0.0')
        if self.cash:
            self.total += self.cash
        if self.total_documents:
            self.total += self.total_documents

    def _new_receipt(self, cash_bank, type_):
        Receipt = Pool().get('cash_bank.receipt')
        party = None
        if type_.party_required:
            party = self.company.party
        return Receipt(
            company=self.company,
            currency=self.currency,
            date=self.date,
            cash_bank=cash_bank,
            type=type_,
            party=party,
            reference=self.reference,
            description=self.description,
            cash=self.cash
        )

    def _create_line(self, type_, amount, transfer_account):
        Line = Pool().get('cash_bank.receipt.line')

        party = None
        if transfer_account.party_required:
            party = self.company.party

        line = Line()
        line.type = 'move_line'
        line.description = 'Transfer'
        line.account = transfer_account
        line.amount = amount
        line.party = party
        return line

    def _get_doc(self, receipt, docs):
        Docs = Pool().get('cash_bank.document')
        for doc in docs:
            doc.last_receipt = receipt
        Docs.save(docs)
        return docs

    def _create_receipt(self, cash_bank, type_, trasnfer_account, docs):
        receipt = self._new_receipt(cash_bank, type_)
        receipt.documents = self._get_doc(receipt, docs)
        receipt.save()
        receipt.lines = [
            self._create_line(
                type_, receipt.total, trasnfer_account),
            ]
        receipt.save()
        return receipt

    def create_receipts(self):
        pool = Pool()
        Config = pool.get('cash_bank.configuration')
        Receipt = pool.get('cash_bank.receipt')

        config = Config(1)
        transfer_account = config.account_transfer

        receipt_from = self._create_receipt(self.cash_bank_from,
                                            self.type_from,
                                            transfer_account,
                                            self.documents)
        Receipt.confirm([receipt_from])

        receipt_to = self._create_receipt(
            self.cash_bank_to, self.type_to, transfer_account, self.documents)
        Receipt.confirm([receipt_to])

        self.receipt_from = receipt_from
        self.receipt_to = receipt_to

    @classmethod
    def set_transfer(cls, receipts, transfer):
        for receipt in receipts:
            receipt.transfer = transfer
            receipt.save()

    @classmethod
    def create(cls, vlist):
        transfers = super(Transfer, cls).create(vlist)
        write_log('Created', transfers)
        return transfers

    @classmethod
    def delete(cls, transfers):
        for transfer in transfers:
            if transfer.state != 'draft':
                raise UserError(
                    gettext('cash_bank.msg_delete_document_cash_bank',
                        doc_name='Transfer',
                        doc_number=transfer.rec_name,
                        state='Draft'
                    ))
        super(Transfer, cls).delete(transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, transfers):
        Receipt = Pool().get('cash_bank.receipt')
        for transfer in transfers:
            receipt_from = transfer.receipt_from
            receipt_to = transfer.receipt_to
            transfer.receipt_from = None
            transfer.receipt_to = None
            Receipt.draft([receipt_from, receipt_to])
            Receipt.delete([receipt_to])
            Receipt.delete([receipt_from])
        cls.save(transfers)
        write_log('Draft', transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, transfers):
        for transfer in transfers:
            if transfer.total <= 0:
                raise UserError(
                    gettext('cash_bank.msg_no_total_cash_bank'
                    ))
            transfer.create_receipts()
            cls.set_transfer([
                transfer.receipt_from,
                transfer.receipt_to
                ],
                transfer)
        cls.save(transfers)  # Update receipts values
        write_log('Confirmed', transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, transfers):
        Receipt = Pool().get('cash_bank.receipt')
        rcps = []
        for transfer in transfers:
            rcps += [
                transfer.receipt_from,
                transfer.receipt_to
                ]
        Receipt.post(rcps)
        write_log('Posted', transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, transfers):
        Receipt = Pool().get('cash_bank.receipt')
        rcps = []
        for transfer in transfers:
            rcps += [
                transfer.receipt_from,
                transfer.receipt_to
                ]
        Receipt.cancel(rcps)
        write_log('Cancelled', transfers)


class DocumentTransfer(ModelSQL):
    'Transfer - Document'
    __name__ = 'cash_bank.document-cash_bank.transfer'
    document = fields.Many2One('cash_bank.document', 'Document',
        ondelete='CASCADE', select=True, required=True)
    transfer = fields.Many2One('cash_bank.transfer', 'Transfer',
        ondelete='CASCADE', select=True, required=True)


class TransferLog(LogActionMixin):
    "Transfer Logs"
    __name__ = "cash_bank.transfer.log_action"
    resource = fields.Many2One('cash_bank.transfer',
        'Receipt', ondelete='CASCADE', select=True)
