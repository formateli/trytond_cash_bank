# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.pyson import Eval, If, Bool, Not, Or


class CashBank(ModelSQL, ModelView):
    "Cash and Bank"
    __name__ = "cash_bank.cash_bank"
    name = fields.Char('Name', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
        ], select=True)
    type = fields.Selection([
            ('cash', 'Cash'),
            ('bank', 'Bank')
        ], 'Type', required=True, translate=True)
    journal_cash_bank = fields.Many2One('account.journal',
        "Journal", required=True,
        domain=[('type', '=', 'cash')])
    account = fields.Many2One('account.account', "Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
        ], depends=['company'])
    bank_account = fields.Many2One('bank.account', "Bank Account",
        ondelete='RESTRICT',
        states={
            'required': Bool(Eval('type') == 'bank'),
            'invisible': Not(Bool(Eval('type') == 'bank')),
        },
        domain=[
            ('id', 'in', Eval('bank_account_owners'))
        ], depends=['type', 'bank_account_owners'])
    bank_account_owners = fields.Function(fields.One2Many('bank.account',
        None, 'Bank Account Owners'),
        'on_change_with_bank_account_owners',
        setter='set_bank_account_owners')
    receipt_types = fields.One2Many('cash_bank.receipt_type',
        'cash_bank', 'Receipt types')

    @classmethod
    def __setup__(cls):
        super(CashBank, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('cash_bank_account_uniq',
                Unique(t, t.account),
                'Account can not be shared between Cash/Bank.'),
            ]

    @classmethod
    def __register__(cls, module_name):
        super(CashBank, cls).__register__(module_name)
        pool = Pool()
        table = cls.__table_handler__(module_name)
        # Migration from 4.8:
        if table.column_exist('journal'):
            table.drop_column('journal')
        # Migration from 5.2.1:
        if table.column_exist('payment_method'):
            PM = pool.get('account.invoice.payment.method')
            cursor = Transaction().connection.cursor()
            sql = "SELECT id, payment_method " \
                "FROM cash_bank_cash_bank"
            cursor.execute(sql)
            records = cursor.fetchall()
            cbs = []
            for row in records:
                cash_bank = cls(row[0])
                payment_method = PM(row[1])
                cash_bank.journal_cash_bank = payment_method.journal
                cash_bank.account = payment_method.debit_account
                cbs.append(cash_bank)
            cls.save(cbs)
            table.drop_column('payment_method')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_bank_account_owners(self, name=None):
        if self.company:
            if self.company.party.bank_accounts:
                res = []
                for acc in self.company.party.bank_accounts:
                    res.append(acc.id)
                return res
        return []

    @classmethod
    def set_bank_account_owners(cls, lines, name, value):
        pass


class ReceiptType(ModelSQL, ModelView):
    "Cash/Bank Receipt Type"
    __name__ = "cash_bank.receipt_type"
    cash_bank = fields.Many2One(
        'cash_bank.cash_bank', 'Cash/Bank', required=True,
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None])
        ])
    cash_bank_type = fields.Function(fields.Char('Cash/Bank type'),
        'on_change_with_cash_bank_type')
    name = fields.Char('Name', required=True, translate=True)
    type = fields.Selection([
            ('in', 'IN'),
            ('out', 'OUT')
        ], 'Type', required=True)
    sequence = fields.Many2One('ir.sequence', "Receipt Sequence",
        required=True,
        domain=[
            ('company', 'in', [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'cash_bank.receipt'),
        ])
    party_required = fields.Boolean('Party Required')
    bank_account = fields.Boolean('Bank Account',
        states={
            'invisible': Or(
                    Bool(Eval('cash_bank_type') != 'bank'),
                    Not(Bool(Eval('party_required')))
                )
        }, depends=['party_required', 'cash_bank_type'])
    bank_account_required = fields.Boolean('Bank Account Required',
        states={
            'invisible': Not(Bool(Eval('bank_account'))),
        }, depends=['bank_account'])
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

    @fields.depends('cash_bank', '_parent_cash_bank.type')
    def on_change_with_cash_bank_type(self, name=None):
        if self.cash_bank:
            return self.cash_bank.type
