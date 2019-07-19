# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If

__all__ = [
    'CashBank',
    'ReceiptType', 
]


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
        ],
        'Type', required=True, translate=True)
    journal_cash_bank = fields.Many2One('account.journal', "Journal", required=True,
        domain=[('type', '=', 'cash')])
    account = fields.Many2One('account.account', "Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    receipt_types = fields.One2Many('cash_bank.receipt_type',
        'cash_bank', 'Receipt types')

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


class ReceiptType(ModelSQL, ModelView):
    "Cash/Bank Receipt Type"
    __name__ = "cash_bank.receipt_type"
    cash_bank = fields.Many2One(
            'cash_bank.cash_bank', 'Cash/Bank', required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None])
            ])
    name = fields.Char('Name', required=True, translate=True)
    type = fields.Selection([
            ('in', 'IN'),
            ('out', 'OUT')
        ],
        'Type', required=True)
    sequence = fields.Many2One('ir.sequence', "Receipt Sequence",
        required=True,
        domain=[
            ('company', 'in', [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'cash_bank.receipt'),
        ])
    party_required = fields.Boolean('Party Required')
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True
