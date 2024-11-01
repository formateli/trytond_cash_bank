# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    sequence_ordered, Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Bool, Not, And, Or, In
from trytond.modules.log_action import LogActionMixin, write_log
from trytond.i18n import gettext
from trytond.exceptions import UserError
from sql import Null
from decimal import Decimal

#TODO Use Monetary
# CAche total for tree displaying

class Receipt(Workflow, ModelSQL, ModelView):
    "Cash/Bank Receipt"
    __name__ = "cash_bank.receipt"

    _states = {
        'readonly': Eval('state') != 'draft',
        }
    _depends = ['state']

    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    cash_bank = fields.Many2One(
        'cash_bank.cash_bank', 'Cash/Bank', required=True,
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None])
        ],
        states={
            'readonly': Bool(Eval('lines')) | Bool(Eval('state') != 'draft')
        }, depends=_depends + ['lines'])
    type = fields.Many2One('cash_bank.receipt_type', 'Type', required=True,
        domain=[
            If(Bool(Eval('cash_bank')),
                [('cash_bank', '=', Eval('cash_bank'))],
                [('id', '=', -1)]
                ),
            ],
        states={
            'readonly': Bool(Eval('lines')) | Bool(Eval('state') != 'draft')
        }, depends=_depends + ['cash_bank', 'lines'])
    type_type = fields.Function(fields.Char('Type of Cash/Bank type',
        size=None), 'on_change_with_type_type')
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={'readonly': True})
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    number = fields.Char('Number', size=None, readonly=True)
    reference = fields.Char('Reference', size=None)
    description = fields.Char('Description', size=None,
        states=_states, depends=_depends)
    date = fields.Date('Date', required=True,
        states=_states, depends=_depends)
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        states={
            'readonly': Eval('state') != 'draft',
            'required': Bool(Eval('party_required'))
        }, depends=_depends + ['party_required'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    bank_account = fields.Many2One('bank.account', 'Bank Account',
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Not(Bool(Eval('bank_account_show'))),
            'required': Bool(Eval('bank_account_required'))
        },
        domain=[
            ('id', 'in', Eval('bank_account_owners'))
        ], depends=_depends + ['party', 'bank_account_show',
            'bank_account_owners', 'bank_account_required'])
    bank_account_show = fields.Function(fields.Boolean('Bank Account Show'),
        'on_change_with_bank_account_show')
    bank_account_owners = fields.Function(fields.One2Many('bank.account',
        None, 'Bank Account Owners'),
        'on_change_with_bank_account_owners',
        setter='set_bank_account_owners')
    bank_account_required = fields.Function(fields.Boolean(
        'Bank Account Required'),
        'on_change_with_bank_account_required')
    cash = fields.Numeric('Cash',
        digits=(16, Eval('currency_digits', 2)),
        states=_states, depends=_depends + ['currency_digits'])
    documents = fields.Many2Many('cash_bank.document-cash_bank.receipt',
        'receipt', 'document', 'Documents',
        domain=[
            If(Eval('state') != 'posted',
                [
                    [('convertion', '=', None)],
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
                ],
                [('id', '!=', -1)]
            )
        ],
        states=_states,
        depends=_depends + ['id', 'type', 'type_type'])
    total_documents = fields.Function(fields.Numeric('Total Documents',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits']),
        'get_total_detail')
    document_allow = fields.Function(fields.Boolean('Allow documents'),
        'on_change_with_document_allow')
    lines = fields.One2Many('cash_bank.receipt.line', 'receipt',
        'Lines', states={
            'readonly': (Not(Bool(Eval('cash_bank')))
                            | Not(Bool(Eval('type')))
                            | Bool(Eval('state') != 'draft'))
        },
        depends=_depends + ['cash_bank', 'type'])
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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('posted', 'Posted'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True, required=True)
    transfer = fields.Many2One('cash_bank.transfer', 'Transfer',
        readonly=True)
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    logs = fields.One2Many('cash_bank.receipt.log_action', 'resource',
        'Logs', readonly=True)

    del _states, _depends

    @classmethod
    def __register__(cls, module_name):
        super(Receipt, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)
        # Migration from 5.2.1:
        if table.column_exist('made_by'):
            cls._migrate_log()
            table.drop_column('made_by')
            table.drop_column('confirmed_by')
            table.drop_column('posted_by')
            table.drop_column('canceled_by')

    @classmethod
    def _migrate_log(cls):
        def add_log(Log, User, receipt, user, action, logs, create=False):
            if not user:
                return
            user = User(user)
            if create:
                date = receipt.create_date
            else:
                date = receipt.write_date
            log = Log(
                resource=receipt,
                date=date,
                user=user,
                action=action
            )
            logs.append(log)

        pool = Pool()
        Log = pool.get('cash_bank.receipt.log_action')
        User = pool.get('res.user')

        logs = []

        cursor = Transaction().connection.cursor()
        sql = "SELECT id, made_by, confirmed_by, canceled_by, posted_by " \
            "FROM cash_bank_receipt"
        cursor.execute(sql)
        records = cursor.fetchall()
        for row in records:
            rcp = cls(row[0])
            add_log(Log, User, rcp, row[1], 'Created', logs, True)
            add_log(Log, User, rcp, row[2], 'Confirmed', logs)
            add_log(Log, User, rcp, row[4], 'Posted', logs)
            add_log(Log, User, rcp, row[3], 'Cancelled', logs)
        Log.save(logs)

    @classmethod
    def __setup__(cls):
        super(Receipt, cls).__setup__()
        cls._order = [
                ('date', 'DESC'),
                ('number', 'DESC'),
                ]

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
                'readonly': Bool(Eval('transfer')),
                },
            'confirm': {
                'invisible': ~Eval('state').in_(['draft']),
                },
            'post': {
                'invisible': ~Eval('state').in_(['confirmed']),
                'readonly': Bool(Eval('transfer')),
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

    @fields.depends('type', 'bank_account_show')
    def on_change_with_bank_account_required(self, name=None):
        if self.type and self.bank_account_show:
            if self.bank_account_show == True:
                return self.type.bank_account_required

    @fields.depends('type', 'party_required')
    def on_change_with_bank_account_show(self, name=None):
        if self.type and self.party_required:
            if self.party_required == True:
                return self.type.bank_account

    @fields.depends('type', 'party')
    def on_change_with_bank_account_owners(self, name=None):
        if self.type and self.party:
            if self.party.bank_accounts:
                res = []
                for acc in self.party.bank_accounts:
                    res.append(acc.id)
                return res
        return []

    @classmethod
    def set_bank_account_owners(cls, lines, name, value):
        pass

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
        total = self._get_total_details(getattr(self, name))
        return total

    def get_total(self, name=None):
        total = self.cash + self.total_documents
        return total

    def get_diff(self, name=None):
        return self.total_lines - self.total

    def get_rec_name(self, name):
        if self.number:
            return self.number
        return str(self.id)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('number',) + tuple(clause[1:])]

    @classmethod
    def view_attributes(cls):
        return super(Receipt, cls).view_attributes() + [
            ('//page[@name="documents"]', 'states', {
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
            journal=self.cash_bank.journal_cash_bank,
            date=self.date,
            origin=self,
            company=self.company,
            description=self.description,
            )
        return move, period_id

    def _get_move_line(self, period):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        debit = Decimal('0.0')
        credit = Decimal('0.0')

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
            debit = amount
        else:
            credit = amount

        description = self.description
        if self.reference:
            if description:
                description += ' / '
            description += self.reference

        return MoveLine(
            period=period,
            debit=debit,
            credit=credit,
            account=self.cash_bank.account,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            description=description,
            )

    @classmethod
    def create(cls, vlist):
        receipts = super(Receipt, cls).create(vlist)
        write_log('log_action.msg_created', receipts)
        return receipts

    @classmethod
    def validate(cls, receipts):
        super(Receipt, cls).validate(receipts)
        cls.set_document_receipt(receipts)

    @classmethod
    def _validate_receipt(cls, receipt):
        pool = Pool()
        Config = pool.get('cash_bank.configuration')

        config = Config(1)

        if config.month_allow:
            month = int(config.month_allow)
            if month != receipt.date.month:
                raise UserError(
                    gettext('cash_bank.msg_receipt_month_not_allow',
                    receipt=receipt.rec_name
                    ))
        if not receipt.lines:
            raise UserError(
                gettext('cash_bank.msg_receipt_no_lines',
                receipt=receipt.rec_name
                ))
        if receipt.diff != 0:
            raise UserError(
                gettext('cash_bank.msg_diff_total_lines_cash_bank'
                ))
        if receipt.total < 0:
            raise UserError(
                gettext('cash_bank.msg_total_less_zero'
                ))
        if receipt.cash < 0:
            raise UserError(
                gettext('cash_bank.msg_cash_less_zero'
                ))
        for doc in receipt.documents:
            if doc.amount <= 0:
                raise UserError(
                    gettext('cash_bank.msg_document_less_equal_zero'
                    ))
        if receipt.type.party_required and not receipt.party:
            raise UserError(
                gettext('cash_bank.msg_party_required_cash_bank'
                ))

    @classmethod
    def set_document_receipt(cls, receipts):
        def doc_exists(id_, docs):
            for dc in docs:
                if dc.id == id_:
                    return True

        Document = Pool().get('cash_bank.document')

        lasts = {}
        for receipt in receipts:
            for doc in receipt.documents:
                if doc.last_receipt != receipt:
                    doc.last_receipt = receipt
                    doc.save()
                    if receipt.transfer and \
                            receipt.transfer.state in ['confirmed', 'post']:
                        pass
                    else:
                        if receipt.rec_name not in lasts:
                            lasts[receipt.rec_name] = []
                        lasts[receipt.rec_name].append(doc)

            # Verify if any document have been deleted from list
            # so last_receipt must be updated
            documents = Document.search([
                ('last_receipt', '=', receipt.id)])
            for doc in documents:
                if not doc_exists(doc.id, receipt.documents):
                    doc.set_previous_receipt()
                    doc.save()

        for key, value in lasts.items():
            write_log('Asigned to Receipt: ' + key, value)

    @classmethod
    def set_number(cls, receipts):
        for receipt in receipts:
            if receipt.number:
                continue
            receipt.number = receipt.type.sequence.get()
        cls.save(receipts)

    @classmethod
    def copy(cls, receipts, default=None):
        Date = Pool().get('ir.date')

        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('date', Date.today())
        default.setdefault('number', None)
        default.setdefault('reference', None)
        default.setdefault('description', None)
        default.setdefault('logs', None)
        default.setdefault('documents', None)
        default.setdefault('move', None)
        default.setdefault('line_move', None)
        default.setdefault('transfer', None)
        default.setdefault('attachments', None)
        return super(Receipt, cls).copy(receipts, default=default)

    @classmethod
    def delete(cls, receipts):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        atts = []
        for receipt in receipts:
            if receipt.state not in ['draft']:
                write_log('log_action.msg_deletion_attempt', [receipt])
                raise UserError(
                    gettext('cash_bank.msg_delete_document_cash_bank',
                        doc_name='Receipt',
                        doc_number=receipt.rec_name,
                        state='Draft'
                    ))
            for doc in receipt.documents:
                doc.set_previous_receipt()
                doc.save()
            for att in receipt.attachments:
                atts.append(att)

        Attachment.delete(atts)
        super(Receipt, cls).delete(receipts)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, receipts):
        write_log('log_action.msg_draft', receipts)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, receipts):
        for receipt in receipts:
            cls._validate_receipt(receipt)

            move, period = receipt._get_move()
            move.save()
            receipt_line_move = receipt._get_move_line(period)
            receipt_line_move.move = move
            receipt_line_move.save()
            move_lines = [receipt_line_move]
            for line in receipt.lines:
                line.validate_line()
                move_line = line.get_move_line(period)
                move_line.move = move
                move_line.save()
                line.line_move = move_line
                line.save()
                move_lines.append(move_line)
            move.lines = move_lines
            move.save()

            receipt.move = move
            receipt.line_move = receipt_line_move
            receipt.save()

        cls.set_number(receipts)
        write_log('log_action.msg_confirmed', receipts)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, receipts):
        Move = Pool().get('account.move')

        for receipt in receipts:
            cls._validate_receipt(receipt)
            for line in receipt.lines:
                line.reconcile()

        Move.post([r.move for r in receipts])
        write_log('log_action.msg_posted', receipts)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, receipts):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('cash_bank.receipt.line')
        lines_to_del = []
        for receipt in receipts:
            for line in receipt.lines:
                # It is necessary if invoice has been paid
                # in any other process
                if line.invoice and line.invoice.state != 'posted':
                    lines_to_del.append(line)
        Line.delete(lines_to_del)
        Move.delete([r.move for r in receipts])
        write_log('log_action.msg_cancelled', receipts)


class Line(sequence_ordered(), ModelSQL, ModelView):
    'Cash/Bank Receipt Line'
    __name__ = 'cash_bank.receipt.line'

    _states = {
        'readonly': Eval('receipt_state') != 'draft',
        }
    _depends = ['receipt_state']

    receipt = fields.Many2One('cash_bank.receipt', 'Receipt',
        required=True, ondelete='CASCADE')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    type = fields.Selection([
        (None, ''),
        ('invoice_customer', 'Customer Invoice'),
        ('invoice_supplier', 'Supplier Invoice'),
        ('move_line', 'Account Move Line'),
        ], 'Type', states={
            'readonly': Eval('receipt_state') != 'draft',
            'required': True,
        }, depends=_depends)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('currency_digits', 2)),
        states=_states, depends=_depends + ['currency_digits'])
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        states={
            'required': Or(
                        Bool(Eval('party_required')),
                        Eval('type') != 'move_line'
                        ),
            'readonly': Or(
                        Eval('receipt_state') != 'draft',
                        Bool(Eval('invoice'))
                        ),
        }, depends=_depends + ['party_required', 'invoice'])
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('_parent_receipt', {}).get('company', -1)),
            ('type', '!=', None),
            ('closed', '!=', True),
        ],
        states={
            'required': True,
            'readonly': Or(
                Eval('receipt_state') != 'draft',
                Eval('type') != 'move_line',
                )
        }, depends=_depends + ['type'])
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    description = fields.Char('Description', states=_states,
        depends=_depends)
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            ('company', '=', Eval('_parent_receipt', {}).get('company', -1)),
            ('state', '=', 'posted'),
            ('currency', '=',
                Eval('_parent_receipt', {}).get('currency', -1)),
            If(In(Eval('type'), ['invoice_customer']),
                [('type', '=', 'out')],
                [('type', '=', 'in')],
            ),
            If(Bool(Eval('party')),
                [('party', '=', Eval('party'))],
                [('party', '=', -1)],
            ),
        ],
        states={
            'readonly': Eval('receipt_state') != 'draft',
            'invisible': Not(In(
                Eval('type'), ['invoice_customer', 'invoice_supplier']))
        },
        depends=_depends + ['party', 'account', 'type'])
    line_move = fields.Many2One('account.move.line', 'Account Move Line',
            readonly=True)
    receipt_state = fields.Function(
        fields.Selection('get_receipt_states', 'Receipt State'),
        'on_change_with_receipt_state')

    del _states, _depends

    @classmethod
    def __register__(cls, module_name):
        super(Line, cls).__register__(module_name)
        pool = Pool()
        Invoice = pool.get('account.invoice')
        table = cls.__table_handler__(module_name)
        invoice_sql = Invoice.__table__()
        sql_table = cls.__table__()

        cursor = Transaction().connection.cursor()

        # Migration 5.2.2:
        if table.column_exist('number'):
            table.drop_column('number')

        # Migration 5.6.2:
        cursor.execute(*sql_table.select(sql_table.id,
                where=sql_table.type == Null,
                limit=1))
        if cursor.fetchone():
            cursor.execute(*sql_table.update(
                    columns=[sql_table.type],
                    values=['invoice_customer'],
                    where=(sql_table.type == Null)
                    & (sql_table.invoice.in_(
                            invoice_sql.select(invoice_sql.id,
                            where=(
                                invoice_sql.type == 'out')
                            )))
                    ))
            cursor.execute(*sql_table.update(
                    columns=[sql_table.type],
                    values=['invoice_supplier'],
                    where=(sql_table.type == Null)
                    & (sql_table.invoice.in_(
                            invoice_sql.select(invoice_sql.id,
                            where=(
                                invoice_sql.type == 'in')
                            )))
                    ))
            cursor.execute(*sql_table.update(
                    columns=[sql_table.type],
                    values=['move_line'],
                    where=sql_table.type == Null))

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_receipt_line_amount', Check(t, t.amount != 0),
                'cash_bank.msg_line_amount_zero'),
            ]

    @fields.depends('receipt', '_parent_receipt.state')
    def on_change_with_receipt_state(self, name=None):
        if self.receipt:
            return self.receipt.state

    @fields.depends('receipt', '_parent_receipt.type')
    def on_change_with_type(self, name=None):
        if self.receipt and self.receipt.type:
            if self.receipt.type.default_receipt_line_type:
                return self.receipt.type.default_receipt_line_type

    @fields.depends('type')
    def on_change_type(self):
        self.party = None
        self.invoice = None
        self.account = None
        self.amount = None

    @fields.depends('invoice', 'description',
                    'receipt', '_parent_receipt.type')
    def on_change_invoice(self):
        if self.invoice:
            self.account = self.invoice.account
            self.amount = self.invoice.amount_to_pay
            if self.receipt:
                if self.receipt.type.type == 'in':
                    if self.invoice.type == 'in':
                        self.amount *= -1
                else:
                    if self.invoice.type == 'out':
                        self.amount *= -1
            if not self.description and self.invoice.reference:
                self.description = self.invoice.reference

    @fields.depends('receipt', '_parent_receipt.currency')
    def on_change_with_currency(self, name=None):
        if self.receipt:
            return self.receipt.currency.id

    @fields.depends('receipt', '_parent_receipt.currency',
            'type', 'account', 'party', 'invoice')
    def on_change_with_currency_digits(self, name=None):
        if self.receipt and self.receipt.currency:
            return self.receipt.currency.digits
        return 2

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required

    def get_rec_name(self, name):
        return str(self.id) + '@' + self.receipt.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('receipt.rec_name',) + tuple(clause[1:])]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('line_move', None)
        default.setdefault('invoice', None)
        return super().copy(lines, default=default)

    @classmethod
    def get_receipt_states(cls):
        pool = Pool()
        Receipt = pool.get('cash_bank.receipt')
        return Receipt.fields_get(['state'])['state']['selection']

    def _format_amount(self, amount):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang, = Lang.search([
                ('code', '=', Transaction().language),
                ])
        amount = Lang.format(lang,
            '%.' + str(self.receipt.currency.digits) + 'f',
            amount, True)
        return amount

    def _check_invalid_amount(self, amount_to_check,
                document, check_greater=True):
        invalid = False
        if amount_to_check > 0 and self.amount < 0:
            invalid = True
        elif amount_to_check < 0 and self.amount > 0:
            invalid = True

        if invalid:
            raise UserError(
                gettext('cash_bank.msg_invalid_amount_sign',
                        amount=self._format_amount(self.amount),
                        document=document
                        ))

        if check_greater:
            if abs(self.amount) > abs(amount_to_check):
                raise UserError(
                    gettext('cash_bank.msg_amount_greater_amount_to_apply',
                            amount=self._format_amount(self.amount),
                            document=document
                            ))

    def validate_line(self):
        pool = Pool()
        Currency = pool.get('currency.currency')

        if self.amount == 0:
            raise UserError(
                gettext('cash_bank.msg_line_amount_zero',
                        ))

        if self.invoice:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount_to_pay = Currency.compute(self.invoice.currency,
                    self.invoice.amount_to_pay,
                    self.receipt.currency)

            if self.receipt.type.type == 'in':
                if self.invoice.type == 'in':
                    amount_to_pay *= -1
            else:
                if self.invoice.type == 'out':
                    amount_to_pay *= -1
            self._check_invalid_amount(amount_to_pay, self.invoice.rec_name)

    def reconcile(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        self.validate_line()

        if self.invoice:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.receipt.currency,
                    self.amount, self.receipt.company.currency)

            amount_to_reconcile = abs(amount)
            if ((self.invoice.type == 'in' and
                    self.invoice.amount_to_pay > 0) or
                    (self.invoice.type == 'out' and
                        self.invoice.amount_to_pay < 0)):
                amount_to_reconcile *= -1

            reconcile_lines, remainder = \
                self.invoice.get_reconcile_lines_for_amount(
                    amount_to_reconcile, self.currency)

            assert self.line_move.account == self.invoice.account

            Invoice.write([self.invoice], {
                    'payment_lines': [('add', [self.line_move.id])],
                    })

            if remainder == 0:
                lines = reconcile_lines + [self.line_move]
                MoveLine.reconcile(lines)

    def get_move_line(self, period):
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
                credit = amount
            else:
                debit = abs(amount)
        else:
            if amount > zero:
                debit = amount
            else:
                credit = abs(amount)

        return MoveLine(
            period=period,
            description=self.description,
            debit=debit,
            credit=credit,
            account=self.account,
            party=self.party if self.account.party_required else None,
            second_currency=second_currency,
            amount_second_currency=amount_second_currency,
            )


class ReceiptLog(LogActionMixin):
    "Receipt Logs"
    __name__ = "cash_bank.receipt.log_action"
    resource = fields.Many2One('cash_bank.receipt',
        'Receipt', ondelete='CASCADE')
