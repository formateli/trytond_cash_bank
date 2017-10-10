# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    sequence_ordered, Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Bool
from decimal import Decimal

__all__ = ['Transfer']

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
            'readonly': (Eval('state') != 'draft') | Eval('documents', [0]),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS, select=True)
    date = fields.Date('Date', required=True,
        states=_STATES, depends=_DEPENDS)
    reference = fields.Char('Reference', size=None, states=_STATES)
    description = fields.Char('Description', size=None, states=_STATES)
    cash_bank_from = fields.Many2One(
            'cash_bank.cash_bank', 'From', required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None])
            ], states=_STATES)
    type_from = fields.Many2One('cash_bank.receipt_type',
        'Type', required=True,
        domain=[
            If(
                (Bool(Eval('cash_bank_from')),
                    [('cash_bank', '=', Eval('cash_bank_from'))], []
                )
            ),
            ('type', '=', 'out')
        ],
        states=_STATES, depends=_DEPENDS)
    cash_bank_to = fields.Many2One('cash_bank.cash_bank', 'To',
        required=True,
        domain=[
            ('id',
            If(Bool(Eval('cash_bank_from')), '!=', '='),
            If(
                Bool(Eval('cash_bank_from')), Eval('cash_bank_from'), Eval(-1))
            )
        ], states=_STATES)
    type_to = fields.Many2One('cash_bank.receipt_type', 'Type', required=True,
        domain=[
            If(
                (Bool(Eval('cash_bank_to')),
                    [('cash_bank', '=', Eval('cash_bank_to'))], []
                )
            ),
            ('type', '=', 'in')
        ],
        states=_STATES, depends=_DEPENDS)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('documents', [0]),
            },
        depends=['state'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    party = fields.Many2One('party.party', 'Party',
        states=_STATES, depends=['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    cash = fields.Numeric('Cash',
        digits=(16, Eval('_parent_receipt', {}).get('currency_digits', 2)),
        states={'readonly': Eval('state') != 'draft'}, depends=['state'])
    documents = fields.Many2Many('cash_bank.document-cash_bank.receipt',
        'receipt', 'document', 'Documents',
        domain=[
            [('convertion', '=', None)],
            [
                If(Bool(Eval('type_from')),
                    [
                        [
                            ('last_receipt.cash_bank.id',
                                '=', Eval('cash_bank_from')
                            )
                        ],
                        ['OR',
                            [
                                ('last_receipt.type.type', '=', 'in'),
                                ('last_receipt.state', '!=', 'draft')
                            ]
                        ]
                    ],
                    [('id', '=', -1)]
                ),
            ]
        ],
        states=_STATES, depends=['document_allow'])
    total_documents = fields.Function(fields.Numeric('Total Documents',
            digits=(16, Eval('currency_digits', 2))),
            'get_total_documents')
    total = fields.Function(fields.Numeric('Total',
                digits=(16, Eval('currency_digits', 2))),
            'get_total')
    receipt_from = fields.Many2One('cash_bank.receipt', 'Receipt From',
        readonly=True)
    receipt_to = fields.Many2One('cash_bank.receipt', 'Receipt To',
        readonly=True)
    state = fields.Selection(STATES, 'State', readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super(Transfer, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'delete_cancel': ('Transfer "%s" must be cancelled before '
                    'deletion.'),
                'no_total': "Total must be greater than zero",
                'party_required': "Party is required by transfer",
                })
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
        return Decimal(0)

    @staticmethod
    def default_total_documents():
        return Decimal(0)

    @staticmethod
    def default_total():
        return Decimal(0)

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

    @fields.depends('type_from, type_to')
    def on_change_with_party_required(self, name=None):
        required = False
        if self.type_from:
            required = self.type_from.party_required
        if not required:
            if self.type_to:
                required = self.type_to.party_required
        return required

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
            self.cash = Decimal(0)
        self._set_total()

    @fields.depends('documents', 'cash', 'total_documents')
    def on_change_documents(self):
        self.total_documents = self.get_total_documents()
        self._set_total()

    def get_total_documents(self, name=None):
        total = Decimal(0)
        if self.documents:
            for doc in self.documents:
                if doc.amount:
                    total += doc.amount
        return total

    def get_total(self, name=None):
        total = self.cash + self.total_documents
        return total

    def _set_total(self):
        self.total = Decimal(0)
        if self.cash:
            self.total += self.cash
        if self.total_documents:
            self.total += self.total_documents

    def _new_receipt(self):
        Receipt = Pool().get('cash_bank.receipt')
        return Receipt(
            company=self.company,
            currency=self.currency,
            date=self.date,
            party=self.party,
            reference=self.reference,
            description=self.description,
            cash=self.cash
        )

    def _create_line(self, type_, amount, transfer_account):
        Line = Pool().get('cash_bank.receipt.line')
        line = Line()
        line.description = 'Transfer'
        line.account = transfer_account
        line.amount = amount
        return line

    def _get_doc(self, receipt, ids):
        Docs = Pool().get('cash_bank.document')
        docs = []
        for id_ in ids:
            doc = Docs.search(['id', '=', id_])[0]
            doc.last_receipt = receipt
            doc.save()
            docs.append(doc)
        return docs

    def _create_receipt(self, cash_bank, type_, trasnfer_account, docs):
        receipt = self._new_receipt()
        receipt.cash_bank = cash_bank
        receipt.type = type_
        receipt.save()
        print(receipt.id)
        documents = self._get_doc(receipt, [doc.id for doc in docs])
        receipt.documents = documents
        receipt.save()
        receipt.lines = [
            self._create_line(
                type_, receipt.total, trasnfer_account),
        ]
        receipt.save()
        return receipt

    def create_receipts(self):
        print("CREATE RECEIPTS")
        pool = Pool()
        Config = pool.get('cash_bank.configuration')
        Receipt = pool.get('cash_bank.receipt')

        config = Config(1)
        transfer_account = config.account_transfer

        print("receipt 1")

        docs = []
        for doc in self.documents:
            docs.append(doc)

        receipt_from = self._create_receipt(
            self.cash_bank_from, self.type_from, transfer_account, docs)
        print(receipt_from)
        Receipt.confirm([receipt_from])
        print("confirm 1")

        receipt_to = self._create_receipt(
            self.cash_bank_to, self.type_to, transfer_account, self.documents)
        print(receipt_to)

        Receipt.confirm([receipt_to])

        self.receipt_from = receipt_from
        self.receipt_to = receipt_to

    @classmethod
    def cancel_receipt(cls, receipts):
        Receipt = Pool().get('cash_bank.receipt')
        for receipt in receipts:
            receipt.transfer = None
            receipt.save()
        Receipt.cancel(receipts)

    @classmethod
    def set_transfer(cls, receipts, transfer):
        for receipt in receipts:
            receipt.transfer = transfer
            receipt.save()

    @classmethod
    def delete(cls, transfers):
        cls.cancel(transfers)
        for transfer in transfers:
            if transfer.state != 'cancel':
                cls.raise_user_error('delete_cancel', (transfer.rec_name,))
        super(Transfer, cls).delete(transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, receipts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, transfers):
        for transfer in transfers:
            if transfer.total <= 0:
                cls.raise_user_error('no_total')
            if transfer.party_required and not transfer.party:
                cls.raise_user_error('party_required')
            transfer.create_receipts()
            cls.set_transfer([
                transfer.receipt_from,
                transfer.receipt_to
                ], transfer)
        cls.save(transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, transfers):
        Receipt = Pool().get('cash_bank.receipt')
        for transfer in transfers:
            Receipt.post([
                transfer.receipt_from,
                transfer.receipt_to
            ], from_transfer=True)
        cls.save(transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, transfers):
        for transfer in transfers:
            for doc in transfer.documents:
                doc.current_cash_bank = transfer.cash_bank_from
                doc.save()
            cls.cancel_receipt(
                [
                    transfer.receipt_from,
                    transfer.receipt_to
                ]
            )
        cls.save(transfers)
