# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.transaction import Transaction
#from trytond.modules.company.model import (
#    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If

__all__ = [
    'CashBank',
    #'CashBankJournal',
    'ReceiptType', 
    #'ReceiptTypeSequence'
]


#class CashBank(ModelSQL, ModelView, CompanyMultiValueMixin):
class CashBank(ModelSQL, ModelView):
    "Cash and Bank"
    __name__ = "cash_bank.cash_bank"

    name = fields.Char('Name', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
        ], select=True)
    type = fields.Selection([('cash', 'Cash'), ('bank', 'Bank')],
        'Type', required=True, translate=True)
#    journal = fields.MultiValue(fields.Many2One('account.journal',
#            'Journal', required=True,
#            domain=[('type', '=', 'cash')]
#        )
#    )
#    journals = fields.One2Many(
#        'cash_bank.journal', 'cash_bank', 'Journal')

    journal = fields.Many2One('account.journal',
        'Journal', required=True,
        domain=[('type', '=', 'cash')])
    receipt_types = fields.One2Many('cash_bank.receipt_type',
        'cash_bank', 'Receipt types')

#    @classmethod
#    def multivalue_model(cls, field):
#        pool = Pool()
#        if field in {'journal'}:
#            return pool.get('cash_bank.journal')
#        return super(CashBank, cls).multivalue_model(field)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


#class CashBankJournal(ModelSQL, CompanyValueMixin):
#    "Cash/Bank Journal"
#    __name__ = 'cash_bank.journal'
#
#    cash_bank = fields.Many2One(
#        'cash_bank.cash_bank', 'Cash/Bank',
#        ondelete='CASCADE', select=True)
#    journal = fields.Many2One('account.journal',
#        'Journal', required=True,
#        domain=[('type', '=', 'cash')]
#    )


#class ReceiptType(ModelSQL, ModelView, CompanyMultiValueMixin):
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
    type = fields.Selection([('in', 'IN'), ('out', 'OUT')],
        'Type', required=True)
#    sequence = fields.MultiValue(fields.Many2One(
#            'ir.sequence', "Receipt Sequence", required=True,
#            domain=[
#                ('company', 'in',
#                    [Eval('context', {}).get('company', -1), None]),
#                ('code', '=', 'cash_bank.receipt'),
#                ]))
    sequence = fields.Many2One('ir.sequence', "Receipt Sequence",
        required=True,
        domain=[
            ('company', 'in', [Eval('context', {}).get('company', -1), None]),
            ('code', '=', 'cash_bank.receipt'),
        ])
#    sequences = fields.One2Many(
#        'cash_bank.receipt_type.sequence', 'receipt_type', 'Sequence')
    document_convert = fields.Boolean('Convert documents',
        help='Automatically convert documents to cash')
    party_required = fields.Boolean('Party Required')
    active = fields.Boolean('Active')

    @staticmethod
    def default_active():
        return True

#    @classmethod
#    def multivalue_model(cls, field):
#        pool = Pool()
#        if field in {'sequence'}:
#            return pool.get('cash_bank.receipt_type.sequence')
#        return super(ReceiptType, cls).multivalue_model(field)


#class ReceiptTypeSequence(ModelSQL, CompanyValueMixin):
#    "Cash/Bank Receipt Type Sequence"
#    __name__ = 'cash_bank.receipt_type.sequence'

#    receipt_type = fields.Many2One('cash_bank.receipt_type',
#        'Receipt type', ondelete='CASCADE', select=True)
#    sequence = fields.Many2One(
#        'ir.sequence', "Receipt Sequence", required=True,
#        domain=[
#            ('company', 'in',
#                [Eval('context', {}).get('company', -1), None]),
#            ('code', '=', 'cash_bank.receipt'),
#        ]
#    )
