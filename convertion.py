# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import (
    sequence_ordered, Workflow, ModelView, ModelSQL, fields, Check)
from trytond.pyson import Eval, If, Bool
from decimal import Decimal

__all__ = ['Convertion']

_STATES = {
    'readonly': Eval('state') != 'draft',
}

_STATES_DET = {
    'readonly': Eval('receipt_state') != 'draft',
}

_DEPENDS = ['state']

STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('posted', 'Posted'),
    ('cancel', 'Canceled'),
]


class Convertion(Workflow, ModelSQL, ModelView):
    "Cash/Bank Convertion from Document to Cash"
    __name__ = "cash_bank.convertion"
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
        depends=_DEPENDS, select=True)
    cash_bank = fields.Many2One(
            'cash_bank.cash_bank', 'Cash/Bank', required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None])
            ], states=_STATES)
    date = fields.Date('Date', required=True,
        states=_STATES, depends=_DEPENDS)
    reference = fields.Char('Reference', size=None,
        states={
            'readonly': Eval('state') == 'posted',
        })
    documents = fields.Many2Many('cash_bank.document-cash_bank.receipt',
        'receipt', 'document', 'Documents',
        domain=[
            ('current_receipt.cash_bank', '=', 'cash_bank'),
            ('converted', '=', False)
        ],
        states=_STATES)
    total_documents = fields.Function(fields.Numeric('Total Documents',
            digits=(16, Eval('currency_digits', 2))),
            'get_total_detail')
