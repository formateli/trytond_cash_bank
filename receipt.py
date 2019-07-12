# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    sequence_ordered, Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from decimal import Decimal

__all__ = ['Receipt', 'Line']

STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('posted', 'Posted'),
    ('cancel', 'Canceled'),
]

_STATES = {
    'readonly': Eval('state') != 'draft',
}

_STATES_DET = {
    'readonly': Eval('receipt_state') != 'draft',
}


class Receipt(Workflow, ModelSQL, ModelView):
    "Cash/Bank Receipt"
    __name__ = "cash_bank.receipt"
    _rec_name = 'number'
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': ((Eval('state') != 'draft') |
                    Eval('documents', [0]) | Eval('lines', [0])
                ),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'], select=True)
    cash_bank = fields.Many2One(
            'cash_bank.cash_bank', 'Cash/Bank', required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None])
            ], states=_STATES)
    type = fields.Many2One('cash_bank.receipt_type', 'Type', required=True,
        domain=[
            If(
                Bool(Eval('cash_bank')),
                [('cash_bank', '=', Eval('cash_bank'))], []
            ),
        ],
        states=_STATES, depends=['cash_bank'])
    type_type = fields.Function(fields.Char('Type of Cash/Bank type',
        size=None), 'on_change_with_type_type')
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft') |
                Eval('documents', [0]) | Eval('lines', [0])
            ),
        },
        depends=['state'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    number = fields.Char('Number', size=None, readonly=True, select=True)
    reference = fields.Char('Reference', size=None)
    description = fields.Char('Description', size=None, states=_STATES)
    date = fields.Date('Date', required=True,
        states=_STATES)
    party = fields.Many2One('party.party', 'Party',
        states=_STATES, depends=['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    cash = fields.Numeric('Cash',
        digits=(16, Eval('_parent_receipt', {}).get('currency_digits', 2)),
        states=_STATES)
    documents = fields.Many2Many('cash_bank.document-cash_bank.receipt',
        'receipt', 'document', 'Documents',
        domain=[
            [('convertion', '=', None)],
            [
                If(Bool(Eval('type')),
                    If(Eval('type_type') == 'in',
                        ['OR',
                            [('last_receipt', '=', None)],
                            [('last_receipt.id', '=', Eval('id'))],
                            [('last_receipt.type.type', '=', 'out')]
                        ],
                        ['OR',
                            [('last_receipt.id', '=', Eval('id'))],
                            [
                                ('last_receipt.type.type', '=', 'in'),
                                ('last_receipt.state', 'in',
                                    ['confirmed', 'posted'])
                            ]
                        ],
                    ),
                    [('id', '=', -1)]
                ),
            ]
        ],
        states=_STATES,
        depends=['id', 'type', 'type_type'])
    total_documents = fields.Function(fields.Numeric('Total Documents',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits']),
        'get_total_detail')
    document_allow = fields.Function(fields.Boolean('Allow documents'),
        'on_change_with_document_allow')
    lines = fields.One2Many('cash_bank.receipt.line', 'receipt',
        'Lines', states=_STATES,
        depends=['state', 'type'])
    total_lines = fields.Function(fields.Numeric('Total Lines',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_total_detail')
    total = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_total')
    diff = fields.Function(fields.Numeric('Diff',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_diff')
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
        ],
        depends=['company'])
    line_move = fields.Many2One('account.move.line', 'Account Move Line',
            readonly=True)
    state = fields.Selection(STATES, 'State', readonly=True, required=True)
    made_by = fields.Many2One('res.user', 'Made by',
            readonly=True)
    confirmed_by = fields.Many2One('res.user', 'Confirmed by',
            readonly=True)
    posted_by = fields.Many2One('res.user', 'Posted by',
            readonly=True)
    canceled_by = fields.Many2One('res.user', 'Canceled by',
            readonly=True)
    transfer = fields.Many2One('cash_bank.transfer', 'Transfer',
            readonly=True)

    @classmethod
    def __setup__(cls):
        super(Receipt, cls).__setup__()
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
                'icon': If(Eval('state') == 'cancel',
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
    def default_total_lines():
        return Decimal('0.0')

    @staticmethod
    def default_total_documents():
        return Decimal('0.0')

    @staticmethod
    def default_total():
        return Decimal('0.0')

    @staticmethod
    def default_diff():
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

    @fields.depends('type')
    def on_change_with_type_type(self, name=None):
        if self.type:
            return self.type.type

    @fields.depends('type', 'documents', 'state')
    def on_change_with_document_allow(self, name=None):
        if self.type:
            if self.type.type == 'in':
                return True
            else:
                if self.documents and self.state != 'draft':
                    return True

    @fields.depends('type')
    def on_change_with_party_required(self, name=None):
        if self.type:
            return self.type.party_required

    @fields.depends()
    def on_change_company(self):
        self.cash_bank = None
        self.type = None

    @fields.depends()
    def on_change_cash_bank(self):
        self.type = None

    @fields.depends('type')
    def on_change_type(self):
        if self.type:
            self.cash_bank = self.type.cash_bank

    @fields.depends('cash', 'total_documents', 'total_lines')
    def on_change_cash(self):
        if not self.cash:
            self.cash = Decimal('0.0')
        self._set_total(
            self.total_documents, self.total_lines)

    @fields.depends('documents', 'cash', 'total_lines')
    def on_change_documents(self):
        self.total_documents = \
            self.get_total_detail('total_documents')
        self._set_total(
            self.total_documents, self.total_lines)

    @fields.depends('lines', 'cash', 'total_documents')
    def on_change_lines(self):
        self.total_lines = \
            self.get_total_detail('total_lines')
        self._set_total(
            self.total_documents, self.total_lines)

    def get_total_detail(self, name):
        name = name[6:]  # Remove 'total_' from begining
        total = self._get_total_details(
            getattr(self, name)
        )
        return total

    def get_total(self, name=None):
        total = self.cash + self.total_documents
        return total

    def get_diff(self, name=None):
        return self.total_lines - self.total

    @classmethod
    def view_attributes(cls):
        return super(Receipt, cls).view_attributes() + [
            ('//page[@id="documents"]', 'states', {
                    'invisible': ~Eval('document_allow'),
                    })]

    def _get_total_details(self, details):
        result = Decimal('0.0')
        if details:
            for detail in details:
                if detail.amount:
                    result += detail.amount
        return result

    def _set_total(self, total_documents, total_lines):
        self.total = Decimal('0.0')
        diff = Decimal('0.0')
        if self.cash:
            self.total += self.cash
        if total_lines:
            diff += total_lines
        if total_documents:
            self.total += total_documents
        self.diff = diff - self.total

    def _get_move(self):
        'Return Move for Receipt'
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        period_id = Period.find(self.company.id, date=self.date)
        move = Move(
            period=period_id,
            journal=self.type.cash_bank.payment_method.journal,
            date=self.date,
            origin=self,
            company=self.company,
            description=self.description,
        )
        return move, self.type.cash_bank.payment_method, period_id

    def _get_move_line(self, period):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        debit = Decimal('0.0')
        credit = Decimal('0.0')
        payment_method = self.type.cash_bank.payment_method

        with Transaction().set_context(date=self.date):
            amount = Currency.compute(self.currency,
                self.total, self.company.currency)
        if self.currency != self.company.currency:
            second_currency = self.currency
            amount_second_currency = self.total
        else:
            amount_second_currency = None
            second_currency = None

        if self.type.type == 'in':
            account = payment_method.debit_account
            debit = amount
        else:
            account = payment_method.credit_account
            credit = amount

        if not account:
            raise UserError(
                gettext('cash_bank.msg_debit_credit_account_receipt_journal_cash_bank',
                    payment=payment_method.rec_name
                ))

        return MoveLine(
            journal=payment_method.journal,
            period=period,
            debit=debit,
            credit=credit,
            account=account,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            description=self.reference,
            )

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if values.get('made_by') is None:
                values['made_by'] = Transaction().user
        receipts = super(Receipt, cls).create(vlist)
        cls.set_document_receipt(receipts)
        return receipts

    @classmethod
    def write(cls, receipts, vlist):
        super(Receipt, cls).write(receipts, vlist)
        cls.set_document_receipt(receipts)

    @classmethod
    def set_document_receipt(cls, receipts):
        def doc_exists(id_, docs):
            for dc in docs:
                if dc.id == id_:
                    return True

        Document = Pool().get('cash_bank.document')

        for receipt in receipts:
            for doc in receipt.documents:
                doc.last_receipt = receipt
                doc.save()

            # Verify if any document have been deleted from list
            # so last_receipt must be updated
            documents = Document.search([
                ('last_receipt', '=', receipt.id)])
            for doc in documents:
                if not doc_exists(doc.id, receipt.documents):
                    doc.set_previous_receipt()
                    doc.save()

    @classmethod
    def set_number(cls, receipts):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        for receipt in receipts:
            if receipt.number:
                continue
            receipt.number = \
                Sequence.get_id(receipt.type.sequence.id)
        cls.save(receipts)

    @classmethod
    def delete(cls, receipts):
        # Cancel before delete
        cls.cancel(receipts)
        for receipt in receipts:
            if receipt.state not in ['draft', 'cancel']:
                raise UserError(
                    gettext('cash_bank.msg_delete_document_cash_bank',
                        doc_name='Receipt',
                        doc_number=receipt.rec_name,
                        state='Draft or Cancelled'
                    ))
            for doc in receipt.documents:
                doc.set_previous_receipt()
                doc.save()
        super(Receipt, cls).delete(receipts)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, receipts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, receipts):
        for receipt in receipts:
            if receipt.total <= 0:
                raise UserError(
                    gettext('cash_bank.msg_no_totals_cash_bank'
                    ))
            if receipt.diff != 0:
                raise UserError(
                    gettext('cash_bank.msg_diff_total_lines_cash_bank'
                    ))
            if receipt.type.party_required and not receipt.party:
                raise UserError(
                    gettext('cash_bank.msg_party_required_cash_bank'
                    ))
            move, payment_method, period = receipt._get_move()
            move.save()
            receipt_line_move = receipt._get_move_line(period)
            receipt_line_move.move = move
            receipt_line_move.save()
            move_lines = [receipt_line_move]
            for line in receipt.lines:
                move_line = line.get_move_line(payment_method, period)
                move_line.move = move
                move_line.save()
                line.line_move = move_line
                line.save()
                move_lines.append(move_line)
            move.lines = move_lines
            move.save()

            for line in receipt.lines:
                line.reconcile()

            receipt.move = move
            receipt.line_move = receipt_line_move
            receipt.confirmed_by = Transaction().user
            receipt.save()

            for doc in receipt.documents:
                doc.last_receipt = receipt
                doc.save()

        cls.set_number(receipts)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, receipts, from_transfer=False):
        Move = Pool().get('account.move')
        Move.post([r.move for r in receipts])
        for receipt in receipts:
            if not from_transfer and receipt.transfer:
                raise UserError(
                    gettext('cash_bank.msg_transfer_exists_cash_bank',
                        receipt=receipt.rec_name,
                        transfer=receipt.transfer.rec_name
                    ))
            receipt.posted_by = Transaction().user
            receipt.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, receipts, from_transfer=False):
        Move = Pool().get('account.move')
        Move.delete([r.move for r in receipts])
        for receipt in receipts:
            if not from_transfer and receipt.transfer:
                raise UserError(
                    gettext('cash_bank.msg_transfer_exists_cash_bank',
                        receipt=receipt.rec_name,
                        transfer=receipt.transfer.rec_name
                    ))
            for doc in receipt.documents:
                doc.last_receipt = None  # TODO move to previous receipt
                doc.save()
            receipt.canceled_by = Transaction().user
        cls.save(receipts)


class Line(sequence_ordered(), ModelSQL, ModelView):
    'Cash/Bank Receipt Line'
    __name__ = 'cash_bank.receipt.line'

    receipt = fields.Many2One('cash_bank.receipt', 'Receipt',
        required=True, ondelete='CASCADE',
        states=_STATES_DET)
    number = fields.Char('Number', states=_STATES_DET)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('_parent_receipt', {}).get('currency_digits', 2)),
        states=_STATES_DET, depends=['receipt_state'])
    party = fields.Many2One('party.party', 'Party',
        states=_STATES_DET, depends=['receipt_state'])
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('_parent_receipt', {}).get('company', -1)),
            ],
        states=_STATES_DET, depends=['receipt_state'])
    description = fields.Char('Description', states=_STATES_DET,
        depends=['receipt_state'])
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            If(Bool(Eval('party')), [('party', '=', Eval('party'))], []),
            If(Bool(Eval('account')), [('account', '=', Eval('account'))], []),
            [('state', '=', 'posted')],
            ],
        states=_STATES_DET,
        depends=['party', 'account', 'receipt_state'])
    line_move = fields.Many2One('account.move.line', 'Account Move Line',
            readonly=True)
    receipt_state = fields.Function(
        fields.Selection(STATES, 'Receipt State'),
        'on_change_with_receipt_state')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_receipt_line_amount', Check(t, t.amount != 0),
                'Amount must be a positive or negative value.'),
            ]

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @fields.depends('receipt', '_parent_receipt.state')
    def on_change_with_receipt_state(self, name=None):
        if self.receipt:
            return self.receipt.state

    @fields.depends('amount', 'party', 'invoice',
        'receipt', '_parent_receipt.cash_bank')
    def on_change_party(self):
        if self.party:
            if self.amount:
                self.account = self._get_party_account(self.amount)
        if self.invoice:
            if self.party:
                if self.invoice.party != self.party:
                    self.invoice = None
            else:
                self.invoice = None
                self.account = None
                self.amount = Decimal('0.0')

    @fields.depends('amount', 'party', 'account', 'invoice', 'receipt',
        '_parent_receipt.currency', '_parent_receipt.cash_bank')
    def on_change_amount(self):
        Currency = Pool().get('currency.currency')
        if self.party:
            if self.account and self.account not in (
                    self.party.account_receivable, self.party.account_payable):
                # The user has entered a non-default value, we keep it.
                pass
            elif self.amount:
                self.account = self._get_party_account(self.amount)
        if self.invoice:
            if self.amount and self.receipt and self.receipt.cash_bank.payment_method.journal:
                invoice = self.invoice
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = Currency.compute(invoice.currency,
                        invoice.amount_to_pay, self.receipt.currency)
                if abs(self.amount) > amount_to_pay:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('account', 'invoice')
    def on_change_account(self):
        if self.invoice:
            if self.account:
                if self.invoice.account != self.account:
                    self.invoice = None
            else:
                self.invoice = None

    @fields.depends('party', 'account', 'invoice', 'amount', 'description')
    def on_change_invoice(self):
        if self.invoice:
            if not self.party:
                self.party = self.invoice.party
            if not self.account:
                self.account = self.invoice.account
            self.amount = self.invoice.amount_to_pay
            if not self.description and self.invoice.reference:
                self.description = self.invoice.reference

    def get_rec_name(self, name):
        return self.receipt.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('receipt.rec_name',) + tuple(clause[1:])]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('move', None)
        default.setdefault('invoice', None)
        return super(Line, cls).copy(lines, default=default)

    def reconcile(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Lang = pool.get('ir.lang')
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        if self.invoice:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount_to_pay = Currency.compute(self.invoice.currency,
                    self.invoice.amount_to_pay,
                    self.receipt.currency)
            if abs(amount_to_pay) < abs(self.amount):
                lang, = Lang.search([
                        ('code', '=', Transaction().language),
                        ])

                amount = Lang.format(lang,
                    '%.' + str(self.receipt.currency.digits) + 'f',
                    self.amount, True)

                raise UserError(
                    gettext('cash_bank.msg_amount_greater_invoice_amount_to_pay_cash_bank',
                        amount=amount
                    ))

            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.receipt.currency,
                    self.amount, self.receipt.company.currency)

            amount_to_reconcile = abs(amount)
            if self.invoice.type == 'in':
                amount_to_reconcile *= -1

            reconcile_lines, remainder = \
                self.invoice.get_reconcile_lines_for_amount(
                    amount_to_reconcile)

            assert self.line_move.account == self.invoice.account

            Invoice.write([self.invoice], {
                    'payment_lines': [('add', [self.line_move.id])],
                    })
            if remainder == Decimal('0.0'):
                lines = reconcile_lines + [self.line_move]
                MoveLine.reconcile(lines)

    def get_move_line(self, payment_method, period):
        '''
        Return the move line for the receipt line
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = Pool().get('currency.currency')
        zero = Decimal('0.0')
        debit = Decimal('0.0')
        credit = Decimal('0.0')
        with Transaction().set_context(date=self.receipt.date):
            amount = Currency.compute(self.receipt.currency,
                self.amount, self.receipt.company.currency)
        if self.receipt.currency != self.receipt.company.currency:
            second_currency = self.receipt.currency
            amount_second_currency = self.amount
        else:
            amount_second_currency = None
            second_currency = None

        if self.receipt.type.type == 'in':
            if amount > zero:
                account = payment_method.credit_account
                credit = amount
            else:
                account = payment_method.debit_account
                debit = abs(amount)
        else:
            if amount > zero:
                account = payment_method.debit_account
                debit = amount
            else:
                account = payment_method.credit_account
                credit = abs(amount)

        return MoveLine(
            journal=payment_method.journal,
            period=period,
            description=self.description,
            debit=debit,
            credit=credit,
            account=self.account,
            party=self.party if self.account.party_required else None,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            )

    def _get_party_account(self, amount):
        account = None
        zero = Decimal('0.0')
        if self.receipt.type.type == 'in':
            if amount > zero:
                account = self.party.account_receivable
            else:
                account = self.party.account_payable
        else:
            if amount > zero:
                account = self.party.account_payable
            else:
                account = self.party.account_receivable
        return account
